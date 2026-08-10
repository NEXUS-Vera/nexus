"""API configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _cors_origins() -> list[str]:
    raw = os.environ.get(
        "NEXUS_API_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    return [part.strip() for part in raw.split(",") if part.strip()]


@dataclass(frozen=True)
class Settings:
    cors_origins: list[str]
    host: str = "127.0.0.1"
    port: int = 8000
    initialization_provider: str = "fixture"
    storage_backend: str = "memory"
    database_url: str = "postgresql+psycopg://nexus:nexus@localhost:5432/nexus"
    model_provider: str = "openai"
    model_name: str = "gpt-4.1-mini"
    model_credential: str = ""
    model_base_url: str = "https://api.openai.com/v1"
    model_timeout_seconds: float = 60.0
    model_max_repair_attempts: int = 1
    wokwi_cli_executable: str = "wokwi-cli"
    wokwi_cli_token: str = ""
    wokwi_firmware_elf: str = ""


def load_settings() -> Settings:
    return Settings(
        cors_origins=_cors_origins(),
        host=os.environ.get("NEXUS_API_HOST", "127.0.0.1"),
        port=int(os.environ.get("NEXUS_API_PORT", "8000")),
        initialization_provider=os.environ.get("NEXUS_INITIALIZATION_PROVIDER", "fixture")
        .strip()
        .lower(),
        storage_backend=os.environ.get("NEXUS_STORAGE_BACKEND", "memory").strip().lower(),
        database_url=os.environ.get(
            "NEXUS_DATABASE_URL",
            "postgresql+psycopg://nexus:nexus@localhost:5432/nexus",
        ),
        model_provider=os.environ.get("NEXUS_MODEL_PROVIDER", "openai"),
        model_name=os.environ.get("NEXUS_MODEL_NAME", "gpt-4.1-mini"),
        model_credential=os.environ.get("NEXUS_MODEL_API_KEY", ""),
        model_base_url=os.environ.get("NEXUS_MODEL_BASE_URL", "https://api.openai.com/v1"),
        model_timeout_seconds=float(os.environ.get("NEXUS_MODEL_TIMEOUT_SECONDS", "60")),
        model_max_repair_attempts=int(os.environ.get("NEXUS_MODEL_MAX_REPAIR_ATTEMPTS", "1")),
        wokwi_cli_executable=os.environ.get("NEXUS_WOKWI_CLI", "wokwi-cli"),
        wokwi_cli_token=os.environ.get("WOKWI_CLI_TOKEN", ""),
        wokwi_firmware_elf=os.environ.get("NEXUS_WOKWI_FIRMWARE_ELF", ""),
    )


settings = load_settings()
