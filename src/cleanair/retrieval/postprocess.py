"""After ranking, before the prompt (SPEC §7.1 steps 7-9): MMR diversity, small-to-big, lost-in-the-middle order."""

import numpy as np

from cleanair.retrieval.schemas import RetrievedChunk


def relevance(c: RetrievedChunk) -> float:
    return c.score_rerank if c.score_rerank is not None else c.score_fused


def mmr(chunks: list[RetrievedChunk], k: int, lam: float = 0.7) -> list[RetrievedChunk]:
    """Maximal marginal relevance: pick next = argmax lam * rel(c) - (1 - lam) * max cos(c, picked).

    Relevance is min-max scaled to [0, 1] so it is comparable with cosine similarity. Needs dense vectors;
    chunks without one are treated as dissimilar to everything. Returns the first k picks, then the rest
    in their original order.
    """
    if len(chunks) <= 1:
        return chunks
    rel = np.array([relevance(c) for c in chunks], dtype=float)
    rel = (rel - rel.min()) / (rel.max() - rel.min()) if rel.max() > rel.min() else np.ones_like(rel)
    vecs = [np.asarray(c.vector, dtype=float) if c.vector is not None else None for c in chunks]

    picked: list[int] = []
    rest = list(range(len(chunks)))
    while rest and len(picked) < k:

        def gain(i: int) -> float:
            sims = [float(vecs[i] @ vecs[j]) for j in picked if vecs[i] is not None and vecs[j] is not None]
            return lam * rel[i] - (1 - lam) * max(sims, default=0.0)

        best = max(rest, key=gain)
        picked.append(best)
        rest.remove(best)
    return [chunks[i] for i in picked] + [chunks[i] for i in rest]


def small_to_big(chunks: list[RetrievedChunk], parents: dict[str, dict], max_tokens: int) -> list[RetrievedChunk]:
    """Swap each chunk for its parent section when the parent fits in max_tokens; each parent appears once.

    The chunk is what matched the query (precise); the parent is what the LLM reads (context).
    No-op for chunks without a known parent (e.g. the fixed chunker produces none).
    """
    out, seen = [], set()
    for c in chunks:
        pid = c.metadata.get("parent_id")
        parent = parents.get(pid) if pid else None
        if parent and parent["token_count"] <= max_tokens:
            if pid in seen:
                continue
            seen.add(pid)
            c = c.model_copy(update={"text": parent["text"], "metadata": {**c.metadata, "expanded_from": c.chunk_id}})
        out.append(c)
    return out


def lost_in_the_middle(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Ranks 1,2,3,4,5 -> order 1,3,5,4,2: the strongest evidence sits at the start and the end of the
    prompt, where long-context models attend best (Liu et al., 2023)."""
    return chunks[0::2] + chunks[1::2][::-1]
