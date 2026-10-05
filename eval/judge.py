"""LLM judge for faithfulness (RAGAS-style: supported claims / total claims). UNCALIBRATED until M4 (SPEC §10.6).

Reasoning before verdict; the judge sees only the sources the generator saw, not the reference answer.
"""

from cleanair.generation.prompts import user_message
from cleanair.generation.synthesize import complete_json
from cleanair.retrieval.schemas import RetrievedChunk

JUDGE_SYSTEM = """You check whether an answer is supported by the provided sources.
1. Split the ANSWER into atomic factual claims (numbers, dates, actions, agencies, conditions). Ignore hedges,
   greetings and statements that information was not found.
2. For each claim, decide if the SOURCES state it (paraphrase is fine; extra precision not in the sources is NOT).
   Write a one-line reason BEFORE the verdict.
Return JSON: {"claims": [{"claim": str, "reason": str, "supported": bool}]}"""


def faithfulness(
    question: str, answer: str, chunks: list[RetrievedChunk], model: str, data_result=None
) -> tuple[float | None, dict, dict]:
    """Returns (supported share or None if the answer makes no claims, raw judge output, usage).

    The judge sees exactly what the generator saw: policy chunks and, for data/mixed answers, the SQL result.
    """
    user = f"SOURCES AND QUESTION:\n{user_message(question, chunks, data_result)}\n\nANSWER: {answer}"
    data, usage = complete_json(model, JUDGE_SYSTEM, user, max_tokens=8192)
    claims = data.get("claims", [])
    if not claims:
        return None, data, usage
    return sum(bool(c.get("supported")) for c in claims) / len(claims), data, usage
