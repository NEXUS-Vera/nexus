"""Both HTTP gateways keep urllib transport and response reads off the event loop."""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any
from urllib import error

import pytest
from nexus_model_gateway import AnthropicGateway, ModelPolicy, OpenAICompatibleGateway


@pytest.mark.parametrize("gateway_type", [OpenAICompatibleGateway, AnthropicGateway])
@pytest.mark.parametrize("retry", [False, True])
async def test_http_transport_runs_off_event_loop(
    monkeypatch: pytest.MonkeyPatch,
    gateway_type: type[OpenAICompatibleGateway] | type[AnthropicGateway],
    retry: bool,
) -> None:
    loop = asyncio.get_running_loop()
    loop_thread = threading.get_ident()
    scheduled = threading.Event()
    attempts = 0
    policy = ModelPolicy(provider="test", model="test", timeout_seconds=17.0)

    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def read(self) -> bytes:
            assert threading.get_ident() != loop_thread
            payload: dict[str, Any]
            if gateway_type is OpenAICompatibleGateway:
                payload = {"choices": [{"message": {"content": '{"ok": true}'}}]}
            else:
                payload = {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "emit_structured_output",
                            "input": {"ok": True},
                        }
                    ]
                }
            return json.dumps(payload).encode()

    def urlopen(req: Any, *, timeout: float) -> Response:
        nonlocal attempts
        assert threading.get_ident() != loop_thread
        assert timeout == policy.timeout_seconds
        # The loop must execute another callback while this synchronous call waits.
        loop.call_soon_threadsafe(scheduled.set)
        assert scheduled.wait(timeout=2)
        scheduled.clear()
        attempts += 1
        if retry and attempts == 1:
            raise error.URLError("temporary failure")
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    result = await gateway_type(model_credential="test-credential").generate_structured(
        task_name="off-loop-test",
        system_instructions="Return JSON.",
        input_payload={},
        output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
        model_policy=policy,
    )
    assert result.parsed_output == {"ok": True}
    assert result.retry_count == int(retry)
    assert attempts == 1 + int(retry)
