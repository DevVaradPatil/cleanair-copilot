import pytest

from cleanair.ingest.download import clean_pdf, read_manifest, sha256, sync, write_manifest

PDF_V1 = b"%PDF-1.5 version one"
PDF_V2 = b"%PDF-1.5 version two"


def row(doc_id="doc-a", url="https://example.gov.in/a.pdf"):
    return {"doc_id": doc_id, "title": "वायु अधिनियम", "source_url": url, "retrieved_on": "", "sha256": ""}


class FakeFetch:
    """Stands in for the network: returns canned bytes per URL and counts calls."""

    def __init__(self, responses):
        self.responses, self.calls = responses, 0

    def __call__(self, url):
        self.calls += 1
        resp = self.responses[url]
        if isinstance(resp, Exception):
            raise resp
        return resp


def test_clean_pdf_strips_html_prefix():
    assert clean_pdf(b"<html><body>\n" + PDF_V1) == PDF_V1


def test_clean_pdf_rejects_non_pdf():
    with pytest.raises(ValueError, match="not a PDF"):
        clean_pdf(b"<html>404 Not Found</html>")


def test_first_run_downloads_and_records_hash(tmp_path):
    rows = [row()]
    status = sync(rows, tmp_path, fetch=FakeFetch({rows[0]["source_url"]: PDF_V1}))
    assert status == {"doc-a": "new"}
    assert (tmp_path / "doc-a.pdf").read_bytes() == PDF_V1
    assert rows[0]["sha256"] == sha256(PDF_V1)
    assert rows[0]["retrieved_on"]


def test_rerun_skips_unchanged_without_network(tmp_path):
    rows = [row()]
    sync(rows, tmp_path, fetch=FakeFetch({rows[0]["source_url"]: PDF_V1}))
    fake = FakeFetch({})
    assert sync(rows, tmp_path, fetch=fake) == {"doc-a": "unchanged"}
    assert fake.calls == 0


def test_refresh_detects_upstream_change(tmp_path):
    rows = [row()]
    url = rows[0]["source_url"]
    sync(rows, tmp_path, fetch=FakeFetch({url: PDF_V1}))
    assert sync(rows, tmp_path, refresh=True, fetch=FakeFetch({url: PDF_V2})) == {"doc-a": "changed"}
    assert rows[0]["sha256"] == sha256(PDF_V2)


def test_tampered_local_file_is_redownloaded(tmp_path):
    rows = [row()]
    url = rows[0]["source_url"]
    sync(rows, tmp_path, fetch=FakeFetch({url: PDF_V1}))
    (tmp_path / "doc-a.pdf").write_bytes(b"corrupted")
    fake = FakeFetch({url: PDF_V1})
    assert sync(rows, tmp_path, fetch=fake) == {"doc-a": "unchanged"}
    assert fake.calls == 1 and (tmp_path / "doc-a.pdf").read_bytes() == PDF_V1


def test_one_failure_does_not_stop_the_rest(tmp_path):
    rows = [row("bad", "https://x/bad.pdf"), row("good", "https://x/good.pdf")]
    fake = FakeFetch({"https://x/bad.pdf": TimeoutError("slow server"), "https://x/good.pdf": PDF_V1})
    status = sync(rows, tmp_path, fetch=fake)
    assert status["bad"].startswith("failed") and status["good"] == "new"
    assert rows[0]["sha256"] == ""  # failed row keeps no stale hash


def test_manifest_roundtrip_keeps_devanagari(tmp_path):
    path = tmp_path / "manifest.csv"
    write_manifest(path, [row()])
    assert read_manifest(path) == [row()]
