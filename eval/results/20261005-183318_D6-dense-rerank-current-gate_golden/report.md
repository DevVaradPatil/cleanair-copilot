# D6-dense-rerank-current-gate on golden

150 questions. 95% bootstrap CIs.

| Metric | Value |
|---|---|
| recall@1 | 0.337 [0.25, 0.43] (n=95) |
| recall@3 | 0.553 [0.46, 0.65] (n=95) |
| recall@5 | 0.574 [0.48, 0.67] (n=95) |
| recall@10 | 0.632 [0.54, 0.73] (n=95) |
| mrr | 0.474 [0.39, 0.56] (n=95) |
| ndcg@5 | 0.476 [0.39, 0.56] (n=95) |
| faithfulness | — |
| must_include_ok | — |
| false_not_found | — |
| not_found_correct | — |
| abstain_unanswerable | 0.800 [0.60, 0.95] (n=20) |
| abstain_answerable | 0.168 [0.09, 0.25] (n=95) |
| sql_execution_accuracy | — |
| route_accuracy | — |

| Category | n | recall@5 | MRR |
|---|---|---|---|
| policy_fact | 40 | 0.950 [0.88, 1.00] (n=40) | 0.759 [0.66, 0.85] (n=40) |
| policy_multi | 15 | 0.433 [0.27, 0.63] (n=15) | 0.439 [0.24, 0.66] (n=15) |
| unanswerable | 16 | — | — |
| data | 29 | — | — |
| mixed | 20 | 0.200 [0.05, 0.40] (n=20) | 0.172 [0.05, 0.33] (n=20) |
| hindi | 20 | 0.333 [0.13, 0.57] (n=15) | 0.272 [0.09, 0.48] (n=15) |
| redteam | 10 | 0.200 [0.00, 0.60] (n=5) | 0.122 [0.00, 0.32] (n=5) |

Retrieval latency: p50 0.743 s, p95 0.779 s
