"""Validate structured ExecutionCommandSpec values."""

from __future__ import annotations

from typing import Any

from nexus_board.errors import CommandValidationError
from nexus_board.paths import normalize_workspace_path

_FORBIDDEN_ENV_KEYS = frozenset(
    {
        "WOKWI_CLI_TOKEN",
        "NEXUS_DATABASE_URL",
        "NEXUS_MODEL_API_KEY",
        "OPENAI_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "DATABASE_URL",
    }
)


def environment_entries_to_mapping(
    entries: list[dict[str, str]] | dict[str, str],
) -> dict[str, str]:
    if isinstance(entries, dict):
        return {str(k): str(v) for k, v in entries.items()}
    mapping: dict[str, str] = {}
    for item in entries:
        mapping[str(item["name"])] = str(item["value"])
    return mapping


def validate_command_spec(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise CommandValidationError("commandSpec must be an object")
    if raw.get("schemaVersion") != "1.0.0":
        raise CommandValidationError("commandSpec.schemaVersion must be 1.0.0")
    executable = raw.get("executable")
    if not isinstance(executable, str) or not executable.strip():
        raise CommandValidationError("commandSpec.executable is required")
    if executable.startswith("/") or executable.startswith("\\"):
        raise CommandValidationError("commandSpec.executable must not be an absolute host path")
    if ".." in executable.split("/"):
        raise CommandValidationError("commandSpec.executable must not contain '..'")

    arguments = raw.get("arguments")
    if not isinstance(arguments, list) or not all(isinstance(a, str) for a in arguments):
        raise CommandValidationError("commandSpec.arguments must be a string array")
    if len(arguments) > 64:
        raise CommandValidationError("commandSpec.arguments exceeds maxItems")

    working_directory = raw.get("workingDirectory", "")
    if not isinstance(working_directory, str):
        raise CommandValidationError("commandSpec.workingDirectory must be a string")
    if working_directory != "":
        working_directory = normalize_workspace_path(working_directory)

    environment = raw.get("environment") or []
    if isinstance(environment, dict):
        environment = [{"name": key, "value": value} for key, value in environment.items()]
    if not isinstance(environment, list):
        raise CommandValidationError("commandSpec.environment must be an array")
    if len(environment) > 64:
        raise CommandValidationError("commandSpec.environment exceeds maxItems")
    cleaned_env: dict[str, str] = {}
    for item in environment:
        if not isinstance(item, dict):
            raise CommandValidationError("commandSpec.environment entries must be objects")
        key = item.get("name")
        value = item.get("value")
        if not isinstance(key, str) or not isinstance(value, str):
            raise CommandValidationError("environment entries require string name and value")
        upper = key.upper()
        if upper in _FORBIDDEN_ENV_KEYS or key in _FORBIDDEN_ENV_KEYS:
            raise CommandValidationError(f"Forbidden environment key: {key}")
        if any(
            token in upper for token in ("SECRET", "TOKEN", "PASSWORD", "API_KEY", "CREDENTIAL")
        ):
            raise CommandValidationError(f"Secret-like environment key rejected: {key}")
        cleaned_env[key] = value

    declared = raw.get("declaredOutputs") or []
    if not isinstance(declared, list):
        raise CommandValidationError("commandSpec.declaredOutputs must be an array")
    if len(declared) > 32:
        raise CommandValidationError("commandSpec.declaredOutputs exceeds maxItems")
    cleaned_outputs: list[dict[str, str]] = []
    for item in declared:
        if not isinstance(item, dict):
            raise CommandValidationError("declaredOutputs entries must be objects")
        path = item.get("path")
        kind = item.get("kind")
        if not isinstance(path, str) or not isinstance(kind, str):
            raise CommandValidationError("declaredOutputs entries require path and kind")
        if kind not in {"result", "artifact", "log"}:
            raise CommandValidationError(f"Unsupported declared output kind: {kind}")
        cleaned_outputs.append({"path": normalize_workspace_path(path), "kind": kind})

    return {
        "schemaVersion": "1.0.0",
        "executable": executable,
        "arguments": list(arguments),
        "workingDirectory": working_directory,
        "environment": [
            {"name": key, "value": value} for key, value in sorted(cleaned_env.items())
        ],
        "declaredOutputs": cleaned_outputs,
    }
