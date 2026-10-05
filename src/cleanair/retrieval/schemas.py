"""Shapes shared by every retrieval stage (SPEC §7.2)."""

from typing import Protocol

from pydantic import BaseModel, Field


class RetrievedChunk(BaseModel):
    chunk_id: str
    doc_id: str
    text: str
    heading_path: str
    score_dense: float | None = None
    score_sparse: float | None = None
    score_fused: float = 0.0
    score_rerank: float | None = None
    metadata: dict = {}
    vector: list[float] | None = Field(default=None, exclude=True)  # dense vector, only when MMR needs it


class Filters(BaseModel):
    current_only: bool = True
    cities: list[str] = []  # match chunks tagged with any of these cities
    jurisdictions: list[str] = []
    doc_types: list[str] = []
    language: str | None = None


class Retriever(Protocol):
    def retrieve(self, query: str, filters: Filters, k: int) -> list[RetrievedChunk]: ...
