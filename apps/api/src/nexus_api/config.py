"""API configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


DEV_SESSION_TOKEN = "nexus-dev-session-token"

#: Origins allowed while the session token is the published development
#: constant. The Vite dev server is the only browser that legitimately talks to
#: a sidecar running under that token, and it is reachable under both spellings
#: of loopback - which the browser treats as two distinct origins.
DEV_CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def _session_token() -> str:
    """Per-session bearer token supplied by the process that spawned the sidecar.

    The Electron shell generates a fresh token per launch and passes it through
    the environment, so it is never written to disk. When unset we fall back to
    a well-known development token so `make dev-api` keeps working.
    """
    return os.environ.get("NEXUS_API_SESSION_TOKEN", "").strip() or DEV_SESSION_TOKEN


def _cors_origins(session_token: str) -> list[str]:
    """Origins the browser is told it may read responses from.

    The session token, not the origin, is the security boundary: a cross-origin
    page cannot obtain the token, and an origin allowlist cannot stop a local
    process that is not a browser at all. A packaged Electron renderer loads
    over ``file://`` and therefore sends ``Origin: null``, which no useful
    allowlist contains, so the unrestricted default is what makes the shipped
    shell work at all.

    That reasoning holds only while the token is actually a secret. When
    ``NEXUS_API_SESSION_TOKEN`` is unset the token is :data:`DEV_SESSION_TOKEN`,
    a constant published in this repository and embedded in the built web
    bundle - so any page the user happens to visit could both guess the
    credential and read the response. In that one case the origin has to carry
    the boundary the token cannot, and the default narrows to the dev server.
    Setting ``NEXUS_API_CORS_ORIGINS`` is an explicit override of both.
    """
    raw = os.environ.get("NEXUS_API_CORS_ORIGINS", "").strip()
    if raw:
        return [part.strip() for part in raw.split(",") if part.strip()]
    if session_token == DEV_SESSION_TOKEN:
        return list(DEV_CORS_ORIGINS)
    return ["*"]


@dataclass(frozen=True)
class Settings:
    cors_origins: list[str]
    session_token: str = DEV_SESSION_TOKEN
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


def load_settings() -> Settings:
    session_token = _session_token()
    return Settings(
        cors_origins=_cors_origins(session_token),
        session_token=session_token,
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
    )


settings = load_settings()
