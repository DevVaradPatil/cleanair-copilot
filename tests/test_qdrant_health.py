"""Health check for local Qdrant.

Needs `docker compose up -d qdrant`; run with `uv run pytest -m integration`.
"""

import json
import urllib.request

import pytest

from cleanair.settings import Settings


@pytest.mark.integration
def test_qdrant_is_up(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "unused")  # only qdrant_url matters here
    url = Settings().qdrant_url
    with urllib.request.urlopen(f"{url}/healthz", timeout=5) as r:
        assert r.status == 200
    with urllib.request.urlopen(url, timeout=5) as r:
        print("qdrant version:", json.load(r)["version"])
