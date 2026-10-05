# Decisions

Format: date — decision — alternatives — reason.

- 2026-10-04 — Spec lives at `SPEC.md` (renamed from `CLEAN_AIR_COPILOT_SPEC.md`) — keep original name — spec and CLAUDE.md reference `SPEC.md` throughout.
- 2026-10-04 — Folder skeleton per SPEC.md §4.2, empty dirs held by `.gitkeep`; no code until M0 starts — scaffold modules up front — avoid writing code before each component is explained and agreed.
- 2026-10-05 — Generator LLM provider: Gemini via LiteLLM (`GEMINI_API_KEY`) — Claude, GPT, local Ollama — Varad's available key; the Flash-tier limits (docs/LLM_LIMITS.md) cover full eval runs. The judge should still come from a different family (TODO T4.2).
- 2026-10-05 — Secrets (`settings.py`, pydantic-settings, `.env`) are kept separate from the experiment config (`config.py`, YAML) — one settings object for everything — YAML configs get saved with each eval run and must never hold keys. The config uses `extra="forbid"`, so a typo in an ablation YAML fails instead of silently using a default.
- 2026-10-05 — Every ablation switch from §10.4 is a config field from M0 — add fields as features land — stops pipeline choices being hardcoded in the meantime.
- 2026-10-05 — Qdrant image pinned to v1.19.1 — `latest` — reproducibility.
- 2026-10-05 — Qdrant health check is a pytest marked `integration` (excluded by default, `pytest -m integration`) — separate scripts/ health script — one less file, and it's reusable in CI later.
- 2026-10-05 — pre-commit runs ruff through `uv run` (local hook) — the ruff-pre-commit mirror — a single ruff version, the one pinned in uv.lock. Ruff excludes `*.md`, so it doesn't reformat the code samples in the spec.
- 2026-10-05 — `requires-python >=3.11`, dev venv on 3.12 (`.python-version`) — 3.11 — 3.12 is what's installed, and the spec asks for 3.11+.
- 2026-10-05 — Manifest conventions: `cities` is `;`-separated (empty = not city-specific); `retrieved_on` and `sha256` stay empty until the download step fills them; only dates seen on an official listing or in the document title are filled, everything else is left blank for Varad to verify — fill dates from secondary sources — metadata errors would leak into `is_current` filtering and into citations.
- 2026-10-05 — `is_current=false` covers two cases: superseded versions (GRAP schedules 2024-12 → 2025-11 → 2026-09, with a `superseded_by` chain), and one-off event orders (Stage invocations and revocations), which stay in the corpus for questions about the past — dropping event orders — "when was Stage IV last invoked?" is a fair question, and the filter test needs non-current docs.
- 2026-10-05 — Kanpur and Lucknow are NOT in NCR, so no CAQM/GRAP doc is tagged with them; the UP IEC plan covers only UP's NCR districts — tag by state — this protects the "GRAP applies only to Delhi-NCR" invariant at the metadata level.
- 2026-10-05 — Known source quirks for step 1.2: some PRANA files (`NAAQMS_Volume-I`, `c_and_d_guidelines_*`) are served with an HTML prefix before `%PDF`, so the downloader must strip it; India Code returns intermittent 504s, so the downloader needs retries.
