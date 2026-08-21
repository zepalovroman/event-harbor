import asyncio
import logging
from datetime import UTC, datetime

from faststream.rabbit import RabbitBroker
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import OutboxEvent
from app.db.session import session_factory
from app.messaging.topology import PAYMENTS_EXCHANGE, declare_topology

logger = logging.getLogger(__name__)


async def publish_one(session: AsyncSession, broker: RabbitBroker) -> bool:
    event = await session.scalar(
        select(OutboxEvent)
        .where(OutboxEvent.published_at.is_(None))
        .order_by(OutboxEvent.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if event is None:
        return False
    try:
        await broker.publish(
            event.payload,
            exchange=PAYMENTS_EXCHANGE,
            routing_key="payments.new",
            headers={"x-attempt": 1},
            message_id=str(event.id),
            mandatory=True,
            persist=True,
        )
    except Exception as exc:
        event.attempts = (event.attempts or 0) + 1
        event.last_error = str(exc)[:2000]
        logger.exception("outbox publish failed", extra={"event_id": str(event.id)})
        return False
    event.published_at = datetime.now(UTC)
    event.attempts = (event.attempts or 0) + 1
    event.last_error = None
    return True


async def run() -> None:
    settings = get_settings()
    broker = RabbitBroker(settings.rabbit_url)
    await broker.connect()
    await declare_topology(broker)
    try:
        while True:
            published = 0
            for _ in range(settings.outbox_batch_size):
                async with session_factory() as session, session.begin():
                    did_publish = await publish_one(session, broker)
                if not did_publish:
                    break
                published += 1
            if not published:
                await asyncio.sleep(settings.outbox_poll_interval)
    finally:
        await broker.close()


if __name__ == "__main__":
    asyncio.run(run())
