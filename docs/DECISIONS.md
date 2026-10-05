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
