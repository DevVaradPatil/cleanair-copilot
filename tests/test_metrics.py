import pytest

from eval.metrics import bootstrap_ci, covers, norm, retrieval_metrics


def c(doc, text):
    return {"doc_id": doc, "text": text}


EV = [
    [{"doc_id": "grap", "quote": "DELHI AQI ranging between 401-450"}],
    [{"doc_id": "grap", "quote": "DELHI AQI > 450"}],
]


def test_norm_folds_typography_and_tables():
    assert norm("Stage III – ‘Severe’ |Air|  Quality") == "stage iii - 'severe' air quality"
    assert norm("ﬁve µg/m3") == norm("five μg/m3")  # ligature + micro sign vs Greek mu


def test_covers_full_quote_and_half_quote_across_boundary():
    q = "Classes VI to IX and XI shall be held in hybrid mode in Delhi"
    assert covers("... " + q + " ...", q)
    assert covers("end of chunk: Classes VI to IX and XI shall", q)  # first half survives the cut
    assert not covers("Classes VI", q)
    short = "The Commission may impose and collect environmental compensation"  # 9 words: whole quote only
    assert not covers("The Commission may impose a fine on industries", short)


def test_recall_mrr_ndcg_hand_computed():
    ranked = [
        c("other", "x"),
        c("grap", "Stage III (DELHI AQI ranging between 401-450)"),
        c("grap", "(DELHI AQI > 450)"),
    ]
    m = retrieval_metrics(ranked, EV, ks=(1, 2, 3))
    assert m["recall@1"] == 0 and m["recall@2"] == 0.5 and m["recall@3"] == 1.0
    assert m["mrr"] == pytest.approx(1 / 2)
    ideal = 1 + 1 / 1.5849625007211562  # log2(3)
    assert m["ndcg@3"] == pytest.approx((1 / 1.5849625007211562 + 1 / 2) / ideal)


def test_right_text_wrong_doc_is_not_relevant():
    """A superseded GRAP version saying the same thing doesn't count: the question asks about the current one."""
    m = retrieval_metrics([c("grap-old", "DELHI AQI ranging between 401-450 and DELHI AQI > 450")], EV)
    assert m["recall@1"] == 0 and m["mrr"] == 0


def test_bootstrap_ci_brackets_mean():
    mean, lo, hi = bootstrap_ci([0, 1, 1, 1, 0, 1, 1, 0, 1, 1])
    assert mean == pytest.approx(0.7) and lo < 0.7 < hi
