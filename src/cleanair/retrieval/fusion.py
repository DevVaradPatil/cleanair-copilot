"""Fusing ranked lists from dense and sparse search (SPEC §7.1 step 5). 🧠 explained in docs/BRAIN_NOTES.md.

Dense and sparse scores live on different scales (cosine ~0.3-0.8 vs. sparse dot products ~0-0.5, with different
spreads per query), so they can't simply be added. Two standard fixes:
- rrf:      ignore scores, use ranks. score = sum over lists of 1 / (k + rank). Robust, no tuning beyond k.
- weighted: min-max normalise each list's scores to [0, 1] per query, then alpha * dense + (1 - alpha) * sparse.
"""

from cleanair.retrieval.schemas import RetrievedChunk


def _merge(lists: list[list[RetrievedChunk]], scores: list[dict[str, float]]) -> list[RetrievedChunk]:
    """Union of chunks across lists (first appearance wins), summed fused score, per-list scores carried over."""
    merged: dict[str, RetrievedChunk] = {}
    total: dict[str, float] = {}
    for chunks, list_scores in zip(lists, scores, strict=True):
        for c in chunks:
            if c.chunk_id not in merged:  # dict keeps insertion order -> stable ties by first appearance
                merged[c.chunk_id] = c.model_copy()
                total[c.chunk_id] = 0.0
            m = merged[c.chunk_id]
            m.score_dense = m.score_dense if m.score_dense is not None else c.score_dense
            m.score_sparse = m.score_sparse if m.score_sparse is not None else c.score_sparse
            m.vector = m.vector if m.vector is not None else c.vector
            total[c.chunk_id] += list_scores.get(c.chunk_id, 0.0)
    for cid, m in merged.items():
        m.score_fused = total[cid]
    # sorted() is stable, so equal scores keep first-appearance order
    return sorted(merged.values(), key=lambda m: m.score_fused, reverse=True)


def rrf(ranked_lists: list[list[RetrievedChunk]], k: int = 60) -> list[RetrievedChunk]:
    """Reciprocal rank fusion: score(chunk) = sum over lists of 1 / (k + rank), rank starting at 1.

    A chunk missing from a list contributes 0 for it. k damps the advantage of rank 1 over rank 2: with k = 60,
    1/61 vs 1/62 is a ~1.6% difference, so agreement between lists matters more than either list's top spot.
    """
    scores = [{c.chunk_id: 1.0 / (k + rank) for rank, c in enumerate(chunks, start=1)} for chunks in ranked_lists]
    return _merge(ranked_lists, scores)


def _minmax(chunks: list[RetrievedChunk]) -> dict[str, float]:
    values = [c.score_fused for c in chunks]
    if not values:
        return {}
    lo, hi = min(values), max(values)
    if hi == lo:  # one hit, or all tied: every member is "the best" of its list
        return {c.chunk_id: 1.0 for c in chunks}
    return {c.chunk_id: (c.score_fused - lo) / (hi - lo) for c in chunks}


def weighted(dense: list[RetrievedChunk], sparse: list[RetrievedChunk], alpha: float = 0.5) -> list[RetrievedChunk]:
    """Weighted score fusion: alpha * minmax(dense) + (1 - alpha) * minmax(sparse); 0 where a chunk is missing.

    Each input chunk's `score_fused` holds its list's own score (dense_search / sparse_search set it).
    """
    d = {cid: alpha * s for cid, s in _minmax(dense).items()}
    s = {cid: (1 - alpha) * v for cid, v in _minmax(sparse).items()}
    return _merge([dense, sparse], [d, s])
