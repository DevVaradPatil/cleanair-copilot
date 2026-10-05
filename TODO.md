# TODO: manual steps for Varad

Things Claude can't or shouldn't do: accounts, credentials, downloads behind a portal, and manual verification.
The IDs match the 👤 markers in [plan.md](plan.md). Tick a box when it's done. Claude adds new items here as they come up.
Secrets go **only** in `.env`. Never paste them into chat or commit them.

## M0: Setup
- [x] **T0.1** Install **uv** and Python 3.11+ (check with `uv --version ; uv python list`).
- [x] **T0.2** Install **Docker Desktop** (WSL2 backend) and confirm `docker run hello-world` works.
- [x] **T0.3** Approve `git init`. Create an empty GitHub repo `cleanair-copilot` (public, for the portfolio) and share its URL.
- [ ] **T0.5** ⚠️ **Gemini key is FREE tier: 20 requests/day per model, 0 for Pro** (found 2026-10-05 from quota errors;
  see `docs/LLM_LIMITS.md`). The limits table you pasted is a paid tier. In AI Studio → API keys, check which Google
  Cloud project the key belongs to and **enable billing on it** (or create a key in the billed project and replace it in `.env`).
  Until then, generation evals can't run on the full set (63 questions ≈ 63 generations + ~48 judge calls).
  After it's enabled: `uv run python -m eval.harness --config configs/ablations/naive.yaml --set golden --generate`
- [ ] **T0.6** KSS cluster: every pending GPU job (all users) shows `Reason=InvalidAccount` (2026-10-05). It's not a
  `--account` flag in our script. Email `manver@iitk.ac.in`. Our job is ready to go:
  `cd ~/cleanair-copilot && sbatch --export=ALL,CHUNKS=data/processed/chunks/<set>.jsonl cluster/job_embed.sh`
- [x] **T0.4** LLM provider: **Gemini**, key in `.env` as `GEMINI_API_KEY`. Limits are in `docs/LLM_LIMITS.md`. Still to do: set a spend limit in the Google AI Studio / Cloud billing dashboard.

## M1: Corpus + baseline
- [x] **T1.1** Manifest reviewed: accepted as a learning-project corpus, imperfect metadata included (2026-10-05). Added the CAQM Act 2021 (eGazette) and the MCGM Mumbai dust mitigation plan. 49 rows.
  Still open, whenever convenient: fill blank `published_on` dates; find the Delhi Winter Action Plan, the UP State Action Plan, Hindi editions of NCAP/AQI.
- [x] **T1.2** Terms of use: accepted. Raw files stay git-ignored; only the manifest and URLs are committed.
- [ ] **T1.3** Tesseract 5 is installed, but only `eng` language data is present. For Hindi OCR, download `hin.traineddata` from https://github.com/tesseract-ocr/tessdata (the `tessdata` repo, about 2 MB)
  into `C:\Program Files\Tesseract-OCR\tessdata\` (needs admin). Check with `tesseract --list-langs` (should list `hin`).
- [ ] **T1.4** Hand-check the parser on the 5 hardest documents. Compare each outline against the PDF in `data/raw/`:
  `uv run python -m cleanair.ingest.parse <doc_id> --outline` (and open `data/processed/<doc_id>.jsonl` for tables).
  1. `grap-schedule-2026-09`: table-heavy (13 tables, 5 headings). Are all Stage I–IV actions inside the tables, with their stage label?
  2. `naaqs-2009`: scanned bilingual gazette. Prose OCRs fine, the standards table is scrambled. (NCAP p24 and C&D-waste p48 carry the same table as clean text.)
  3. `cap-delhi`: fully scanned, 84 OCR pages. Is the OCR text readable?
  4. `ngt-oa681-kanpur-qpr`: mixed scan/text, 531 'headings', so there are probably many false positives.
  5. `caqm-act-2021`: law layout with margin notes. Do the section titles come out as headings?
  Write down what's wrong; it decides whether we need Docling (an architecture change → DECISIONS).
- [ ] **T1.6** India Code (Air Act EN/HI) was returning 504 all day on 2026-10-05. Re-run `uv run python -m cleanair.ingest.download` later; it retries only the missing files.
- [ ] **T1.5** Verify `eval/golden/questions.jsonl` (63 items: 40 single-fact, 8 multi-fact, 15 unanswerable).
  Every quote is machine-verified to occur in its document, but check that each *question* is natural and
  unambiguous, each *reference_answer* is right, and each unanswerable one really isn't answerable (two are flagged
  "verify in T1.5"). Relevance is evidence-based (doc_id + quote), so there are no chunk IDs to confirm.
- [ ] **T3.1 (start early)** Begin getting station data. See M3.

## M2: Retrieval
- [ ] **T2.1** Make sure there's ~6 GB of free disk for the Hugging Face model downloads (embedder + reranker).
- [ ] **T2.2** Write your own insight per step in `docs/LEARNING_LOG.md`. Claude can prompt you, but the words should be yours.
- [ ] **🧠 2.1** Implement `structure_chunker` in `src/cleanair/ingest/chunk.py`. The spec is `tests/test_chunk.py`
  (7 xfail tests). When they XPASS, delete the `brain` marker. Then build and evaluate A1:
  `uv run python -m cleanair.ingest.chunk --config configs/ablations/struct_chunk.yaml`
  `uv run python -m cleanair.ingest.embed --chunks data/processed/chunks/structure-400-60.jsonl`
  `uv run python -m cleanair.ingest.index --config configs/ablations/struct_chunk.yaml`
  `uv run python -m eval.harness --config configs/ablations/struct_chunk.yaml --set golden`
- [ ] **🧠 2.3** Implement `rrf` and `weighted` in `src/cleanair/retrieval/fusion.py`. The spec is `tests/test_fusion.py`
  (6 xfail tests). Then run A2 (`hybrid.yaml`) and A3 (`hybrid_rerank.yaml`) with `eval.harness` (same index as A1).
  A3 is two passes: its threshold is `null` until you run `eval.threshold` on the first A3 run (see the yaml comment),
  then `uv run python -m eval.report --runs eval/results/*golden` and update the README table.

## M3: Data + routing
- [ ] **T3.1** Get 2–3 years of daily readings for Kanpur, Lucknow, Delhi and Mumbai from the CPCB CAAQMS portal (manual export). If that stalls: create an **OpenAQ** account and API key (into `.env`), or a **Kaggle** account plus `kaggle.json` for the fallback dataset.
- [ ] **T3.2** Record the data source, terms and retrieval date in DECISIONS.
- [ ] **T3.3** Decide the city-AQI definition (max over stations vs mean) and confirm it in `docs/DATA_DICTIONARY.md`.
- [ ] **T3.4** Verify the 90 new golden questions (data / mixed / Hindi / red-team).
- [ ] Implement 🧠 SQL validator (plan 3.4).

## M4: Quality + eval
- [ ] **T4.1** Hand-label 80–100 answers (correct? faithful?) into `eval/golden/human_labels.jsonl`.
- [ ] **T4.2** Get an API key from a **second model family** for the judge, and put it in `.env`.
- [ ] **T4.3** Add the LLM API key(s) as **GitHub Actions secrets** for the smoke-gate CI.
- [ ] Implement 🧠 citation checker (plan 4.1).

## M5: Ship
- [ ] **T5.1** Create a **Langfuse** cloud project (or approve self-hosting). Put the public and secret keys in `.env`.
- [ ] **T5.2** Create a hosting account (Render / Railway / a VM) and decide the RAM budget (see the risks in plan.md).
- [ ] **T5.3** Create a **Qdrant Cloud** free cluster (or approve the same-VM option). Put the URL and API key in `.env`.
- [ ] **T5.4** Set the daily budget alarm / spend cap on every LLM provider used in production.
- [ ] **T5.5** Record the demo GIF or video for the README.
