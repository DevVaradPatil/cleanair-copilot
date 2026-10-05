# D2-dense-rerank on golden

150 questions. 95% bootstrap CIs.

| Metric | Value |
|---|---|
| recall@1 | 0.332 [0.24, 0.42] (n=95) |
| recall@3 | 0.510 [0.42, 0.61] (n=95) |
| recall@5 | 0.542 [0.45, 0.64] (n=95) |
| recall@10 | 0.684 [0.59, 0.77] (n=95) |
| mrr | 0.467 [0.38, 0.55] (n=95) |
| ndcg@5 | 0.455 [0.37, 0.54] (n=95) |
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
| policy_fact | 40 | 0.825 [0.70, 0.93] (n=40) | 0.702 [0.59, 0.81] (n=40) |
| policy_multi | 15 | 0.333 [0.13, 0.53] (n=15) | 0.377 [0.18, 0.59] (n=15) |
| unanswerable | 16 | — | — |
| data | 29 | — | — |
| mixed | 20 | 0.250 [0.10, 0.45] (n=20) | 0.197 [0.07, 0.35] (n=20) |
| hindi | 20 | 0.500 [0.27, 0.73] (n=15) | 0.398 [0.21, 0.60] (n=15) |
| redteam | 10 | 0.200 [0.00, 0.60] (n=5) | 0.151 [0.02, 0.33] (n=5) |

Retrieval latency: p50 0.576 s, p95 0.802 s
