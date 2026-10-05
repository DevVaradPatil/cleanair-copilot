"""Sparse (lexical) search over BGE-M3's learned term weights -- the BM25-like half of hybrid retrieval."""

from qdrant_client import QdrantClient, models

from cleanair.retrieval.dense import to_chunk
from cleanair.retrieval.schemas import RetrievedChunk


def sparse_search(
    client: QdrantClient,
    collection: str,
    query_sparse: dict[int, float],
    qfilter,
    k: int,
    with_vectors: bool = False,
) -> list[RetrievedChunk]:
    if not query_sparse:  # e.g. a query of only stop-word-like tokens
        return []
    res = client.query_points(
        collection,
        query=models.SparseVector(indices=list(query_sparse), values=list(query_sparse.values())),
        using="sparse",
        query_filter=qfilter,
        limit=k,
        with_payload=True,
        with_vectors=["dense"] if with_vectors else False,
    )
    out = []
    for pt in res.points:
        c = to_chunk(pt)
        c.score_sparse = c.score_fused = pt.score
        out.append(c)
    return out
