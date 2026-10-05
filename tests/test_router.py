import pytest

from cleanair.generation.schemas import Route
from cleanair.routing import router as r


@pytest.mark.parametrize(
    "q, route",
    [
        ("What restrictions apply under GRAP Stage III?", Route.POLICY),
        ("What is the 24-hour NAAQS limit for PM2.5?", Route.POLICY),
        ("Average AQI in Lucknow in November 2025?", Route.DATA),
        ("How many days was Kanpur's AQI Severe in winter 2024-25?", Route.DATA),
        (
            "Kanpur's AQI was 320 yesterday; what does GRAP require, and how many days was it that bad last winter?",
            Route.MIXED,
        ),
        ("Which air purifier should I buy?", Route.OUT_OF_SCOPE),
        ("NCAP का लक्ष्य क्या है?", Route.POLICY),
    ],
)
def test_rules_router_spec_examples(q, route):
    assert r.route_rules(q).route == route


def test_language_detection():
    assert r.detect_language("NCAP का लक्ष्य क्या है?") == "hi"
    assert r.detect_language("Delhi ka AQI kitna hai aur GRAP kya kehta hai?") == "hinglish"
    assert r.detect_language("What is the NCAP target?") == "en"


def test_time_ranges():
    assert r.extract_time_range("Severe days in winter 2024-25") == "2024-11-01/2025-02-28"
    assert r.extract_time_range("winter 2023-24 in Delhi") == "2023-11-01/2024-02-29"  # leap year
    assert r.extract_time_range("average AQI in November 2025") == "2025-11-01/2025-11-30"
    assert r.extract_time_range("in 2024") == "2024-01-01/2024-12-31"
    assert r.extract_time_range("what does GRAP say") is None


def test_cities_in_english_and_hindi():
    assert r.route_rules("कानपुर और Delhi का AQI").cities == ["Delhi", "Kanpur"]


def test_llm_router_falls_back_to_rules_on_malformed_output(monkeypatch):
    monkeypatch.setattr(r, "complete_json", lambda *a, **k: ({"route": "banana"}, {"model": "fake"}))
    out, usage = r.route_llm("How many days was Delhi Severe in 2024?", "fake")
    assert out.route == Route.DATA and usage["fallback"] == "rules"


def test_malformed_time_range_is_dropped_not_fatal():
    assert r.RouterOutput(route="data", language="en", time_range="last winter").time_range is None
