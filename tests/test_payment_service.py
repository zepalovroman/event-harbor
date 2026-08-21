import uuid
from decimal import Decimal

from app.db.models import OutboxEvent, Payment
from app.services.payment import create_payment_with_outbox


class Session:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, item: object) -> None:
        self.added.append(item)

    async def flush(self) -> None:
        for item in self.added:
            if isinstance(item, Payment) and item.id is None:
                item.id = uuid.uuid4()


async def test_payment_and_outbox_share_event_id_in_single_session() -> None:
    session = Session()
    payment = await create_payment_with_outbox(
        session,
        amount=Decimal("12.00"),
        currency="RUB",
        description="order",
        metadata={},
        webhook_url="https://example.test/hook",
        idempotency_key="key",
        request_hash="hash",
    )

    event = next(item for item in session.added if isinstance(item, OutboxEvent))
    assert event.payment_id == payment.id
    assert event.payload["event_id"] == str(event.id)
