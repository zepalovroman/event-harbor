from types import SimpleNamespace

from app.services.consumption import handle_delivery


class Message:
    def __init__(self, attempt: int) -> None:
        self.headers = {"x-attempt": attempt}
        self.message_id = "message-1"
        self.actions: list[str] = []

    async def ack(self) -> None:
        self.actions.append("ack")

    async def reject(self, *, requeue: bool) -> None:
        assert requeue is False
        self.actions.append("reject")

    async def nack(self, *, requeue: bool) -> None:
        assert requeue is True
        self.actions.append("nack")


async def test_technical_webhook_failure_publishes_retry_before_ack() -> None:
    actions: list[tuple[str, object]] = []
    message = Message(attempt=1)
    payment = SimpleNamespace(id="payment-1", webhook_url="https://example.test")

    async def process(_: str) -> tuple[object, dict[str, str]]:
        return payment, {"event_id": "event-1"}

    async def failing_delivery(_: str, __: dict[str, str]) -> None:
        raise RuntimeError("timeout")

    async def mark(_: str) -> None:
        raise AssertionError("must not mark delivery")

    async def publish(event: dict[str, str], queue: str, attempt: int, message_id: str) -> None:
        actions.append(("publish", (event, queue, attempt, message_id)))

    await handle_delivery(
        event={"payment_id": "payment-1"},
        message=message,
        process_payment=process,
        deliver_webhook=failing_delivery,
        mark_delivered=mark,
        publish_retry=publish,
    )

    assert actions == [
        ("publish", ({"payment_id": "payment-1"}, "payments.retry.2", 2, "message-1"))
    ]
    assert message.actions == ["ack"]


async def test_third_technical_failure_rejects_to_dlq() -> None:
    message = Message(attempt=3)
    payment = SimpleNamespace(id="payment-1", webhook_url="https://example.test")

    async def process(_: str) -> tuple[object, dict[str, str]]:
        return payment, {"event_id": "event-1"}

    async def failing_delivery(_: str, __: dict[str, str]) -> None:
        raise RuntimeError("timeout")

    async def unexpected(*_: object) -> None:
        raise AssertionError("must not be called")

    await handle_delivery(
        event={"payment_id": "payment-1"},
        message=message,
        process_payment=process,
        deliver_webhook=failing_delivery,
        mark_delivered=unexpected,
        publish_retry=unexpected,
    )

    assert message.actions == ["reject"]


async def test_terminal_payment_without_delivery_skips_gateway_in_process_dependency() -> None:
    message = Message(attempt=1)
    payment = SimpleNamespace(id="payment-1", webhook_url="https://example.test")
    deliveries: list[dict[str, str]] = []

    async def process(_: str) -> tuple[object, dict[str, str]]:
        return payment, {"event_id": "event-1", "status": "failed"}

    async def deliver(_: str, payload: dict[str, str]) -> None:
        deliveries.append(payload)

    async def mark(_: str) -> None:
        return None

    async def retry(*_: object) -> None:
        raise AssertionError("business failure must not retry")

    await handle_delivery(
        event={"payment_id": "payment-1"},
        message=message,
        process_payment=process,
        deliver_webhook=deliver,
        mark_delivered=mark,
        publish_retry=retry,
    )

    assert deliveries == [{"event_id": "event-1", "status": "failed"}]
    assert message.actions == ["ack"]


async def test_database_failure_before_webhook_routes_to_retry() -> None:
    message = Message(attempt=1)
    retries: list[tuple[str, int]] = []

    async def failing_process(_: str) -> tuple[object, dict[str, str]]:
        raise RuntimeError("database unavailable")

    async def unexpected(*_: object) -> None:
        raise AssertionError("must not be called")

    async def retry(_: dict[str, str], queue: str, attempt: int, __: str) -> None:
        retries.append((queue, attempt))

    await handle_delivery(
        event={"payment_id": "payment-1"},
        message=message,
        process_payment=failing_process,
        deliver_webhook=unexpected,
        mark_delivered=unexpected,
        publish_retry=retry,
    )

    assert retries == [("payments.retry.2", 2)]
    assert message.actions == ["ack"]


async def test_database_failure_after_webhook_routes_to_retry() -> None:
    message = Message(attempt=2)
    payment = SimpleNamespace(id="payment-1", webhook_url="https://example.test")

    async def process(_: str) -> tuple[object, dict[str, str]]:
        return payment, {"event_id": "event-1"}

    async def deliver(_: str, __: dict[str, str]) -> None:
        return None

    async def failing_mark(_: str) -> None:
        raise RuntimeError("database unavailable")

    retries: list[tuple[str, int]] = []

    async def retry(_: dict[str, str], queue: str, attempt: int, __: str) -> None:
        retries.append((queue, attempt))

    await handle_delivery(
        event={"payment_id": "payment-1"},
        message=message,
        process_payment=process,
        deliver_webhook=deliver,
        mark_delivered=failing_mark,
        publish_retry=retry,
    )

    assert retries == [("payments.retry.4", 3)]
    assert message.actions == ["ack"]


async def test_retry_publish_failure_nacks_original_message() -> None:
    message = Message(attempt=1)

    async def failing_process(_: str) -> tuple[object, dict[str, str]]:
        raise RuntimeError("database unavailable")

    async def unexpected(*_: object) -> None:
        raise AssertionError("must not be called")

    async def failing_retry(*_: object) -> None:
        raise RuntimeError("broker unavailable")

    await handle_delivery(
        event={"payment_id": "payment-1"},
        message=message,
        process_payment=failing_process,
        deliver_webhook=unexpected,
        mark_delivered=unexpected,
        publish_retry=failing_retry,
    )

    assert message.actions == ["nack"]
