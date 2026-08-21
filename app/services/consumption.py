from collections.abc import Awaitable, Callable
from typing import Any

from app.services.consumer_logic import retry_queue_name


async def handle_delivery(
    *,
    event: dict[str, str],
    message: Any,
    process_payment: Callable[[str], Awaitable[tuple[Any | None, dict[str, str] | None]]],
    deliver_webhook: Callable[[str, dict[str, str]], Awaitable[None]],
    mark_delivered: Callable[[str], Awaitable[None]],
    publish_retry: Callable[[dict[str, str], str, int, str], Awaitable[None]],
) -> None:
    try:
        payment, payload = await process_payment(event["payment_id"])
        if payment is None or payload is None:
            await message.ack()
            return
        await deliver_webhook(payment.webhook_url, payload)
        await mark_delivered(str(payment.id))
    except Exception:
        attempt = int(message.headers.get("x-attempt", 1))
        queue_name = retry_queue_name(attempt)
        if queue_name is None:
            await message.reject(requeue=False)
            return
        try:
            await publish_retry(event, queue_name, attempt + 1, message.message_id)
        except Exception:
            await message.nack(requeue=True)
            return
        await message.ack()
        return
    await message.ack()
