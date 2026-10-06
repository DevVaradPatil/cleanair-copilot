# 🧠 Brain notes — the parts to understand deeply

Claude wrote the code; this file is for understanding it well enough to rebuild it and defend it in an interview.
Each section: the concept → the options → walkthrough of our code → a worked example → pitfalls → interview Q&A.
Measured numbers come from `eval/results/` (golden set v1, 150 questions) — see README for the full table.

---

## 1. Hybrid fusion: RRF and weighted fusion — `src/cleanair/retrieval/fusion.py`

### The problem
Hybrid retrieval runs two searches for the same query: **dense** (semantic: BGE-M3 embedding, cosine similarity)
and **sparse** (lexical: BGE-M3's learned term weights, a dot product). Each returns a ranked list with scores.
You can't add the scores: cosine sits around 0.3–0.8, sparse dot products around 0–0.5, and both distributions
shift from query to query. "Dense 0.62 + sparse 0.11" mixes two different units.

### Option A — Reciprocal Rank Fusion (RRF), what A2/A3 use
Throw the scores away and use only the **rank** of each chunk in each list:

    score(chunk) = Σ over lists  1 / (k + rank_in_that_list)        (rank starts at 1; k = 60)

A chunk missing from a list adds nothing for that list. Sort by the summed score.

**Why k = 60?** k damps the head of each list. With k = 60, rank 1 → 1/61 = 0.0164, rank 2 → 1/62 = 0.0161 — only
~1.6% apart — so *agreement between the lists* dominates: a chunk that is #3 in both lists (2/63 = 0.0317) beats
a chunk that is #1 in one and absent from the other (1/61 = 0.0164). Small k (say 1) makes rank 1 worth far more
(1/2 vs 1/3) — it trusts each list's top hit. 60 comes from the original paper (Cormack et al., 2009) and works
well without tuning; that's RRF's main selling point.

### Option B — weighted score fusion (min–max, α)
Per query, rescale each list's scores to [0, 1]: `norm = (s − min) / (max − min)`, then
`fused = α · dense_norm + (1 − α) · sparse_norm` (0 for a list the chunk is missing from). It keeps *how much*
better the top hit is (RRF only knows it's first), but needs α tuned, and min–max is fragile: one outlier score
squashes everything else toward 0, and a list of one hit (or all ties) has max = min — we define that as 1.0.

### Walkthrough of our code
- `rrf()` builds, per input list, a dict `{chunk_id: 1/(k+rank)}` and hands it to `_merge`.
- `weighted()` builds `{chunk_id: α·minmax}` for dense and `{chunk_id: (1−α)·minmax}` for sparse, same `_merge`.
- `_merge()` walks the lists in order; the first time a chunk_id is seen it **copies** the chunk (never mutate the
  caller's objects) into an insertion-ordered dict; it sums the per-list scores and carries over `score_dense`,
  `score_sparse` and the dense `vector` (MMR needs it) from whichever list had them. Python's `sorted()` is stable,
  so equal scores keep first-appearance order — deterministic ties, which matters for reproducible evals.

### Worked example (it's a unit test: `tests/test_fusion.py`)
Dense ranks `[a, b, c]`, sparse ranks `[c, x, a]`, k = 60:
`a = 1/61 + 1/63 = 0.03227`, `c = 1/63 + 1/61 = 0.03227` (tie → a first, it appeared first),
`b = 1/62 = 0.01613`, `x = 1/62 = 0.01613`. Final order: a, c, b, x.

### Pitfalls
- Fusing lists of very different length/quality: RRF still gives a junk-only list's rank-1 hit 1/61. Retrieve
  enough (we take top 50 from each) and let the reranker clean up.
- Forgetting that weighted fusion needs per-*query* normalisation, not global.
- Mutating shared objects during the merge (we copy).

### Interview Q&A
- *RRF vs weighted — which did you choose and why?* (SPEC §17 hook) RRF for A2/A3: no tuning, robust to score
  scales, standard. Weighted is implemented for the comparison; α would need a dev set to tune.
- *What does k do?* Controls how much the head of each list dominates; large k rewards agreement across lists.
- *Why not just add cosine and BM25?* Different units and per-query distributions; the sum is dominated by
  whichever has the larger spread.

---

## 2. SQL validator — `src/cleanair/sql/validate.py`

### The problem
The LLM writes SQL from a user's question. The user (or a prompt injection) can steer it towards
`DROP TABLE`, `COPY … TO`, reading files with `read_csv('C:/…/.env')`, or `ATTACH`ing another database.
We need a guarantee we can *state*: "only a single read-only SELECT over these tables and columns runs."

### Allow-list, not deny-list
A deny-list ("reject if the text contains DROP/DELETE/…") always misses something: `dRoP`, comments
(`SELECT 1 -- x\n; DROP …`), a dangerous *function* inside a harmless-looking SELECT (`read_text(...)`), a file
used as a table (`FROM 'secrets.csv'`), engine statements we didn't think of (`EXPORT DATABASE`, `CALL …`). So we
**parse** the SQL into a syntax tree with sqlglot (DuckDB dialect) and accept it only if *every* part is something
we explicitly allow. Anything sqlglot can't parse is rejected too.

### The checks, in order (`validate()`)
1. **Parse** (`_parse_single`): `sqlglot.parse(sql, read="duckdb")`. Parse error → reject. Exactly **one**
   statement — this is what kills `SELECT 1; DROP TABLE x` and the comment trick.
2. **Root must be a query**: `isinstance(tree, exp.Query)` — `Select`, `Union`/`Except`/`Intersect`; a
   `WITH … SELECT` is a `Select`. `DROP`, `INSERT`, `COPY`, `ATTACH`, `PRAGMA`, `SET`, `INSTALL`, and whatever
   sqlglot falls back to as a generic `Command` (`LOAD`, `CALL`) all fail here.
3. **Tables** (`_check_tables`): every `exp.Table` node must be (a) a plain identifier — not a string literal
   (`FROM 'file.csv'`) or a function (`FROM read_csv(...)`, `FROM duckdb_settings()`); (b) not schema-qualified
   (`information_schema.tables`); (c) either in the allow-list or a CTE name defined in this same query.
4. **Functions** (`_check_functions`): no function anywhere in the tree whose name is in `FORBIDDEN_FUNCTIONS`
   (file/network readers, `getenv`, settings). This catches them even inside sub-queries and expressions.
5. **Columns** (`_check_columns`): every column must belong to a referenced table, or be an alias defined in the
   query (`SELECT count(*) AS n … ORDER BY n`). Unknown columns get a precise message — the repair loop feeds it
   back to the LLM, which then fixes its own SQL.
6. **LIMIT** (`_apply_limit`): add `LIMIT 1000` if missing; cap a larger literal; reject a non-literal LIMIT.
   Then re-render with `tree.sql(dialect="duckdb")` — what runs is *our* rendering of the checked tree.

### Defence in depth
Layer 2 (`sql/execute.py`) doesn't trust layer 1: read-only connection (writes fail in the engine),
`enable_external_access = false` (DuckDB itself refuses file/network access), a timeout via
`connection.interrupt()`, and a row cap. Each layer is tested on its own (`test_sql_execute.py` passes SQL that
the validator would reject straight to the executor and shows it still can't do damage).

### Worked example
`SELECT city FROM city_aqi_daily WHERE city IN (SELECT * FROM read_csv('x.csv'))` — one statement ✓, a SELECT ✓,
but the inner `FROM read_csv(...)` is a Table whose `this` is a function, not an identifier → rejected with
`'READ_CSV('x.csv')' is not allowed in FROM`. Every one of the 28 attack strings in `tests/test_sql_validate.py`
is rejected *for the intended reason* (we printed them), and all 55 golden reference queries are accepted
(`test_every_golden_reference_query_is_accepted` — a validator that blocks correct answers is also broken).

### Pitfalls
- Over-strictness is a real failure mode: it silently turns answerable data questions into "couldn't answer".
  That's why the golden reference SQL is in the test suite.
- Column check is against the *union* of referenced tables' columns, not per qualifier (`ponytail:` comment in
  the code) — it stops invented columns; a truly ambiguous reference still fails in DuckDB (read-only).
- Dialect matters: parse with the dialect you execute (DuckDB), or valid queries fail to parse.

### Interview Q&A
- *How do you stop text-to-SQL from being dangerous?* (SPEC §17 hook) Two independent layers: an AST allow-list
  validator (one SELECT, allowed tables/columns, no file/env functions, LIMIT) and an engine-level sandbox
  (read-only, external access off, timeout, row cap). Each tested alone; 28/28 attacks rejected.
- *Why parse instead of regex?* SQL is a language: comments, quoting, nesting and dialect features defeat regexes;
  the parser sees the same structure the database will.
- *What if the validator has a bug?* The executor still can't write, read files or run forever.

---

## 3. Structure-aware chunker — `src/cleanair/ingest/chunk.py`

### The problem
Retrieval returns *chunks*, so the chunk is the unit of evidence. A fixed 500-token window (A0) cuts wherever the
count runs out — mid-clause, mid-table-row. We saw the canonical failure: the NAAQS row
`|PM2.5 µg/m3|24 Hours|60|60|` was split across two chunks, so neither chunk "contained" the 24-hour limit and the
generator correctly said "not found". Regulations are written in a hierarchy (Act › Chapter › Section › clause;
GRAP › Stage III › Actions), so cut along that hierarchy instead.

### The algorithm (`structure_chunker`)
1. **Sections from headings** (`_sections`). The parser labels blocks `heading/text/table` with a `level` (rank of
   font size). Walk the blocks keeping a *heading stack*: a heading at level L pops every heading at level ≥ L, then
   pushes itself — "Stage IV" (level 2) replaces "Stage III" but keeps "Revised GRAP" (level 1). Each heading starts
   a section; body blocks join the current one. `heading_path = " › ".join(stack)` ("Revised GRAP › Stage III").
2. **Units ≤ max_tokens** (`_units`). A block that fits is one unit. Too big: prose → sentences (split after
   `. ! ? ; ।` — the last is the Hindi danda); a sentence still too big → word windows (`_split_words`). Tables →
   `_table_units`: split **between rows only**, and **repeat the header** (first row + `|---|` separator) on every
   piece, so `|PM2.5 µg/m3|24 Hours|60|` never loses its column names.
3. **Pack** units greedily into chunks ≤ `max_tokens` *within* a section (sections never mix). When a section needs
   several chunks, the next prose chunk starts with the last ≤ `overlap` tokens of the previous one (`_tail`), so a
   fact straddling the cut appears whole somewhere. No overlap next to tables — they carry headers instead.
4. **Contextual header**: `embed_text = heading_path + "\n" + text` — the *embedding* knows the chunk is "Stage IV
   › Actions" even when the text only says "Stop truck entry".
5. **Parents**: one per section (`parent_id = "<doc>::s<NNN>"`, full section text), so small-to-big can swap a
   matched chunk for its whole section when that fits the budget.

### Worked example (the unit test `STRUCT_DOC`)
Blocks: `Revised GRAP`(h1) · `Stage III`(h2) · "Ban on construction…" · `Stage IV`(h2) · a 4-row table · `Dust`(h2) ·
a 12-sentence paragraph. With max 40 tokens / overlap 6: chunk 1 = "Ban on construction…" with path
"Revised GRAP › Stage III"; the table under "Revised GRAP › Stage IV" fits whole at max 60 but at max 12 becomes
header+2 rows, header+2 rows; the paragraph becomes ~4 chunks of ≤ 40 words, each next one starting with the
previous chunk's last 6 words.

### What it measured (golden v1, 95 questions with policy evidence)
| | Recall@5 | MRR | Multi-fact | Mixed | Hindi |
|---|---|---|---|---|---|
| A0 fixed 500, dense | 0.458 | 0.331 | 0.27 | 0.15 | 0.37 |
| A1 structure 400, dense | 0.421 | 0.311 | 0.33 | 0.20 | 0.27 |
| A3 structure + hybrid + rerank + filter | 0.621 | 0.451 | **0.60** | **0.35** | 0.40 |
| D3 fixed + dense + rerank + filter | **0.647** | **0.522** | 0.50 | 0.25 | **0.60** |

- **Not a free win.** At the same k, A1 is slightly worse (−0.04, n.s.) — but structure chunks are about half the
  size (median 247 vs 494 tokens), so top-5 hands over half the text. At an equal token budget (A1 top-10 vs A0
  top-5) it's +0.04, also n.s.
- **Where it helps:** questions that need *a specific unit* — multi-fact (+0.10 for A3 vs D3), mixed (+0.10).
- **Where it hurts:** single facts (0.85 vs 0.95) and Hindi (0.40 vs 0.60, n = 15, wide CI). Removing sparse (D8)
  did not recover Hindi, so the cause is the chunking itself — plausibly that smaller chunks give a cross-lingual
  embedding less context. A hypothesis, not a conclusion.
- 8% of chunks are tiny (< 30 tokens): parser heading false-positives (signatures, OCR debris) create one-line
  sections. Merging tiny sections is the obvious next ablation.

### Pitfalls
- The chunker is only as good as heading detection: noisy headings → noisy paths and tiny sections.
- Compare chunkers at equal *token* budget, not just equal k.
- Chunk ids change with the chunker — relevance must not be keyed to chunk ids (we use evidence quotes).
- Measure tokens with the **embedder's** tokenizer (BGE-M3), or "400 tokens" means nothing to the model.

### Interview Q&A
- *Why structure-aware chunking for regulations? What did it change in your numbers?* (SPEC §17 hook) Clauses and
  table rows are the unit of meaning; fixed windows split them. Measured: it helps multi-fact/mixed questions,
  hurts single facts and Hindi at equal k, and is neutral at equal token budget — so it's a trade-off, not a
  default win. Being able to say that, with numbers, is the point.
- *Why repeat table headers?* A row without its column names is unreadable to both the embedder and the LLM.
- *What is the overlap for?* So a fact that straddles a chunk boundary appears whole in at least one chunk.

---

## 4. Citation checker — M4, not built yet (SPEC §9.3)
