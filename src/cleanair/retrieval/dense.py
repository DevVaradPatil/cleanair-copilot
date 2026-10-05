"""Dense (semantic) search over the "dense" named vector; to_chunk is shared with sparse.py."""

from qdrant_client import QdrantClient, models

from cleanair.retrieval.schemas import RetrievedChunk

PAYLOAD_KEYS = ("chunk_id", "doc_id", "text", "heading_path")


def to_chunk(point: models.ScoredPoint) -> RetrievedChunk:
    p = point.payload or {}
    vector = point.vector.get("dense") if isinstance(point.vector, dict) else None
    return RetrievedChunk(
        **{k: p.get(k, "") for k in PAYLOAD_KEYS},
        metadata={k: v for k, v in p.items() if k not in PAYLOAD_KEYS and k != "embed_text"},
        vector=vector,
    )


def dense_search(
    client: QdrantClient,
    collection: str,
    query_vector: list[float],
    qfilter,
    k: int,
    with_vectors: bool = False,
) -> list[RetrievedChunk]:
    res = client.query_points(
        collection,
        query=query_vector,
        using="dense",
        query_filter=qfilter,
        limit=k,
        with_payload=True,
        with_vectors=["dense"] if with_vectors else False,
    )
    out = []
    for pt in res.points:
        c = to_chunk(pt)
        c.score_dense = c.score_fused = pt.score
        out.append(c)
    return out
