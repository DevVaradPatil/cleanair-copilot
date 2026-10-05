# Decisions

Format: date — decision — alternatives — reason.

- 2026-10-04 — Spec lives at `SPEC.md` (renamed from `CLEAN_AIR_COPILOT_SPEC.md`) — keep original name — spec and CLAUDE.md reference `SPEC.md` throughout.
- 2026-10-04 — Folder skeleton per SPEC.md §4.2, empty dirs held by `.gitkeep`; no code until M0 starts — scaffold modules up front — avoid writing code before each component is explained and agreed.
- 2026-10-05 — Generator LLM provider: Gemini via LiteLLM (`GEMINI_API_KEY`) — Claude, GPT, local Ollama — Varad's available key; the Flash-tier limits (docs/LLM_LIMITS.md) cover full eval runs. The judge should still come from a different family (TODO T4.2).
