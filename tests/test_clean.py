import unicodedata

from cleanair.ingest.clean import clean_doc, clean_table, clean_text, fix_glyphs


def block(text, page=1, kind="text"):
    return {"doc_id": "d", "page": page, "kind": kind, "level": None, "text": text, "ocr": False}


def test_symbol_font_glyphs_mapped():
    assert fix_glyphs("PM2.5 g/m3") == "PM2.5 µg/m3"  # Symbol-font 'm'
    assert fix_glyphs("AQI  401") == "AQI ≥ 401"
    assert fix_glyphs(" Stop C&D work") == "• Stop C&D work"
    assert fix_glyphs("odd glyph") == "odd glyph"  # unknown PUA chars dropped
    assert fix_glyphs("40 μg/m3") == "40 µg/m3"  # Greek mu unified to micro sign


def test_nfc_composes_and_keeps_devanagari():
    hindi = "वायु (प्रदूषण निवारण और नियंत्रण) अधिनियम"
    assert clean_text(hindi, "text") == hindi
    decomposed = unicodedata.normalize("NFD", "µg/m³ café")
    assert clean_text(decomposed, "text") == "µg/m³ café"


def test_prose_lines_joined_and_dehyphenated():
    assert clean_text("ensure imple-\nmentation of\nStage-\nIII  actions", "text") == (
        "ensure implementation of Stage- III actions"
    )


def test_table_tidied():
    md = (
        "|Col1|Col2|Col3|\n"
        "|---|---|---|\n"
        "|**Stage I**<br>**Poor**|**Stage I**<br>**Poor**|AQI 201-300|\n"
        "||||\n"
        "|PM2.5|24 hours|60|"
    )
    assert clean_table(md) == "||||\n|---|---|---|\n|Stage I Poor||AQI 201-300|\n|PM2.5|24 hours|60|"


def test_equal_numbers_in_adjacent_cells_are_kept():
    md = "|Pollutant|Avg|Residential|Sensitive|\n|---|---|---|---|\n|SO2|24 hours|80|80|"
    assert clean_table(md).splitlines()[-1] == "|SO2|24 hours|80|80|"


def test_repeated_headers_and_page_numbers_dropped():
    blocks = []
    topics = ["dust control on roads", "stubble burning", "industrial fuel", "vehicle emissions"]
    for page, topic in zip(range(10, 14), topics, strict=True):  # 2-digit page numbers
        blocks += [
            block(f"THE GAZETTE OF INDIA : EXTRAORDINARY {page}", page),  # header, number varies
            block(f"Clause on {topic}.", page),
            block(f"- {page} -", page),  # page number
            block("|PM10|100|", page, kind="table"),  # repeated table rows are content, not boilerplate
        ]
    kept, removed = clean_doc(blocks)
    assert removed == 8
    assert {b["kind"] for b in kept} == {"text", "table"} and len(kept) == 8
    assert not any("GAZETTE" in b["text"] for b in kept)


def test_short_doc_keeps_blocks_seen_on_one_page():
    kept, removed = clean_doc([block("Annexure I", 1), block("Body text about stubble burning.", 1)])
    assert removed == 0 and len(kept) == 2


def test_ocr_specks_dropped():
    kept, _ = clean_doc([block("| |", 1), block("Ss", 1), block("Real sentence here.", 1)])
    assert [b["text"] for b in kept] == ["Ss", "Real sentence here."]
