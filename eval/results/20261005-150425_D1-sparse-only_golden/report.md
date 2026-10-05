# D1-sparse-only on golden

63 questions. 95% bootstrap CIs.

| Metric | Value |
|---|---|
| recall@1 | 0.438 [0.29, 0.58] (n=48) |
| recall@3 | 0.646 [0.50, 0.77] (n=48) |
| recall@5 | 0.750 [0.62, 0.86] (n=48) |
| recall@10 | 0.792 [0.68, 0.90] (n=48) |
| mrr | 0.565 [0.44, 0.68] (n=48) |
| ndcg@5 | 0.600 [0.48, 0.71] (n=48) |
| faithfulness | — |
| must_include_ok | — |
| false_not_found | — |
| not_found_correct | — |
| abstain_unanswerable | 0.000 [0.00, 0.00] (n=15) |
| abstain_answerable | 0.000 [0.00, 0.00] (n=48) |

| Category | n | recall@5 | MRR |
|---|---|---|---|
| policy_fact | 40 | 0.850 [0.72, 0.95] (n=40) | 0.653 [0.53, 0.77] (n=40) |
| policy_multi | 8 | 0.250 [0.06, 0.50] (n=8) | 0.125 [0.03, 0.25] (n=8) |
| unanswerable | 15 | — | — |

Retrieval latency: p50 0.02 s, p95 0.044 s
