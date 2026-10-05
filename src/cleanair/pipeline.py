"""The online pipeline (SPEC §4): route -> policy path and/or data path (in parallel) -> grounded synthesis.

routing.router = "none" keeps A0-A3 policy-only; "rules" / "llm" enable the data and mixed paths (A4).
"""

import asyncio
from dataclasses import dataclass, field

from qdrant_client import QdrantClient

from cleanair.config import PipelineConfig
from cleanair.generation.schemas import Answer, Route
from cleanair.generation.synthesize import synthesize
from cleanair.retrieval.filters import filters_for
from cleanair.retrieval.retriever import PipelineRetriever
from cleanair.routing.router import RouterOutput, detect_language, route_llm, route_rules
from cleanair.settings import Settings
from cleanair.sql.text_to_sql import DataResult, answer_data

OUT_OF_SCOPE = {
    "en": "I can only help with India's air-quality policy (NCAP, GRAP, NAAQS, the CAQM Act, city clean-air plans) "
    'and CPCB air-quality data. Try asking, for example, "What restrictions apply under GRAP Stage III?" or '
    '"How many days was Kanpur\'s AQI Severe in winter 2024-25?"',
    "hi": "मैं केवल भारत की वायु-गुणवत्ता नीति (NCAP, GRAP, NAAQS, CAQM अधिनियम, शहरों की स्वच्छ वायु योजनाएँ) और CPCB के "
    "वायु-गुणवत्ता आँकड़ों से जुड़े सवालों में मदद कर सकता हूँ।",
}


@dataclass
class Trace:
    route: RouterOutput | None = None
    router_usage: dict = field(default_factory=dict)
    chunks: list = field(default_factory=list)
    data: DataResult | None = None
    data_error: str | None = None
    generation: dict = field(default_factory=dict)


class Copilot:
    def __init__(self, cfg: PipelineConfig, retriever: PipelineRetriever | None = None):
        self.cfg = cfg
        self._retriever = retriever

    @property
    def retriever(self) -> PipelineRetriever:
        if self._retriever is None:  # lazy: data-only questions never load the embedder/reranker
            self._retriever = PipelineRetriever(self.cfg, QdrantClient(url=Settings().qdrant_url))
        return self._retriever

    def route(self, question: str) -> tuple[RouterOutput, dict]:
        mode = self.cfg.routing.router
        if mode == "llm":
            return route_llm(question, self.cfg.routing.model)
        if mode == "rules":
            return route_rules(question), {}
        return RouterOutput(route=Route.POLICY, language=detect_language(question), policy_subquery=question), {}

    def _policy(self, question: str, route: RouterOutput):
        query = route.policy_subquery or question
        return self.retriever.retrieve(query, filters_for(question, self.cfg.retrieval.current_only))

    def _data(self, question: str, route: RouterOutput) -> DataResult:
        return answer_data(question, self.cfg, route)

    async def aanswer(self, question: str) -> tuple[Answer, Trace]:
        trace = Trace()
        trace.route, trace.router_usage = self.route(question)
        r = trace.route
        if r.route == Route.OUT_OF_SCOPE:
            msg = OUT_OF_SCOPE["hi" if r.language == "hi" else "en"]
            return Answer(answer=msg, citations=[], not_found=True, route=r.route), trace

        jobs = {}
        if r.route in (Route.POLICY, Route.MIXED):
            jobs["policy"] = asyncio.to_thread(self._policy, question, r)
        if r.route in (Route.DATA, Route.MIXED):
            jobs["data"] = asyncio.to_thread(self._data, question, r)
        results = dict(zip(jobs, await asyncio.gather(*jobs.values(), return_exceptions=True), strict=True))

        if isinstance(results.get("policy"), Exception):
            raise results["policy"]
        trace.chunks = results.get("policy") or []
        data = results.get("data")
        if isinstance(data, Exception):  # e.g. the 🧠 validator isn't implemented yet: degrade, don't crash
            trace.data_error = f"{type(data).__name__}: {data}"
            data = None
        trace.data = data
        answer, trace.generation = synthesize(question, trace.chunks, self.cfg.generation, data, r.route)
        return answer, trace

    def answer(self, question: str) -> tuple[Answer, Trace]:
        return asyncio.run(self.aanswer(question))
