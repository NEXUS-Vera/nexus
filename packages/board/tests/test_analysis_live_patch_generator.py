"""Unit tests for LiveAnalysisPatchGenerator materialization (hermetic, no network)."""

from __future__ import annotations

from typing import Any

from nexus_board.analysis.live_patch_generator import LiveAnalysisPatchGenerator
from nexus_board.analysis.patch import materialize_model_patch_operations
from nexus_model_gateway import ModelPolicy


class _FakeGenerated:
    def __init__(self, parsed: dict[str, Any]) -> None:
        self.parsed_output = parsed
        self.provider = "fixture"
        self.model = "fake"


class _FakeGateway:
    def __init__(self, parsed: dict[str, Any]) -> None:
        self._parsed = parsed

    async def generate_structured(self, **_kwargs: Any) -> _FakeGenerated:
        return _FakeGenerated(self._parsed)


def test_materialize_model_patch_operations_sets_expected_base_hash() -> None:
    base_snapshot = {
        "snapshotId": "snap_1",
        "content": {
            "kind": "filesystem",
            "filesystemManifest": {
                "entries": [
                    {"path": "analysis.py", "contentHash": "hash_a", "sizeBytes": 10},
                ]
            },
        },
    }
    ops = materialize_model_patch_operations(
        generated={
            "operations": [
                {
                    "operationType": "replace-file",
                    "path": "analysis.py",
                    "content": "print('hi')\n",
                }
            ]
        },
        base_snapshot=base_snapshot,
    )
    assert ops[0]["expectedBaseHash"] == "hash_a"
    assert ops[0]["contentHash"]


def test_live_generator_uses_gateway_and_returns_metadata() -> None:
    base_snapshot = {
        "snapshotId": "snap_1",
        "content": {
            "kind": "filesystem",
            "filesystemManifest": {
                "entries": [
                    {"path": "analysis.py", "contentHash": "hash_a", "sizeBytes": 10},
                ]
            },
        },
    }
    gateway = _FakeGateway(
        {
            "operations": [
                {
                    "operationType": "replace-file",
                    "path": "analysis.py",
                    "content": "print(1)\n",
                }
            ]
        }
    )
    gen = LiveAnalysisPatchGenerator(
        gateway=gateway,
        model_policy=ModelPolicy(provider="openai", model="gpt-test", timeout_seconds=10),
    )
    result = gen.generate(
        context={
            "requestedChange": "update analysis",
            "baseSnapshotId": "snap_1",
            "snapshotFiles": [],
            "fileContents": {},
        },
        base_snapshot=base_snapshot,
    )
    assert result["operations"]
    assert result["generatorMetadata"]["mode"] == "llm"
    assert result["generatorId"].endswith("llm-v1")
