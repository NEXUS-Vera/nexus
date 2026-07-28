"""API configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _cors_origins() -> list[str]:
    raw = os.environ.get("NEXUS_API_CORS_ORIGINS", "http://localhost:5173")
    return [part.strip() for part in raw.split(",") if part.strip()]


@dataclass(frozen=True)
class Settings:
    cors_origins: list[str]
    host: str = "127.0.0.1"
    port: int = 8000


settings = Settings(cors_origins=_cors_origins())
