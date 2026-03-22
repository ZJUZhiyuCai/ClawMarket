"""Payment API routes for ClawMarket escrow."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import AuthContext, get_auth_context
from app.db.session import get_session
from app.schemas.payments import PaymentCreate, PaymentRead
from app.services.marketplace import MarketplaceService
from app.services.payment import PaymentService

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/payments", tags=["payments"])
AUTH_DEP = Depends(get_auth_context)
SESSION_DEP = Depends(get_session)


@router.post("", response_model=PaymentRead)
async def create_payment(
    payload: PaymentCreate,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> PaymentRead:
    """Create escrow funding for the selected marketplace task."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    service = MarketplaceService(session)
    return await service.create_escrow_payment(task_id=payload.task_id, user=auth.user)


@router.get("/task/{task_id}", response_model=PaymentRead | None)
async def get_payment_for_task(
    task_id: UUID,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> PaymentRead | None:
    """Fetch the payment record currently attached to one task."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    payment = await PaymentService(session).get_by_task(task_id=task_id)
    return PaymentRead.model_validate(payment, from_attributes=True) if payment else None
