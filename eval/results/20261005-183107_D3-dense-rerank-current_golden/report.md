# D3-dense-rerank-current on golden

150 questions. 95% bootstrap CIs.

| Metric | Value |
|---|---|
| recall@1 | 0.358 [0.26, 0.45] (n=95) |
| recall@3 | 0.611 [0.52, 0.71] (n=95) |
| recall@5 | 0.647 [0.56, 0.74] (n=95) |
| recall@10 | 0.721 [0.64, 0.81] (n=95) |
| mrr | 0.522 [0.44, 0.60] (n=95) |
| ndcg@5 | 0.528 [0.45, 0.61] (n=95) |
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
| policy_fact | 40 | 0.950 [0.88, 1.00] (n=40) | 0.759 [0.66, 0.85] (n=40) |
| policy_multi | 15 | 0.500 [0.33, 0.67] (n=15) | 0.482 [0.29, 0.68] (n=15) |
| unanswerable | 16 | — | — |
| data | 29 | — | — |
| mixed | 20 | 0.250 [0.10, 0.45] (n=20) | 0.197 [0.07, 0.35] (n=20) |
| hindi | 20 | 0.600 [0.37, 0.80] (n=15) | 0.463 [0.27, 0.66] (n=15) |
| redteam | 10 | 0.400 [0.00, 0.80] (n=5) | 0.222 [0.02, 0.42] (n=5) |

Retrieval latency: p50 0.745 s, p95 0.827 s
