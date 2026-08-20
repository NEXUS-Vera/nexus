"""Loopback sidecar hardening tests (issue #43).

These exercise the public HTTP/process surface the Electron shell will drive:
session-token auth, the stdout port handshake, and parent-death lifecycle.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api.main import app

SIDECAR_TOKEN = "test-session-token"


@pytest.mark.asyncio
async def test_request_without_session_token_is_401() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/projects/proj_abcdefghijklmnop")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_TOKEN_REQUIRED"


def _sidecar_env(**overrides: str) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(entry for entry in sys.path if entry)
    env["NEXUS_API_SESSION_TOKEN"] = SIDECAR_TOKEN
    env["NEXUS_API_PORT"] = "0"
    env.update(overrides)
    return env


def _read_handshake(process: subprocess.Popen[str], timeout: float = 30.0) -> dict[str, object]:
    """Read the single handshake line the sidecar emits on stdout."""
    result: queue.Queue[str] = queue.Queue(maxsize=1)

    def reader() -> None:
        assert process.stdout is not None
        result.put(process.stdout.readline())

    threading.Thread(target=reader, daemon=True).start()
    try:
        line = result.get(timeout=timeout)
    except queue.Empty:  # pragma: no cover - only reached on regression
        raise AssertionError("sidecar emitted no handshake line on stdout") from None
    assert line, "sidecar closed stdout without emitting a handshake line"
    return dict(json.loads(line))


def test_startup_announces_bound_port_as_json() -> None:
    process = subprocess.Popen(
        [sys.executable, "-m", "nexus_api"],
        env=_sidecar_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        handshake = _read_handshake(process)

        assert handshake["event"] == "nexus.api.listening"
        assert handshake["schemaVersion"] == "1.0.0"
        assert handshake["host"] == "127.0.0.1"
        assert handshake["pid"] == process.pid
        port = handshake["port"]
        assert isinstance(port, int)
        assert port > 0
        assert port != 8000

        # The announced port must be the port actually bound.
        response = httpx.get(
            f"http://127.0.0.1:{port}/healthz",
            headers={"Authorization": f"Bearer {SIDECAR_TOKEN}"},
            timeout=10.0,
        )
        assert response.status_code == 200
    finally:
        process.terminate()
        process.wait(timeout=10)
