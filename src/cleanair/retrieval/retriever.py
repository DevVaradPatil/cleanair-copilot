"""The policy-path retriever: one config in, ranked evidence out (SPEC §7.1).

rank():     query -> embed -> dense and/or sparse search (filtered) -> fusion -> rerank (+ threshold) -> MMR
finalize(): top k -> small-to-big -> lost-in-the-middle ordering  (what the LLM reads)
Eval scores rank() (recall@k, MRR); generation uses retrieve() = finalize(rank()[:k]).
Every stage is switched by RetrievalConfig, so A0..A5 are the same code with different YAML.
"""

import json
from pathlib import Path

from qdrant_client import QdrantClient

from cleanair.config import PipelineConfig
from cleanair.ingest.embed import BGEM3
from cleanair.retrieval import fusion
from cleanair.retrieval.dense import dense_search
from cleanair.retrieval.filters import to_qdrant
from cleanair.retrieval.postprocess import lost_in_the_middle, mmr, small_to_big
from cleanair.retrieval.rerank import CrossEncoder, rerank
from cleanair.retrieval.schemas import Filters, RetrievedChunk
from cleanair.retrieval.sparse import sparse_search


class PipelineRetriever:
    def __init__(
        self,
        cfg: PipelineConfig,
        client: QdrantClient,
        embedder: BGEM3 | None = None,
        reranker: CrossEncoder | None = None,
        chunks_dir: Path = Path("data/processed/chunks"),
    ):
        self.cfg, self.r, self.client = cfg, cfg.retrieval, client
        self.embedder = embedder or BGEM3(cfg.embedder.model, cfg.embedder.max_length)
        self.reranker = reranker if not self.r.rerank else reranker or CrossEncoder(self.r.rerank_model)
        parents_file = chunks_dir / f"{cfg.chunk_set}.parents.jsonl"
        self.parents = {}
        if self.r.small_to_big and parents_file.exists():
            for line in parents_file.read_text(encoding="utf-8").splitlines():
                p = json.loads(line)
                self.parents[p["parent_id"]] = p

    def rank(self, query: str, filters: Filters) -> list[RetrievedChunk]:
        r, qfilter = self.r, to_qdrant(filters)
        dense_vec, sparse_vec = self.embedder.encode([query])
        lists = []
        if r.dense:
            lists.append(
                dense_search(self.client, self.cfg.collection, dense_vec[0].tolist(), qfilter, r.dense_k, r.mmr)
            )
        if r.sparse:
            lists.append(sparse_search(self.client, self.cfg.collection, sparse_vec[0], qfilter, r.sparse_k, r.mmr))
        if not lists:
            raise ValueError("config enables neither dense nor sparse retrieval")
        if len(lists) == 1:
            ranked = lists[0]
        elif r.fusion == "rrf":
            ranked = fusion.rrf(lists, r.rrf_k)
        else:
            ranked = fusion.weighted(lists[0], lists[1], r.alpha)

        if r.rerank:
            ranked = rerank(
                self.reranker, query, ranked[: r.rerank_candidates], r.rerank_threshold, r.rerank_threshold_mode
            )
        if r.mmr:
            ranked = mmr(ranked, r.k_final, r.mmr_lambda)
        return ranked

    def finalize(self, ranked: list[RetrievedChunk], k: int) -> list[RetrievedChunk]:
        top = ranked[:k]
        if self.r.small_to_big:
            top = small_to_big(top, self.parents, self.r.small_to_big_max_tokens)
        if self.r.reorder:
            top = lost_in_the_middle(top)
        return top

    def retrieve(self, query: str, filters: Filters, k: int | None = None) -> list[RetrievedChunk]:
        return self.finalize(self.rank(query, filters), k or self.r.k_final)
