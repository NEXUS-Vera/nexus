"""Shadow mode: fixture response + independent LLM evaluation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .base import AutonomyMode, InitializationRequestContext
from .fixture_provider import FixtureInitializationProvider
from .llm_provider import LlmInitializationError, LlmInitializationProvider

logger = logging.getLogger("nexus.embedded.project_initialization.shadow")


@dataclass
class ShadowInitializationProvider:
    """Return fixture results while evaluating the LLM path privately.

    Shadow failures never break the user-visible fixture response.
    For this phase, shadow execution is sequential and local.
    """

    fixture_provider: FixtureInitializationProvider
    llm_provider: LlmInitializationProvider

    async def initialize(
        self,
        message: str,
        autonomy_mode: AutonomyMode,
        request_context: InitializationRequestContext,
    ) -> dict[str, Any]:
        result = await self.fixture_provider.initialize(message, autonomy_mode, request_context)
        try:
            shadow = await self.llm_provider.initialize(message, autonomy_mode, request_context)
            logger.info(
                "shadow_llm_initialization_succeeded",
                extra={
                    "request_id": request_context.request_id,
                    "shadow_project_id": shadow.get("project", {}).get("projectId"),
                    "shadow_workflow_run_id": shadow.get("workflowRun", {}).get("workflowRunId"),
                },
            )
        except (LlmInitializationError, Exception) as exc:  # noqa: BLE001
            logger.warning(
                "shadow_llm_initialization_failed",
                extra={
                    "request_id": request_context.request_id,
                    "error_type": type(exc).__name__,
                    "error_code": getattr(exc, "code", None),
                },
            )
        return result
