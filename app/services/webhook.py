from typing import Any

import httpx


class WebhookDeliveryError(RuntimeError):
    pass


class WebhookClient:
    def __init__(self, timeout_seconds: float) -> None:
        self._timeout = timeout_seconds

    async def deliver(self, url: str, payload: dict[str, Any]) -> None:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Idempotency-Key": str(payload["event_id"])},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise WebhookDeliveryError(str(exc)) from exc
