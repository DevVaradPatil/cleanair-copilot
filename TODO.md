# TODO: manual steps for Varad

Things Claude can't or shouldn't do: accounts, credentials, downloads behind a portal, and manual verification.
The IDs match the 👤 markers in [plan.md](plan.md). Tick a box when it's done. Claude adds new items here as they come up.
Secrets go **only** in `.env`. Never paste them into chat or commit them.

## M0: Setup
- [x] **T0.1** Install **uv** and Python 3.11+ (check with `uv --version ; uv python list`).
- [x] **T0.2** Install **Docker Desktop** (WSL2 backend) and confirm `docker run hello-world` works.
- [x] **T0.3** Approve `git init`. Create an empty GitHub repo `cleanair-copilot` (public, for the portfolio) and share its URL.
- [x] **T0.4** LLM provider: **Gemini**, key in `.env` as `GEMINI_API_KEY`. Limits are in `docs/LLM_LIMITS.md`. Still to do: set a spend limit in the Google AI Studio / Cloud billing dashboard.

## M1: Corpus + baseline
- [ ] **T1.1** Review the draft `data/manifest.csv` (47 rows, all URLs from official portals, 45 verified to download as PDFs). For each row:
  check the title and publisher; fill the blank `published_on` dates from the document's first page; confirm `is_current` / `superseded_by`.
  Specific doubts: (a) `ncap-funds-guidelines-amended` and `svs-ranking-2022`, which I marked as superseded based on their titles alone;
  (b) `cap-kanpur` (0.2 MB) and `cap-lucknow` (0.1 MB) are suspiciously small, so check they're the full plans and not cover letters;
  (c) `naqi-2014` is CPCB's 'About AQI' PDF: is it the full 2014 AQI report with breakpoints?
  Gaps worth adding (couldn't find stable official URLs): the CAQM Act 2021, the Delhi Winter Action Plan, an updated Mumbai plan (MPCB/BMC), the UP State Action Plan, Hindi editions of NCAP/AQI, NGT orders in O.A. 681/2018.
- [ ] **T1.2** Check each site's terms of use. Note anything that can't be redistributed (those raw files stay out of git anyway).
- [ ] **T1.3** Install **Tesseract OCR** for Windows, with the Hindi (`hin`) language data, and add it to PATH.
- [ ] **T1.4** Hand-check the parser output on the 5 hardest documents: headings and tables correct?
- [ ] **T1.5** Verify every golden-set reference answer (60) against the source document, and confirm the chunk IDs.
- [ ] **T3.1 (start early)** Begin getting station data. See M3.

## M2: Retrieval
- [ ] **T2.1** Make sure there's ~6 GB of free disk for the Hugging Face model downloads (embedder + reranker).
- [ ] **T2.2** Write your own insight per step in `docs/LEARNING_LOG.md`. Claude can prompt you, but the words should be yours.
- [ ] Implement 🧠 structure-aware chunker (plan 2.1) and 🧠 RRF / weighted fusion (plan 2.3).

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
