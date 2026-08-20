"""SQLAlchemy models for project package persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Portable JSON payload column: JSONB on PostgreSQL, plain JSON elsewhere (e.g. SQLite).
JSON_PAYLOAD = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class ProjectRow(Base):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    domain: Mapped[str] = mapped_column(String(128), nullable=False)
    project_phase: Mapped[str] = mapped_column(String(64), nullable=False)
    autonomy_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    current_state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UserTurnRow(Base):
    __tablename__ = "user_turns"

    turn_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.project_id"), nullable=False, index=True
    )
    parent_turn_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False)


class TurnRouteRow(Base):
    __tablename__ = "turn_routes"

    route_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    turn_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("user_turns.turn_id"), nullable=False, index=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False)


class WorkflowRunRow(Base):
    __tablename__ = "workflow_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    turn_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("user_turns.turn_id"), nullable=False, index=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False)


class ArtifactRevisionRow(Base):
    __tablename__ = "artifact_revisions"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "artifact_type",
            "artifact_version",
            name="uq_artifact_project_type_version",
        ),
    )

    artifact_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_turn_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workflow_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    supersedes_artifact_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False)


class ValidationIssueRow(Base):
    __tablename__ = "validation_issues"

    issue_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False)


class OpenQuestionRow(Base):
    __tablename__ = "open_questions"

    question_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False)


class VeraResponseRow(Base):
    __tablename__ = "vera_responses"

    response_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    turn_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False)


class ArtifactDependencyRow(Base):
    __tablename__ = "artifact_dependencies"

    dependency_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
