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


class RetrievalConfig(_Strict):
    dense_k: int = 50
    sparse: bool = True
    sparse_k: int = 50
    fusion: Literal["rrf", "weighted"] = "rrf"
    rrf_k: int = 60
    alpha: float = 0.5  # weight of dense scores in weighted fusion
    rerank: bool = True
    rerank_candidates: int = 30
    rerank_threshold: float | None = None  # chosen from data in plan step 2.4
    k_final: int = 6
    mmr: bool = False
    mmr_lambda: float = 0.7
    small_to_big: bool = False


class RoutingConfig(_Strict):
    router: Literal["none", "rules", "llm"] = "llm"  # "none" = policy path only (A0-A3)
    condense: bool = False


class GenerationConfig(_Strict):
    citation_check: bool = False


class PipelineConfig(_Strict):
    name: str
    chunker: ChunkerConfig = ChunkerConfig()
    embedder: EmbedderConfig = EmbedderConfig()
    retrieval: RetrievalConfig = RetrievalConfig()
    routing: RoutingConfig = RoutingConfig()
    generation: GenerationConfig = GenerationConfig()


def load_config(path: str | Path) -> PipelineConfig:
    return PipelineConfig.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))
