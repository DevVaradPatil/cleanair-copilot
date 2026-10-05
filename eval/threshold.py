"""Choose the reranker relevance threshold from data (plan step 2.4).

Per question, take the best cross-encoder score among its candidates. A good threshold keeps (nearly) every
answerable question above it and pushes unanswerable ones below it, so retrieval itself can say
"insufficient evidence". We pick the threshold maximising balanced accuracy subject to keeping >= --min-keep of
answerable questions.

Caveat: tuning and measuring on the same 63 questions is optimistic. M4 splits a dev set for tuning.

Run: uv run python -m eval.threshold --run eval/results/<D2 run dir>
"""

import argparse
import json
import sys
from pathlib import Path


def best_scores(rows: list[dict]) -> tuple[list[float], list[float]]:
    ans = [r["top"][0][1] for r in rows if r["answerable"] and r["top"]]
    una = [r["top"][0][1] for r in rows if not r["answerable"] and r["top"]]
    return ans, una


def sweep(ans: list[float], una: list[float], min_keep: float) -> tuple[float, list[tuple[float, float, float, float]]]:
    table = []
    for t in sorted(set(ans + una)):
        keep = sum(a >= t for a in ans) / len(ans)
        reject = sum(u < t for u in una) / len(una)
        table.append((t, keep, reject, (keep + reject) / 2))
    feasible = [row for row in table if row[1] >= min_keep]
    best = max(feasible, key=lambda row: (row[3], row[0]))
    return best[0], table


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Pick a rerank threshold from a rerank-enabled eval run.")
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--min-keep", type=float, default=0.9)
    args = p.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    rows = [json.loads(line) for line in (args.run / "items.jsonl").read_text(encoding="utf-8").splitlines()]
    ans, una = best_scores(rows)
    t, table = sweep(ans, una, args.min_keep)
    lines = [
        f"# Rerank threshold from {args.run.name}",
        "",
        f"Best cross-encoder score per question. Answerable n={len(ans)}, unanswerable n={len(una)}.",
        f"Answerable: min {min(ans):.3f}, median {sorted(ans)[len(ans) // 2]:.3f}. "
        f"Unanswerable: max {max(una):.3f}, median {sorted(una)[len(una) // 2]:.3f}.",
        "",
        f"**Chosen threshold: {t:.4f}** (max balanced accuracy with >= {args.min_keep:.0%} answerable kept).",
        "",
        "| threshold | answerable kept | unanswerable rejected | balanced acc. |",
        "|---|---|---|---|",
    ]
    step = max(1, len(table) // 25)
    for row in table[::step] + [r for r in table if r[0] == t]:
        lines.append(f"| {row[0]:.4f}{' ←' if row[0] == t else ''} | {row[1]:.2f} | {row[2]:.2f} | {row[3]:.2f} |")
    lines += ["", "Tuned and measured on the same questions: optimistic until the M4 dev/test split."]
    out = "\n".join(lines) + "\n"
    (args.run / "threshold.md").write_text(out, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
