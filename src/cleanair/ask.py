"""Ask one question from the terminal: route -> policy/data paths -> answer, with sources, SQL and coverage.

Run: uv run python -m cleanair.ask "How many days was Kanpur's AQI Severe in winter 2024-25?" \
       --config configs/ablations/diag_router_rules.yaml
"""

import argparse
import sys
from pathlib import Path

from cleanair.config import load_config
from cleanair.pipeline import Copilot


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Ask Clean Air Copilot a question.")
    p.add_argument("question")
    p.add_argument("--config", type=Path, default=Path("configs/ablations/diag_router_rules.yaml"))
    args = p.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252: µ and Devanagari break

    answer, trace = Copilot(load_config(args.config)).answer(args.question)
    r = trace.route
    print(f"[route: {r.route.value}, language: {r.language}, cities: {r.cities}, time: {r.time_range}]\n")
    print(answer.answer, "\n")
    for c in answer.citations:
        print(f"  {c.marker}  {c.quote or ''}")
    if trace.chunks:
        print("\nretrieved:", ", ".join(c.chunk_id for c in trace.chunks))
    if trace.data:
        d = trace.data
        print(f"\nSQL ({d.attempts} attempt(s)): {d.sql or '-'}")
        if d.result:
            print(d.result.to_markdown(10))
        for c in d.coverage:
            print(
                f"coverage {c['city']}: {c['days_reported']}/{c['days_in_range']} days, "
                f"stations {c['station_coverage_pct']}%"
            )
    if trace.data_error:
        print("\ndata path unavailable:", trace.data_error)
    print("\nusage:", trace.generation)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
