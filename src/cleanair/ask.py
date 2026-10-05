"""Ask one question from the terminal: retrieve -> synthesize -> print the answer with its sources.

Run: uv run python -m cleanair.ask "What is the 24-hour PM2.5 standard?" --config configs/ablations/naive.yaml
"""

import argparse
import sys
from pathlib import Path

from qdrant_client import QdrantClient

from cleanair.config import load_config
from cleanair.generation.synthesize import synthesize
from cleanair.retrieval.filters import filters_for
from cleanair.retrieval.retriever import PipelineRetriever
from cleanair.settings import Settings


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Ask Clean Air Copilot a policy question.")
    p.add_argument("question")
    p.add_argument("--config", type=Path, default=Path("configs/ablations/naive.yaml"))
    args = p.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252: µ and Devanagari break

    cfg = load_config(args.config)
    retriever = PipelineRetriever(cfg, QdrantClient(url=Settings().qdrant_url))
    chunks = retriever.retrieve(args.question, filters_for(args.question, cfg.retrieval.current_only))
    answer, usage = synthesize(args.question, chunks, cfg.generation)

    print(answer.answer, "\n")
    for c in answer.citations:
        print(f'  {c.marker}  "{c.quote}"')
    print("\nretrieved:", ", ".join(f"{c.chunk_id} ({c.score_fused:.3f})" for c in chunks))
    print("usage:", usage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
