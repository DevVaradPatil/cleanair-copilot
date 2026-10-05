"""Download every document in data/manifest.csv to data/raw/<doc_id>.pdf and record its sha256.

Idempotent: a file already on disk whose hash matches the manifest is skipped without any network call.
--refresh re-downloads everything and reports which sources changed upstream (status "changed"),
so later stages know what to re-process.

Run: uv run python -m cleanair.ingest.download [--refresh]
"""

import argparse
import csv
import hashlib
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import date
from pathlib import Path

# Some government portals reject Python's default User-Agent.
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"


def fetch(url: str, retries: int = 3, timeout: int = 120) -> bytes:
    """GET with retries on timeouts and 5xx (India Code returns intermittent 504s). 4xx fails immediately."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError) as e:
            permanent = isinstance(e, urllib.error.HTTPError) and e.code < 500
            if permanent or attempt == retries - 1:
                raise
            time.sleep(5 * 2**attempt)
    raise AssertionError("unreachable")


def clean_pdf(data: bytes) -> bytes:
    """Return the PDF bytes, dropping any HTML prefix (some PRANA files ship one before %PDF).

    Raises ValueError if this isn't a PDF at all, e.g. an error page served with status 200.
    """
    start = data.find(b"%PDF-", 0, 4096)
    if start == -1:
        raise ValueError(f"not a PDF (starts with {data[:40]!r})")
    return data[start:]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_manifest(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    tmp = path.with_suffix(".tmp")  # write-then-rename so a crash never leaves a half-written manifest
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)


def sync(
    rows: list[dict[str, str]],
    raw_dir: Path,
    refresh: bool = False,
    fetch: Callable[[str], bytes] = fetch,
) -> dict[str, str]:
    """Download what's needed, updating rows' sha256/retrieved_on in place. Returns {doc_id: status}."""
    status = {}
    for row in rows:
        doc_id, path = row["doc_id"], raw_dir / f"{row['doc_id']}.pdf"
        if not refresh and row["sha256"] and path.exists() and sha256(path.read_bytes()) == row["sha256"]:
            status[doc_id] = "unchanged"
        else:
            try:
                data = clean_pdf(fetch(row["source_url"]))
            except Exception as e:  # one bad source must not stop the other 48
                status[doc_id] = f"failed: {type(e).__name__}: {e}"
            else:
                digest = sha256(data)
                if not row["sha256"]:
                    status[doc_id] = "new"
                else:
                    status[doc_id] = "unchanged" if digest == row["sha256"] else "changed"
                path.write_bytes(data)
                row["sha256"], row["retrieved_on"] = digest, date.today().isoformat()
        print(f"{status[doc_id][:70]:<70} {doc_id}", flush=True)
    return status


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Download manifest documents into data/raw/.")
    p.add_argument("--manifest", type=Path, default=Path("data/manifest.csv"))
    p.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    p.add_argument("--refresh", action="store_true", help="re-download everything to detect upstream changes")
    args = p.parse_args(argv)

    rows = read_manifest(args.manifest)
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    status: dict[str, str] = {}
    try:
        status = sync(rows, args.raw_dir, refresh=args.refresh)
    finally:  # record whatever finished, even on Ctrl+C
        write_manifest(args.manifest, rows)

    counts: dict[str, int] = {}
    for s in status.values():
        counts[s.split(":")[0]] = counts.get(s.split(":")[0], 0) + 1
    print("summary:", counts)
    return 1 if counts.get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
