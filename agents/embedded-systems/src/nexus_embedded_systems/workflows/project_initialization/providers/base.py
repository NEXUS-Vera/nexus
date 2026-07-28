"""Initialization provider protocol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

AutonomyMode = Literal["collaborate", "delegate"]


@dataclass(frozen=True)
class InitializationRequestContext:
    request_id: str | None = None


class InitializationProvider(Protocol):
    """Source of a ProjectInitializationResult.

    The API must not know whether the package came from fixtures or an LLM.
    """

    async def initialize(
        self,
        message: str,
        autonomy_mode: AutonomyMode,
        request_context: InitializationRequestContext,
    ) -> dict[str, Any]: ...
