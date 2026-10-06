"""Chunk cleaned blocks into retrieval units -> data/processed/chunks/<chunk_set>.jsonl.

Two chunkers (SPEC §6):
- fixed_chunker: a sliding token window over the whole document, blind to structure (the A0 baseline).
- structure_chunker: 🧠 headings -> paragraphs -> sentences, heading_path, parents (docs/BRAIN_NOTES.md).
  tests/test_chunk.py is its specification.
Token counts use the embedder's own tokenizer, so `max_tokens` means what the embedder actually sees.

Run: uv run python -m cleanair.ingest.chunk --config configs/ablations/naive.yaml
"""

import argparse
import json
import re
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


SENTENCE_END = re.compile(r"(?<=[.!?।;])\s+")  # '।' = Devanagari danda (Hindi full stop)
PATH_SEP = " › "
HEADING_MAX_CHARS = 80  # long false-positive "headings" would bloat every chunk's contextual header


def _sections(blocks: list[dict]) -> list[dict]:
    """Group body blocks under the heading stack in force. A heading at level L closes every open heading at L or
    deeper (so 'Stage IV' replaces 'Stage III' but keeps 'Revised GRAP'). Each heading starts a new section."""
    stack: list[tuple[int, str]] = []
    sections: list[dict] = [{"path": "", "blocks": []}]
    for b in blocks:
        if b["kind"] == "heading":
            level = b.get("level") or 1
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, re.sub(r"\s+", " ", b["text"])[:HEADING_MAX_CHARS].strip()))
            sections.append({"path": PATH_SEP.join(t for _, t in stack), "blocks": []})
        else:
            sections[-1]["blocks"].append(b)
    return [s for s in sections if s["blocks"]]  # a heading followed directly by a heading has no body


def _split_words(text: str, count_tokens: CountTokens, max_tokens: int) -> list[str]:
    """Last resort for a single sentence/row longer than max_tokens: greedy word windows."""
    pieces, cur = [], []
    for word in text.split():
        if cur and count_tokens(" ".join([*cur, word])) > max_tokens:
            pieces.append(" ".join(cur))
            cur = []
        cur.append(word)
    return pieces + ([" ".join(cur)] if cur else [])


def _table_units(text: str, count_tokens: CountTokens, max_tokens: int) -> list[str]:
    """Split a markdown table between rows, repeating its header (first row + separator) on every piece, so each
    piece stays self-describing: '|PM2.5 µg/m3|24 Hours|60|' is useless without the column names."""
    lines = text.splitlines()
    has_sep = len(lines) > 1 and set(lines[1].replace("|", "").strip()) <= set("-: ")
    header = lines[:2] if has_sep else lines[:1]
    rows = lines[len(header) :]
    pieces, cur = [], list(header)
    for row in rows:
        if count_tokens("\n".join([*cur, row])) > max_tokens and len(cur) > len(header):
            pieces.append("\n".join(cur))
            cur = list(header)
        if count_tokens("\n".join([*cur, row])) > max_tokens:  # one row alone is too big: unavoidable cut
            pieces += _split_words(row, count_tokens, max_tokens)
            continue
        cur.append(row)
    if len(cur) > len(header):
        pieces.append("\n".join(cur))
    return pieces


def _units(block: dict, count_tokens: CountTokens, max_tokens: int) -> list[tuple[str, bool]]:
    """(text, is_table) pieces of one block, each <= max_tokens: whole block, else sentences / table rows."""
    text = block["text"]
    if count_tokens(text) <= max_tokens:
        return [(text, block["kind"] == "table")]
    if block["kind"] == "table":
        return [(t, True) for t in _table_units(text, count_tokens, max_tokens)]
    out = []
    for sentence in SENTENCE_END.split(text):
        if count_tokens(sentence) <= max_tokens:
            out.append((sentence, False))
        else:
            out += [(w, False) for w in _split_words(sentence, count_tokens, max_tokens)]
    return out


def _tail(text: str, count_tokens: CountTokens, overlap: int) -> str:
    """The last <= overlap tokens of text, on word boundaries."""
    words = text.split()
    tail: list[str] = []
    while words and count_tokens(" ".join([words[-1], *tail])) <= overlap:
        tail.insert(0, words.pop())
    return " ".join(tail)


def structure_chunker(
    blocks: list[dict], doc_id: str, count_tokens: CountTokens, max_tokens: int = 400, overlap: int = 60
) -> tuple[list[dict], list[dict]]:
    """Structure-aware chunking (SPEC §6.1). 🧠 explained in docs/BRAIN_NOTES.md. Returns (chunks, parents).

    - split at headings first, then paragraphs (blocks), then sentences, until a piece is <= max_tokens;
      consecutive prose pieces of one oversized section share `overlap` tokens
    - every chunk carries heading_path ("Revised GRAP › Stage III"), built from the parser's heading levels
    - embed_text = heading_path + "\\n" + text (contextual chunk header)
    - a table is never split mid-row; a table that fits is kept whole; split tables repeat their header
    - parents: one per section {parent_id, doc_id, heading_path, text, token_count}; each chunk's parent_id points
      at the section it came from (small-to-big retrieval)
    - chunk_id = f"{doc_id}::s{NNN}::c{NN}"; page_start/page_end from the blocks used
    """
    chunks: list[dict] = []
    parents: list[dict] = []
    for s_idx, section in enumerate(_sections(blocks)):
        path, section_id = section["path"], f"{doc_id}::s{s_idx:03d}"
        parent_text = (path + "\n" if path else "") + "\n".join(b["text"] for b in section["blocks"])
        parents.append(
            {
                "parent_id": section_id,
                "doc_id": doc_id,
                "heading_path": path,
                "text": parent_text,
                "token_count": count_tokens(parent_text),
            }
        )

        units = [
            (u, is_table, b["page"]) for b in section["blocks"] for u, is_table in _units(b, count_tokens, max_tokens)
        ]
        pieces: list[tuple[list[str], list[int], bool]] = []  # (texts, pages, ends_with_table)
        cur: list[str] = []
        pages: list[int] = []
        size = 0
        last_table = False
        for text, is_table, page in units:
            n = count_tokens(text)
            if cur and size + n > max_tokens:
                pieces.append((cur, pages, last_table))
                tail = "" if (last_table or is_table) else _tail("\n".join(cur), count_tokens, overlap)
                tail_n = count_tokens(tail) if tail else 0
                cur, pages, size = ([tail], [pages[-1]], tail_n) if tail and tail_n + n <= max_tokens else ([], [], 0)
            cur.append(text)
            pages.append(page)
            size += n
            last_table = is_table
        if cur:
            pieces.append((cur, pages, last_table))

        for c_idx, (texts, piece_pages, _) in enumerate(pieces):
            text = "\n".join(texts).strip()
            chunks.append(
                {
                    "chunk_id": f"{section_id}::c{c_idx:02d}",
                    "doc_id": doc_id,
                    "heading_path": path,
                    "text": text,
                    "embed_text": f"{path}\n{text}" if path else text,
                    "page_start": min(piece_pages),
                    "page_end": max(piece_pages),
                    "parent_id": section_id,
                    "token_count": count_tokens(text),
                }
            )
    return chunks, parents


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
