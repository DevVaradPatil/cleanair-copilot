import pytest
from pydantic import ValidationError

from cleanair.settings import Settings


def test_missing_api_key_fails_loudly(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValidationError, match="gemini_api_key"):
        Settings(_env_file=None)


def test_key_is_read_and_hidden(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    s = Settings(_env_file=None)
    assert s.gemini_api_key.get_secret_value() == "test-key"
    assert "test-key" not in repr(s)  # SecretStr keeps it out of logs
