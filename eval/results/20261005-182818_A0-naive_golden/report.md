# A0-naive on golden

150 questions. 95% bootstrap CIs.

| Metric | Value |
|---|---|
| recall@1 | 0.216 [0.14, 0.30] (n=95) |
| recall@3 | 0.400 [0.31, 0.49] (n=95) |
| recall@5 | 0.458 [0.36, 0.56] (n=95) |
| recall@10 | 0.526 [0.43, 0.63] (n=95) |
| mrr | 0.331 [0.25, 0.41] (n=95) |
| ndcg@5 | 0.346 [0.27, 0.43] (n=95) |
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
| policy_fact | 40 | 0.775 [0.65, 0.90] (n=40) | 0.565 [0.44, 0.68] (n=40) |
| policy_multi | 15 | 0.267 [0.10, 0.47] (n=15) | 0.221 [0.08, 0.41] (n=15) |
| unanswerable | 16 | — | — |
| data | 29 | — | — |
| mixed | 20 | 0.150 [0.00, 0.35] (n=20) | 0.060 [0.00, 0.14] (n=20) |
| hindi | 20 | 0.367 [0.13, 0.60] (n=15) | 0.288 [0.11, 0.49] (n=15) |
| redteam | 10 | 0.000 [0.00, 0.00] (n=5) | 0.000 [0.00, 0.00] (n=5) |

Retrieval latency: p50 0.037 s, p95 0.065 s
