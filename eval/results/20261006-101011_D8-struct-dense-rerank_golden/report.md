# D8-struct-dense-rerank on golden

150 questions. 95% bootstrap CIs.

| Metric | Value |
|---|---|
| recall@1 | 0.268 [0.18, 0.36] (n=95) |
| recall@3 | 0.453 [0.36, 0.55] (n=95) |
| recall@5 | 0.584 [0.49, 0.68] (n=95) |
| recall@10 | 0.626 [0.54, 0.73] (n=95) |
| mrr | 0.412 [0.33, 0.50] (n=95) |
| ndcg@5 | 0.434 [0.36, 0.52] (n=95) |
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
| policy_fact | 40 | 0.825 [0.70, 0.93] (n=40) | 0.617 [0.50, 0.73] (n=40) |
| policy_multi | 15 | 0.533 [0.37, 0.70] (n=15) | 0.416 [0.23, 0.60] (n=15) |
| unanswerable | 16 | — | — |
| data | 29 | — | — |
| mixed | 20 | 0.250 [0.05, 0.45] (n=20) | 0.179 [0.03, 0.36] (n=20) |
| hindi | 20 | 0.433 [0.20, 0.67] (n=15) | 0.237 [0.09, 0.41] (n=15) |
| redteam | 10 | 0.600 [0.20, 1.00] (n=5) | 0.212 [0.08, 0.37] (n=5) |

Retrieval latency: p50 0.473 s, p95 0.515 s
