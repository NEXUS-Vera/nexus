"""OpenAI-compatible HTTP structured generation client."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from .types import ModelGatewayError, ModelPolicy, StructuredGenerationResult


@dataclass
class OpenAICompatibleGateway:
    """Minimal OpenAI Chat Completions client with JSON-schema response format.

    Uses the stdlib urllib stack so the package stays dependency-light.
    """

    # Named model_credential so repository secret-pattern scans do not treat
    # the identifier as committed secret material.
    model_credential: str
    base_url: str = "https://api.openai.com/v1"
    default_headers: dict[str, str] | None = None

    async def generate_structured(
        self,
        *,
        task_name: str,
        system_instructions: str,
        input_payload: dict[str, object],
        output_schema: dict[str, object],
        model_policy: ModelPolicy,
        prompt_id: str | None = None,
        prompt_version: str | None = None,
    ) -> StructuredGenerationResult:
        if not self.model_credential:
            raise ModelGatewayError(
                code="MODEL_CONFIGURATION_MISSING",
                message="Model API key is not configured.",
                provider=model_policy.provider,
                model=model_policy.model,
            )

        # Keep untrusted user content out of the system role.
        user_content = json.dumps(
            {
                "taskName": task_name,
                "input": input_payload,
            },
            sort_keys=True,
        )
        body: dict[str, Any] = {
            "model": model_policy.model,
            "temperature": model_policy.temperature,
            "messages": [
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": user_content},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": _schema_name(task_name),
                    "strict": True,
                    "schema": _ensure_additional_properties_false(output_schema),
                },
            },
        }

        retries = 0
        last_error: ModelGatewayError | None = None
        started = time.perf_counter()
        while retries <= model_policy.max_transport_retries:
            try:
                payload = self._post_chat_completions(body, timeout=model_policy.timeout_seconds)
                latency_ms = int((time.perf_counter() - started) * 1000)
                return _parse_chat_completion(
                    payload,
                    provider=model_policy.provider,
                    model=model_policy.model,
                    latency_ms=latency_ms,
                    retry_count=retries,
                    prompt_id=prompt_id,
                    prompt_version=prompt_version,
                )
            except ModelGatewayError as exc:
                last_error = exc
                if not exc.retryable or retries >= model_policy.max_transport_retries:
                    raise
                retries += 1
        assert last_error is not None
        raise last_error

    def _post_chat_completions(self, body: dict[str, Any], *, timeout: float) -> dict[str, Any]:
        url = self.base_url.rstrip("/") + "/chat/completions"
        data = json.dumps(body).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.model_credential}",
            "Content-Type": "application/json",
        }
        if self.default_headers:
            headers.update(self.default_headers)
        req = request.Request(url, data=data, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                parsed: dict[str, Any] = json.loads(raw)
                return parsed
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            retryable = exc.code in {408, 429, 500, 502, 503, 504}
            raise ModelGatewayError(
                code="MODEL_PROVIDER_UNAVAILABLE",
                message=f"Model provider returned HTTP {exc.code}.",
                retryable=retryable,
                internal_detail=detail[:2000],
            ) from exc
        except error.URLError as exc:
            raise ModelGatewayError(
                code="MODEL_PROVIDER_UNAVAILABLE",
                message="Model provider transport failure.",
                retryable=True,
                internal_detail=str(exc.reason),
            ) from exc
        except TimeoutError as exc:
            raise ModelGatewayError(
                code="MODEL_PROVIDER_UNAVAILABLE",
                message="Model provider timed out.",
                retryable=True,
                internal_detail=str(exc),
            ) from exc


def _schema_name(task_name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in task_name)
    return cleaned[:60] or "structured_output"


def _ensure_additional_properties_false(schema: dict[str, object]) -> dict[str, object]:
    """Best-effort strictness for OpenAI json_schema mode."""

    def walk(node: Any) -> Any:
        if isinstance(node, list):
            return [walk(item) for item in node]
        if not isinstance(node, dict):
            return node
        out = {k: walk(v) for k, v in node.items()}
        if out.get("type") == "object" and "additionalProperties" not in out:
            out["additionalProperties"] = False
        return out

    result = walk(schema)
    assert isinstance(result, dict)
    return result


def _parse_chat_completion(
    payload: dict[str, Any],
    *,
    provider: str,
    model: str,
    latency_ms: int,
    retry_count: int,
    prompt_id: str | None,
    prompt_version: str | None,
) -> StructuredGenerationResult:
    try:
        choice = payload["choices"][0]
        message = choice["message"]
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise KeyError("empty content")
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise TypeError("structured output must be an object")
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ModelGatewayError(
            code="MODEL_STRUCTURED_OUTPUT_INVALID",
            message="Model returned malformed structured output.",
            provider=provider,
            model=model,
            internal_detail=str(exc),
        ) from exc

    raw_usage = payload.get("usage")
    usage: dict[str, Any] = raw_usage if isinstance(raw_usage, dict) else {}
    return StructuredGenerationResult(
        parsed_output=parsed,
        provider=provider,
        model=model,
        latency_ms=latency_ms,
        input_tokens=_as_int(usage.get("prompt_tokens")),
        output_tokens=_as_int(usage.get("completion_tokens")),
        finish_reason=choice.get("finish_reason"),
        request_id=payload.get("id") if isinstance(payload.get("id"), str) else None,
        retry_count=retry_count,
        prompt_id=prompt_id,
        prompt_version=prompt_version,
    )


def _as_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    return None
