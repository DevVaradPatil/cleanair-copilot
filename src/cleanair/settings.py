"""Secrets and machine-specific settings, read from environment variables / .env.

Experiment choices (chunker, retrieval, routing...) live in configs/*.yaml instead; see config.py.
"""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: SecretStr  # required: fails at startup if missing
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr | None = None  # only needed for Qdrant Cloud
