import hashlib
import json
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OutboxEvent, Payment


def canonical_request_hash(data: dict[str, Any]) -> str:
    normalized = json.dumps(data, default=str, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode()).hexdigest()


def created_event_payload(payment: Payment, event_id: uuid.UUID) -> dict[str, str]:
    return {
        "event_id": str(event_id),
        "payment_id": str(payment.id),
        "event_type": "payment.created.v1",
    }


def webhook_event_id(payment_id: uuid.UUID) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"payment.processed.v1:{payment_id}"))


def payment_event_payload(
    *,
    event_id: str,
    payment_id: str,
    status: str,
    amount: Decimal,
    currency: str,
    processed_at: str,
) -> dict[str, str]:
    return {
        "event_id": event_id,
        "event_type": "payment.processed.v1",
        "payment_id": payment_id,
        "status": status,
        "amount": f"{amount:.2f}",
        "currency": currency,
        "processed_at": processed_at,
    }


async def create_payment_with_outbox(
    session: AsyncSession,
    *,
    amount: Decimal,
    currency: str,
    description: str,
    metadata: dict[str, Any],
    webhook_url: str,
    idempotency_key: str,
    request_hash: str,
) -> Payment:
    payment = Payment(
        amount=amount,
        currency=currency,
        description=description,
        metadata_=metadata,
        webhook_url=webhook_url,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    session.add(payment)
    await session.flush()
    event_id = uuid.uuid4()
    event = OutboxEvent(
        id=event_id,
        payment_id=payment.id,
        event_type="payment.created.v1",
        payload=created_event_payload(payment, event_id),
    )
    session.add(event)
    return payment


def webhook_payload_for(payment: Payment) -> dict[str, str]:
    assert payment.processed_at is not None
    return payment_event_payload(
        event_id=webhook_event_id(payment.id),
        payment_id=str(payment.id),
        status=payment.status,
        amount=payment.amount,
        currency=payment.currency,
        processed_at=payment.processed_at.isoformat(),
    )
