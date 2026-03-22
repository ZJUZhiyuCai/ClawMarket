"""Schemas for escrow payment APIs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlmodel import Field, SQLModel

RUNTIME_ANNOTATION_TYPES = (datetime, UUID)


class PaymentCreate(SQLModel):
    """Create a payment authorization for one marketplace task."""

    task_id: UUID
    amount: int = Field(ge=0)
    currency: str = "cny"


class PaymentRead(SQLModel):
    """Payment payload returned by payment APIs."""

    id: UUID
    task_id: UUID
    amount: int
    currency: str
    status: str
    payer_id: UUID
    payee_id: UUID
    provider: str
    provider_payment_id: str | None = None
    provider_client_secret: str | None = None
    platform_fee_amount: int
    payee_amount: int
    released_at: datetime | None = None
    refunded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PaymentAction(SQLModel):
    """Mutating payment action payload."""

    reason: str | None = None
