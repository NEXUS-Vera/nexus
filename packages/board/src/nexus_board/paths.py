"""Centralized workspace path normalization and validation."""

from __future__ import annotations

import re

from nexus_board.errors import WorkspacePathError

MAX_PATH_LENGTH = 1024
MAX_PATH_SEGMENTS = 64
MAX_SEGMENT_LENGTH = 255

# Reject Windows device / reserved names and control characters.
_RESERVED_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}
_CONTROL_OR_FORBIDDEN = re.compile(r"[\x00-\x1f\x7f<>:\"|?*\\]")


def normalize_workspace_path(raw: str) -> str:
    """Normalize and validate an untrusted workspace-relative path.

    Returns a portable path using ``/`` separators with no leading slash.
    Does not touch the host filesystem and never follows symlinks.
    """
    if not isinstance(raw, str):
        raise WorkspacePathError("Workspace path must be a string")
    if raw == "" or raw.strip() == "":
        raise WorkspacePathError("Workspace path must not be empty")
    if "\x00" in raw:
        raise WorkspacePathError("Workspace path must not contain NUL characters")
    if len(raw) > MAX_PATH_LENGTH:
        raise WorkspacePathError("Workspace path exceeds maximum length")
    if raw.startswith("/") or raw.startswith("\\"):
        raise WorkspacePathError("Workspace path must be relative")
    if re.match(r"^[A-Za-z]:[/\\]", raw):
        raise WorkspacePathError("Workspace path must not be an absolute Windows path")
    if "\\" in raw:
        raise WorkspacePathError("Workspace path must use '/' separators")
    if _CONTROL_OR_FORBIDDEN.search(raw):
        raise WorkspacePathError("Workspace path contains forbidden characters")

    segments = raw.split("/")
    if len(segments) > MAX_PATH_SEGMENTS:
        raise WorkspacePathError("Workspace path has too many segments")

    normalized: list[str] = []
    for segment in segments:
        if segment == "" or segment == ".":
            raise WorkspacePathError("Workspace path contains an empty or '.' segment")
        if segment == "..":
            raise WorkspacePathError("Workspace path must not contain '..'")
        if len(segment) > MAX_SEGMENT_LENGTH:
            raise WorkspacePathError("Workspace path segment exceeds maximum length")
        if segment.endswith(" ") or segment.endswith("."):
            raise WorkspacePathError("Workspace path segment has trailing space or dot")
        stem = segment.split(".", 1)[0].lower()
        if stem in _RESERVED_NAMES:
            raise WorkspacePathError("Workspace path uses a reserved name")
        if segment.startswith("~"):
            raise WorkspacePathError("Workspace path must not start a segment with '~'")
        normalized.append(segment)

    if not normalized:
        raise WorkspacePathError("Workspace path must not be empty")
    return "/".join(normalized)


__all__ = [
    "MAX_PATH_LENGTH",
    "WorkspacePathError",
    "normalize_workspace_path",
]
