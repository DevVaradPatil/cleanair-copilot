"""Chunk cleaned blocks into retrieval units -> data/processed/chunks/<chunk_set>.jsonl.

Two chunkers (SPEC §6):
- fixed_chunker: a sliding token window over the whole document, blind to structure (the A0 baseline).
- structure_chunker: 🧠 Varad implements -- headings -> paragraphs -> sentences, heading_path, parents.
  tests/test_chunk.py is its specification.
Token counts use the embedder's own tokenizer, so `max_tokens` means what the embedder actually sees.

Run: uv run python -m cleanair.ingest.chunk --config configs/ablations/naive.yaml
"""

import argparse
import json
import statistics
from collections.abc import Callable
from pathlib import Path

from cleanair.config import load_config
from cleanair.ingest.download import read_manifest

# (text) -> [(char_start, char_end), ...] one pair per token. Production: the HF fast tokenizer's offsets.
Tokenize = Callable[[str], list[tuple[int, int]]]
CountTokens = Callable[[str], int]


def fixed_chunker(
    blocks: list[dict], doc_id: str, tokenize: Tokenize, size: int = 500, overlap: int = 50
) -> list[dict]:
    """Windows of `size` tokens, stepping size - overlap, over the document's blocks joined by blank lines."""
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")
    text, block_starts = "", []
    for b in blocks:
        block_starts.append((len(text), b["page"]))
        text += b["text"] + "\n\n"
    offsets = tokenize(text)

    chunks, start = [], 0
    while start < len(offsets):
        end = min(start + size, len(offsets))
        a, z = offsets[start][0], offsets[end - 1][1]
        pages = [page for pos, page in block_starts if pos < z] or [1]
        first_page = max((page for pos, page in block_starts if pos <= a), default=pages[0])
        chunks.append(
            {
                "chunk_id": f"{doc_id}::fixed::c{len(chunks):03d}",
                "doc_id": doc_id,
                "heading_path": "",
                "text": text[a:z].strip(),
                "embed_text": text[a:z].strip(),  # A0: no contextual header
                "page_start": first_page,
                "page_end": pages[-1],
                "parent_id": None,
                "token_count": end - start,
            }
        )
        if end == len(offsets):
            break
        start += size - overlap
    return chunks


def structure_chunker(
    blocks: list[dict], doc_id: str, count_tokens: CountTokens, max_tokens: int = 400, overlap: int = 60
) -> tuple[list[dict], list[dict]]:
    """🧠 Varad implements. Returns (chunks, parents). See tests/test_chunk.py for the contract:

    - split at headings first, then paragraphs (blocks), then sentences, until a piece is <= max_tokens;
      consecutive pieces of one oversized section share `overlap` tokens
    - every chunk carries heading_path ("Revised GRAP › Stage III › Actions"), built from block levels
    - embed_text = heading_path + "\\n" + text (contextual chunk header)
    - a table block is never split mid-row; a table that fits is kept whole
    - parents: one per top-level section {parent_id, doc_id, heading_path, text, token_count};
      each chunk's parent_id points at one of them (small-to-big retrieval)
    - chunk_id = f"{doc_id}::{section}::c{NN}"; page_start/page_end from the blocks used
    """
    raise NotImplementedError("🧠 structure_chunker is Varad's to implement (plan step 2.1)")


def hf_tokenizer(model_name: str) -> tuple[Tokenize, CountTokens]:
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(model_name)
    tok.model_max_length = 10**9  # we tokenize whole documents to window them; silence the length warning

    def tokenize(text: str) -> list[tuple[int, int]]:
        return tok(text, add_special_tokens=False, return_offsets_mapping=True)["offset_mapping"]

    def count_tokens(text: str) -> int:
        return len(tok(text, add_special_tokens=False)["input_ids"])

    return tokenize, count_tokens


def doc_metadata(row: dict) -> dict:
    """The manifest fields every chunk carries as Qdrant payload (used by filters and citations)."""
    return {
        "title": row["title"],
        "doc_type": row["doc_type"],
        "jurisdiction": row["jurisdiction"],
        "cities": [c for c in row["cities"].split(";") if c],
        "language": row["language"],
        "is_current": row["is_current"] == "true",
        "published_on": row["published_on"] or None,
        "source_url": row["source_url"],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Chunk cleaned documents for one pipeline config.")
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--manifest", type=Path, default=Path("data/manifest.csv"))
    p.add_argument("--clean-dir", type=Path, default=Path("data/processed/clean"))
    p.add_argument("--out-dir", type=Path, default=Path("data/processed/chunks"))
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    tokenize, count_tokens = hf_tokenizer(cfg.embedder.model)
    rows = {r["doc_id"]: r for r in read_manifest(args.manifest)}
    chunks, parents = [], []
    for path in sorted(args.clean_dir.glob("*.jsonl")):
        doc_id = path.stem
        blocks = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        if cfg.chunker.type == "fixed":
            doc_chunks, doc_parents = (
                fixed_chunker(blocks, doc_id, tokenize, cfg.chunker.max_tokens, cfg.chunker.overlap),
                [],
            )
        else:
            doc_chunks, doc_parents = structure_chunker(
                blocks, doc_id, count_tokens, cfg.chunker.max_tokens, cfg.chunker.overlap
            )
        meta = doc_metadata(rows[doc_id])
        chunks += [{**c, **meta} for c in doc_chunks]
        parents += doc_parents

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"{cfg.chunk_set}.jsonl"
    out.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in chunks), encoding="utf-8")
    if parents:
        (args.out_dir / f"{cfg.chunk_set}.parents.jsonl").write_text(
            "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in parents), encoding="utf-8"
        )
    sizes = [c["token_count"] for c in chunks]
    print(
        f"{out}: {len(chunks)} chunks from {len({c['doc_id'] for c in chunks})} docs, "
        f"tokens mean {statistics.mean(sizes):.0f} / max {max(sizes)}, {len(parents)} parents"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
