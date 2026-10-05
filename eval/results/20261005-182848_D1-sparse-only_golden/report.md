# D1-sparse-only on golden

150 questions. 95% bootstrap CIs.

| Metric | Value |
|---|---|
| recall@1 | 0.274 [0.19, 0.36] (n=95) |
| recall@3 | 0.421 [0.33, 0.52] (n=95) |
| recall@5 | 0.495 [0.40, 0.59] (n=95) |
| recall@10 | 0.542 [0.44, 0.64] (n=95) |
| mrr | 0.372 [0.29, 0.46] (n=95) |
| ndcg@5 | 0.389 [0.31, 0.48] (n=95) |
| faithfulness | — |
| must_include_ok | — |
| false_not_found | — |
| not_found_correct | — |
| abstain_unanswerable | 0.000 [0.00, 0.00] (n=20) |
| abstain_answerable | 0.000 [0.00, 0.00] (n=95) |
| sql_execution_accuracy | — |
| route_accuracy | — |

| Category | n | recall@5 | MRR |
|---|---|---|---|
| policy_fact | 40 | 0.850 [0.72, 0.95] (n=40) | 0.653 [0.53, 0.77] (n=40) |
| policy_multi | 15 | 0.200 [0.07, 0.37] (n=15) | 0.209 [0.06, 0.39] (n=15) |
| unanswerable | 16 | — | — |
| data | 29 | — | — |
| mixed | 20 | 0.250 [0.10, 0.45] (n=20) | 0.106 [0.02, 0.23] (n=20) |
| hindi | 20 | 0.267 [0.07, 0.53] (n=15) | 0.200 [0.04, 0.39] (n=15) |
| redteam | 10 | 0.200 [0.00, 0.60] (n=5) | 0.200 [0.00, 0.60] (n=5) |

Retrieval latency: p50 0.032 s, p95 0.051 s
