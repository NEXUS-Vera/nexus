"""Centralized ExecutionJob resource limits."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace


@dataclass(frozen=True)
class ExecutionLimits:
    wall_time_ms: int = 30_000
    stdout_bytes: int = 1_048_576
    stderr_bytes: int = 1_048_576
    total_log_bytes: int = 2_097_152
    produced_output_bytes: int = 4_194_304
    output_file_count: int = 32
    workspace_bytes: int = 16_777_216
    memory_bytes: int | None = None
    cpu_millis: int | None = None
    process_count: int | None = None
    log_chunk_bytes: int = 16_384

    def to_contract(self) -> dict[str, int]:
        payload: dict[str, int] = {
            "wallTimeMs": self.wall_time_ms,
            "stdoutBytes": self.stdout_bytes,
            "stderrBytes": self.stderr_bytes,
            "totalLogBytes": self.total_log_bytes,
            "producedOutputBytes": self.produced_output_bytes,
            "outputFileCount": self.output_file_count,
            "workspaceBytes": self.workspace_bytes,
        }
        if self.memory_bytes is not None:
            payload["memoryBytes"] = self.memory_bytes
        if self.cpu_millis is not None:
            payload["cpuMillis"] = self.cpu_millis
        if self.process_count is not None:
            payload["processCount"] = self.process_count
        return payload

    def override(self, **kwargs: int) -> ExecutionLimits:
        return replace(self, **kwargs)

    @classmethod
    def from_mapping(cls, raw: dict[str, object] | None) -> ExecutionLimits:
        if not raw:
            return default_execution_limits()
        base = default_execution_limits()
        mapping = {
            "wallTimeMs": "wall_time_ms",
            "stdoutBytes": "stdout_bytes",
            "stderrBytes": "stderr_bytes",
            "totalLogBytes": "total_log_bytes",
            "producedOutputBytes": "produced_output_bytes",
            "outputFileCount": "output_file_count",
            "workspaceBytes": "workspace_bytes",
            "memoryBytes": "memory_bytes",
            "cpuMillis": "cpu_millis",
            "processCount": "process_count",
        }
        updates: dict[str, int] = {}
        for key, attr in mapping.items():
            value = raw.get(key)
            if isinstance(value, bool) or not isinstance(value, int | str):
                continue
            updates[attr] = int(value)
        return replace(base, **updates) if updates else base


def default_execution_limits() -> ExecutionLimits:
    return ExecutionLimits()


def limits_as_dict(limits: ExecutionLimits) -> dict[str, object]:
    return asdict(limits)
