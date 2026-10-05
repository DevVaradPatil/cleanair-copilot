# Development Plan: Clean Air Copilot

The phase-by-phase build plan, taken from SPEC.md §13 and broken into one-module steps.
SPEC.md is still the source of truth for *what* to build. This file covers the *order*, and what counts as done.

**Legend:** 🧠 = Varad writes the core logic, and Claude only scaffolds the interface and tests (§0.1).
👤 = a manual step for Varad, tracked in [TODO.md](TODO.md) under the ID shown.
Each step follows explain → propose → implement → test, and its decisions go into `docs/DECISIONS.md`.

**Timeline:** about 3 weeks part-time (SPEC §13), plus about a week of buffer, so it's ready well before the
Dec 2026 placements. The day numbers below are working days, not calendar days.

| Phase | Working days | Outcome |
|---|---|---|
| M0 Setup | ½ | Skeleton runs, tests green, Qdrant up |
| M1 Corpus + naive baseline | 1–4 | A0 ablation report on 60 questions |
| M2 Better retrieval | 5–8 | A1–A3 runs, README table v1 |
| M3 Data path + routing | 9–12 | A4 run, SQL and router accuracy, golden set reaches 150 |
| M4 Quality, safety, eval rigour | 13–16 | A5/A6, calibrated judge (κ), EVAL_REPORT.md |
| M5 Ship | 17–21 | Public demo, streaming UI, tracing, README |
| Buffer | 22–26 | Fix the top failure cases, interview prep (§17) |

---

## M0: Setup (½ day)

**Learn:** uv vs pip/venv, src layout, pydantic-settings, Docker basics.

| # | Step | Done when |
|---|---|---|
| 0.1 ✅ | `git init`, plus a GitHub repo (👤 T0.3) | First commit pushed |
| 0.2 ✅ | `pyproject.toml` via `uv init`: Python 3.11+, dev deps pytest + ruff only | `uv sync` works |
| 0.3 ✅ | `src/cleanair/settings.py` (pydantic-settings), `.env.example` | Settings load from `.env`, and a test proves a missing required key fails loudly |
| 0.4 ✅ | Pipeline config schema: a Pydantic model for `configs/base.yaml`, with every ablation switch (§10.4) stubbed as a field | Loading `base.yaml` gives a typed object |
| 0.5 ✅ | `docker-compose.yml` with Qdrant, plus a health-check script | `docker compose up qdrant` and the health check passes (👤 T0.2) |
| 0.6 ✅ | pre-commit with ruff, and a trivial pytest | `uv run pytest` is green |
| 0.7 ✅ | `docs/DECISIONS.md` updated, CLAUDE.md milestone set to M1 | — |

Step 0.4 comes this early on purpose: if the ablation toggles live in config from day one, no feature ends up hardcoded.

## M1: Corpus + naive baseline (days 1–4)

**Learn:** RAG architecture, chunking trade-offs, embeddings (Guide 16 §1–3).

| # | Step | Done when |
|---|---|---|
| 1.1 ✅ | `data/manifest.csv` with the §5.1 columns. Claude drafts candidate rows, Varad verifies URLs, dates and terms (👤 T1.1, T1.2) | ≥ 40 verified documents |
| 1.2 ✅ | `ingest/download.py`: reads the manifest, writes `sha256`, skips unchanged files | Re-running it is a no-op (test) |
| 1.3 🟡 | `ingest/parse.py`: PyMuPDF with pages and heading detection, OCR fallback when a page has < 50 chars (👤 T1.3) | Parser comparison on 5 hard documents logged in DECISIONS (👤 T1.4) |
| 1.4 | `ingest/clean.py`: strips repeated headers and footers, NFC, keeps Devanagari intact | Tests on synthetic pages |
| 1.5 | `fixed_chunker(size=500, overlap=50)` (the A0 baseline, not 🧠) | Tests: sizes and overlap |
| 1.6 | `ingest/embed.py` and `ingest/index.py`: one embedder (decision: bge-m3 vs e5), collection metadata records the model and its version | Filtered search test passes |
| 1.7 | `retrieval/dense.py` and the `Retriever` protocol / `RetrievedChunk` (§7.2) | Returns chunks for a query |
| 1.8 | LLM access via LiteLLM, plus a minimal grounded synthesis with `[chunk_id]` citations and a not-found path (👤 T0.4) | CLI demo answers one policy question with citations |
| 1.9 | Golden set v0: 60 questions (policy + unanswerable). Claude drafts them, **Varad checks every answer against the source** (👤 T1.5) | `eval/golden/questions.jsonl` with chunk IDs |
| 1.10 | `eval/harness.py` + `metrics.py`: recall@k, MRR, nDCG, uncalibrated faithfulness judge | **A0 report** in `eval/results/` |

Note: M1 faithfulness numbers come from a judge that hasn't been calibrated yet. Label them that way until M4.

## M2: Better retrieval (days 5–8)

**Learn:** structure-aware chunking, BM25, RRF, cross-encoders, filters (Guide 16 §4–5, Guide 17 §5–6, §11).

| # | Step | Done when |
|---|---|---|
| 2.1 | 🧠 Structure-aware chunker: Claude scaffolds the interface and tests on synthetic documents, Varad implements it | Tests green, no chunk over the embedder's max length → **A1 run** |
| 2.2 | `retrieval/sparse.py` (Qdrant sparse or rank-bm25, a logged decision) | Sparse top-50 works |
| 2.3 | 🧠 `retrieval/fusion.py`: RRF (k = 60) and weighted min–max fusion. Claude writes hand-computed tests, Varad implements | RRF test (1,3) → 1/61 + 1/63 passes → **A2 run** |
| 2.4 | `retrieval/rerank.py`: cross-encoder with a relevance threshold and an "insufficient evidence" signal (👤 T2.1) | Threshold chosen from data, not guessed → **A3 run** |
| 2.5 | `retrieval/filters.py`: `is_current`, city, jurisdiction | Test: an out-of-filter chunk is never returned |
| 2.6 | Small-to-big parents, MMR (λ = 0.7), lost-in-the-middle ordering (all behind config flags, measured in A5) | Unit tests |
| 2.7 | README results table v1, plus `docs/LEARNING_LOG.md` with one insight per step (👤 T2.2) | — |

## M3: Data path + routing (days 9–12)

**Learn:** text-to-SQL, SQL safety, structured outputs, routing (Guide 14 §5, §7).

| # | Step | Done when |
|---|---|---|
| 3.1 | Get station data for the 4 cities (CPCB export, OpenAQ, or the Kaggle fallback) (👤 T3.1, T3.2) | Raw files in `data/raw/` |
| 3.2 | `data/schema.sql`, `data/load_stations.py`, `data/quality_report.py` | `aq.duckdb` rebuilds from a script, and the coverage report is generated |
| 3.3 | `docs/DATA_DICTIONARY.md`: units, the city-AQI definition (👤 T3.3), known gaps | — |
| 3.4 | 🧠 `sql/validate.py`: Claude writes the malicious and allowed SQL test list, Varad implements it with sqlglot | 100% of malicious tests rejected |
| 3.5 | `sql/schema_context.py`, `text_to_sql.py` (`SQLPlan`), `execute.py` (read-only, timeout), repair loop (≤ 2), coverage check | Works end-to-end on a fixture DuckDB |
| 3.6 | `routing/router.py`: keyword baseline + LLM structured output. The mixed route uses `asyncio.gather` | Router confusion matrix |
| 3.7 | Golden set grows to 150: data, mixed, Hindi/Hinglish, red-team (👤 T3.4) | Every reference answer verified |
| 3.8 | **A4 run**: SQL execution accuracy, router accuracy | Reported in the README table |

## M4: Answer quality, safety, eval rigour (days 13–16)

**Learn:** hallucination detection, LLM-judge calibration, statistics (Guide 18).

| # | Step | Done when |
|---|---|---|
| 4.1 | 🧠 `generation/citations.py` citation checker: Claude scaffolds it and the tests, Varad implements | Unsupported sentences get removed or flagged |
| 4.2 | `routing/condense.py`: turns a follow-up into a standalone query | Tests on multi-turn fixtures |
| 4.3 | `guardrails/input.py` and `output.py`: injection neutralising, length limits, poisoned-document eval collection | Injection success rate measured |
| 4.4 | Judge calibration: hand-label 80–100 answers (👤 T4.1), judge from a different model family (👤 T4.2), iterate until κ ≥ 0.6 | κ reported |
| 4.5 | Bootstrap CIs, paired bootstrap, per-slice reports in `eval/report.py` (`dataviz` skill for charts) | — |
| 4.6 | **A5 and A6 runs** (A6 needs the second embedder → a new collection) | Final table |
| 4.7 | GitHub Actions smoke gate, 20 questions (👤 T4.3) | A PR fails on a metric regression |
| 4.8 | `docs/EVAL_REPORT.md`: table, CIs, κ, slices, top-10 failure analysis | — |

## M5: Ship (days 17–21)

**Learn:** SSE streaming, observability, deployment (Guide 15).

| # | Step | Done when |
|---|---|---|
| 5.1 | FastAPI: `/chat` (SSE events per §11.1), `/chat/sync`, `/feedback`, `/sources/{id}`, `/health`, `/admin/reindex` | Integration test: `/chat/sync` returns a valid `Answer` |
| 5.2 | Langfuse tracing: spans per stage, tokens, cost (👤 T5.1) | A trace is visible for one request |
| 5.3 | Next.js UI in `web/`: streaming chat, sources panel, SQL/data panel, 👍/👎, disclaimer (`frontend-design` skill) | Works locally against the API |
| 5.4 | Rate limit, input/output caps, daily budget alarm (👤 T5.4) | — |
| 5.5 | Docker images, `docker compose up` brings up everything | One-command local run |
| 5.6 | Deploy API, web and Qdrant (👤 T5.2, T5.3) | Public URL, p95 TTFT measured |
| 5.7 | Light load test (20 concurrent requests) | p95 recorded |
| 5.8 | README per §15: pitch, demo GIF (👤 T5.5), ablation table, diagram, limitations | Resume bullet filled with real numbers |

## Buffer / stretch

The buffer goes first to the top failure cases from 4.8, then to the §17 interview answers. Stretch goals (§13):
a Hindi cross-lingual study, a fine-tuned embedder, agentic mode, a camera-PM link to the thesis, and a weekly digest.
These are parked until after placements unless the buffer is unused.

## Known risks to watch

- **Reranker latency on CPU** could break the 2.5 s p95 time-to-first-token target. Measure it in 2.4, and decide on hosting resources (or a smaller reranker) before 5.6.
- **Hosting RAM:** bge-m3 and the reranker together need several GB. The free tiers probably won't fit, so decide in 5.6.
- **Getting CPCB data** may be slow or manual, so start 👤 T3.1 during M1, not in M3.
