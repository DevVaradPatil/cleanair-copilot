# A0-naive on golden

63 questions. 95% bootstrap CIs.

| Metric | Value |
|---|---|
| recall@1 | 0.344 [0.22, 0.48] (n=48) |
| recall@3 | 0.635 [0.50, 0.76] (n=48) |
| recall@5 | 0.698 [0.57, 0.82] (n=48) |
| recall@10 | 0.771 [0.66, 0.89] (n=48) |
| mrr | 0.509 [0.40, 0.62] (n=48) |
| ndcg@5 | 0.540 [0.43, 0.65] (n=48) |
| faithfulness | — |
| must_include_ok | — |
| false_not_found | — |
| not_found_correct | — |
| abstain_unanswerable | 0.000 [0.00, 0.00] (n=15) |
| abstain_answerable | 0.000 [0.00, 0.00] (n=48) |

| Category | n | recall@5 | MRR |
|---|---|---|---|
| policy_fact | 40 | 0.775 [0.65, 0.90] (n=40) | 0.565 [0.44, 0.68] (n=40) |
| policy_multi | 8 | 0.312 [0.06, 0.62] (n=8) | 0.229 [0.04, 0.48] (n=8) |
| unanswerable | 15 | — | — |

Retrieval latency: p50 0.019 s, p95 0.041 s
