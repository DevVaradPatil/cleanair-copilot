# A2-hybrid on golden

150 questions. 95% bootstrap CIs.

| Metric | Value |
|---|---|
| recall@1 | 0.242 [0.16, 0.34] (n=95) |
| recall@3 | 0.405 [0.32, 0.50] (n=95) |
| recall@5 | 0.479 [0.38, 0.58] (n=95) |
| recall@10 | 0.532 [0.44, 0.63] (n=95) |
| mrr | 0.358 [0.28, 0.45] (n=95) |
| ndcg@5 | 0.367 [0.29, 0.45] (n=95) |
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
| policy_fact | 40 | 0.725 [0.57, 0.85] (n=40) | 0.531 [0.40, 0.66] (n=40) |
| policy_multi | 15 | 0.400 [0.20, 0.63] (n=15) | 0.319 [0.13, 0.52] (n=15) |
| unanswerable | 16 | — | — |
| data | 29 | — | — |
| mixed | 20 | 0.200 [0.05, 0.40] (n=20) | 0.118 [0.03, 0.25] (n=20) |
| hindi | 20 | 0.233 [0.07, 0.43] (n=15) | 0.207 [0.04, 0.40] (n=15) |
| redteam | 10 | 0.600 [0.20, 1.00] (n=5) | 0.500 [0.10, 0.90] (n=5) |

Retrieval latency: p50 0.065 s, p95 0.092 s
