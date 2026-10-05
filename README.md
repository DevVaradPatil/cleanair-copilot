# Clean Air Copilot (India)

A bilingual RAG + text-to-SQL assistant for Indian air-quality **policy** (NCAP, GRAP, NAAQS, CAQM Act, city
action plans) and **CPCB monitoring data**, with clause-level citations and a measured evaluation suite.
Work in progress — see [SPEC.md](SPEC.md) and [plan.md](plan.md). Full README comes in M5.

## Results so far (retrieval)

**Golden set v1** — 150 questions: 40 single-fact, 15 multi-fact, 30 data (SQL), 20 mixed, 20 Hindi/Hinglish,
16 unanswerable, 10 red-team — over 47 official documents (1,874 fixed 500-token chunks, BGE-M3, Qdrant) and
3 years of CPCB daily AQI bulletins (258,605 city-days, DuckDB). Relevance = the chunk contains the verified
evidence quote **from the current document**. 95% bootstrap CIs. Retrieval metrics cover the 103 items with
policy evidence.

| Config | What changes | Recall@5 | MRR | Policy facts | Multi-fact | Hindi/Hinglish | Mixed |
|---|---|---|---|---|---|---|---|
| **A0** naive | fixed chunks, dense top-5 | 0.458 [0.36–0.56] | 0.331 | 0.78 | 0.27 | 0.37 | 0.15 |
| D1 | sparse (BGE-M3 lexical) only | 0.495 [0.40–0.59] | 0.372 | 0.85 | 0.20 | 0.27 | 0.25 |
| D2 | A0 + cross-encoder rerank | 0.542 [0.45–0.64] | 0.467 | 0.82 | 0.33 | 0.50 | 0.25 |
| **D3** | D2 + current-document filter | **0.647** [0.56–0.74] | **0.522** | 0.95 | 0.50 | 0.60 | 0.25 |
| D6 | D3 + "not found" gate (0.637) | 0.574 [0.48–0.67] | 0.474 | 0.95 | 0.43 | 0.33 | 0.20 |
| A1–A4 | structure chunks, hybrid + RRF, LLM router | *pending 🧠 code and a paid LLM tier* | | | | | |

- The gate (tuned on English questions) abstains on 80% of unanswerable questions but also on **8 of 15 Hindi**
  ones — a single global threshold doesn't fit a bilingual system (M4: multilingual calibration).
- Cross-lingual retrieval works: 10 of 13 Hindi/Hinglish translations match their English source's recall.
- Rules router baseline: route accuracy 0.827 [0.77–0.89], language detection 0.987 (LLM router: needs quota).
- Text-to-SQL, mixed answers and faithfulness are built and unit-tested; their evals need the 🧠 SQL validator
  and a paid Gemini tier. v0 results (63 English questions) are archived in `eval/results/v0/`.

Full table: `uv run python -m eval.report --runs eval/results/*_golden`. D-rows are diagnostics outside the
SPEC ablation. Coverage of the monitoring data: [docs/DATA_QUALITY.md](docs/DATA_QUALITY.md).

## Run it

```bash
docker compose up -d qdrant
uv run python -m cleanair.ask "What AQI triggers GRAP Stage III?"   # routes, retrieves, answers with citations
uv run python -m eval.harness --config configs/ablations/naive.yaml --set golden
```
