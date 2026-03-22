"""API routes for ClawMarket marketplace flows."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import AuthContext, get_auth_context
from app.db.session import get_session
from app.schemas.marketplace import (
    ArbitrationCaseRead,
    ArbitrationResolve,
    MarketplaceApprovalDecisionPayload,
    MarketplaceDeliverySubmit,
    MarketplaceMatchRequest,
    MarketplaceTaskSelect,
    MarketplaceTaskCreate,
    MarketplaceTaskRead,
    RequesterDashboardRead,
    SupplierAgentRead,
    SupplierAgentRegister,
    SupplierDashboardRead,
)
from app.services.marketplace import MarketplaceService

if TYPE_CHECKING:
    from fastapi.responses import FileResponse
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(tags=["marketplace"])
AUTH_DEP = Depends(get_auth_context)
SESSION_DEP = Depends(get_session)


@router.post("/agents/register", response_model=SupplierAgentRead)
async def register_supplier_agent(
    payload: SupplierAgentRegister,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> SupplierAgentRead:
    """Register or refresh a supplier-owned OpenClaw instance."""
    service = MarketplaceService(session)
    return await service.register_supplier_agent(payload=payload, auth=auth)


@router.get("/agents/me/marketplace", response_model=list[SupplierAgentRead])
async def list_my_supplier_agents(
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> list[SupplierAgentRead]:
    """Return marketplace supplier listings owned by the current user."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    service = MarketplaceService(session)
    return await service.list_supplier_agents(user=auth.user)


@router.post("/agents/{agent_id}/skills/import", response_model=SupplierAgentRead)
async def import_supplier_skills(
    agent_id: UUID,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> SupplierAgentRead:
    """Import installed skills from the supplier runtime."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    service = MarketplaceService(session)
    return await service.refresh_supplier_skills(agent_id=agent_id, user=auth.user)


@router.get("/marketplace/tasks", response_model=list[MarketplaceTaskRead])
async def list_marketplace_tasks(
    session: AsyncSession = SESSION_DEP,
) -> list[MarketplaceTaskRead]:
    """List the public marketplace task feed."""
    service = MarketplaceService(session)
    return await service.list_public_tasks()


@router.get("/marketplace/tasks/mine", response_model=list[MarketplaceTaskRead])
async def list_my_marketplace_tasks(
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> list[MarketplaceTaskRead]:
    """List marketplace tasks created by the current requester."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    service = MarketplaceService(session)
    return await service.list_requester_tasks(user=auth.user)


@router.post("/marketplace/tasks", response_model=MarketplaceTaskRead)
async def create_marketplace_task(
    payload: MarketplaceTaskCreate,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> MarketplaceTaskRead:
    """Create a new marketplace task and return initial match candidates."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    service = MarketplaceService(session)
    return await service.create_marketplace_task(payload=payload, user=auth.user)


@router.post("/tasks/match", response_model=MarketplaceTaskRead)
async def rematch_marketplace_task(
    payload: MarketplaceMatchRequest,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> MarketplaceTaskRead:
    """Recompute the ranked top supplier matches for one task."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    service = MarketplaceService(session)
    return await service.rematch_task(task_id=payload.task_id, user=auth.user)


@router.post("/marketplace/tasks/{task_id}/select", response_model=MarketplaceTaskRead)
async def select_marketplace_agent(
    task_id: UUID,
    payload: MarketplaceTaskSelect,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> MarketplaceTaskRead:
    """Select one supplier listing for a marketplace task."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    service = MarketplaceService(session)
    return await service.select_listing_agent(
        task_id=task_id,
        agent_id=payload.agent_id,
        user=auth.user,
    )


@router.post("/marketplace/tasks/{task_id}/supplier-approval", response_model=MarketplaceTaskRead)
async def supplier_task_approval(
    task_id: UUID,
    payload: MarketplaceApprovalDecisionPayload,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> MarketplaceTaskRead:
    """Approve or reject execution as the supplier."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    service = MarketplaceService(session)
    return await service.supplier_decision(task_id=task_id, user=auth.user, payload=payload)


@router.post("/marketplace/tasks/{task_id}/submit", response_model=MarketplaceTaskRead)
async def submit_marketplace_delivery(
    task_id: UUID,
    payload: MarketplaceDeliverySubmit,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> MarketplaceTaskRead:
    """Submit final delivery artifacts for requester acceptance."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    service = MarketplaceService(session)
    return await service.submit_delivery(task_id=task_id, user=auth.user, payload=payload)


@router.post("/marketplace/tasks/{task_id}/requester-approval", response_model=MarketplaceTaskRead)
async def requester_task_approval(
    task_id: UUID,
    payload: MarketplaceApprovalDecisionPayload,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> MarketplaceTaskRead:
    """Accept or dispute a delivered marketplace task."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    service = MarketplaceService(session)
    return await service.requester_decision(task_id=task_id, user=auth.user, payload=payload)


@router.post("/marketplace/tasks/{task_id}/fail", response_model=MarketplaceTaskRead)
async def fail_marketplace_task(
    task_id: UUID,
    payload: MarketplaceApprovalDecisionPayload,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> MarketplaceTaskRead:
    """Mark a marketplace task as failed and refund escrow."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    service = MarketplaceService(session)
    return await service.mark_task_failed(
        task_id=task_id,
        user=auth.user,
        reason=payload.comment or "Supplier marked the task as failed.",
    )


@router.get("/supplier/dashboard", response_model=SupplierDashboardRead)
async def supplier_dashboard(
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> SupplierDashboardRead:
    """Return supplier dashboard metrics and active orders."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    service = MarketplaceService(session)
    return await service.supplier_dashboard(user=auth.user)


@router.get("/requester/dashboard", response_model=RequesterDashboardRead)
async def requester_dashboard(
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> RequesterDashboardRead:
    """Return requester dashboard tasks and completed case studies."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    service = MarketplaceService(session)
    return await service.requester_dashboard(user=auth.user)


@router.get("/admin/arbitration", response_model=list[ArbitrationCaseRead])
async def list_arbitration_cases(
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> list[ArbitrationCaseRead]:
    """List disputed or failed marketplace orders for admin arbitration."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    service = MarketplaceService(session)
    return await service.arbitration_cases(user=auth.user)


@router.post("/admin/arbitration/{task_id}", response_model=MarketplaceTaskRead)
async def resolve_arbitration_case(
    task_id: UUID,
    payload: ArbitrationResolve,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> MarketplaceTaskRead:
    """Resolve one arbitration case by refunding or releasing payment."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    service = MarketplaceService(session)
    return await service.resolve_arbitration(task_id=task_id, user=auth.user, payload=payload)


@router.get("/marketplace/tasks/{task_id}/files/{file_id}")
async def serve_marketplace_task_file(
    task_id: UUID,
    file_id: str,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> FileResponse:
    """Download a task attachment, delivery artifact, or stored screenshot."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    service = MarketplaceService(session)
    return await service.serve_task_file(task_id=task_id, file_id=file_id, user=auth.user)
