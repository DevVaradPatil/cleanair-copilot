from cleanair.config import GenerationConfig
from cleanair.generation import synthesize as syn
from cleanair.generation.prompts import NOT_FOUND
from cleanair.retrieval.schemas import RetrievedChunk

CHUNK = RetrievedChunk(
    chunk_id="grap::fixed::c001", doc_id="grap", text="Stage III: DELHI AQI 401-450", heading_path=""
)


def fake_llm(payload, calls):
    def complete_json(*args, **kwargs):
        calls.append(args)
        return payload, {"model": "fake", "latency_s": 0, "cost_usd": 0}

    return complete_json


def test_no_evidence_means_not_found_without_llm_call(monkeypatch):
    calls = []
    monkeypatch.setattr(syn, "complete_json", fake_llm({}, calls))
    answer, usage = syn.synthesize("q", [], GenerationConfig())
    assert answer.not_found and answer.answer == NOT_FOUND and calls == [] and usage["model"] is None


def test_odd_llm_shapes_do_not_crash_and_unknown_citations_are_dropped(monkeypatch):
    payload = {
        "answer": "Stage III applies at AQI 401-450 [grap::fixed::c001].",
        "citations": ["[grap::fixed::c001]", {"chunk_id": "never-shown::c9", "marker": "[x]"}, 42],
        "assumptions": "Delhi AQI",
        "not_found": False,
    }
    monkeypatch.setattr(syn, "complete_json", fake_llm(payload, []))
    answer, usage = syn.synthesize("What triggers Stage III?", [CHUNK], GenerationConfig())
    assert [c.chunk_id for c in answer.citations] == ["grap::fixed::c001"]
    assert answer.assumptions == ["Delhi AQI"]
    assert usage["dropped_citations"] == 2
