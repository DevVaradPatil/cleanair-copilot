"""Retrieval metrics over chunker-independent evidence, plus a bootstrap CI.

Relevance can't be a fixed list of chunk ids: every chunker cuts different chunks, and the ablation compares
chunkers. So each golden question carries `evidence`: a list of required facts, each a list of acceptable
(doc_id, quote) alternatives. A retrieved chunk *covers* a fact if it comes from that doc and contains the quote
(after normalisation), or -- for quotes of 12+ words that a chunk boundary may cut -- either half of it
(halves of >= 6 words; shorter halves like "the commission may impose" match unrelated clauses).
"""

import math
import random
import re
import unicodedata

HALF_MATCH_MIN_WORDS = 12
FOLD = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "−": "-", " ": " "})


def norm(s: str) -> str:
    """Comparison form: NFKC (folds ligatures, µ), ASCII quotes/dashes, no markdown table syntax, lower, 1 space."""
    s = unicodedata.normalize("NFKC", s).translate(FOLD).lower()
    s = re.sub(r"[|*_`#]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def covers(chunk_text: str, quote: str) -> bool:
    text, q = norm(chunk_text), norm(quote)
    if q in text:
        return True
    words = q.split()
    if len(words) < HALF_MATCH_MIN_WORDS:
        return False
    mid = len(words) // 2
    return " ".join(words[:mid]) in text or " ".join(words[mid:]) in text


def facts_covered(chunk: dict, evidence: list[list[dict]]) -> set[int]:
    """Indices of the evidence facts this chunk (needs doc_id and text) covers."""
    return {
        i
        for i, alternatives in enumerate(evidence)
        if any(chunk["doc_id"] == a["doc_id"] and covers(chunk["text"], a["quote"]) for a in alternatives)
    }


def retrieval_metrics(ranked: list[dict], evidence: list[list[dict]], ks: tuple[int, ...] = (1, 3, 5, 10)) -> dict:
    """recall@k = share of required facts covered by the top k; MRR = 1/rank of the first chunk covering any fact;
    nDCG@k with binary gains (a chunk is relevant if it covers a fact not covered by a higher-ranked chunk)."""
    hits = [facts_covered(c, evidence) for c in ranked]
    out: dict[str, float] = {}
    for k in ks:
        got = set().union(*hits[:k]) if hits[:k] else set()
        out[f"recall@{k}"] = len(got) / len(evidence)
    first = next((r for r, h in enumerate(hits, start=1) if h), None)
    out["mrr"] = 1.0 / first if first else 0.0

    seen: set[int] = set()
    gains = []
    for h in hits:
        new = h - seen
        gains.append(1.0 if new else 0.0)
        seen |= h
    for k in ks:
        dcg = sum(g / math.log2(r + 2) for r, g in enumerate(gains[:k]))
        ideal = sum(1.0 / math.log2(r + 2) for r in range(min(k, len(evidence))))
        out[f"ndcg@{k}"] = dcg / ideal if ideal else 0.0
    return out


def _cell(v) -> object:
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, int | float):
        return round(float(v), 1)
    return str(v).strip().lower()


def _same_column(a: list, b: list, tol: float) -> bool:
    a, b = sorted(map(_cell, a), key=str), sorted(map(_cell, b), key=str)
    if len(a) != len(b):
        return False
    for x, y in zip(a, b, strict=True):
        if isinstance(x, float) and isinstance(y, float):
            if abs(x - y) > max(tol, 0.01 * abs(x)):
                return False
        elif x != y:
            return False
    return True


def results_match(ref_cols: list, ref_rows: list, got_cols: list, got_rows: list, tol: float = 0.15) -> bool:
    """SQL execution accuracy (SPEC §10.3): compare result SETS, not SQL strings.

    Same number of rows, and every reference column's values (as a multiset, order-insensitive, numbers within
    tolerance) appear as some column of the generated result. Extra generated columns (e.g. a days count the
    prompt asks for) and different column names are fine.
    """
    if len(ref_rows) != len(got_rows):
        return False
    got_columns = [[r[j] for r in got_rows] for j in range(len(got_cols))]
    used: set[int] = set()
    for i in range(len(ref_cols)):
        ref_col = [r[i] for r in ref_rows]
        j = next((j for j, g in enumerate(got_columns) if j not in used and _same_column(ref_col, g, tol)), None)
        if j is None:
            return False
        used.add(j)
    return True


def bootstrap_ci(values: list[float], n: int = 2000, alpha: float = 0.05, seed: int = 0) -> tuple[float, float, float]:
    """Mean and percentile bootstrap (1 - alpha) CI over questions."""
    if not values:
        return (float("nan"),) * 3
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(n))
    return sum(values) / len(values), means[int(n * alpha / 2)], means[int(n * (1 - alpha / 2)) - 1]
