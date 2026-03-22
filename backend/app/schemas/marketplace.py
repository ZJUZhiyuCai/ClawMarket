"""Schemas for ClawMarket supplier, task, and arbitration APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator
from sqlmodel import SQLModel

from app.schemas.agents import AgentRead
from app.schemas.common import NonEmptyStr
from app.schemas.payments import PaymentRead
from app.schemas.tasks import TaskRead

MarketplaceRole = Literal["supplier", "requester"]
MarketplaceTaskType = Literal["crawl", "excel", "report", "code"]
PricingMode = Literal["fixed", "hourly"]
ArbitrationDecision = Literal["refund", "release_supplier"]
RUNTIME_ANNOTATION_TYPES = (datetime, UUID, AgentRead, PaymentRead, TaskRead, NonEmptyStr)


class AvailabilityWindow(SQLModel):
    """Supplier availability declaration."""

    day: NonEmptyStr
    start: NonEmptyStr
    end: NonEmptyStr


class SupplierPricing(SQLModel):
    """Marketplace supplier pricing configuration."""

    mode: PricingMode = "fixed"
    amount: int = Field(ge=0)
    currency: str = "cny"


class SupplierAgentRegister(SQLModel):
    """Supplier self-service gateway registration payload."""

    gateway_name: NonEmptyStr
    gateway_url: NonEmptyStr
    auth_token: str | None = None
    allow_insecure_tls: bool = False
    disable_device_pairing: bool = False
    workspace_root: str = "/workspace"
    pricing: SupplierPricing
    availability: list[AvailabilityWindow] = Field(default_factory=list)
    max_concurrency: int = Field(default=1, ge=1, le=20)
    skill_tags: list[str] = Field(default_factory=list)

    @field_validator("skill_tags", mode="before")
    @classmethod
    def normalize_skill_tags(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        for item in value:
            text = str(item).strip().lower()
            if text and text not in normalized:
                normalized.append(text)
        return normalized


class SupplierAgentRead(SQLModel):
    """Read model for supplier dashboard cards."""

    agent: AgentRead
    gateway_connected: bool
    imported_skills: list[str] = Field(default_factory=list)
    active_tasks: int = 0
    completed_tasks: int = 0
    total_revenue_amount: int = 0


class MarketplaceFileUpload(SQLModel):
    """Inline attachment payload used by the MVP upload flow."""

    filename: NonEmptyStr
    content_type: NonEmptyStr
    size_bytes: int = Field(ge=0)
    data_base64: NonEmptyStr


class MarketplaceTaskCreate(SQLModel):
    """Requester task-posting payload."""

    description: NonEmptyStr
    budget_amount: int = Field(ge=0)
    deadline_at: datetime
    task_type: MarketplaceTaskType
    attachments: list[MarketplaceFileUpload] = Field(default_factory=list)
    public_market: bool = True


class MarketplaceMatchRequest(SQLModel):
    """Re-run match selection for one task."""

    task_id: UUID


class MarketplaceMatchCandidate(SQLModel):
    """Single ranked supplier match for a task."""

    agent_id: UUID
    owner_id: UUID | None = None
    name: str
    score: float
    current_load: int
    max_concurrency: int
    skills: list[str] = Field(default_factory=list)
    skill_tags: list[str] = Field(default_factory=list)
    pricing: dict[str, object] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)


class MarketplaceTaskSelect(SQLModel):
    """Select one supplier listing from the top matches."""

    agent_id: UUID


class MarketplaceApprovalDecisionPayload(SQLModel):
    """Approve/reject a supplier or requester step."""

    approve: bool
    comment: str | None = None


class MarketplaceDeliverySubmit(SQLModel):
    """Supplier delivery submission payload."""

    note: NonEmptyStr
    artifacts: list[MarketplaceFileUpload] = Field(default_factory=list)


class MarketplaceTaskRead(SQLModel):
    """Expanded marketplace task view."""

    task: TaskRead
    payment: PaymentRead | None = None
    listing_agent: AgentRead | None = None
    worker_agent: AgentRead | None = None
    pending_approvals: list[dict[str, object]] = Field(default_factory=list)


class SupplierDashboardRead(SQLModel):
    """Supplier dashboard response."""

    agents: list[SupplierAgentRead] = Field(default_factory=list)
    active_tasks: list[MarketplaceTaskRead] = Field(default_factory=list)
    income_released_amount: int = 0
    income_pending_amount: int = 0


class RequesterDashboardRead(SQLModel):
    """Requester dashboard response."""

    tasks: list[MarketplaceTaskRead] = Field(default_factory=list)
    history_cases: list[MarketplaceTaskRead] = Field(default_factory=list)


class ArbitrationResolve(SQLModel):
    """Admin arbitration decision payload."""

    decision: ArbitrationDecision
    comment: str | None = None


class ArbitrationCaseRead(SQLModel):
    """Admin arbitration case card."""

    task: MarketplaceTaskRead
    timeline: list[dict[str, object]] = Field(default_factory=list)
