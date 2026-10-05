# D2-dense-rerank on golden

63 questions. 95% bootstrap CIs.

| Metric | Value |
|---|---|
| recall@1 | 0.510 [0.36, 0.65] (n=48) |
| recall@3 | 0.698 [0.57, 0.82] (n=48) |
| recall@5 | 0.740 [0.61, 0.85] (n=48) |
| recall@10 | 0.844 [0.75, 0.93] (n=48) |
| mrr | 0.649 [0.54, 0.76] (n=48) |
| ndcg@5 | 0.642 [0.53, 0.75] (n=48) |
| faithfulness | — |
| must_include_ok | — |
| false_not_found | — |
| not_found_correct | — |
| abstain_unanswerable | 0.000 [0.00, 0.00] (n=15) |
| abstain_answerable | 0.000 [0.00, 0.00] (n=48) |

| Category | n | recall@5 | MRR |
|---|---|---|---|
| policy_fact | 40 | 0.825 [0.70, 0.93] (n=40) | 0.702 [0.59, 0.81] (n=40) |
| policy_multi | 8 | 0.312 [0.06, 0.56] (n=8) | 0.382 [0.13, 0.67] (n=8) |
| unanswerable | 15 | — | — |

Retrieval latency: p50 0.553 s, p95 0.578 s
