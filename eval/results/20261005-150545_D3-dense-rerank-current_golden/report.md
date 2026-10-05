# D3-dense-rerank-current on golden

63 questions. 95% bootstrap CIs.

| Metric | Value |
|---|---|
| recall@1 | 0.542 [0.40, 0.68] (n=48) |
| recall@3 | 0.844 [0.74, 0.93] (n=48) |
| recall@5 | 0.885 [0.80, 0.96] (n=48) |
| recall@10 | 0.906 [0.83, 0.97] (n=48) |
| mrr | 0.724 [0.63, 0.82] (n=48) |
| ndcg@5 | 0.742 [0.65, 0.82] (n=48) |
| faithfulness | — |
| must_include_ok | — |
| false_not_found | — |
| not_found_correct | — |
| abstain_unanswerable | 0.000 [0.00, 0.00] (n=15) |
| abstain_answerable | 0.000 [0.00, 0.00] (n=48) |

| Category | n | recall@5 | MRR |
|---|---|---|---|
| policy_fact | 40 | 0.950 [0.88, 1.00] (n=40) | 0.759 [0.66, 0.85] (n=40) |
| policy_multi | 8 | 0.562 [0.38, 0.75] (n=8) | 0.552 [0.30, 0.81] (n=8) |
| unanswerable | 15 | — | — |

Retrieval latency: p50 0.581 s, p95 0.622 s
