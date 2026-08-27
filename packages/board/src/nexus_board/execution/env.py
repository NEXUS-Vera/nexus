"""Explicit allowlisted environment construction for sandboxed jobs."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping

# Never copy these from the host process, even if present in approved values.
BLOCKED_HOST_KEYS = frozenset(
    {
        "WOKWI_CLI_TOKEN",
        "NEXUS_DATABASE_URL",
        "NEXUS_MODEL_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_SECURITY_TOKEN",
        "DATABASE_URL",
        "PGPASSWORD",
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "NPM_TOKEN",
        "DOCKER_AUTH_CONFIG",
    }
)


def default_sandbox_path() -> str:
    """Build a minimal PATH for basename executable lookup.

    Includes ``os.defpath`` plus the directory of the current interpreter so
    local/dev/test fixtures can use ``python3`` without allowing absolute host
    paths in ``commandSpec.executable``.
    """
    parts = [os.defpath]
    interp_dir = os.path.dirname(os.path.realpath(sys.executable))
    if interp_dir and interp_dir not in parts:
        parts.append(interp_dir)
    return os.pathsep.join(parts)


def build_sandbox_environment(
    approved: Mapping[str, str],
    *,
    path: str | None = None,
) -> dict[str, str]:
    """Build a minimal process environment with no host secret inheritance.

    Only ``PATH`` (sanitized) and explicitly approved non-secret values are included.
    """
    env: dict[str, str] = {
        "PATH": path if path is not None else default_sandbox_path(),
        "HOME": "/tmp",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
    }
    for key, value in approved.items():
        upper = key.upper()
        if key in BLOCKED_HOST_KEYS or upper in BLOCKED_HOST_KEYS:
            continue
        if any(
            token in upper for token in ("SECRET", "TOKEN", "PASSWORD", "API_KEY", "CREDENTIAL")
        ):
            continue
        env[key] = value
    return env


def assert_no_host_secrets(env: Mapping[str, str]) -> None:
    for key in env:
        if key in BLOCKED_HOST_KEYS or key.upper() in BLOCKED_HOST_KEYS:
            raise ValueError(f"Sandbox environment contains blocked key: {key}")
