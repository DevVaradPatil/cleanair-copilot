# Learning log

One insight per step (SPEC §13 M2): what improved, what didn't, why. **The "Insight" lines are Varad's to write**
(TODO T2.2); the "Measured" lines are facts from the eval runs in `eval/results/`, written by Claude as prompts.

## M1 — A0 baseline (2026-10-05)

**Measured:** A0 recall@5 0.698, MRR 0.509, multi-fact recall@5 0.312 (63 questions).
The PM2.5 24-hour NAAQS row was cut at a chunk boundary (`…PM2.5 µg/m3|24 Hour` / `s|60|60|60|` in the next
chunk), so the generator correctly answered "not found" although the value is in the corpus.
**Prompt:** what does this say about fixed-size chunking for tables, and what should the structure-aware chunker
guarantee? (Guide 16 §2)
**Insight:** _…_

## 2.2 — Sparse retrieval (D1)

**Measured:** sparse-only recall@5 0.750 vs dense 0.698; paired Δ +0.05 [−0.04, +0.16], not significant.
Sparse is worse on multi-fact (0.25 vs 0.31). BGE-M3's sparse head weighs exact tokens like "2.5", "60", "NAAQS".
**Prompt:** when would you expect lexical to beat semantic retrieval here, and why does that motivate hybrid?
**Insight:** _…_

## 2.4 — Cross-encoder rerank and threshold (D2, D4, D6)

**Measured:** rerank: recall@5 +0.04 (n.s.) but MRR +0.14 [+0.06, +0.22]; adds ~0.55 s p95 on the 4060.
Best-score distribution: answerable median 0.987, unanswerable median 0.518, max 0.961. Threshold 0.637
(≥ 95% answerable kept) abstains on 73% of unanswerable and 2% of answerable questions.
Hypothesis "per-chunk filtering hurts multi-fact questions" was **wrong** at top-5 (gate = filter there);
it only showed at recall@10 (0.885 vs 0.865).
**Prompt:** why does a cross-encoder improve ordering more than recall@5? Why choose the 95%-keep threshold
over the balanced-accuracy optimum (0.90)? How would you avoid tuning and testing on the same questions? (§17 hook)
**Insight:** _…_

## 2.5 — Current-document filter (D3)

**Measured:** recall@5 +0.15 [+0.06, +0.25]; 6 of the 8 wins are GRAP questions where older GRAP orders that
repeat the schedule's text outranked the current schedule.
**Prompt:** is this a real gain or an artefact of the golden set (GRAP-heavy, current-doc-only relevance)?
**Insight:** _…_

## 2.6 — MMR, lost-in-the-middle, small-to-big (D5)

**Measured:** MMR λ=0.7 lowered MRR slightly (0.714 → 0.702), no recall change; ordering doesn't affect
retrieval metrics (it only changes the prompt); small-to-big is a no-op until the structure chunker creates parents.
**Prompt:** why might MMR not help when k=5 and near-duplicates are rare? What would you measure instead?
**Insight:** _…_
