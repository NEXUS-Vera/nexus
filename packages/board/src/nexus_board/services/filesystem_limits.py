"""Configurable filesystem workspace quotas."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspaceFilesystemLimits:
    """Conservative development defaults; override via configuration."""

    max_file_bytes: int = 1_048_576
    max_workspace_bytes: int = 16_777_216
    max_file_count: int = 256

    def __post_init__(self) -> None:
        if self.max_file_bytes < 1:
            raise ValueError("max_file_bytes must be positive")
        if self.max_workspace_bytes < 1:
            raise ValueError("max_workspace_bytes must be positive")
        if self.max_file_count < 1:
            raise ValueError("max_file_count must be positive")
