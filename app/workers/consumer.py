import asyncio
from datetime import UTC, datetime

from faststream import AckPolicy, FastStream
from faststream.rabbit import RabbitBroker
from faststream.rabbit.annotations import RabbitMessage
from sqlalchemy import select

from app.config import get_settings
from app.db.models import Payment
from app.db.session import session_factory
from app.messaging.topology import (
    PAYMENTS_EXCHANGE,
    PAYMENTS_QUEUE,
    RETRY_2_QUEUE,
    RETRY_4_QUEUE,
    declare_topology,
)
from app.services.consumer_logic import requires_gateway
from app.services.consumption import handle_delivery
from app.services.gateway import SimulatedGateway
from app.services.payment import webhook_payload_for
from app.services.webhook import WebhookClient

settings = get_settings()
broker = RabbitBroker(settings.rabbit_url)
app = FastStream(broker)
gateway = SimulatedGateway()
webhook_client = WebhookClient(settings.webhook_timeout_seconds)


@app.after_startup
async def declare_all_queues() -> None:
    await declare_topology(broker)


async def process_payment(payment_id: str) -> tuple[Payment | None, dict[str, str] | None]:
    async with session_factory() as session, session.begin():
        payment = await session.scalar(
            select(Payment).where(Payment.id == payment_id).with_for_update()
        )
        if payment is None or payment.webhook_delivered_at is not None:
            return payment, None
        if requires_gateway(payment.status):
            payment.status = await gateway.process()
            payment.processed_at = datetime.now(UTC)
        return payment, webhook_payload_for(payment)


async def mark_webhook_delivered(payment_id: str) -> None:
    async with session_factory() as session, session.begin():
        payment = await session.scalar(
            select(Payment).where(Payment.id == payment_id).with_for_update()
        )
        if payment is not None and payment.webhook_delivered_at is None:
            payment.webhook_delivered_at = datetime.now(UTC)


@broker.subscriber(PAYMENTS_QUEUE, exchange=PAYMENTS_EXCHANGE, ack_policy=AckPolicy.MANUAL)
async def consume(event: dict[str, str], message: RabbitMessage) -> None:
    async def publish_retry(
        event: dict[str, str], queue_name: str, attempt: int, message_id: str
    ) -> None:
        retry_queue = RETRY_2_QUEUE if queue_name == RETRY_2_QUEUE.name else RETRY_4_QUEUE
        await broker.publish(
            event,
            queue=retry_queue,
            headers={"x-attempt": attempt},
            message_id=message_id,
            mandatory=True,
            persist=True,
        )

    await handle_delivery(
        event=event,
        message=message,
        process_payment=process_payment,
        deliver_webhook=webhook_client.deliver,
        mark_delivered=mark_webhook_delivered,
        publish_retry=publish_retry,
    )


if __name__ == "__main__":
    asyncio.run(app.run())
