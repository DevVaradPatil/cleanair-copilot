"""Fusing ranked lists from dense and sparse search (SPEC §7.1 step 5). 🧠 Varad implements both.

tests/test_fusion.py is the specification (hand-computed examples).
"""

from cleanair.retrieval.schemas import RetrievedChunk


def rrf(ranked_lists: list[list[RetrievedChunk]], k: int = 60) -> list[RetrievedChunk]:
    """🧠 Reciprocal rank fusion: score(chunk) = sum over lists of 1 / (k + rank), rank starting at 1.

    - a chunk missing from a list contributes nothing for that list
    - the output holds each chunk once, sorted by fused score (descending), with score_fused set
    - keep the per-list scores on the merged chunk (score_dense from the dense hit, score_sparse from the sparse hit)
    - ties: keep the order of first appearance (stable)
    """
    raise NotImplementedError("🧠 rrf is Varad's to implement (plan step 2.3)")


def weighted(dense: list[RetrievedChunk], sparse: list[RetrievedChunk], alpha: float = 0.5) -> list[RetrievedChunk]:
    """🧠 Weighted score fusion: min-max normalise each list's scores to [0, 1], then
    score_fused = alpha * dense_norm + (1 - alpha) * sparse_norm, with 0 for a list the chunk is missing from.

    - a list whose scores are all equal normalises to 1.0 for every member (avoid dividing by zero)
    - same output contract as rrf
    """
    raise NotImplementedError("🧠 weighted fusion is Varad's to implement (plan step 2.3)")
