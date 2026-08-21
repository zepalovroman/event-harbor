import uuid

from app.db.models import OutboxEvent
from app.workers.outbox import publish_one


class Session:
    def __init__(self, event: OutboxEvent) -> None:
        self.event = event

    async def scalar(self, _: object) -> OutboxEvent:
        return self.event


class FailingBroker:
    async def publish(self, *_: object, **__: object) -> None:
        raise RuntimeError("broker unavailable")


class Broker:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] = {}

    async def publish(self, *_: object, **kwargs: object) -> None:
        self.kwargs = kwargs


def event() -> OutboxEvent:
    return OutboxEvent(
        id=uuid.uuid4(),
        payment_id=uuid.uuid4(),
        event_type="payment.created.v1",
        payload={"event_id": "payload-event", "payment_id": "payment"},
    )


async def test_publish_failure_keeps_event_unpublished_for_retry() -> None:
    outbox_event = event()

    published = await publish_one(Session(outbox_event), FailingBroker())

    assert published is False
    assert outbox_event.attempts == 1
    assert outbox_event.last_error == "broker unavailable"
    assert outbox_event.published_at is None


async def test_publish_success_marks_event_only_after_confirm_and_is_persistent() -> None:
    outbox_event = event()
    broker = Broker()

    published = await publish_one(Session(outbox_event), broker)

    assert published is True
    assert outbox_event.published_at is not None
    assert broker.kwargs["mandatory"] is True
    assert broker.kwargs["persist"] is True
    assert broker.kwargs["message_id"] == str(outbox_event.id)
