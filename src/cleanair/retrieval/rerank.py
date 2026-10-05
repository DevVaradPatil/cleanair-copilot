"""Cross-encoder reranking (SPEC §7.1 step 6) with BAAI/bge-reranker-v2-m3 in plain transformers.

A bi-encoder (BGE-M3) embeds query and passage separately, so it can pre-index millions of passages but
never sees them together. A cross-encoder reads "query [SEP] passage" jointly -- far more accurate,
far too slow for the whole corpus -- so it only re-scores the top ~30 candidates.
"""

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from cleanair.retrieval.schemas import RetrievedChunk


class CrossEncoder:
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3", max_length: int = 1024, device: str | None = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        dtype = torch.float16 if self.device == "cuda" else torch.float32
        self.tok = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name, dtype=dtype).to(self.device).eval()
        self.max_length = max_length

    @torch.inference_mode()
    def score(self, query: str, passages: list[str], batch_size: int = 16) -> list[float]:
        """Relevance in [0, 1] (sigmoid of the logit) for each passage."""
        scores: list[float] = []
        for s in range(0, len(passages), batch_size):
            batch = [[query, p] for p in passages[s : s + batch_size]]
            enc = self.tok(batch, padding=True, truncation=True, max_length=self.max_length, return_tensors="pt")
            logits = self.model(**enc.to(self.device)).logits.view(-1).float()
            scores += torch.sigmoid(logits).tolist()
        return scores


def rerank(
    reranker: CrossEncoder,
    query: str,
    chunks: list[RetrievedChunk],
    threshold: float | None = None,
    mode: str = "gate",
) -> list[RetrievedChunk]:
    """Re-sort by cross-encoder score. With a threshold, `gate` returns [] when even the best chunk is below it,
    `filter` drops each chunk below it. An empty result = insufficient evidence."""
    for c, s in zip(chunks, reranker.score(query, [c.text for c in chunks]), strict=True):
        c.score_rerank = s
    ranked = sorted(chunks, key=lambda c: c.score_rerank, reverse=True)
    if threshold is None or not ranked:
        return ranked
    if mode == "gate":
        return ranked if ranked[0].score_rerank >= threshold else []
    return [c for c in ranked if c.score_rerank >= threshold]
