"""Provider defaults and patch gateway diagnostics without live model calls."""

from email.message import Message
from typing import Any
from urllib.error import HTTPError

import pytest
from nexus_api import main
from nexus_api.config import load_settings
from nexus_board.errors import AnalysisPatchGenerationError, FirmwarePatchGenerationError
from nexus_model_gateway import AnthropicGateway, ModelGatewayError


@pytest.mark.parametrize(
    "provider,expected",
    [
        ("anthropic", "https://api.anthropic.com"),
        ("claude", "https://api.anthropic.com"),
        (" Anthropic ", "https://api.anthropic.com"),
        ("openai", "https://api.openai.com/v1"),
        ("other", "https://api.openai.com/v1"),
    ],
)
def test_provider_base_url(monkeypatch: pytest.MonkeyPatch, provider: str, expected: str) -> None:
    monkeypatch.setenv("NEXUS_MODEL_PROVIDER", provider)
    monkeypatch.delenv("NEXUS_MODEL_BASE_URL", raising=False)
    assert load_settings().model_base_url == expected
    monkeypatch.setenv("NEXUS_MODEL_BASE_URL", "https://gateway.example/custom")
    assert load_settings().model_base_url == "https://gateway.example/custom"


def test_default_provider_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEXUS_MODEL_PROVIDER", raising=False)
    monkeypatch.delenv("NEXUS_MODEL_BASE_URL", raising=False)
    assert load_settings().model_base_url == "https://api.openai.com/v1"


@pytest.mark.parametrize("target", ["firmware", "analysis"])
@pytest.mark.parametrize("provider", ["anthropic", "claude"])
def test_patch_gateway_default_and_safe_error_log(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, target: str, provider: str
) -> None:
    monkeypatch.setenv("NEXUS_MODEL_PROVIDER", provider)
    monkeypatch.setenv("NEXUS_MODEL_API_KEY", "test-only-credential")
    monkeypatch.delenv("NEXUS_MODEL_BASE_URL", raising=False)
    monkeypatch.setattr(main, "settings", load_settings())
    generator = getattr(main, f"_build_{target}_patch_generator")()
    assert isinstance(generator.gateway, AnthropicGateway)
    assert generator.gateway.base_url == "https://api.anthropic.com"

    async def fail(**kwargs: Any) -> Any:
        try:
            raise HTTPError("https://example.invalid", 404, "private-response", Message(), None)
        except HTTPError as exc:
            raise ModelGatewayError(
                code="MODEL_PROVIDER_UNAVAILABLE",
                message="private-message",
                internal_detail="private-payload",
            ) from exc

    monkeypatch.setattr(generator.gateway, "generate_structured", fail)
    context = {
        "requestedChange": "private-request",
        "baseSnapshotId": "snapshot",
        "inputArtifactReferences": [],
        "artifacts": {},
        "snapshotFiles": [],
        "fileContents": {},
    }
    with pytest.raises((FirmwarePatchGenerationError, AnalysisPatchGenerationError)) as caught:
        generator.generate(context=context, base_snapshot={})
    assert caught.value.code == "MODEL_PROVIDER_UNAVAILABLE"
    assert (
        f"{target}_patch_gateway_failed code=MODEL_PROVIDER_UNAVAILABLE http_status=404"
        in caplog.text
    )
    assert any(record.levelname == "WARNING" for record in caplog.records)
    assert "private-" not in caplog.text
    assert "test-only-credential" not in caplog.text
