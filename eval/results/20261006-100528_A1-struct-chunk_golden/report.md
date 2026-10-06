# A1-struct-chunk on golden

150 questions. 95% bootstrap CIs.

| Metric | Value |
|---|---|
| recall@1 | 0.216 [0.14, 0.31] (n=95) |
| recall@3 | 0.337 [0.25, 0.43] (n=95) |
| recall@5 | 0.421 [0.33, 0.52] (n=95) |
| recall@10 | 0.500 [0.41, 0.60] (n=95) |
| mrr | 0.311 [0.23, 0.39] (n=95) |
| ndcg@5 | 0.318 [0.24, 0.40] (n=95) |
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
| policy_fact | 40 | 0.600 [0.45, 0.75] (n=40) | 0.470 [0.34, 0.61] (n=40) |
| policy_multi | 15 | 0.333 [0.13, 0.53] (n=15) | 0.241 [0.10, 0.41] (n=15) |
| unanswerable | 16 | — | — |
| data | 29 | — | — |
| mixed | 20 | 0.200 [0.05, 0.40] (n=20) | 0.102 [0.01, 0.23] (n=20) |
| hindi | 20 | 0.267 [0.07, 0.47] (n=15) | 0.222 [0.07, 0.41] (n=15) |
| redteam | 10 | 0.600 [0.20, 1.00] (n=5) | 0.350 [0.05, 0.70] (n=5) |

Retrieval latency: p50 0.044 s, p95 0.063 s
