# LLM rate limits

> **Correction (2026-10-05, observed from API errors):** the key in `.env` is on the **free tier**, not the tier in
> the table below. Free tier = **20 requests/day per model** for every Flash and Flash-Lite model we tried
> (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, quotaValue 20), and **0** for Pro models.
> `gemini-2.5-flash` / `gemini-2.5-pro` return 404 "no longer available to new users", even though `ListModels`
> shows them. Working ids (2026-10-05): gemini-3.8-flash, 3.7-flash (often 503), 3.6-flash, 3.5-flash,
> 3.5-flash-lite, 3.1-flash-lite, 3-flash-preview. TODO T0.5: enable billing so the table below applies.

Gemini API limits for Varad's key, copied from the AI Studio rate-limit page on 2026-10-05.
Limits change with tier and over time, so re-check the dashboard before planning a large eval run.

RPM = requests/min, TPM = input tokens/min, RPD = requests/day.

| Model | RPM | TPM | RPD |
|---|---|---|---|
| Gemini 2 Flash | 2K | 4M | Unlimited |
| Gemini 2 Flash Lite | 4K | 4M | Unlimited |
| Gemini 2.5 Flash | 1K | 1M | 10K |
| Gemini 2.5 Flash Lite | 4K | 4M | Unlimited |
| Gemini 2.5 Pro | 150 | 2M | 1K |
| Gemini 3 Flash | 1K | 2M | 10K |
| Gemini 3.1 Pro | 25 | 2M | 250 |
| Gemini 3.1 Flash Lite | 4K | 4M | 150K |
| Gemini 3.5 Flash | 1K | 2M | 10K |
| Gemini 3.5 Flash Lite | 4K | 4M | 150K |
| Gemini 3.6 Flash | 1K | 2M | 10K |
| Gemini 3.7 Flash | 1K | 2M | 10K |
| Gemini 3.8 Flash | 1K | 2M | 10K |

## What this means for the project

- **Eval runs fit comfortably on Flash models.** A full golden-set run is about 150 questions × ~3–4 calls (router, generation, judge), so roughly 600 requests. With 7 ablation configs that's about 4K requests/day, which sits under the 10K RPD of the Flash models.
- **Pro models are the bottleneck.** 3.1 Pro allows 250 RPD, which is too few for full eval runs, so keep it for spot checks.
- **High-volume, low-difficulty calls** (router, query condensation) suit the Flash Lite models (4K RPM).
- **Judge:** SPEC §10.6 prefers a judge from a *different model family* than the generator. A Gemini judge for a Gemini generator falls short of that, so TODO T4.2 still applies.
- The exact LiteLLM model IDs (`gemini/<id>`) get verified when the LLM client is built (plan step 1.8). They aren't recorded here.
