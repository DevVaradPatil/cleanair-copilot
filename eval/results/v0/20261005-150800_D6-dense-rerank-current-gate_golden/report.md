# D6-dense-rerank-current-gate on golden

63 questions. 95% bootstrap CIs.

| Metric | Value |
|---|---|
| recall@1 | 0.542 [0.40, 0.68] (n=48) |
| recall@3 | 0.833 [0.73, 0.93] (n=48) |
| recall@5 | 0.865 [0.77, 0.94] (n=48) |
| recall@10 | 0.885 [0.80, 0.96] (n=48) |
| mrr | 0.714 [0.61, 0.81] (n=48) |
| ndcg@5 | 0.728 [0.63, 0.81] (n=48) |
| faithfulness | — |
| must_include_ok | — |
| false_not_found | — |
| not_found_correct | — |
| abstain_unanswerable | 0.733 [0.47, 0.93] (n=15) |
| abstain_answerable | 0.021 [0.00, 0.06] (n=48) |

| Category | n | recall@5 | MRR |
|---|---|---|---|
| policy_fact | 40 | 0.950 [0.88, 1.00] (n=40) | 0.759 [0.66, 0.85] (n=40) |
| policy_multi | 8 | 0.438 [0.25, 0.62] (n=8) | 0.490 [0.21, 0.79] (n=8) |
| unanswerable | 15 | — | — |

Retrieval latency: p50 0.591 s, p95 0.627 s
