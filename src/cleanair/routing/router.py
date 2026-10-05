"""Question router (SPEC §9.1): policy / data / mixed / out_of_scope, plus language, cities and time range.

Two implementations with one output shape:
- route_rules: keyword baseline -- free, instant, the number the LLM router has to beat
- route_llm:   structured-output LLM call with few-shot examples
time_range is normalised to "YYYY-MM-DD/YYYY-MM-DD" so the SQL coverage check can use it directly.
"""

import calendar
import re
from typing import Literal

from pydantic import BaseModel, field_validator

from cleanair.generation.schemas import Route
from cleanair.generation.synthesize import complete_json

TARGET_CITIES = {"Delhi": "दिल्ली", "Kanpur": "कानपुर", "Lucknow": "लखनऊ", "Mumbai": "मुंबई"}
TIME_RANGE = re.compile(r"^\d{4}-\d{2}-\d{2}/\d{4}-\d{2}-\d{2}$")


class RouterOutput(BaseModel):
    route: Route
    language: Literal["en", "hi", "hinglish"]
    cities: list[str] = []
    time_range: str | None = None  # "YYYY-MM-DD/YYYY-MM-DD"
    policy_subquery: str | None = None  # what to retrieve
    data_subquery: str | None = None  # what to compute

    @field_validator("time_range")
    @classmethod
    def _iso_range(cls, v: str | None) -> str | None:
        return v if v is None or TIME_RANGE.match(v) else None  # drop malformed ranges rather than fail


# ---------- language ----------

HINGLISH = re.compile(
    r"\b(kya|hai|hain|ka|ki|ke|mein|me|kitne|kitna|kaise|kab|kaun|batao|bataiye|hota|hoti|tha|thi|aur)\b"
)


def detect_language(q: str) -> str:
    if re.search(r"[ऀ-ॿ]", q):
        return "hi"
    return "hinglish" if len(HINGLISH.findall(q.lower())) >= 2 else "en"


# ---------- time ranges ----------

MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m} | {
    m.lower(): i for i, m in enumerate(calendar.month_abbr) if m
}


def extract_time_range(q: str) -> str | None:
    """'winter 2024-25' -> Nov 1 .. Feb end; 'November 2025' -> that month; 'in 2024' -> that year."""
    s = q.lower()
    if m := re.search(r"winter (?:of )?(\d{4})\s*[-–/]\s*(\d{2,4})", s):
        y = int(m.group(1))
        return f"{y}-11-01/{y + 1}-02-{calendar.monthrange(y + 1, 2)[1]:02d}"
    if m := re.search(r"\b(" + "|".join(MONTHS) + r")\.? (\d{4})\b", s):
        mo, y = MONTHS[m.group(1)], int(m.group(2))
        return f"{y}-{mo:02d}-01/{y}-{mo:02d}-{calendar.monthrange(y, mo)[1]:02d}"
    if m := re.search(r"\b(20\d\d)\b", s):
        y = int(m.group(1))
        return f"{y}-01-01/{y}-12-31"
    return None


# ---------- rules baseline ----------

DOMAIN = re.compile(
    r"\b(air|aqi|pollut\w*|pm ?2\.?5|pm ?10|grap|ncap|naaqs|caqm|cpcb|smog|stubble|dust|emission\w*|"
    r"ozone|no2|so2|clean air|monitoring|kiln|c&d|construction|vehicle|bs-?\w+|puc\w*|swachh vayu)\b"
    r"|वायु|प्रदूषण|हवा|एक्यूआई|ग्रैप",
    re.IGNORECASE,
)
DATA = re.compile(
    r"\b(average|mean|median|how many days|number of days|days (?:was|were|did)|highest|lowest|maximum|minimum|"
    r"worst|best|trend|compare[ds]?|ranked|rank|most polluted|was the aqi|aqi was|aqi on|aqi in|reading|"
    r"recorded|kitne din|last (?:winter|month|year))\b|कितने दिन|औसत",
    re.IGNORECASE,
)
OUT_OF_SCOPE = re.compile(
    r"\b(buy|purchase|price|cost of|brand|recommend (?:a|an|me)|which (?:mask|purifier)|best (?:mask|purifier)|"
    r"recipe|movie|cricket|stock)\b",
    re.IGNORECASE,
)
POLICY = re.compile(
    r"\b(rule|rules|require\w*|stage|standard|limit|act|direction|order|plan|guideline\w*|measure\w*|ban\w*|"
    r"penalt\w*|fine|target|schedule|mandat\w*|permitted|allowed|restriction\w*|what does|under (?:the )?\w+|"
    r"according to|section|commission)\b|नियम|लक्ष्य|मानक|चरण",
    re.IGNORECASE,
)


def route_rules(q: str) -> RouterOutput:
    lang = detect_language(q)
    cities = [c for c, hi in TARGET_CITIES.items() if re.search(rf"\b{c}\b", q, re.I) or hi in q]
    is_data, is_policy = bool(DATA.search(q)), bool(POLICY.search(q))
    in_domain = DOMAIN.search(q) or (cities and (is_data or is_policy))  # "How many days was Delhi Severe?"
    if OUT_OF_SCOPE.search(q) or not in_domain:  # shopping intent first: "which air purifier" mentions air
        route = Route.OUT_OF_SCOPE
    else:
        route = Route.MIXED if is_data and is_policy else Route.DATA if is_data else Route.POLICY
    return RouterOutput(
        route=route,
        language=lang,
        cities=cities,
        time_range=extract_time_range(q),
        policy_subquery=q if route in (Route.POLICY, Route.MIXED) else None,
        data_subquery=q if route in (Route.DATA, Route.MIXED) else None,
    )


# ---------- LLM router ----------

ROUTER_SYSTEM = """You route questions for an assistant about India's air-quality POLICY documents (NCAP, GRAP,
NAAQS, CAQM Act and directions, city clean-air action plans, CPCB guidelines) and air-quality DATA (a database of
daily city AQI values and categories from CPCB bulletins, Oct 2023 onwards, for ~250 Indian cities).

route:
- "policy": answered from documents (rules, standards, thresholds, actions, targets, definitions)
- "data": needs computing over AQI measurements (averages, counts of days, maxima, trends, comparisons)
- "mixed": needs both (e.g. "AQI was 320 yesterday -- what does GRAP require and how often was it that bad?")
- "out_of_scope": not about Indian air-quality policy or data (shopping, medical advice, other topics)
language: "en", "hi" (Devanagari), or "hinglish" (Hindi in Latin script).
cities: cities named in the question, English spelling. time_range: "YYYY-MM-DD/YYYY-MM-DD" or null
(winter = 1 Nov to end of Feb). policy_subquery: a standalone English search query for the documents, or null.
data_subquery: what to compute, in English, or null.
Return JSON with exactly these keys: route, language, cities, time_range, policy_subquery, data_subquery.

Examples:
Q: What restrictions apply under GRAP Stage III?
{"route":"policy","language":"en","cities":[],"time_range":null,"policy_subquery":"GRAP Stage III restrictions","data_subquery":null}
Q: How many days was Lucknow's AQI Very Poor or worse in winter 2023-24?
{"route":"data","language":"en","cities":["Lucknow"],"time_range":"2023-11-01/2024-02-29","policy_subquery":null,"data_subquery":"count days with AQI category Very Poor or Severe in Lucknow"}
Q: Delhi ka AQI kal 420 tha, GRAP ka kaunsa stage lagega aur pichhli sardiyon mein aise kitne din the?
{"route":"mixed","language":"hinglish","cities":["Delhi"],"time_range":null,"policy_subquery":"GRAP stage for Delhi AQI 420","data_subquery":"count days with Delhi AQI above 400 last winter"}
Q: एनसीएपी का लक्ष्य क्या है?
{"route":"policy","language":"hi","cities":[],"time_range":null,"policy_subquery":"NCAP national target","data_subquery":null}
Q: Which mask brand is best for kids?
{"route":"out_of_scope","language":"en","cities":[],"time_range":null,"policy_subquery":null,"data_subquery":null}"""


def route_llm(q: str, model: str) -> tuple[RouterOutput, dict]:
    data, usage = complete_json(model, ROUTER_SYSTEM, f"Q: {q}", max_tokens=2048)
    try:
        return RouterOutput.model_validate(data), usage
    except Exception:  # malformed output: fall back to the rules router rather than fail the request
        usage["fallback"] = "rules"
        return route_rules(q), usage
