"""Clean parsed blocks: data/processed/<doc_id>.jsonl -> data/processed/clean/<doc_id>.jsonl.

Per block: Unicode NFC (Devanagari-safe), mapping of Symbol-font Private Use Area glyphs back to real
characters (µ, ≥, bullets), prose line-joining (de-hyphenation), and markdown-table tidying
(<br>, bold markers, ColN placeholders, cells duplicated by merged-cell extraction, empty rows).
Per document: drops page-number blocks and headers/footers repeated on >= 50% of pages (SPEC §6.1).

Cheap, so it always re-cleans everything; the expensive parse output is never modified.
Run: uv run python -m cleanair.ingest.clean
"""

import argparse
import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path

REPEAT_SHARE = 0.5  # SPEC §6.1: boilerplate = same text on >= 50% of pages
REPEAT_MAX_CHARS = 200  # only short blocks can be headers/footers; long repeated text is content
PAGE_NUMBER = re.compile(r"^\W*(page\s*)?\d+(\s*(of|/)\s*\d+)?\W*$", re.IGNORECASE)
SEPARATOR_CELL = re.compile(r"^:?-{3,}:?$")


# Symbol/Wingdings fonts put glyphs in the Private Use Area at U+F000 + their 8-bit code. Map the ones
# seen in this corpus back to real characters; any other PUA char is dropped (meaningless to embedders).
SYMBOL_FONT = str.maketrans(
    {
        0xF06D: "µ",  # Symbol 'm' renders as mu: "µg/m3"
        0xF061: "α",
        0xF062: "β",
        0xF0B3: "≥",
        0xF0A3: "≤",
        0xF0B0: "°",
        0xF020: " ",
        0xF0B7: "•",  # bullets
        0xF0A8: "•",
        0xF0A7: "•",
        0xF0D8: "•",
    }
)
PRIVATE_USE = re.compile("[-]")


def fix_glyphs(text: str) -> str:
    text = PRIVATE_USE.sub("", text.translate(SYMBOL_FONT))
    return re.sub(r"μ(?=g\s*/\s*m|m\b)", "µ", text)  # Greek mu -> micro sign, so "µg/m3" matches one way


def clean_prose(text: str) -> str:
    text = re.sub(r"([a-z])-\n([a-z])", r"\1\2", text)  # "imple-\nmentation"; keeps "Stage-\nIII"
    return re.sub(r"\s+", " ", text).strip()


def clean_table(md: str) -> str:
    rows = []
    for line in md.splitlines():
        cells = [
            re.sub(r"\s+", " ", c.replace("<br>", " ").replace("**", "")).strip()
            for c in line.split("|")[1:-1]
        ]
        if cells and all(SEPARATOR_CELL.match(c) for c in cells):
            rows.append(line.strip())
            continue
        cells = ["" if re.fullmatch(r"Col\d+", c) else c for c in cells]
        # Merged cells come out copied into every spanned column; keep the first copy only. Only text labels
        # are merged in practice -- equal numbers side by side are real values (NAAQS SO2 24h: 80 | 80).
        has_letter = [bool(re.search(r"[^\W\d_]", c)) for c in cells]
        cells = ["" if i > 0 and c == cells[i - 1] and has_letter[i] else c for i, c in enumerate(cells)]
        if not rows or (any(cells) and cells != rows[-1]):  # first row = header, always kept
            rows.append(cells)
    return "\n".join(r if isinstance(r, str) else "|" + "|".join(r) + "|" for r in rows)


def clean_text(text: str, kind: str) -> str:
    text = fix_glyphs(unicodedata.normalize("NFC", text))
    return clean_table(text) if kind == "table" else clean_prose(text)


def _boilerplate_key(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", text.lower())).strip()


def drop_repeated(blocks: list[dict]) -> tuple[list[dict], int]:
    """Remove page numbers and short non-table blocks that recur on >= REPEAT_SHARE of the pages."""
    n_pages = len({b["page"] for b in blocks})
    pages_with = Counter()
    for key in {(b["page"], _boilerplate_key(b["text"])) for b in blocks if b["kind"] != "table"}:
        pages_with[key[1]] += 1
    threshold = max(2, math.ceil(REPEAT_SHARE * n_pages))

    def is_boilerplate(b):
        if b["kind"] == "table":
            return False
        if PAGE_NUMBER.match(b["text"]):
            return True
        return len(b["text"]) <= REPEAT_MAX_CHARS and pages_with[_boilerplate_key(b["text"])] >= threshold

    kept = [b for b in blocks if not is_boilerplate(b)]
    return kept, len(blocks) - len(kept)


def clean_doc(blocks: list[dict]) -> tuple[list[dict], int]:
    cleaned = [{**b, "text": clean_text(b["text"], b["kind"])} for b in blocks]
    cleaned = [b for b in cleaned if len(re.findall(r"\w", b["text"])) >= 2]  # empty / OCR specks
    return drop_repeated(cleaned)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Clean parsed blocks into data/processed/clean/.")
    p.add_argument("--in-dir", type=Path, default=Path("data/processed"))
    p.add_argument("--out-dir", type=Path, default=Path("data/processed/clean"))
    args = p.parse_args(argv)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for src in sorted(args.in_dir.glob("*.jsonl")):
        blocks = [json.loads(line) for line in src.read_text(encoding="utf-8").splitlines()]
        pua = sum(len(PRIVATE_USE.findall(b["text"])) for b in blocks)
        cleaned, removed = clean_doc(blocks)
        with open(args.out_dir / src.name, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(b, ensure_ascii=False) + "\n" for b in cleaned)
        counts = f"{len(blocks):>5} -> {len(cleaned):>5} blocks, {removed:>4} boilerplate, {pua:>4} glyphs"
        print(f"{src.stem:<40} {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
