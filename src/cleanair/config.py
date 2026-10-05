"""Typed pipeline config loaded from configs/*.yaml.

Every ablation switch in SPEC.md §10.4 is a field here, so A0..A6 differ only by YAML.
Defaults follow the spec; extra="forbid" makes a typo in a YAML key fail loudly.
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChunkerConfig(_Strict):
    type: Literal["fixed", "structure"] = "structure"
    max_tokens: int = 400
    overlap: int = 60


class EmbedderConfig(_Strict):
    model: str = "BAAI/bge-m3"
    max_length: int = 1024  # tokens; chunks are <= 500, so nothing should be truncated (counted at embed time)


class RetrievalConfig(_Strict):
    dense: bool = True
    dense_k: int = 50
    sparse: bool = True
    sparse_k: int = 50
    fusion: Literal["rrf", "weighted"] = "rrf"
    rrf_k: int = 60
    alpha: float = 0.5  # weight of dense scores in weighted fusion
    rerank: bool = True
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_candidates: int = 30
    rerank_threshold: float | None = None  # chosen from data in plan step 2.4
    # gate: abstain only if the BEST chunk is below the threshold, else keep the normal top k.
    # filter: drop every chunk below it (cuts the weaker second fact of multi-fact questions; measured in D4 vs D6).
    rerank_threshold_mode: Literal["gate", "filter"] = "gate"
    k_final: int = 6
    mmr: bool = False
    mmr_lambda: float = 0.7
    small_to_big: bool = False
    small_to_big_max_tokens: int = 1200  # swap a chunk for its parent section only if the parent fits
    reorder: bool = False  # lost-in-the-middle: best chunks first and last
    current_only: bool = True  # filter is_current=true unless the question asks about the past


class RoutingConfig(_Strict):
    router: Literal["none", "rules", "llm"] = "llm"  # "none" = policy path only (A0-A3)
    condense: bool = False


class GenerationConfig(_Strict):
    model: str = "gemini/gemini-3.8-flash"  # LiteLLM id; ids verified against the API on 2026-10-05
    fallback_model: str | None = "gemini/gemini-3.6-flash"  # used only after repeated 503/429; logged per call
    temperature: float = 0.0
    max_output_tokens: int = 8192  # Gemini 3 reasoning tokens count against this
    citation_check: bool = False


class PipelineConfig(_Strict):
    name: str
    chunker: ChunkerConfig = ChunkerConfig()
    embedder: EmbedderConfig = EmbedderConfig()
    retrieval: RetrievalConfig = RetrievalConfig()
    routing: RoutingConfig = RoutingConfig()
    generation: GenerationConfig = GenerationConfig()

    @property
    def chunk_set(self) -> str:
        """Name of the chunk set this config's chunker produces, e.g. "fixed-500-50"."""
        c = self.chunker
        return f"{c.type}-{c.max_tokens}-{c.overlap}"

    @property
    def collection(self) -> str:
        """Qdrant collection = chunk set x embedder, so a new model never overwrites an index (blue-green)."""
        return f"{self.chunk_set}__{self.embedder.model.split('/')[-1].lower()}"


def load_config(path: str | Path) -> PipelineConfig:
    return PipelineConfig.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))
