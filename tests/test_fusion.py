"""Specification for 🧠 fusion.rrf / fusion.weighted (hand-computed, SPEC §7.3)."""

import pytest

from cleanair.retrieval.fusion import rrf, weighted
from cleanair.retrieval.schemas import RetrievedChunk

brain = pytest.mark.xfail(raises=NotImplementedError, strict=True, reason="🧠 fusion not implemented")


def hits(ids, kind):
    out = []
    for rank, cid in enumerate(ids, start=1):
        score = 1.0 / rank
        c = RetrievedChunk(chunk_id=cid, doc_id="d", text=cid, heading_path="", score_fused=score)
        setattr(c, "score_dense" if kind == "dense" else "score_sparse", score)
        out.append(c)
    return out


@brain
def test_rrf_hand_computed():
    dense, sparse = hits(["a", "b", "c"], "dense"), hits(["c", "x", "a"], "sparse")
    fused = {c.chunk_id: c.score_fused for c in rrf([dense, sparse], k=60)}
    assert fused["a"] == pytest.approx(1 / 61 + 1 / 63)  # ranks (1, 3) -- the SPEC §7.3 example
    assert fused["c"] == pytest.approx(1 / 63 + 1 / 61)
    assert fused["b"] == pytest.approx(1 / 62)  # only in one list
    assert fused["x"] == pytest.approx(1 / 62)


@brain
def test_rrf_sorted_unique_and_keeps_both_scores():
    dense, sparse = hits(["a", "b", "c"], "dense"), hits(["c", "x", "a"], "sparse")
    out = rrf([dense, sparse], k=60)
    assert [c.chunk_id for c in out][:2] in (["a", "c"], ["c", "a"])  # tie on 1/61 + 1/63
    assert len(out) == 4 and len({c.chunk_id for c in out}) == 4
    a = next(c for c in out if c.chunk_id == "a")
    assert a.score_dense == pytest.approx(1.0) and a.score_sparse == pytest.approx(1 / 3)


@brain
def test_rrf_tie_order_is_first_appearance():
    out = rrf([hits(["a", "b"], "dense"), hits(["b", "a"], "sparse")], k=60)
    assert [c.chunk_id for c in out] == ["a", "b"]  # equal scores; "a" was seen first


@brain
def test_rrf_small_k_rewards_top_ranks_more():
    dense, sparse = hits(["a", "b", "c", "d"], "dense"), hits(["d", "c", "b", "a"], "sparse")
    assert rrf([dense, sparse], k=1)[0].chunk_id in ("a", "d")


@brain
def test_weighted_min_max_and_alpha():
    dense = hits(["a", "b", "c"], "dense")  # scores 1, 1/2, 1/3 -> normalised 1, 0.25, 0
    sparse = hits(["c", "a"], "sparse")  # scores 1, 1/2 -> normalised 1, 0
    fused = {c.chunk_id: c.score_fused for c in weighted(dense, sparse, alpha=0.5)}
    assert fused["a"] == pytest.approx(0.5 * 1 + 0.5 * 0)
    assert fused["b"] == pytest.approx(0.5 * 0.25)  # missing from sparse -> 0 there
    assert fused["c"] == pytest.approx(0.5 * 0 + 0.5 * 1)


@brain
def test_weighted_constant_list_does_not_divide_by_zero():
    dense = hits(["a"], "dense")
    fused = weighted(dense, [], alpha=0.7)
    assert fused[0].score_fused == pytest.approx(0.7)
