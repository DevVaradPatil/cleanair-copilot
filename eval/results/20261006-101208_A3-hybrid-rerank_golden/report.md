# A3-hybrid-rerank on golden

150 questions. 95% bootstrap CIs.

| Metric | Value |
|---|---|
| recall@1 | 0.300 [0.22, 0.39] (n=95) |
| recall@3 | 0.500 [0.41, 0.60] (n=95) |
| recall@5 | 0.621 [0.53, 0.71] (n=95) |
| recall@10 | 0.695 [0.61, 0.78] (n=95) |
| mrr | 0.451 [0.37, 0.53] (n=95) |
| ndcg@5 | 0.471 [0.39, 0.55] (n=95) |
| faithfulness | — |
| must_include_ok | — |
| false_not_found | — |
| not_found_correct | — |
| abstain_unanswerable | 0.450 [0.25, 0.65] (n=20) |
| abstain_answerable | 0.042 [0.01, 0.08] (n=95) |
| sql_execution_accuracy | — |
| route_accuracy | — |

| Category | n | recall@5 | MRR |
|---|---|---|---|
| policy_fact | 40 | 0.850 [0.72, 0.95] (n=40) | 0.651 [0.53, 0.76] (n=40) |
| policy_multi | 15 | 0.600 [0.40, 0.80] (n=15) | 0.461 [0.29, 0.64] (n=15) |
| unanswerable | 16 | — | — |
| data | 29 | — | — |
| mixed | 20 | 0.350 [0.15, 0.55] (n=20) | 0.260 [0.09, 0.44] (n=20) |
| hindi | 20 | 0.400 [0.13, 0.67] (n=15) | 0.236 [0.08, 0.40] (n=15) |
| redteam | 10 | 0.600 [0.20, 1.00] (n=5) | 0.237 [0.09, 0.39] (n=5) |

Retrieval latency: p50 0.502 s, p95 0.544 s
