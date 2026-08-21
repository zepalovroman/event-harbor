from app.services.consumer_logic import requires_gateway, retry_queue_name


def test_only_pending_payment_requires_gateway() -> None:
    assert requires_gateway("pending") is True
    assert requires_gateway("succeeded") is False
    assert requires_gateway("failed") is False


def test_retry_routing_allows_three_attempts_total() -> None:
    assert retry_queue_name(1) == "payments.retry.2"
    assert retry_queue_name(2) == "payments.retry.4"
    assert retry_queue_name(3) is None
