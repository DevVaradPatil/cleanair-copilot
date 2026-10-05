# A0-naive on smoke

6 questions. 95% bootstrap CIs.

| Metric | Value |
|---|---|
| recall@1 | 0.333 [0.00, 0.67] (n=6) |
| recall@3 | 0.333 [0.00, 0.67] (n=6) |
| recall@5 | 0.333 [0.00, 0.67] (n=6) |
| recall@10 | 0.500 [0.17, 0.83] (n=6) |
| mrr | 0.361 [0.03, 0.72] (n=6) |
| ndcg@5 | 0.333 [0.00, 0.67] (n=6) |
| faithfulness | 1.000 [1.00, 1.00] (n=6) |
| must_include_ok | 0.333 [0.00, 0.67] (n=6) |
| false_not_found | 0.000 [0.00, 0.00] (n=6) |
| not_found_correct | — |
| abstain_unanswerable | — |
| abstain_answerable | 0.000 [0.00, 0.00] (n=6) |

| Category | n | recall@5 | MRR |
|---|---|---|---|
| policy_fact | 6 | 0.333 [0.00, 0.67] (n=6) | 0.361 [0.03, 0.72] (n=6) |

Retrieval latency: p50 0.089 s, p95 0.771 s
Generation: {'gemini/gemini-3-flash-preview': 6}, p50 10.489999999999998 s, total $0.0382
Faithfulness judge is UNCALIBRATED (calibration is M4).
