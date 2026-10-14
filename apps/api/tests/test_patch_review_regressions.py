"""N32 F-09/F-11: proposal calls yield the loop and validate text before generation."""

from __future__ import annotations

import asyncio
import threading
import time
from unittest.mock import Mock

import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api import main


@pytest.mark.parametrize("change", [None, "", "   ", 42, False, []])
async def test_f11_invalid_requested_change_rejected(
    change: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    generate = Mock(return_value={"status": "proposed"})
    monkeypatch.setattr(main._kernel.workspace_runtime, "propose_firmware_patch", generate)
    async with AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Authorization": "Bearer nexus-dev-session-token"},
    ) as client:
        response = await client.post(
            "/v1/projects/proj_" + "a" * 32 + "/artifacts/firmware/workspace/patch/propose",
            json={"requestedChange": change},
        )
    assert response.status_code == 422
    generate.assert_not_called()


async def test_f09_model_generation_does_not_block_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    started = threading.Event()
    release = threading.Event()

    def generate(**kwargs: object) -> dict:
        started.set()
        release.wait(1)
        return {"status": "proposed"}

    monkeypatch.setattr(main._kernel.workspace_runtime, "propose_firmware_patch", generate)
    async with AsyncClient(
        transport=ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Authorization": "Bearer nexus-dev-session-token"},
    ) as client:
        pending = asyncio.create_task(
            client.post(
                "/v1/projects/proj_" + "a" * 32 + "/artifacts/firmware/workspace/patch/propose",
                json={"requestedChange": "update LED"},
            )
        )
        loop_started = time.monotonic()
        for _ in range(50):
            if started.is_set():
                break
            await asyncio.sleep(0.01)
        try:
            assert time.monotonic() - loop_started < 0.5
            assert started.is_set()
            assert not pending.done(), "Generation held the event loop until completion"
            health = await client.get("/healthz")
            assert health.status_code == 200
        finally:
            release.set()
            await asyncio.wait_for(pending, timeout=3)
