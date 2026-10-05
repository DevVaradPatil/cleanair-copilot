"""Answer shapes (SPEC §9.1-9.2). The streamed UI renders the same fields."""

from enum import StrEnum

from pydantic import BaseModel


class Route(StrEnum):
    POLICY = "policy"
    DATA = "data"
    MIXED = "mixed"
    OUT_OF_SCOPE = "out_of_scope"


class Citation(BaseModel):
    marker: str  # "[grap-schedule-2026-09::fixed::c004]" or "[SQL]"
    chunk_id: str | None
    quote: str | None  # short supporting span (<= 25 words)


class Answer(BaseModel):
    answer: str
    citations: list[Citation]
    not_found: bool
    route: Route = Route.POLICY
    assumptions: list[str] = []
