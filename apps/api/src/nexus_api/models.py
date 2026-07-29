"""API models for project initialization and modification requests."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AutonomyMode = Literal["collaborate", "delegate"]

ARTIFACT_TYPES = Literal[
    "project-brief",
    "requirement-set",
    "functional-architecture",
    "next-action",
]


class InitializeProjectRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    autonomyMode: AutonomyMode = "collaborate"


class ProjectTurnRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    autonomyMode: AutonomyMode = "collaborate"
