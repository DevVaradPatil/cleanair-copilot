"""Comparison table across eval runs (the README headline, SPEC §10.4).

Run: uv run python -m eval.report --runs eval/results/*golden
"""

import argparse
import json
import sys
from pathlib import Path


def cell(m: dict | None, digits: int = 3) -> str:
    if not m:
        return "—"
    return f"{m['mean']:.{digits}f} [{m['ci95'][0]:.2f}–{m['ci95'][1]:.2f}]"


def table(run_dirs: list[Path]) -> str:
    header = [
        "Config",
        "Set",
        "n",
        "Recall@5",
        "Recall@10",
        "MRR",
        "nDCG@5",
        "Multi-fact R@5",
        "Abstain: unanswerable",
        "Abstain: answerable",
        "Faithfulness*",
        "Not-found acc.",
        "p95 retrieval",
    ]
    rows = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for d in run_dirs:
        f = d / "summary.json"
        if not f.exists():
            continue
        s = json.loads(f.read_text(encoding="utf-8"))
        limit = f" (first {s['limit']})" if s.get("limit") else ""
        cells = [
            s["config"],
            s["set"] + limit,
            str(s["n"]),
            cell(s["recall@5"]),
            cell(s["recall@10"]),
            cell(s["mrr"]),
            cell(s["ndcg@5"]),
            cell(s["by_category"].get("policy_multi", {}).get("recall@5")),
            cell(s.get("abstain_unanswerable")),
            cell(s.get("abstain_answerable")),
            cell(s.get("faithfulness")),
            cell(s.get("not_found_correct")),
            f"{s['retrieval_latency_s']['p95']} s",
        ]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows) + "\n\n*Faithfulness judge uncalibrated until M4. 95% bootstrap CIs over questions.\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build the ablation comparison table.")
    p.add_argument("--runs", nargs="+", type=Path, required=True)
    args = p.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    print(table(sorted(args.runs)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
