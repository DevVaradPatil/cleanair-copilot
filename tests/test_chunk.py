import re

import pytest

from cleanair.ingest.chunk import fixed_chunker, structure_chunker


def ws_tokenize(text):  # one token per whitespace-separated word; stands in for the HF tokenizer
    return [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]


def ws_count(text):
    return len(text.split())


def block(text, page, kind="text", level=None):
    return {"doc_id": "d", "page": page, "kind": kind, "level": level, "text": text, "ocr": False}


WORDS = [f"w{i}" for i in range(230)]
DOC = [block(" ".join(WORDS[:120]), 1), block(" ".join(WORDS[120:]), 2)]


# ---------- fixed_chunker (A0 baseline) ----------


def test_fixed_windows_have_size_and_overlap():
    chunks = fixed_chunker(DOC, "d", ws_tokenize, size=100, overlap=20)
    words = [c["text"].split() for c in chunks]
    assert all(len(w) <= 100 for w in words)
    assert [len(w) for w in words] == [100, 100, 70]  # steps of 80 over 230 tokens
    assert words[0][-20:] == words[1][:20]  # exactly `overlap` tokens shared


def test_fixed_covers_whole_document_and_tracks_pages():
    chunks = fixed_chunker(DOC, "d", ws_tokenize, size=100, overlap=20)
    assert chunks[0]["text"].split()[0] == "w0" and chunks[-1]["text"].split()[-1] == "w229"
    assert (chunks[0]["page_start"], chunks[0]["page_end"]) == (1, 1)  # w0..w99
    assert (chunks[1]["page_start"], chunks[1]["page_end"]) == (1, 2)  # w80..w179 crosses the page
    assert [c["chunk_id"] for c in chunks] == ["d::fixed::c000", "d::fixed::c001", "d::fixed::c002"]


def test_fixed_small_doc_is_one_chunk_and_bad_overlap_rejected():
    assert len(fixed_chunker([block("just a few words", 1)], "d", ws_tokenize, size=100, overlap=20)) == 1
    with pytest.raises(ValueError):
        fixed_chunker(DOC, "d", ws_tokenize, size=50, overlap=50)


# ---------- structure_chunker (🧠, explained in docs/BRAIN_NOTES.md). These tests are its specification. ----------

LONG = " ".join(f"Sentence number {i} explains a dust control measure for construction sites." for i in range(12))
TABLE = "|Action|Agency|\n|---|---|\n" + "\n".join(f"|Stop activity {i} immediately|Agency {i}|" for i in range(4))
STRUCT_DOC = [
    block("Revised GRAP", 1, "heading", 1),
    block("Stage III", 2, "heading", 2),
    block("Ban on construction. Trucks are stopped at borders.", 2),
    block("Stage IV", 3, "heading", 2),
    block(TABLE, 3, "table"),
    block("Dust", 4, "heading", 2),
    block(LONG, 4),
]


def run(max_tokens=40, overlap=6):
    return structure_chunker(STRUCT_DOC, "d", ws_count, max_tokens=max_tokens, overlap=overlap)


def test_struct_heading_path_and_embed_text():
    chunks, _ = run()
    c = next(c for c in chunks if "Ban on construction" in c["text"])
    assert c["heading_path"] == "Revised GRAP › Stage III"
    assert c["embed_text"] == c["heading_path"] + "\n" + c["text"]


def test_struct_respects_max_tokens():
    chunks, _ = run(max_tokens=40)
    assert all(ws_count(c["text"]) <= 40 for c in chunks)


def test_struct_sections_are_not_mixed():
    chunks, _ = run()
    assert not any("Ban on construction" in c["text"] and "Stop activity" in c["text"] for c in chunks)


def test_struct_small_table_kept_whole():
    chunks, _ = run(max_tokens=60)
    assert sum(TABLE in c["text"] for c in chunks) == 1


def test_struct_big_table_split_only_between_rows():
    chunks, _ = run(max_tokens=12)
    for c in chunks:
        for line in c["text"].splitlines():
            if line.startswith("|"):
                assert line.endswith("|"), f"row cut mid-way: {line!r}"


def test_struct_long_paragraph_split_with_overlap():
    chunks, _ = run(max_tokens=40, overlap=6)
    dust = [c["text"].split() for c in chunks if c["heading_path"].endswith("Dust")]
    assert len(dust) >= 2
    assert set(dust[0][-6:]) & set(dust[1][:12]), "consecutive pieces of one section should overlap"


def test_struct_parents_and_ids():
    chunks, parents = run()
    parent_ids = {p["parent_id"] for p in parents}
    assert all(c["parent_id"] in parent_ids for c in chunks)
    assert len({c["chunk_id"] for c in chunks}) == len(chunks)
    assert all(re.fullmatch(r"d::[^:]+::c\d{2,}", c["chunk_id"]) for c in chunks)
    table_chunk = next(c for c in chunks if "Stop activity 0" in c["text"])
    assert table_chunk["page_start"] == 3
