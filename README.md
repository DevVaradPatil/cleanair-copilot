# Clean Air Copilot (India)

A bilingual RAG + text-to-SQL assistant for Indian air-quality **policy** (NCAP, GRAP, NAAQS, CAQM Act, city
action plans) and **CPCB monitoring data**, with clause-level citations and a measured evaluation suite.
Work in progress — see [SPEC.md](SPEC.md) and [plan.md](plan.md). Full README comes in M5.

## Results so far

**Golden set v1** — 150 questions: 40 single-fact, 15 multi-fact, 30 data (SQL), 20 mixed, 20 Hindi/Hinglish,
16 unanswerable, 10 red-team — over 47 official documents (BGE-M3, Qdrant) and 3 years of CPCB daily AQI bulletins
(258,605 city-days, DuckDB). Relevance = the chunk contains the verified evidence quote **from the current
document**. Retrieval metrics cover the 95 questions with policy evidence; 95% bootstrap CIs.

### Retrieval ablation (SPEC §10.4)

| Config | What changes | Recall@5 | MRR | Policy facts | Multi-fact | Mixed | Hindi |
|---|---|---|---|---|---|---|---|
| **A0** | fixed 500-token chunks, dense top-5 | 0.458 [0.36–0.56] | 0.331 | 0.78 | 0.27 | 0.15 | 0.37 |
| **A1** | + structure-aware chunks (≤ 400, heading paths) | 0.421 [0.33–0.52] | 0.311 | 0.60 | 0.33 | 0.20 | 0.27 |
| **A2** | + BGE-M3 sparse + RRF (hybrid) | 0.479 [0.38–0.58] | 0.358 | 0.72 | 0.40 | 0.20 | 0.23 |
| **A3** | + cross-encoder rerank, current-doc filter, gate 0.184 | 0.621 [0.53–0.71] | 0.451 | 0.85 | **0.60** | **0.35** | 0.40 |
| D3 | A0 + rerank + current-doc filter (fixed chunks, dense) | **0.647** [0.56–0.74] | **0.522** | **0.95** | 0.50 | 0.25 | **0.60** |

What the numbers say (paired bootstrap over the same questions):
- **Reranking and the current-document filter carry most of the gain** (A0 → D3: +0.19 recall@5; A2 → A3: +0.14).
- **Structure-aware chunking is a trade-off, not a free win**: it helps questions that need a specific clause or
  several facts (multi-fact 0.60 vs 0.50, mixed 0.35 vs 0.25) and hurts single facts and Hindi at equal k; at an
  equal *token* budget it is neutral (+0.04, n.s.). Structure chunks are half the size of fixed ones.
- **Hybrid helps structure chunks** (A3 0.621 vs the same stack without sparse 0.584).
- **One "not found" threshold doesn't fit a bilingual system**: to keep 95% of answerable questions it must drop to
  0.184 (0.637 on English-only questions), and then catches only 45% of unanswerable ones.

### Data path and routing

- **Text-to-SQL** (gemini-3.5-flash-lite, free tier, first 17 data questions): **17/17** correct result sets, all
  first try (14/17 under strict matching — the 3 differences were a full ranking with the right winner on top and
  `'2025-07'` vs `7` month labels). SQL safety: 28/28 attack strings rejected, 55/55 golden reference queries accepted.
- **Router**: rules baseline 0.827 [0.77–0.89] on all 150; on a 19-question stratified sample the LLM router
  (gemini-3.1-flash-lite) scored 0.89 vs rules 0.84 (CIs overlap). Language detection 0.99–1.00.
- Full end-to-end answers + faithfulness on 150 questions need a paid Gemini tier (free tier = 20 requests/day/model).
  v0 results (63 English questions) are archived in `eval/results/v0/`.

Full table: `uv run python -m eval.report --runs eval/results/*_golden`. D-rows are diagnostics outside the
SPEC ablation. Coverage of the monitoring data: [docs/DATA_QUALITY.md](docs/DATA_QUALITY.md).

## Run it

```bash
docker compose up -d qdrant
uv run python -m cleanair.ask "What AQI triggers GRAP Stage III?"   # routes, retrieves, answers with citations
uv run python -m eval.harness --config configs/ablations/naive.yaml --set golden
```
