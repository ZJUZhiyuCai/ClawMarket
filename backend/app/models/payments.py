"""Payment records for marketplace escrow and settlement flows."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class Payment(QueryModel, table=True):
    """Escrow payment record for one marketplace task."""

    __tablename__ = "payments"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (UniqueConstraint("task_id", name="uq_payments_task_id"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    task_id: UUID = Field(foreign_key="tasks.id", index=True)
    amount: int = Field(default=0)
    currency: str = Field(default="cny")
    status: str = Field(default="pending", index=True)
    payer_id: UUID = Field(foreign_key="users.id", index=True)
    payee_id: UUID = Field(foreign_key="users.id", index=True)
    provider: str = Field(default="mock", index=True)
    provider_payment_id: str | None = Field(default=None, index=True)
    provider_client_secret: str | None = None
    platform_fee_amount: int = Field(default=0)
    payee_amount: int = Field(default=0)
    metadata_: dict[str, object] = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSON, nullable=False),
    )
    released_at: datetime | None = Field(default=None)
    refunded_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
