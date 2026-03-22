"""Rule-based supplier matching for ClawMarket MVP."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import TYPE_CHECKING
from uuid import UUID

from sqlmodel import col, select

from app.models.agents import Agent
from app.models.tasks import Task
from app.schemas.marketplace import MarketplaceMatchCandidate

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

ACTIVE_MARKETPLACE_STATES = {
    "awaiting_payment",
    "awaiting_supplier_approval",
    "executing",
    "awaiting_acceptance",
    "disputed",
}
TASK_TYPE_KEYWORDS: dict[str, set[str]] = {
    "crawl": {"crawl", "crawler", "scrape", "scraping", "web", "browser", "research"},
    "excel": {"excel", "sheet", "spreadsheet", "csv", "xlsx", "cleanup", "formula"},
    "report": {"report", "summary", "deck", "analysis", "brief", "insight"},
    "code": {"code", "script", "api", "automation", "python", "typescript", "debug"},
}


def _normalize_terms(values: Iterable[str]) -> set[str]:
    terms: set[str] = set()
    for value in values:
        for token in re.split(r"[^a-z0-9]+", value.lower()):
            if token:
                terms.add(token)
    return terms


def _extract_price_amount(agent: Agent) -> int:
    raw_amount = agent.pricing.get("amount") if isinstance(agent.pricing, dict) else None
    if isinstance(raw_amount, int):
        return max(raw_amount, 0)
    if isinstance(raw_amount, float):
        return max(int(raw_amount), 0)
    if isinstance(raw_amount, str):
        try:
            return max(int(float(raw_amount)), 0)
        except ValueError:
            return 0
    return 0


def _task_terms(task: Task) -> set[str]:
    values = [task.title, task.description or "", task.marketplace_task_type or ""]
    keywords = TASK_TYPE_KEYWORDS.get(task.marketplace_task_type or "", set())
    return _normalize_terms([*values, *keywords])


class MatchingService:
    """Simple weighted matcher using skills, score, load, and price."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _current_load(self, *, listing_agent_id: UUID) -> int:
        statement = (
            select(col(Task.id))
            .where(col(Task.marketplace_listing_agent_id) == listing_agent_id)
            .where(col(Task.marketplace_state).in_(ACTIVE_MARKETPLACE_STATES))
        )
        return len(list(await self.session.exec(statement)))

    def _match_skill_score(self, *, task: Task, agent: Agent) -> tuple[float, list[str]]:
        terms = _task_terms(task)
        agent_terms = _normalize_terms(
            [
                *(agent.skills or []),
                *(agent.skill_tags or []),
                task.marketplace_task_type or "",
            ]
        )
        overlap = sorted(terms & agent_terms)
        reasons: list[str] = []
        if overlap:
            reasons.append(f"Skill overlap: {', '.join(overlap[:4])}")
        type_terms = TASK_TYPE_KEYWORDS.get(task.marketplace_task_type or "", set())
        type_overlap = len(type_terms & agent_terms)
        score = min(55.0, float(len(overlap) * 8 + type_overlap * 10))
        if score == 0:
            reasons.append("No direct skill overlap, relying on generic score and load.")
        return score, reasons

    def _price_score(self, *, task: Task, agent: Agent) -> tuple[float, str]:
        budget = task.marketplace_budget_amount or 0
        amount = _extract_price_amount(agent)
        if budget <= 0 or amount <= 0:
            return 5.0, "Price neutral."
        if amount <= budget:
            ratio = amount / budget if budget else 1.0
            return max(6.0, 20.0 - ratio * 10.0), "Fits budget."
        overflow = amount - budget
        penalty = min(18.0, max(6.0, overflow / max(budget, 1) * 25.0))
        return -penalty, "Above budget."

    async def match_task(self, task: Task, *, limit: int = 3) -> list[MarketplaceMatchCandidate]:
        statement = (
            select(Agent)
            .where(col(Agent.marketplace_enabled).is_(True))
            .where(col(Agent.board_id).is_(None))
            .order_by(col(Agent.updated_at).desc())
        )
        agents = list(await self.session.exec(statement))
        ranked: list[MarketplaceMatchCandidate] = []

        for agent in agents:
            if not agent.owner_id:
                continue
            if agent.status in {"offline", "deleting"}:
                continue

            current_load = await self._current_load(listing_agent_id=agent.id)
            max_concurrency = max(int(agent.max_concurrency or 1), 1)
            skill_score, reasons = self._match_skill_score(task=task, agent=agent)
            reputation_score = max(0.0, min(float(agent.score or 0.0), 100.0)) * 0.25
            load_penalty = min(24.0, (current_load / max_concurrency) * 18.0)
            if current_load >= max_concurrency:
                load_penalty += 8.0
                reasons.append("Currently at or above declared concurrency.")
            else:
                reasons.append(f"Current load {current_load}/{max_concurrency}.")
            price_score, price_reason = self._price_score(task=task, agent=agent)
            reasons.append(price_reason)
            final_score = round(skill_score + reputation_score + price_score - load_penalty, 2)
            ranked.append(
                MarketplaceMatchCandidate(
                    agent_id=agent.id,
                    owner_id=agent.owner_id,
                    name=agent.name,
                    score=final_score,
                    current_load=current_load,
                    max_concurrency=max_concurrency,
                    skills=list(agent.skills or []),
                    skill_tags=list(agent.skill_tags or []),
                    pricing=dict(agent.pricing or {}),
                    reasons=reasons,
                )
            )

        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[:limit]
