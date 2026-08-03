"""Unit tests for AnthropicGateway (mocked HTTP)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch
from urllib import error

import pytest
from nexus_model_gateway import AnthropicGateway, ModelGatewayError, ModelPolicy
from nexus_model_gateway.anthropic import _CREDENTIAL_HEADER

POLICY = ModelPolicy(provider="anthropic", model="claude-sonnet-4-6")


def _messages_payload(tool_input: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "msg_test123",
        "type": "message",
        "role": "assistant",
        "model": POLICY.model,
        "content": [
            {
                "type": "tool_use",
                "id": "toolu_1",
                "name": "emit_structured_output",
                "input": tool_input,
            }
        ],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 12, "output_tokens": 34},
    }


async def test_anthropic_generate_structured_parses_tool_use() -> None:
    gateway = AnthropicGateway(model_credential="test-credential")
    body_holder: dict[str, Any] = {}

    class _Resp:
        def read(self) -> bytes:
            return json.dumps(_messages_payload({"hello": "world"})).encode("utf-8")

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_urlopen(req: Any, timeout: float = 0) -> _Resp:  # noqa: ARG001
        body_holder["url"] = req.full_url
        # urllib Request lowercases header names in .headers
        body_holder["headers"] = {k.lower(): v for k, v in req.headers.items()}
        body_holder["body"] = json.loads(req.data.decode("utf-8"))
        return _Resp()

    with patch("nexus_model_gateway.anthropic.request.urlopen", side_effect=fake_urlopen):
        result = await gateway.generate_structured(
            task_name="unit-test",
            system_instructions="Return JSON via the tool.",
            input_payload={"x": 1},
            output_schema={
                "type": "object",
                "properties": {"hello": {"type": "string"}},
                "required": ["hello"],
            },
            model_policy=POLICY,
        )

    assert result.parsed_output == {"hello": "world"}
    assert result.provider == "anthropic"
    assert result.input_tokens == 12
    assert result.output_tokens == 34
    assert result.request_id == "msg_test123"
    assert body_holder["url"] == "https://api.anthropic.com/v1/messages"
    assert body_holder["headers"][_CREDENTIAL_HEADER] == "test-credential"
    assert body_holder["headers"]["anthropic-version"] == "2023-06-01"
    assert body_holder["body"]["tool_choice"] == {
        "type": "tool",
        "name": "emit_structured_output",
    }
    assert body_holder["body"]["tools"][0]["name"] == "emit_structured_output"


async def test_anthropic_missing_credential() -> None:
    gateway = AnthropicGateway(model_credential="")
    with pytest.raises(ModelGatewayError) as exc:
        await gateway.generate_structured(
            task_name="unit-test",
            system_instructions="sys",
            input_payload={},
            output_schema={"type": "object", "properties": {}},
            model_policy=POLICY,
        )
    assert exc.value.code == "MODEL_CONFIGURATION_MISSING"


async def test_anthropic_http_401() -> None:
    gateway = AnthropicGateway(model_credential="bad-credential")

    def boom(req: Any, timeout: float = 0) -> Any:  # noqa: ARG001
        raise error.HTTPError(
            url=req.full_url,
            code=401,
            msg="Unauthorized",
            hdrs=None,  # type: ignore[arg-type]
            fp=MagicMock(read=MagicMock(return_value=b'{"error":"invalid"}')),
        )

    with (
        patch("nexus_model_gateway.anthropic.request.urlopen", side_effect=boom),
        pytest.raises(ModelGatewayError) as exc,
    ):
        await gateway.generate_structured(
            task_name="unit-test",
            system_instructions="sys",
            input_payload={},
            output_schema={"type": "object", "properties": {}},
            model_policy=POLICY,
        )
    assert exc.value.code == "MODEL_PROVIDER_UNAVAILABLE"
    assert "401" in exc.value.message
    assert exc.value.retryable is False


async def test_anthropic_malformed_without_tool_use() -> None:
    gateway = AnthropicGateway(model_credential="test-credential")

    class _Resp:
        def read(self) -> bytes:
            return json.dumps(
                {
                    "id": "msg_x",
                    "content": [{"type": "text", "text": "not a tool"}],
                    "usage": {},
                }
            ).encode("utf-8")

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    with (
        patch(
            "nexus_model_gateway.anthropic.request.urlopen",
            return_value=_Resp(),
        ),
        pytest.raises(ModelGatewayError) as exc,
    ):
        await gateway.generate_structured(
            task_name="unit-test",
            system_instructions="sys",
            input_payload={},
            output_schema={"type": "object", "properties": {}},
            model_policy=POLICY,
        )
    assert exc.value.code == "MODEL_STRUCTURED_OUTPUT_INVALID"
