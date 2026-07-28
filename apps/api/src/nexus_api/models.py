"""API models for project initialization requests (server-generated IDs elsewhere)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AutonomyMode = Literal["collaborate", "delegate"]


class InitializeProjectRequest(BaseModel):
    message: str = Field(min_length=1)
    autonomyMode: AutonomyMode = "collaborate"
