import uuid

import numpy as np
import pytest

from cleanair.retrieval.filters import Filters, to_qdrant, wants_history
from cleanair.retrieval.postprocess import lost_in_the_middle, mmr, small_to_big
from cleanair.retrieval.schemas import RetrievedChunk


def chunk(cid, score, vector=None, parent=None):
    return RetrievedChunk(
        chunk_id=cid,
        doc_id="d",
        text=f"text {cid}",
        heading_path="",
        score_fused=score,
        vector=vector,
        metadata={"parent_id": parent} if parent else {},
    )


def test_wants_history():
    assert wants_history("What did the earlier GRAP schedule say about Stage IV?")
    assert wants_history("GRAP in 2024")
    assert wants_history("पहले क्या नियम था?")
    assert not wants_history("What restrictions apply under GRAP Stage III?")


def test_to_qdrant_builds_must_conditions():
    assert to_qdrant(Filters(current_only=False)) is None
    f = to_qdrant(Filters(current_only=True, cities=["Delhi"]))
    assert {c.key for c in f.must} == {"is_current", "cities"}


def test_lost_in_the_middle_puts_best_at_both_ends():
    out = [c.chunk_id for c in lost_in_the_middle([chunk(str(i), 1.0) for i in range(1, 6)])]
    assert out == ["1", "3", "5", "4", "2"]


def test_mmr_skips_near_duplicate():
    a, a_dup, b = [1.0, 0.0], [0.999, 0.0447], [0.0, 1.0]
    ranked = [chunk("a", 0.9, a), chunk("a_dup", 0.89, a_dup), chunk("b", 0.5, b)]
    assert [c.chunk_id for c in mmr(ranked, k=2, lam=0.5)][:2] == ["a", "b"]
    assert [c.chunk_id for c in mmr(ranked, k=2, lam=1.0)][:2] == ["a", "a_dup"]  # lam=1 = pure relevance


def test_small_to_big_swaps_in_parent_once_and_respects_budget():
    parents = {
        "p1": {"text": "whole section", "token_count": 300},
        "p2": {"text": "huge", "token_count": 5000},
    }
    out = small_to_big(
        [chunk("a", 1, parent="p1"), chunk("b", 1, parent="p1"), chunk("c", 1, parent="p2")], parents, 1200
    )
    assert [c.text for c in out] == ["whole section", "text c"]  # p1 once; p2 too big, chunk kept
    assert out[0].metadata["expanded_from"] == "a"


@pytest.mark.integration
def test_filtered_search_never_returns_out_of_filter_chunks():
    """SPEC §7.3: no out-of-filter chunk is ever returned, even when it is the nearest neighbour."""
    from qdrant_client import QdrantClient, models

    from cleanair.retrieval.dense import dense_search
    from cleanair.settings import Settings

    client = QdrantClient(url=Settings(gemini_api_key="unused").qdrant_url)
    name = f"test_filters_{uuid.uuid4().hex[:8]}"
    rng = np.random.default_rng(0)
    client.create_collection(
        name, vectors_config={"dense": models.VectorParams(size=8, distance=models.Distance.COSINE)}
    )
    try:
        points = []
        for i in range(200):
            city = ["Delhi", "Kanpur", "Mumbai", "Lucknow"][i % 4]
            payload = {
                "chunk_id": f"c{i}",
                "doc_id": "d",
                "text": "t",
                "heading_path": "",
                "cities": [city],
                "is_current": i % 3 != 0,
            }
            points.append(models.PointStruct(id=i, vector={"dense": rng.normal(size=8).tolist()}, payload=payload))
        client.upload_points(name, points, wait=True)
        query = points[0].vector["dense"]  # nearest neighbour is c0: Delhi, NOT current
        hits = dense_search(client, name, query, to_qdrant(Filters(current_only=True, cities=["Kanpur"])), k=50)
        assert hits, "filter should still return matching chunks"
        assert all(h.metadata["cities"] == ["Kanpur"] and h.metadata["is_current"] for h in hits)
        assert "c0" not in {h.chunk_id for h in hits}
    finally:
        client.delete_collection(name)
