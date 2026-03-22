"""Marketplace orchestration service for ClawMarket MVP."""

from __future__ import annotations

import base64
import binascii
import mimetypes
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from fastapi.responses import FileResponse
from sqlmodel import col, select

from app.core.auth_mode import AuthMode
from app.core.config import settings
from app.core.time import utcnow
from app.models.activity_events import ActivityEvent
from app.models.agents import Agent
from app.models.approvals import Approval
from app.models.board_memory import BoardMemory
from app.models.boards import Board
from app.models.gateways import Gateway
from app.models.organizations import Organization
from app.models.payments import Payment
from app.models.tasks import Task
from app.models.users import User
from app.schemas.agents import AgentRead
from app.schemas.marketplace import (
    ArbitrationCaseRead,
    ArbitrationResolve,
    MarketplaceApprovalDecisionPayload,
    MarketplaceDeliverySubmit,
    MarketplaceFileUpload,
    MarketplaceTaskCreate,
    MarketplaceTaskRead,
    RequesterDashboardRead,
    SupplierAgentRead,
    SupplierAgentRegister,
    SupplierDashboardRead,
)
from app.schemas.payments import PaymentRead
from app.schemas.tasks import TaskRead
from app.services.activity_log import record_activity
from app.services.approval_task_links import replace_approval_task_links
from app.services.matching import MatchingService
from app.services.openclaw.admin_service import GatewayAdminLifecycleService
from app.services.openclaw.gateway_dispatch import GatewayDispatchService
from app.services.openclaw.gateway_rpc import GatewayConfig as GatewayClientConfig
from app.services.openclaw.gateway_rpc import OpenClawGatewayError, openclaw_call
from app.services.openclaw.provisioning_db import AgentLifecycleService
from app.services.payment import PaymentService

if TYPE_CHECKING:
    from app.core.auth import AuthContext
    from sqlmodel.ext.asyncio.session import AsyncSession

MARKETPLACE_ORG_SLUG = "clawmarket-marketplace"
SUPPLIER_APPROVAL_ACTION = "marketplace.supplier_execute"
REQUESTER_APPROVAL_ACTION = "marketplace.requester_acceptance"
ACTIVE_TASK_STATES = {
    "awaiting_payment",
    "awaiting_supplier_approval",
    "executing",
    "awaiting_acceptance",
    "disputed",
}
SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(filename: str) -> str:
    cleaned = SAFE_FILENAME_PATTERN.sub("-", filename.strip()).strip(".-")
    return cleaned or "file"


def _currency_label(currency: str | None) -> str:
    normalized = (currency or settings.payment_currency).lower()
    if normalized == "cny":
        return "CNY"
    return normalized.upper()


def _amount_label(amount: int | None, currency: str | None) -> str:
    value = max(int(amount or 0), 0) / 100
    return f"{_currency_label(currency)} {value:,.2f}"


def _task_title_from_description(description: str) -> str:
    normalized = " ".join(description.strip().split())
    if len(normalized) <= 72:
        return normalized
    return f"{normalized[:69]}..."


def _read_preview_payload(payload: object) -> str | None:
    if isinstance(payload, str) and payload.strip():
        return payload.strip()
    if not isinstance(payload, dict):
        return None
    for key in ("data_url", "dataUrl", "image", "preview", "screenshot", "png"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for value in payload.values():
        nested = _read_preview_payload(value)
        if nested:
            return nested
    return None


class MarketplaceService:
    """Application service that coordinates supplier and requester flows."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.matching = MatchingService(session)
        self.payments = PaymentService(session)

    async def ensure_marketplace_org(self) -> Organization:
        existing = (
            await Organization.objects.filter_by(name=settings.clawmarket_org_name)
            .order_by(col(Organization.created_at).asc())
            .first(self.session)
        )
        if existing is not None:
            return existing
        org = Organization(name=settings.clawmarket_org_name, created_at=utcnow(), updated_at=utcnow())
        self.session.add(org)
        await self.session.commit()
        await self.session.refresh(org)
        return org

    def _require_authenticated_user(self, user: User | None) -> User:
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return user

    def _require_admin(self, user: User | None) -> User:
        resolved = self._require_authenticated_user(user)
        if settings.auth_mode == AuthMode.LOCAL or resolved.is_super_admin:
            return resolved
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Marketplace admin privileges are required.",
        )

    async def _gateway_health(
        self,
        *,
        gateway_url: str,
        token: str | None,
        allow_insecure_tls: bool,
        disable_device_pairing: bool,
    ) -> tuple[bool, list[str]]:
        config = GatewayClientConfig(
            url=gateway_url,
            token=token,
            allow_insecure_tls=allow_insecure_tls,
            disable_device_pairing=disable_device_pairing,
        )
        health_payload = await openclaw_call("health", config=config)
        skills: list[str] = []
        for method in ("skills.status", "skills.bins"):
            try:
                payload = await openclaw_call(method, config=config)
            except OpenClawGatewayError:
                continue
            skills.extend(self._extract_skill_names(payload))
        if not isinstance(health_payload, (dict, list, str)):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Gateway health probe returned an unsupported payload.",
            )
        deduped_skills: list[str] = []
        for skill in skills:
            cleaned = skill.strip()
            if cleaned and cleaned not in deduped_skills:
                deduped_skills.append(cleaned)
        return True, deduped_skills

    def _extract_skill_names(self, payload: object) -> list[str]:
        if isinstance(payload, str):
            return [payload]
        if isinstance(payload, list):
            values: list[str] = []
            for item in payload:
                values.extend(self._extract_skill_names(item))
            return values
        if not isinstance(payload, dict):
            return []

        values: list[str] = []
        for key in ("skills", "bins", "installed", "items"):
            nested = payload.get(key)
            if isinstance(nested, list):
                for item in nested:
                    values.extend(self._extract_skill_names(item))
        for key in ("id", "name", "slug", "package"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                values.append(value.strip())
        return values

    async def register_supplier_agent(
        self,
        *,
        payload: SupplierAgentRegister,
        auth: AuthContext,
    ) -> SupplierAgentRead:
        user = self._require_authenticated_user(auth.user)
        org = await self.ensure_marketplace_org()
        gateway_service = GatewayAdminLifecycleService(self.session)
        await gateway_service.assert_gateway_runtime_compatible(
            url=payload.gateway_url,
            token=payload.auth_token,
            allow_insecure_tls=payload.allow_insecure_tls,
            disable_device_pairing=payload.disable_device_pairing,
        )
        _connected, imported_skills = await self._gateway_health(
            gateway_url=payload.gateway_url,
            token=payload.auth_token,
            allow_insecure_tls=payload.allow_insecure_tls,
            disable_device_pairing=payload.disable_device_pairing,
        )

        gateway = (
            await Gateway.objects.filter_by(url=payload.gateway_url, organization_id=org.id).first(
                self.session
            )
        )
        now = utcnow()
        if gateway is None:
            gateway = Gateway(
                organization_id=org.id,
                name=payload.gateway_name,
                url=payload.gateway_url,
                token=payload.auth_token,
                disable_device_pairing=payload.disable_device_pairing,
                workspace_root=payload.workspace_root,
                allow_insecure_tls=payload.allow_insecure_tls,
                created_at=now,
                updated_at=now,
            )
            self.session.add(gateway)
            await self.session.commit()
            await self.session.refresh(gateway)
        else:
            gateway.name = payload.gateway_name
            gateway.token = payload.auth_token
            gateway.workspace_root = payload.workspace_root
            gateway.allow_insecure_tls = payload.allow_insecure_tls
            gateway.disable_device_pairing = payload.disable_device_pairing
            gateway.updated_at = now
            self.session.add(gateway)
            await self.session.commit()
            await self.session.refresh(gateway)

        main_agent = await gateway_service.ensure_main_agent(gateway, auth, action="provision")
        deduped_skills = list(dict.fromkeys([*imported_skills, *payload.skill_tags]))
        main_agent.owner_id = user.id
        main_agent.gateway_url = gateway.url
        main_agent.skills = deduped_skills
        main_agent.skill_tags = payload.skill_tags
        main_agent.pricing = payload.pricing.model_dump()
        main_agent.availability = [window.model_dump() for window in payload.availability]
        main_agent.max_concurrency = payload.max_concurrency
        main_agent.score = max(float(main_agent.score or 80.0), 80.0)
        main_agent.marketplace_enabled = True
        main_agent.updated_at = utcnow()
        user.account_role = "supplier"
        self.session.add(main_agent)
        self.session.add(user)
        record_activity(
            self.session,
            event_type="marketplace.agent.registered",
            message=f"Supplier agent registered: {main_agent.name}.",
            agent_id=main_agent.id,
        )
        await self.session.commit()
        await self.session.refresh(main_agent)
        return await self._supplier_agent_read(main_agent)

    async def refresh_supplier_skills(self, *, agent_id: UUID, user: User) -> SupplierAgentRead:
        agent = await self._require_listing_agent(agent_id=agent_id)
        self._require_supplier_owner(agent=agent, user=user)
        gateway = await Gateway.objects.by_id(agent.gateway_id).first(self.session)
        if gateway is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gateway not found.")
        _connected, imported_skills = await self._gateway_health(
            gateway_url=gateway.url,
            token=gateway.token,
            allow_insecure_tls=gateway.allow_insecure_tls,
            disable_device_pairing=gateway.disable_device_pairing,
        )
        agent.skills = list(dict.fromkeys([*imported_skills, *(agent.skill_tags or [])]))
        agent.updated_at = utcnow()
        self.session.add(agent)
        record_activity(
            self.session,
            event_type="marketplace.agent.skills_imported",
            message=f"Supplier skills imported for {agent.name}.",
            agent_id=agent.id,
        )
        await self.session.commit()
        await self.session.refresh(agent)
        return await self._supplier_agent_read(agent)

    async def list_supplier_agents(self, *, user: User) -> list[SupplierAgentRead]:
        statement = (
            select(Agent)
            .where(col(Agent.owner_id) == user.id)
            .where(col(Agent.marketplace_enabled).is_(True))
            .where(col(Agent.board_id).is_(None))
            .order_by(col(Agent.updated_at).desc())
        )
        agents = list(await self.session.exec(statement))
        return [await self._supplier_agent_read(agent) for agent in agents]

    async def create_marketplace_task(
        self,
        *,
        payload: MarketplaceTaskCreate,
        user: User,
    ) -> MarketplaceTaskRead:
        title = _task_title_from_description(payload.description)
        task = Task(
            title=title,
            description=payload.description,
            status="inbox",
            priority="medium",
            due_at=payload.deadline_at,
            created_by_user_id=user.id,
            marketplace_state="open",
            marketplace_task_type=payload.task_type,
            marketplace_budget_amount=payload.budget_amount,
            marketplace_budget_currency=settings.payment_currency,
            marketplace_public=payload.public_market,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)

        task.marketplace_attachments = [
            await self._store_upload(task_id=task.id, upload=upload, kind="attachment")
            for upload in payload.attachments
        ]
        task.marketplace_match_candidates = [
            candidate.model_dump(mode="json")
            for candidate in await self.matching.match_task(task)
        ]
        user.account_role = "requester"
        self.session.add(task)
        self.session.add(user)
        record_activity(
            self.session,
            event_type="marketplace.task.created",
            message=f"Marketplace task published: {task.title}.",
            task_id=task.id,
        )
        await self.session.commit()
        await self.session.refresh(task)
        return await self.marketplace_task_read(task)

    async def rematch_task(self, *, task_id: UUID, user: User) -> MarketplaceTaskRead:
        task = await self._require_requester_task(task_id=task_id, user=user)
        task.marketplace_match_candidates = [
            candidate.model_dump(mode="json")
            for candidate in await self.matching.match_task(task)
        ]
        task.updated_at = utcnow()
        self.session.add(task)
        record_activity(
            self.session,
            event_type="marketplace.task.rematched",
            message=f"Marketplace task rematched: {task.title}.",
            task_id=task.id,
            agent_id=task.marketplace_listing_agent_id,
        )
        await self.session.commit()
        await self.session.refresh(task)
        return await self.marketplace_task_read(task)

    async def select_listing_agent(
        self,
        *,
        task_id: UUID,
        agent_id: UUID,
        user: User,
    ) -> MarketplaceTaskRead:
        task = await self._require_requester_task(task_id=task_id, user=user)
        agent = await self._require_listing_agent(agent_id=agent_id)
        task.marketplace_listing_agent_id = agent.id
        task.marketplace_state = "awaiting_payment"
        task.updated_at = utcnow()
        self.session.add(task)
        record_activity(
            self.session,
            event_type="marketplace.task.agent_selected",
            message=f"Supplier selected for task {task.title}: {agent.name}.",
            task_id=task.id,
            agent_id=agent.id,
        )
        await self.session.commit()
        await self.session.refresh(task)
        return await self.marketplace_task_read(task)

    async def create_escrow_payment(self, *, task_id: UUID, user: User) -> PaymentRead:
        task = await self._require_requester_task(task_id=task_id, user=user)
        if task.marketplace_listing_agent_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Select a supplier before creating escrow.",
            )
        listing_agent = await self._require_listing_agent(agent_id=task.marketplace_listing_agent_id)
        payee_id = listing_agent.owner_id
        if payee_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Selected supplier agent has no owner.",
            )
        payment = await self.payments.create_escrow(
            task_id=task.id,
            amount=max(int(task.marketplace_budget_amount or 0), 0),
            currency=task.marketplace_budget_currency or settings.payment_currency,
            payer_id=user.id,
            payee_id=payee_id,
            description=f"ClawMarket escrow for {task.title}",
        )
        await self._ensure_order_workspace(task=task, listing_agent=listing_agent)
        await self._ensure_supplier_approval(task=task)
        task.marketplace_state = "awaiting_supplier_approval"
        task.updated_at = utcnow()
        self.session.add(task)
        record_activity(
            self.session,
            event_type="marketplace.payment.escrowed",
            message=f"Escrow funded for task {task.title}.",
            task_id=task.id,
            agent_id=task.marketplace_listing_agent_id,
            board_id=task.board_id,
        )
        await self.session.commit()
        await self.session.refresh(payment)
        return PaymentRead.model_validate(payment, from_attributes=True)

    async def supplier_decision(
        self,
        *,
        task_id: UUID,
        user: User,
        payload: MarketplaceApprovalDecisionPayload,
    ) -> MarketplaceTaskRead:
        task = await self._require_task_for_supplier(task_id=task_id, user=user)
        approval = await self._require_pending_approval(task=task, action_type=SUPPLIER_APPROVAL_ACTION)
        approval.status = "approved" if payload.approve else "rejected"
        approval.resolved_at = utcnow()
        self.session.add(approval)

        if not payload.approve:
            task.marketplace_state = "failed"
            task.marketplace_failure_reason = payload.comment or "Supplier rejected the execution request."
            payment = await self.payments.get_by_task(task_id=task.id)
            if payment is not None:
                await self.payments.refund(payment, reason="supplier_rejected")
            record_activity(
                self.session,
                event_type="marketplace.supplier.rejected",
                message=f"Supplier rejected task {task.title}.",
                task_id=task.id,
                agent_id=task.marketplace_listing_agent_id,
                board_id=task.board_id,
            )
            await self.session.commit()
            await self.session.refresh(task)
            return await self.marketplace_task_read(task)

        if task.assigned_agent_id is None or task.board_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Workspace is not ready for task execution.",
            )
        worker_agent = await Agent.objects.by_id(task.assigned_agent_id).first(self.session)
        board = await Board.objects.by_id(task.board_id).first(self.session)
        if board is None or worker_agent is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Execution workspace is incomplete.",
            )

        dispatch = GatewayDispatchService(self.session)
        _gateway, config = await dispatch.require_gateway_config_for_board(board)
        await dispatch.send_agent_message(
            session_key=worker_agent.openclaw_session_id or AgentLifecycleService.resolve_session_key(worker_agent),
            config=config,
            agent_name=worker_agent.name,
            message=self._task_dispatch_message(task=task),
            deliver=False,
        )
        task.status = "in_progress"
        task.in_progress_at = utcnow()
        task.marketplace_state = "executing"
        task.updated_at = utcnow()
        self.session.add(task)
        record_activity(
            self.session,
            event_type="marketplace.supplier.approved",
            message=f"Supplier approved execution for task {task.title}.",
            task_id=task.id,
            agent_id=worker_agent.id,
            board_id=board.id,
        )
        await self._capture_task_screenshot(task=task, board=board, worker_agent=worker_agent)
        await self.session.commit()
        await self.session.refresh(task)
        return await self.marketplace_task_read(task)

    async def submit_delivery(
        self,
        *,
        task_id: UUID,
        user: User,
        payload: MarketplaceDeliverySubmit,
    ) -> MarketplaceTaskRead:
        task = await self._require_task_for_supplier(task_id=task_id, user=user)
        if task.board_id is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task board is missing.")
        board = await Board.objects.by_id(task.board_id).first(self.session)
        if board is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found.")

        task.status = "review"
        task.marketplace_state = "awaiting_acceptance"
        task.marketplace_delivery_note = payload.note
        task.marketplace_delivery_artifacts = [
            *list(task.marketplace_delivery_artifacts or []),
            *[
                await self._store_upload(task_id=task.id, upload=upload, kind="artifact")
                for upload in payload.artifacts
            ],
        ]
        task.updated_at = utcnow()
        self.session.add(task)
        await self._ensure_requester_acceptance_approval(task=task)
        record_activity(
            self.session,
            event_type="marketplace.delivery.submitted",
            message=f"Delivery submitted for task {task.title}.",
            task_id=task.id,
            agent_id=task.assigned_agent_id,
            board_id=board.id,
        )
        worker_agent = (
            await Agent.objects.by_id(task.assigned_agent_id).first(self.session)
            if task.assigned_agent_id
            else None
        )
        if worker_agent is not None:
            await self._capture_task_screenshot(task=task, board=board, worker_agent=worker_agent)
        await self.session.commit()
        await self.session.refresh(task)
        return await self.marketplace_task_read(task)

    async def requester_decision(
        self,
        *,
        task_id: UUID,
        user: User,
        payload: MarketplaceApprovalDecisionPayload,
    ) -> MarketplaceTaskRead:
        task = await self._require_requester_task(task_id=task_id, user=user)
        approval = await self._require_pending_approval(task=task, action_type=REQUESTER_APPROVAL_ACTION)
        approval.status = "approved" if payload.approve else "rejected"
        approval.resolved_at = utcnow()
        self.session.add(approval)

        payment = await self.payments.get_by_task(task_id=task.id)
        if payload.approve:
            task.status = "done"
            task.marketplace_state = "completed"
            task.updated_at = utcnow()
            if payment is not None:
                await self.payments.release(payment, reason="requester_accepted")
            record_activity(
                self.session,
                event_type="marketplace.requester.accepted",
                message=f"Requester accepted task {task.title}.",
                task_id=task.id,
                agent_id=task.assigned_agent_id,
                board_id=task.board_id,
            )
        else:
            task.marketplace_state = "disputed"
            task.marketplace_failure_reason = payload.comment or "Requester requested arbitration."
            task.updated_at = utcnow()
            record_activity(
                self.session,
                event_type="marketplace.requester.disputed",
                message=f"Requester disputed task {task.title}.",
                task_id=task.id,
                agent_id=task.assigned_agent_id,
                board_id=task.board_id,
            )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return await self.marketplace_task_read(task)

    async def mark_task_failed(self, *, task_id: UUID, user: User, reason: str) -> MarketplaceTaskRead:
        task = await self._require_task_for_supplier(task_id=task_id, user=user)
        task.marketplace_state = "failed"
        task.marketplace_failure_reason = reason
        task.updated_at = utcnow()
        self.session.add(task)
        payment = await self.payments.get_by_task(task_id=task.id)
        if payment is not None:
            await self.payments.refund(payment, reason="supplier_marked_failed")
        record_activity(
            self.session,
            event_type="marketplace.task.failed",
            message=f"Task failed: {task.title}.",
            task_id=task.id,
            agent_id=task.assigned_agent_id,
            board_id=task.board_id,
        )
        await self.session.commit()
        await self.session.refresh(task)
        return await self.marketplace_task_read(task)

    async def list_public_tasks(self) -> list[MarketplaceTaskRead]:
        statement = (
            select(Task)
            .where(col(Task.marketplace_state).is_not(None))
            .where(col(Task.marketplace_public).is_(True))
            .order_by(col(Task.created_at).desc())
        )
        tasks = list(await self.session.exec(statement))
        return [await self.marketplace_task_read(task) for task in tasks]

    async def list_requester_tasks(self, *, user: User) -> list[MarketplaceTaskRead]:
        statement = (
            select(Task)
            .where(col(Task.created_by_user_id) == user.id)
            .where(col(Task.marketplace_state).is_not(None))
            .order_by(col(Task.created_at).desc())
        )
        tasks = list(await self.session.exec(statement))
        return [await self.marketplace_task_read(task) for task in tasks]

    async def requester_dashboard(self, *, user: User) -> RequesterDashboardRead:
        tasks = await self.list_requester_tasks(user=user)
        history_cases = [task for task in tasks if task.task.marketplace_state == "completed"][:6]
        return RequesterDashboardRead(tasks=tasks, history_cases=history_cases)

    async def supplier_dashboard(self, *, user: User) -> SupplierDashboardRead:
        agents = await self.list_supplier_agents(user=user)
        active_tasks = await self._tasks_for_supplier(user=user, include_states=ACTIVE_TASK_STATES)
        released_payments = list(
            await self.session.exec(
                select(Payment)
                .where(col(Payment.payee_id) == user.id)
                .where(col(Payment.status) == "released")
            )
        )
        pending_payments = list(
            await self.session.exec(
                select(Payment)
                .where(col(Payment.payee_id) == user.id)
                .where(col(Payment.status).in_(("pending", "escrowed")))
            )
        )
        return SupplierDashboardRead(
            agents=agents,
            active_tasks=active_tasks,
            income_released_amount=sum(payment.payee_amount for payment in released_payments),
            income_pending_amount=sum(payment.payee_amount for payment in pending_payments),
        )

    async def arbitration_cases(self, *, user: User) -> list[ArbitrationCaseRead]:
        self._require_admin(user)
        statement = (
            select(Task)
            .where(col(Task.marketplace_state).in_(("disputed", "failed")))
            .order_by(col(Task.updated_at).desc())
        )
        tasks = list(await self.session.exec(statement))
        return [
            ArbitrationCaseRead(
                task=await self.marketplace_task_read(task),
                timeline=await self._activity_timeline(task=task),
            )
            for task in tasks
        ]

    async def resolve_arbitration(
        self,
        *,
        task_id: UUID,
        user: User,
        payload: ArbitrationResolve,
    ) -> MarketplaceTaskRead:
        self._require_admin(user)
        task = await Task.objects.by_id(task_id).first(self.session)
        if task is None or task.marketplace_state is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
        payment = await self.payments.get_by_task(task_id=task.id)
        if payload.decision == "refund":
            if payment is not None:
                await self.payments.refund(payment, reason="admin_refund")
            task.marketplace_state = "refunded"
        else:
            if payment is not None:
                await self.payments.release(payment, reason="admin_release")
            task.status = "done"
            task.marketplace_state = "completed"
        task.updated_at = utcnow()
        if payload.comment:
            task.marketplace_delivery_note = (
                (task.marketplace_delivery_note or "") + f"\n\nAdmin note: {payload.comment}"
            ).strip()
        self.session.add(task)
        record_activity(
            self.session,
            event_type="marketplace.arbitration.resolved",
            message=f"Arbitration resolved for task {task.title}: {payload.decision}.",
            task_id=task.id,
            agent_id=task.assigned_agent_id,
            board_id=task.board_id,
        )
        await self.session.commit()
        await self.session.refresh(task)
        return await self.marketplace_task_read(task)

    async def marketplace_task_read(self, task: Task) -> MarketplaceTaskRead:
        listing_agent = (
            await Agent.objects.by_id(task.marketplace_listing_agent_id).first(self.session)
            if task.marketplace_listing_agent_id
            else None
        )
        worker_agent = (
            await Agent.objects.by_id(task.assigned_agent_id).first(self.session)
            if task.assigned_agent_id
            else None
        )
        payment = await self.payments.get_by_task(task_id=task.id)
        approvals = await self._task_approvals(task=task)
        return MarketplaceTaskRead(
            task=TaskRead.model_validate(task, from_attributes=True),
            payment=PaymentRead.model_validate(payment, from_attributes=True) if payment else None,
            listing_agent=self._to_agent_read(listing_agent),
            worker_agent=self._to_agent_read(worker_agent),
            pending_approvals=approvals,
        )

    async def serve_task_file(self, *, task_id: UUID, file_id: str, user: User) -> FileResponse:
        task = await Task.objects.by_id(task_id).first(self.session)
        if task is None or task.marketplace_state is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
        await self._assert_task_visibility(task=task, user=user)
        for group in (
            task.marketplace_attachments or [],
            task.marketplace_delivery_artifacts or [],
            task.marketplace_screenshots or [],
        ):
            for item in group:
                if not isinstance(item, dict) or item.get("file_id") != file_id:
                    continue
                storage_path = item.get("storage_path")
                if not isinstance(storage_path, str):
                    break
                file_path = Path(storage_path)
                if not file_path.exists():
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Stored file no longer exists.",
                    )
                return FileResponse(
                    path=file_path,
                    filename=str(item.get("name") or file_path.name),
                    media_type=str(item.get("content_type") or "application/octet-stream"),
                )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")

    async def _supplier_agent_read(self, agent: Agent) -> SupplierAgentRead:
        current_tasks = await self._tasks_for_listing_agent(agent_id=agent.id, states=ACTIVE_TASK_STATES)
        completed_tasks = await self._tasks_for_listing_agent(agent_id=agent.id, states={"completed"})
        released_payments = list(
            await self.session.exec(
                select(Payment)
                .where(col(Payment.payee_id) == agent.owner_id)
                .where(col(Payment.status) == "released")
            )
        )
        return SupplierAgentRead(
            agent=self._to_agent_read(agent) or AgentRead.model_validate(agent, from_attributes=True),
            gateway_connected=agent.status not in {"offline", "deleting"},
            imported_skills=list(agent.skills or []),
            active_tasks=len(current_tasks),
            completed_tasks=len(completed_tasks),
            total_revenue_amount=sum(payment.payee_amount for payment in released_payments),
        )

    async def _tasks_for_listing_agent(
        self,
        *,
        agent_id: UUID,
        states: set[str],
    ) -> list[Task]:
        statement = (
            select(Task)
            .where(col(Task.marketplace_listing_agent_id) == agent_id)
            .where(col(Task.marketplace_state).in_(tuple(states)))
            .order_by(col(Task.updated_at).desc())
        )
        return list(await self.session.exec(statement))

    async def _tasks_for_supplier(
        self,
        *,
        user: User,
        include_states: set[str],
    ) -> list[MarketplaceTaskRead]:
        statement = (
            select(Task)
            .join(Agent, col(Task.marketplace_listing_agent_id) == col(Agent.id))
            .where(col(Agent.owner_id) == user.id)
            .where(col(Task.marketplace_state).in_(tuple(include_states)))
            .order_by(col(Task.updated_at).desc())
        )
        tasks = list(await self.session.exec(statement))
        return [await self.marketplace_task_read(task) for task in tasks]

    async def _require_requester_task(self, *, task_id: UUID, user: User) -> Task:
        task = await Task.objects.by_id(task_id).first(self.session)
        if task is None or task.marketplace_state is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
        if task.created_by_user_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Task does not belong to you.")
        return task

    async def _require_listing_agent(self, *, agent_id: UUID) -> Agent:
        agent = await Agent.objects.by_id(agent_id).first(self.session)
        if agent is None or not agent.marketplace_enabled or agent.board_id is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier listing not found.")
        return agent

    def _require_supplier_owner(self, *, agent: Agent, user: User) -> None:
        if agent.owner_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not own this supplier listing.",
            )

    async def _require_task_for_supplier(self, *, task_id: UUID, user: User) -> Task:
        task = await Task.objects.by_id(task_id).first(self.session)
        if task is None or task.marketplace_state is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
        listing_agent_id = task.marketplace_listing_agent_id
        if listing_agent_id is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task has no selected supplier.")
        listing_agent = await self._require_listing_agent(agent_id=listing_agent_id)
        self._require_supplier_owner(agent=listing_agent, user=user)
        return task

    async def _assert_task_visibility(self, *, task: Task, user: User) -> None:
        if task.created_by_user_id == user.id:
            return
        listing_agent = (
            await Agent.objects.by_id(task.marketplace_listing_agent_id).first(self.session)
            if task.marketplace_listing_agent_id
            else None
        )
        if listing_agent is not None and listing_agent.owner_id == user.id:
            return
        self._require_admin(user)

    async def _ensure_order_workspace(self, *, task: Task, listing_agent: Agent) -> None:
        if task.board_id is not None and task.assigned_agent_id is not None:
            return
        org = await self.ensure_marketplace_org()
        gateway = await Gateway.objects.by_id(listing_agent.gateway_id).first(self.session)
        if gateway is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gateway not found.")

        board = Board(
            organization_id=org.id,
            name=f"Order - {task.title}",
            slug=f"{MARKETPLACE_ORG_SLUG}-{uuid4().hex[:10]}",
            description=task.description or task.title,
            gateway_id=gateway.id,
            board_type="goal",
            objective=task.description or task.title,
            success_metrics={
                "task_type": task.marketplace_task_type or "general",
                "budget": _amount_label(task.marketplace_budget_amount, task.marketplace_budget_currency),
            },
            goal_confirmed=True,
            goal_source="clawmarket",
            require_approval_for_done=True,
            require_review_before_done=True,
            comment_required_for_review=True,
            block_status_changes_with_pending_approval=True,
            only_lead_can_change_status=False,
            max_agents=1,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        self.session.add(board)
        await self.session.commit()
        await self.session.refresh(board)

        worker_service = AgentLifecycleService(self.session)
        requested_name = f"{listing_agent.name} Worker"
        await worker_service.ensure_unique_agent_name(
            board=board,
            gateway=gateway,
            requested_name=requested_name,
        )
        agent_data: dict[str, Any] = {
            "board_id": board.id,
            "gateway_id": gateway.id,
            "owner_id": listing_agent.owner_id,
            "name": requested_name,
            "status": "provisioning",
            "gateway_url": listing_agent.gateway_url or gateway.url,
            "skills": list(listing_agent.skills or []),
            "pricing": dict(listing_agent.pricing or {}),
            "availability": list(listing_agent.availability or []),
            "skill_tags": list(listing_agent.skill_tags or []),
            "max_concurrency": 1,
            "score": listing_agent.score,
            "marketplace_enabled": False,
            "heartbeat_config": listing_agent.heartbeat_config,
            "identity_profile": listing_agent.identity_profile,
            "identity_template": listing_agent.identity_template,
            "soul_template": listing_agent.soul_template,
        }
        worker_agent, raw_token = await worker_service.persist_new_agent(data=agent_data)
        supplier_user = await User.objects.by_id(listing_agent.owner_id).first(self.session)
        await worker_service.provision_new_agent(
            agent=worker_agent,
            board=board,
            gateway=gateway,
            auth_token=raw_token,
            user=supplier_user,
            force_bootstrap=False,
        )

        task.board_id = board.id
        task.assigned_agent_id = worker_agent.id
        task.updated_at = utcnow()
        self.session.add(task)
        record_activity(
            self.session,
            event_type="marketplace.workspace.provisioned",
            message=f"Execution workspace provisioned for task {task.title}.",
            task_id=task.id,
            agent_id=worker_agent.id,
            board_id=board.id,
        )
        await self.session.commit()
        await self.session.refresh(task)

    async def _ensure_supplier_approval(self, *, task: Task) -> Approval:
        existing = await self._find_approval(task=task, action_type=SUPPLIER_APPROVAL_ACTION, pending_only=True)
        if existing is not None:
            return existing
        approval = Approval(
            board_id=task.board_id,
            task_id=task.id,
            agent_id=task.assigned_agent_id,
            action_type=SUPPLIER_APPROVAL_ACTION,
            payload={
                "reason": "Supplier must explicitly approve each marketplace order before execution.",
                "task_type": task.marketplace_task_type,
            },
            confidence=100,
            status="pending",
        )
        self.session.add(approval)
        await self.session.flush()
        await replace_approval_task_links(self.session, approval_id=approval.id, task_ids=[task.id])
        record_activity(
            self.session,
            event_type="marketplace.approval.created",
            message=f"Supplier approval requested for task {task.title}.",
            task_id=task.id,
            agent_id=task.assigned_agent_id,
            board_id=task.board_id,
        )
        await self.session.commit()
        await self.session.refresh(approval)
        return approval

    async def _ensure_requester_acceptance_approval(self, *, task: Task) -> Approval:
        existing = await self._find_approval(task=task, action_type=REQUESTER_APPROVAL_ACTION, pending_only=True)
        if existing is not None:
            return existing
        approval = Approval(
            board_id=task.board_id,
            task_id=task.id,
            agent_id=task.assigned_agent_id,
            action_type=REQUESTER_APPROVAL_ACTION,
            payload={"reason": "Requester must approve the delivery before settlement."},
            confidence=100,
            status="pending",
        )
        self.session.add(approval)
        await self.session.flush()
        await replace_approval_task_links(self.session, approval_id=approval.id, task_ids=[task.id])
        record_activity(
            self.session,
            event_type="marketplace.approval.created",
            message=f"Requester acceptance requested for task {task.title}.",
            task_id=task.id,
            agent_id=task.assigned_agent_id,
            board_id=task.board_id,
        )
        await self.session.commit()
        await self.session.refresh(approval)
        return approval

    async def _find_approval(
        self,
        *,
        task: Task,
        action_type: str,
        pending_only: bool,
    ) -> Approval | None:
        statement = (
            select(Approval)
            .where(col(Approval.task_id) == task.id)
            .where(col(Approval.action_type) == action_type)
            .order_by(col(Approval.created_at).desc())
        )
        if pending_only:
            statement = statement.where(col(Approval.status) == "pending")
        return (await self.session.exec(statement)).first()

    async def _require_pending_approval(self, *, task: Task, action_type: str) -> Approval:
        approval = await self._find_approval(task=task, action_type=action_type, pending_only=True)
        if approval is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pending approval not found.",
            )
        return approval

    async def _task_approvals(self, *, task: Task) -> list[dict[str, object]]:
        approvals = list(
            await self.session.exec(
                select(Approval)
                .where(col(Approval.task_id) == task.id)
                .order_by(col(Approval.created_at).desc())
            )
        )
        return [
            {
                "id": str(approval.id),
                "action_type": approval.action_type,
                "status": approval.status,
                "created_at": approval.created_at.isoformat(),
                "resolved_at": approval.resolved_at.isoformat() if approval.resolved_at else None,
            }
            for approval in approvals
        ]

    async def _activity_timeline(self, *, task: Task) -> list[dict[str, object]]:
        statement = (
            select(ActivityEvent)
            .where(col(ActivityEvent.task_id) == task.id)
            .order_by(col(ActivityEvent.created_at).asc())
        )
        events = list(await self.session.exec(statement))
        board_messages = []
        if task.board_id is not None:
            board_messages = list(
                await self.session.exec(
                    select(BoardMemory)
                    .where(col(BoardMemory.board_id) == task.board_id)
                    .where(col(BoardMemory.is_chat).is_(True))
                    .order_by(col(BoardMemory.created_at).asc())
                )
            )
        timeline = [
            {
                "kind": "activity",
                "event_type": event.event_type,
                "message": event.message,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ]
        timeline.extend(
            {
                "kind": "chat",
                "event_type": "board.chat",
                "message": message.content,
                "created_at": message.created_at.isoformat(),
            }
            for message in board_messages
        )
        timeline.sort(key=lambda item: str(item["created_at"]))
        return timeline

    async def _store_upload(
        self,
        *,
        task_id: UUID,
        upload: MarketplaceFileUpload,
        kind: str,
    ) -> dict[str, object]:
        data = upload.data_base64
        if "," in data:
            data = data.split(",", maxsplit=1)[1]
        try:
            raw = base64.b64decode(data, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Attachment {upload.filename} is not valid base64 data.",
            ) from exc
        if len(raw) > settings.clawmarket_max_attachment_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Attachment {upload.filename} exceeds the configured size limit.",
            )
        file_id = uuid4().hex
        file_name = _safe_filename(upload.filename)
        directory = Path(settings.clawmarket_upload_dir) / str(task_id) / kind
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{file_id}-{file_name}"
        path.write_bytes(raw)
        content_type = upload.content_type or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        return {
            "file_id": file_id,
            "name": file_name,
            "content_type": content_type,
            "size_bytes": len(raw),
            "kind": kind,
            "storage_path": str(path),
            "download_url": f"/api/v1/marketplace/tasks/{task_id}/files/{file_id}",
            "created_at": utcnow().isoformat(),
        }

    async def _capture_task_screenshot(self, *, task: Task, board: Board, worker_agent: Agent) -> None:
        if not worker_agent.openclaw_session_id:
            return
        dispatch = GatewayDispatchService(self.session)
        _gateway, config = await dispatch.require_gateway_config_for_board(board)
        preview_payload: object | None = None
        for params in (
            {"key": worker_agent.openclaw_session_id},
            {"sessionKey": worker_agent.openclaw_session_id},
            {"sessionId": worker_agent.openclaw_session_id},
        ):
            try:
                preview_payload = await openclaw_call("sessions.preview", params=params, config=config)
                if preview_payload is not None:
                    break
            except OpenClawGatewayError:
                continue
        preview_data = _read_preview_payload(preview_payload)
        if not preview_data:
            return
        screenshot_ref = await self._store_upload(
            task_id=task.id,
            upload=MarketplaceFileUpload(
                filename="preview.png",
                content_type="image/png",
                size_bytes=0,
                data_base64=preview_data,
            ),
            kind="screenshot",
        )
        task.marketplace_screenshots = [*list(task.marketplace_screenshots or []), screenshot_ref]
        task.updated_at = utcnow()
        self.session.add(task)
        record_activity(
            self.session,
            event_type="marketplace.screenshot.captured",
            message=f"Execution screenshot captured for task {task.title}.",
            task_id=task.id,
            agent_id=worker_agent.id,
            board_id=board.id,
        )

    def _task_dispatch_message(self, *, task: Task) -> str:
        attachment_lines = [
            f"- {item.get('name')} ({item.get('content_type')})"
            for item in (task.marketplace_attachments or [])
            if isinstance(item, dict)
        ]
        attachment_block = "\n".join(attachment_lines) if attachment_lines else "- None"
        return "\n".join(
            [
                "CLAWMARKET TASK ASSIGNMENT",
                f"Task: {task.title}",
                f"Task ID: {task.id}",
                f"Type: {task.marketplace_task_type or 'general'}",
                f"Budget: {_amount_label(task.marketplace_budget_amount, task.marketplace_budget_currency)}",
                f"Deadline: {task.due_at.isoformat() if task.due_at else 'N/A'}",
                "",
                "Brief:",
                task.description or task.title,
                "",
                "Attachments:",
                attachment_block,
                "",
                "Hard constraints:",
                "- Only low-sensitivity tasks are allowed.",
                "- Human approval is required before execution and before settlement.",
                "- Never access email or local filesystem.",
                "",
                "Take action: post progress into Mission Control comments and deliver artifacts for review.",
            ]
        )

    def _to_agent_read(self, agent: Agent | None) -> AgentRead | None:
        if agent is None:
            return None
        return AgentLifecycleService.to_agent_read(AgentLifecycleService.with_computed_status(agent))
