"""Parse data/raw/<doc_id>.pdf into ordered blocks -> data/processed/<doc_id>.jsonl (one JSON block per line).

Each block: {doc_id, page, kind: heading|text|table, level, text, size, bold, ocr}.
- Text and font info come from PyMuPDF. Pages with < 50 chars of text are OCR'd with Tesseract
  (built into PyMuPDF; needs only the tessdata folder).
- Tables found by page.find_tables() are emitted as one markdown block; text inside them is skipped.
- `kind: heading` and `level` are a heuristic guess (size / bold / caps / numbering) for the chunker to use.
Re-parses a document only when its manifest sha256 differs from the one it was last parsed at.

Run: uv run python -m cleanair.ingest.parse [doc_id ...] [--force] [--outline]
"""

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path

import pymupdf

from cleanair.ingest.download import read_manifest

OCR_MIN_CHARS = 50  # SPEC §6.1: OCR a page that has less text than this
HEADING_MAX_CHARS = 150
SIZE_RATIO = 1.15  # a block this much larger than body text counts as a heading
NUMBERED = re.compile(r"^(\d+(\.\d+)*\.?|[IVX]+\.)\s+\S")  # "3.2 Actions", "IV. Stage"
KEYWORD = re.compile(r"^(CHAPTER|PART|SCHEDULE|ANNEXURE|APPENDIX|STAGE)\b", re.IGNORECASE)
DEFAULT_TESSDATA = Path(r"C:\Program Files\Tesseract-OCR\tessdata")


def find_tessdata() -> str | None:
    """TESSDATA_PREFIX env var wins; otherwise the default Windows install location."""
    path = os.environ.get("TESSDATA_PREFIX") or (str(DEFAULT_TESSDATA) if DEFAULT_TESSDATA.exists() else None)
    return path


def ocr_language(doc_language: str, tessdata: str | None) -> str:
    if doc_language == "hi" and tessdata and (Path(tessdata) / "hin.traineddata").exists():
        return "hin+eng"
    return "eng"  # Hindi pages without hin.traineddata come out as garbage; see TODO T1.3


def _raw_blocks(page: pymupdf.Page, textpage=None) -> list[dict]:
    blocks = []
    for b in page.get_text("dict", textpage=textpage, sort=True)["blocks"]:
        if b["type"] != 0:  # image block
            continue
        spans = [s for line in b["lines"] for s in line["spans"] if s["text"].strip()]
        if not spans:
            continue
        text = "\n".join("".join(s["text"] for s in line["spans"]).strip() for line in b["lines"]).strip()
        sizes = Counter()
        for s in spans:
            sizes[round(s["size"], 1)] += len(s["text"])
        blocks.append(
            {
                "text": text,
                "bbox": b["bbox"],
                "size": sizes.most_common(1)[0][0],
                "bold": all(s["flags"] & 16 or "bold" in s["font"].lower() for s in spans),
                "lines": len(b["lines"]),
            }
        )
    return blocks


def _inside(bbox, rect) -> bool:
    cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    return rect[0] <= cx <= rect[2] and rect[1] <= cy <= rect[3]


def _page_items(page: pymupdf.Page, lang: str, tessdata: str | None) -> list[dict]:
    """Blocks of one page in reading order, tables merged in by vertical position."""
    if len(page.get_text().strip()) >= OCR_MIN_CHARS:
        tables = [t for t in page.find_tables().tables if t.row_count >= 2 and t.col_count >= 2]
        rects = [t.bbox for t in tables]
        items = [
            {**b, "ocr": False} for b in _raw_blocks(page) if not any(_inside(b["bbox"], r) for r in rects)
        ]
        for t in tables:
            items.append({"kind": "table", "text": t.to_markdown().strip(), "bbox": t.bbox, "ocr": False})
        return sorted(items, key=lambda i: (round(i["bbox"][1]), i["bbox"][0]))
    if tessdata is None:
        print(f"  warning: page {page.number + 1} needs OCR but no tessdata found; skipped")
        return []
    textpage = page.get_textpage_ocr(language=lang, dpi=300, full=True, tessdata=tessdata)
    return [{**b, "ocr": True} for b in _raw_blocks(page, textpage)]


def _is_heading(item: dict, body_size: float) -> bool:
    text = item["text"]
    if len(text) > HEADING_MAX_CHARS or item["lines"] > 2:
        return False
    letters = re.findall(r"[A-Za-z]", text)
    return (
        item["size"] >= body_size * SIZE_RATIO
        or item["bold"]
        or bool(KEYWORD.match(text))
        or (len(letters) >= 4 and text.isupper())
        or (bool(NUMBERED.match(text)) and not text.endswith((".", ";", ",", ":")))
    )


def parse_pdf(path: Path, doc_id: str, doc_language: str = "en", tessdata: str | None = None) -> list[dict]:
    lang = ocr_language(doc_language, tessdata)
    with pymupdf.open(path) as doc:
        pages = [(page.number + 1, _page_items(page, lang, tessdata)) for page in doc]

    # Body size = the font size covering the most characters in the document.
    weight = Counter()
    for _, items in pages:
        for i in items:
            if i.get("kind") != "table":
                weight[i["size"]] += len(i["text"])
    body_size = weight.most_common(1)[0][0] if weight else 0.0

    blocks = []
    for page_no, items in pages:
        for i in items:
            kind = i.get("kind") or ("heading" if _is_heading(i, body_size) else "text")
            blocks.append(
                {
                    "doc_id": doc_id,
                    "page": page_no,
                    "kind": kind,
                    "level": None,
                    "text": i["text"],
                    "size": i.get("size"),
                    "bold": i.get("bold"),
                    "ocr": i["ocr"],
                }
            )

    # ponytail: level = rank of the heading's font size (largest = 1), capped at 3. Ignores numbering depth;
    # refine if the T1.4 hand-check shows flat outlines for documents that number headings at body size.
    sizes = sorted({b["size"] for b in blocks if b["kind"] == "heading"}, reverse=True)
    for b in blocks:
        if b["kind"] == "heading":
            b["level"] = min(sizes.index(b["size"]) + 1, 3)
    return blocks


def print_outline(blocks: list[dict]) -> None:
    for b in blocks:
        if b["kind"] == "heading":
            print(f"{'  ' * (b['level'] - 1)}{b['text'][:90].replace(chr(10), ' ')}  (p{b['page']})")
        elif b["kind"] == "table":
            print(f"  [table p{b['page']}, {b['text'].count(chr(10)) + 1} lines]")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Parse raw PDFs into blocks in data/processed/.")
    p.add_argument("doc_ids", nargs="*", help="only these documents (default: all)")
    p.add_argument("--manifest", type=Path, default=Path("data/manifest.csv"))
    p.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    p.add_argument("--out-dir", type=Path, default=Path("data/processed"))
    p.add_argument("--force", action="store_true", help="re-parse even if unchanged")
    p.add_argument("--outline", action="store_true", help="print the detected heading outline")
    args = p.parse_args(argv)

    tessdata = find_tessdata()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    state_path = args.out_dir / "_parsed.json"  # {doc_id: sha256 it was parsed from}
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}

    failed = 0
    for row in read_manifest(args.manifest):
        doc_id, src = row["doc_id"], args.raw_dir / f"{row['doc_id']}.pdf"
        out = args.out_dir / f"{doc_id}.jsonl"
        if args.doc_ids and doc_id not in args.doc_ids:
            continue
        if not src.exists():
            print(f"missing    {doc_id} (run the downloader first)")
            failed += 1
            continue
        if not args.force and out.exists() and state.get(doc_id) == row["sha256"] and not args.outline:
            print(f"unchanged  {doc_id}")
            continue
        try:
            blocks = parse_pdf(src, doc_id, row["language"], tessdata)
        except Exception as e:  # a broken PDF must not stop the batch
            print(f"failed     {doc_id}: {type(e).__name__}: {e}")
            failed += 1
            continue
        with open(out, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(b, ensure_ascii=False) + "\n" for b in blocks)
        state[doc_id] = row["sha256"]
        state_path.write_text(json.dumps(state, indent=1), encoding="utf-8")
        kinds = Counter(b["kind"] for b in blocks)
        ocr = len({b["page"] for b in blocks if b["ocr"]})
        print(
            f"parsed     {doc_id}: {max((b['page'] for b in blocks), default=0)} pages, "
            f"{kinds['heading']} headings, {kinds['text']} text, {kinds['table']} tables, {ocr} OCR pages"
        )
        if args.outline:
            print_outline(blocks)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
