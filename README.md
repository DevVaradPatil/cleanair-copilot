# Clean Air Copilot (India)

A bilingual RAG + text-to-SQL assistant for Indian air-quality **policy** (NCAP, GRAP, NAAQS, CAQM Act, city
action plans) and **CPCB monitoring data**, with clause-level citations and a measured evaluation suite.
Work in progress — see [SPEC.md](SPEC.md) and [plan.md](plan.md). Full README comes in M5.

## Results so far (retrieval, golden set v0)

63 questions (40 single-fact, 8 multi-fact, 15 unanswerable) over 47 official documents, 1,874 fixed 500-token
chunks, BGE-M3 embeddings, Qdrant. Relevance = the chunk contains the verified evidence quote **from the current
document**. 95% bootstrap CIs over questions.

| Config | What changes | Recall@5 | MRR | Multi-fact R@5 | Abstain on unanswerable | Abstain on answerable |
|---|---|---|---|---|---|---|
| **A0** naive | fixed chunks, dense top-5 | 0.698 [0.57–0.82] | 0.509 [0.40–0.62] | 0.312 | — | — |
| D1 | sparse (BGE-M3 lexical) instead of dense | 0.750 [0.62–0.86] | 0.565 [0.44–0.68] | 0.250 | — | — |
| D2 | A0 + cross-encoder rerank (top 30 → 5) | 0.740 [0.61–0.85] | 0.649 [0.54–0.76] | 0.312 | — | — |
| D3 | D2 + `is_current` filter | **0.885** [0.80–0.96] | **0.724** [0.63–0.82] | 0.562 | — | — |
| D6 | D3 + rerank gate at 0.637 | 0.865 [0.77–0.94] | 0.714 [0.61–0.81] | 0.438 | 0.733 | 0.021 |
| A1–A3 | structure-aware chunks, hybrid + RRF | *pending the 🧠 chunker and fusion* | | | | |

Paired over the same questions: the reranker's gain is in **ranking** (MRR +0.14 [+0.06, +0.22]) rather than
recall@5 (+0.04, not significant); the current-document filter adds recall@5 +0.15 [+0.06, +0.25], mostly on GRAP
questions where superseded orders repeat the current schedule's text. Sparse vs dense: +0.05, not significant.
D-rows are diagnostics outside the SPEC ablation; the threshold was tuned on the same questions (optimistic).
Full table incl. D4/D5: `uv run python -m eval.report --runs eval/results/*_golden`. Generation metrics
(faithfulness, not-found accuracy) wait for a paid Gemini tier.

## Run it

```bash
docker compose up -d qdrant
uv run python -m cleanair.ask "What AQI triggers GRAP Stage III?" --config configs/ablations/diag_threshold_gate.yaml
uv run python -m eval.harness --config configs/ablations/naive.yaml --set golden
```
