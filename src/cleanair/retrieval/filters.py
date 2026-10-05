"""Metadata filters -> Qdrant payload filter (SPEC §7.1 step 2).

Filtering happens inside Qdrant's HNSW search (not after it), so a filtered top-50 is still 50 matching chunks.
Until the router lands (M3), the only automatic rule is: current documents only, unless the question
is about the past.
"""

import re

from qdrant_client import models

from cleanair.retrieval.schemas import Filters

# ponytail: keyword heuristic for "asks about the past"; the M3 router's time_range replaces it.
PAST = re.compile(
    r"\b(previous(ly)?|earlier|older|old|superseded|history|historical|used to|before the (revision|amendment)|"
    r"original(ly)?|first version|(19|20)\d\d)\b|पहले|पुरान",
    re.IGNORECASE,
)


def wants_history(query: str) -> bool:
    return bool(PAST.search(query))


def filters_for(query: str, current_only_default: bool) -> Filters:
    return Filters(current_only=current_only_default and not wants_history(query))


def to_qdrant(f: Filters) -> models.Filter | None:
    must: list[models.Condition] = []
    if f.current_only:
        must.append(models.FieldCondition(key="is_current", match=models.MatchValue(value=True)))
    for key, values in (("cities", f.cities), ("jurisdiction", f.jurisdictions), ("doc_type", f.doc_types)):
        if values:
            must.append(models.FieldCondition(key=key, match=models.MatchAny(any=values)))
    if f.language:
        must.append(models.FieldCondition(key="language", match=models.MatchValue(value=f.language)))
    return models.Filter(must=must) if must else None
