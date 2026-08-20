"""Loopback sidecar hardening tests (issue #43).

These exercise the public HTTP/process surface the Electron shell will drive:
session-token auth, the stdout port handshake, and parent-death lifecycle.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api.main import app


@pytest.mark.asyncio
async def test_request_without_session_token_is_401() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/projects/proj_abcdefghijklmnop")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_TOKEN_REQUIRED"
