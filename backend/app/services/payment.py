"""Escrow payment service with mock and Stripe test-mode adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException, status
from sqlmodel import col

from app.core.config import settings
from app.core.time import utcnow
from app.models.payments import Payment


@dataclass(frozen=True, slots=True)
class ProviderPaymentIntent:
    """Normalized provider intent payload."""

    provider_payment_id: str
    client_secret: str | None
    status: str
    raw: dict[str, Any]


class PaymentService:
    """Create, capture, and refund marketplace escrow payments."""

    def __init__(self, session) -> None:
        self.session = session

    @property
    def platform_fee_bps(self) -> int:
        return max(0, settings.clawmarket_platform_fee_bps)

    def split_amount(self, amount: int) -> tuple[int, int]:
        fee = amount * self.platform_fee_bps // 10_000
        return fee, max(amount - fee, 0)

    async def get_by_task(self, *, task_id: UUID) -> Payment | None:
        return (
            await Payment.objects.filter_by(task_id=task_id)
            .order_by(col(Payment.created_at).desc())
            .first(self.session)
        )

    async def create_escrow(
        self,
        *,
        task_id: UUID,
        amount: int,
        currency: str,
        payer_id: UUID,
        payee_id: UUID,
        description: str,
    ) -> Payment:
        existing = await self.get_by_task(task_id=task_id)
        if existing is not None:
            return existing

        fee_amount, payee_amount = self.split_amount(amount)
        provider = settings.payment_provider.strip().lower() or "mock"
        intent = await self._create_provider_intent(
            amount=amount,
            currency=currency,
            description=description,
            metadata={"task_id": str(task_id), "payee_id": str(payee_id)},
        )
        if bool(intent.raw.get("mock")):
            provider = "mock"
        payment = Payment(
            task_id=task_id,
            amount=amount,
            currency=currency,
            status="escrowed",
            payer_id=payer_id,
            payee_id=payee_id,
            provider=provider,
            provider_payment_id=intent.provider_payment_id,
            provider_client_secret=intent.client_secret,
            platform_fee_amount=fee_amount,
            payee_amount=payee_amount,
            metadata_=intent.raw,
        )
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def release(self, payment: Payment, *, reason: str | None = None) -> Payment:
        if payment.status == "released":
            return payment
        if payment.status == "refunded":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot release a refunded payment.",
            )
        await self._capture_provider_payment(payment)
        payment.status = "released"
        payment.released_at = utcnow()
        payment.updated_at = utcnow()
        if reason:
            payment.metadata_ = {**payment.metadata_, "release_reason": reason}
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def refund(self, payment: Payment, *, reason: str | None = None) -> Payment:
        if payment.status == "refunded":
            return payment
        await self._refund_provider_payment(payment)
        payment.status = "refunded"
        payment.refunded_at = utcnow()
        payment.updated_at = utcnow()
        if reason:
            payment.metadata_ = {**payment.metadata_, "refund_reason": reason}
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def _create_provider_intent(
        self,
        *,
        amount: int,
        currency: str,
        description: str,
        metadata: dict[str, str],
    ) -> ProviderPaymentIntent:
        provider = settings.payment_provider.strip().lower()
        if provider != "stripe_test":
            return self._mock_intent(amount=amount, currency=currency)

        secret = settings.stripe_secret_key.strip()
        test_method = settings.stripe_test_payment_method.strip()
        if not secret or not test_method:
            return self._mock_intent(amount=amount, currency=currency)

        form_data: dict[str, str] = {
            "amount": str(amount),
            "currency": currency.lower(),
            "capture_method": "manual",
            "confirm": "true",
            "payment_method": test_method,
            "description": description,
            "automatic_payment_methods[enabled]": "true",
        }
        for key, value in metadata.items():
            form_data[f"metadata[{key}]"] = value

        payload = await self._stripe_request("POST", "/payment_intents", data=form_data)
        provider_payment_id = str(payload.get("id") or "")
        if not provider_payment_id:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Stripe did not return a payment intent id.",
            )
        return ProviderPaymentIntent(
            provider_payment_id=provider_payment_id,
            client_secret=payload.get("client_secret"),
            status=str(payload.get("status") or "requires_capture"),
            raw=payload,
        )

    async def _capture_provider_payment(self, payment: Payment) -> None:
        if payment.provider != "stripe_test":
            return
        secret = settings.stripe_secret_key.strip()
        if not secret or not payment.provider_payment_id:
            return
        await self._stripe_request(
            "POST",
            f"/payment_intents/{payment.provider_payment_id}/capture",
            data={},
        )

    async def _refund_provider_payment(self, payment: Payment) -> None:
        if payment.provider != "stripe_test":
            return
        secret = settings.stripe_secret_key.strip()
        if not secret or not payment.provider_payment_id:
            return
        await self._stripe_request(
            "POST",
            "/refunds",
            data={"payment_intent": payment.provider_payment_id},
        )

    async def _stripe_request(
        self,
        method: str,
        path: str,
        *,
        data: dict[str, str],
    ) -> dict[str, Any]:
        secret = settings.stripe_secret_key.strip()
        url = f"{settings.stripe_api_base.rstrip('/')}{path}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.request(
                method,
                url,
                data=data,
                auth=(secret, ""),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if response.status_code >= 400:
            detail = response.text
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Payment provider request failed: {detail}",
            )
        payload = response.json()
        if isinstance(payload, dict):
            return payload
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unexpected payment provider response.",
        )

    @staticmethod
    def _mock_intent(*, amount: int, currency: str) -> ProviderPaymentIntent:
        provider_payment_id = f"pi_mock_{uuid4().hex[:18]}"
        return ProviderPaymentIntent(
            provider_payment_id=provider_payment_id,
            client_secret=f"{provider_payment_id}_secret_mock",
            status="requires_capture",
            raw={"mock": True, "amount": amount, "currency": currency},
        )
