"""Pipeline orchestration with fakes: out-of-scope, mixed (both paths), and a broken data path degrading."""

from cleanair import pipeline as pl
from cleanair.config import PipelineConfig, RoutingConfig
from cleanair.generation import synthesize as syn
from cleanair.generation.schemas import Route
from cleanair.retrieval.schemas import RetrievedChunk
from cleanair.sql.execute import QueryResult
from cleanair.sql.text_to_sql import DataResult

CHUNK = RetrievedChunk(chunk_id="grap::c1", doc_id="grap", text="Stage III: AQI 401-450", heading_path="")


class FakeRetriever:
    def retrieve(self, query, filters, k=None):
        return [CHUNK]


def copilot(router="rules"):
    return pl.Copilot(PipelineConfig(name="t", routing=RoutingConfig(router=router)), retriever=FakeRetriever())


def fake_llm(captured):
    def complete_json(model, system, user, *a, **k):
        captured.append(user)
        return {"answer": "ok [grap::c1] [SQL]", "citations": ["[grap::c1]", "[SQL]"], "not_found": False}, {
            "model": "fake"
        }

    return complete_json


def test_out_of_scope_answers_without_any_llm_call(monkeypatch):
    calls = []
    monkeypatch.setattr(syn, "complete_json", fake_llm(calls))
    answer, trace = copilot().answer("Which air purifier should I buy?")
    assert answer.route == Route.OUT_OF_SCOPE and answer.not_found and calls == []


def test_mixed_question_uses_both_paths_and_cites_both(monkeypatch):
    calls = []
    monkeypatch.setattr(syn, "complete_json", fake_llm(calls))
    monkeypatch.setattr(
        pl,
        "answer_data",
        lambda q, cfg, route: DataResult(
            question=q, sql="SELECT 1", result=QueryResult(["severe_days"], [(12,)], False, 0.01)
        ),
    )
    q = "Kanpur's AQI was 320 yesterday; what does GRAP require, and how many days was it that bad last winter?"
    answer, trace = copilot().answer(q)
    assert answer.route == Route.MIXED
    assert '<source id="grap::c1"' in calls[0] and '<source id="SQL"' in calls[0]
    assert {c.chunk_id for c in answer.citations} == {"grap::c1", "SQL"}


def test_broken_data_path_degrades_instead_of_crashing(monkeypatch):
    calls = []
    monkeypatch.setattr(syn, "complete_json", fake_llm(calls))

    def boom(q, cfg, route):
        raise NotImplementedError("🧠 validate")

    monkeypatch.setattr(pl, "answer_data", boom)
    answer, trace = copilot().answer("How many days was Kanpur's AQI Severe in winter 2024-25?")
    assert trace.data_error.startswith("NotImplementedError") and answer.not_found and calls == []


def test_router_none_keeps_policy_only(monkeypatch):
    monkeypatch.setattr(syn, "complete_json", fake_llm([]))
    answer, trace = copilot(router="none").answer("How many days was Kanpur's AQI Severe?")
    assert trace.route.route == Route.POLICY and trace.data is None
