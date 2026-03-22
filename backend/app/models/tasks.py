"""Task model representing board work items and execution metadata."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, Text
from sqlmodel import Field

from app.core.time import utcnow
from app.models.tenancy import TenantScoped

RUNTIME_ANNOTATION_TYPES = (datetime,)


class Task(TenantScoped, table=True):
    """Board-scoped task entity with ownership, status, and timing fields."""

    __tablename__ = "tasks"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    board_id: UUID | None = Field(default=None, foreign_key="boards.id", index=True)

    title: str
    description: str | None = None
    status: str = Field(default="inbox", index=True)
    priority: str = Field(default="medium", index=True)
    due_at: datetime | None = None
    in_progress_at: datetime | None = None
    previous_in_progress_at: datetime | None = None

    created_by_user_id: UUID | None = Field(
        default=None,
        foreign_key="users.id",
        index=True,
    )
    assigned_agent_id: UUID | None = Field(
        default=None,
        foreign_key="agents.id",
        index=True,
    )
    auto_created: bool = Field(default=False)
    auto_reason: str | None = None
    marketplace_state: str | None = Field(default=None, index=True)
    marketplace_task_type: str | None = Field(default=None, index=True)
    marketplace_budget_amount: int | None = None
    marketplace_budget_currency: str | None = None
    marketplace_public: bool = Field(default=False, index=True)
    marketplace_listing_agent_id: UUID | None = Field(
        default=None,
        foreign_key="agents.id",
        index=True,
    )
    marketplace_attachments: list[dict[str, object]] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )
    marketplace_match_candidates: list[dict[str, object]] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )
    marketplace_delivery_artifacts: list[dict[str, object]] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )
    marketplace_screenshots: list[dict[str, object]] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )
    marketplace_delivery_note: str | None = Field(default=None, sa_column=Column(Text))
    marketplace_failure_reason: str | None = Field(default=None, sa_column=Column(Text))

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
