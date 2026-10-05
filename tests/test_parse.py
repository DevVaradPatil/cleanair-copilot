import pymupdf
import pytest

from cleanair.ingest.parse import find_tessdata, parse_pdf

BODY = "The Commission shall take measures to control dust from construction sites in the region. " * 3


def make_pdf(path, build):
    doc = pymupdf.open()
    build(doc)
    doc.save(path)
    doc.close()
    return path


def text_page(doc):
    page = doc.new_page()
    page.insert_text((72, 80), "CHAPTER II", fontsize=16, fontname="hebo")
    page.insert_text((72, 110), "3.2 Actions to be taken", fontsize=11, fontname="hebo")
    page.insert_textbox(pymupdf.Rect(72, 130, 520, 300), BODY, fontsize=11, fontname="helv")


def test_headings_and_body_are_separated(tmp_path):
    blocks = parse_pdf(make_pdf(tmp_path / "a.pdf", text_page), "doc-a")
    kind = {b["text"][:20]: b["kind"] for b in blocks}
    assert kind["CHAPTER II"] == "heading"
    assert kind["3.2 Actions to be ta"] == "heading"
    assert kind[BODY[:20]] == "text"
    assert all(b["page"] == 1 and b["doc_id"] == "doc-a" and not b["ocr"] for b in blocks)


def test_bigger_heading_gets_higher_level(tmp_path):
    blocks = parse_pdf(make_pdf(tmp_path / "a.pdf", text_page), "doc-a")
    level = {b["text"]: b["level"] for b in blocks if b["kind"] == "heading"}
    assert level["CHAPTER II"] < level["3.2 Actions to be taken"]


def test_long_numbered_sentence_is_not_a_heading(tmp_path):
    def build(doc):
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(72, 72, 520, 200), "1. This Act may be called the Air Act.", fontsize=11)
        page.insert_textbox(pymupdf.Rect(72, 220, 520, 400), BODY, fontsize=11)

    blocks = parse_pdf(make_pdf(tmp_path / "b.pdf", build), "doc-b")
    assert all(b["kind"] == "text" for b in blocks)


def test_table_becomes_one_markdown_block(tmp_path):
    def build(doc):
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(72, 40, 520, 140), BODY, fontsize=11)
        rows = [
            ["Pollutant", "Time weighted average", "Limit"],
            ["PM2.5", "24 hours", "60"],
            ["PM10", "24 hours", "100"],
        ]
        x, y, w, h = 72, 160, 150, 30  # cells tall enough that insert_textbox doesn't drop the text
        for r, row in enumerate(rows):
            for c, cell in enumerate(row):
                rect = pymupdf.Rect(x + c * w, y + r * h, x + (c + 1) * w, y + (r + 1) * h)
                page.draw_rect(rect, color=(0, 0, 0), width=0.8)
                page.insert_textbox(rect + (4, 4, -4, -4), cell, fontsize=10)

    blocks = parse_pdf(make_pdf(tmp_path / "t.pdf", build), "doc-t")
    tables = [b for b in blocks if b["kind"] == "table"]
    assert len(tables) == 1 and "PM2.5" in tables[0]["text"] and "|" in tables[0]["text"]
    assert not any("PM2.5" in b["text"] for b in blocks if b["kind"] != "table")  # no duplicate cell text


@pytest.mark.skipif(find_tessdata() is None, reason="Tesseract tessdata not installed")
def test_scanned_page_is_ocred(tmp_path):
    src = make_pdf(tmp_path / "src.pdf", text_page)
    with pymupdf.open(src) as d:
        png = d[0].get_pixmap(dpi=200).tobytes("png")

    def build(doc):  # a page that is only an image of text, like a scan
        doc.new_page().insert_image(pymupdf.Rect(0, 0, 595, 842), stream=png)

    blocks = parse_pdf(make_pdf(tmp_path / "scan.pdf", build), "doc-s", tessdata=find_tessdata())
    text = " ".join(b["text"] for b in blocks)
    assert all(b["ocr"] for b in blocks)
    assert "Commission" in text and "dust" in text
