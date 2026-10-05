"""Grounded answer synthesis through LiteLLM (provider-agnostic: model id comes from the config)."""

import json
import time

import litellm

from cleanair.config import GenerationConfig
from cleanair.generation.prompts import NOT_FOUND, SYSTEM_PROMPT, user_message
from cleanair.generation.schemas import Answer, Citation, Route
from cleanair.retrieval.schemas import RetrievedChunk
from cleanair.settings import Settings

litellm.suppress_debug_info = True


TRANSIENT = (
    litellm.exceptions.ServiceUnavailableError,  # 503 "model is experiencing high demand"
    litellm.exceptions.RateLimitError,  # 429
    litellm.exceptions.Timeout,
    litellm.exceptions.APIConnectionError,
    litellm.exceptions.InternalServerError,
)


def _call(model: str, messages: list[dict], temperature: float, max_tokens: int):
    return litellm.completion(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=Settings().gemini_api_key.get_secret_value(),
    )


def complete_json(
    model: str,
    system: str,
    user: str,
    temperature: float = 0.0,
    max_tokens: int = 8192,
    fallback: str | None = None,
    retries: int = 4,
) -> tuple[dict, dict]:
    """One JSON-mode LLM call with backoff on transient errors, then `fallback` if the model stays down.

    Returns (parsed JSON, usage incl. the model actually used, latency, tokens, cost).
    """
    t0 = time.time()
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    resp, used = None, None
    for m in (model, fallback):
        if m is None:
            continue
        for attempt in range(retries):
            try:
                resp, used = _call(m, messages, temperature, max_tokens), m
                break
            except TRANSIENT:
                if attempt < retries - 1:
                    time.sleep(3 * 2**attempt)  # 3, 6, 12 s
        if resp is not None:
            break
    if resp is None:
        raise RuntimeError(f"LLM unavailable after retries: {model}, fallback {fallback}")
    content = resp.choices[0].message.content or "{}"
    try:
        cost = litellm.completion_cost(resp)
    except Exception:  # unknown price for a brand-new model id: report None rather than crash
        cost = None
    usage = {
        "model": used,
        "latency_s": round(time.time() - t0, 2),
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
        "cost_usd": cost,
    }
    try:
        return json.loads(content), usage
    except json.JSONDecodeError as e:  # usually finish_reason == "length": reasoning tokens ate the budget
        raise ValueError(f"{used} returned invalid JSON (finish_reason={resp.choices[0].finish_reason})") from e


def synthesize(question: str, chunks: list[RetrievedChunk], cfg: GenerationConfig) -> tuple[Answer, dict]:
    if not chunks:  # retrieval said "insufficient evidence": don't let the LLM improvise
        return Answer(answer=NOT_FOUND, citations=[], not_found=True, route=Route.POLICY), {"model": None}
    data, usage = complete_json(
        cfg.model,
        SYSTEM_PROMPT,
        user_message(question, chunks),
        cfg.temperature,
        cfg.max_output_tokens,
        fallback=cfg.fallback_model,
    )
    provided = {c.chunk_id for c in chunks}
    raw = data.get("citations") or []
    citations = []
    for c in raw if isinstance(raw, list) else []:
        if isinstance(c, str):  # model returned bare markers like "[doc::fixed::c003]"
            c = {"marker": c, "chunk_id": c.strip("[] "), "quote": None}
        if isinstance(c, dict) and c.get("chunk_id") in provided:  # drop citations to chunks never shown
            citations.append(Citation(marker=str(c.get("marker", "")), chunk_id=c["chunk_id"], quote=c.get("quote")))
    assumptions = data.get("assumptions") or []
    answer = Answer(
        answer=str(data.get("answer", "")),
        citations=citations,
        not_found=bool(data.get("not_found", False)),
        route=Route.POLICY,
        assumptions=[assumptions] if isinstance(assumptions, str) else [str(a) for a in assumptions],
    )
    usage["dropped_citations"] = (len(raw) if isinstance(raw, list) else 0) - len(citations)
    return answer, usage
