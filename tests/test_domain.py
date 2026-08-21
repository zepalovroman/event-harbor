from decimal import Decimal

from app.services.payment import canonical_request_hash, payment_event_payload


def test_canonical_request_hash_is_stable_for_equivalent_json() -> None:
    first = {
        "amount": Decimal("10.00"),
        "currency": "RUB",
        "description": "Order",
        "metadata": {"b": 2, "a": 1},
        "webhook_url": "https://example.test/hook",
    }
    second = {**first, "metadata": {"a": 1, "b": 2}}

    assert canonical_request_hash(first) == canonical_request_hash(second)


def test_webhook_payload_uses_stable_event_id_and_string_amount() -> None:
    payload = payment_event_payload(
        event_id="event-1",
        payment_id="payment-1",
        status="succeeded",
        amount=Decimal("12.30"),
        currency="EUR",
        processed_at="2026-01-01T00:00:00+00:00",
    )

    assert payload == {
        "event_id": "event-1",
        "event_type": "payment.processed.v1",
        "payment_id": "payment-1",
        "status": "succeeded",
        "amount": "12.30",
        "currency": "EUR",
        "processed_at": "2026-01-01T00:00:00+00:00",
    }
