from app.messaging.topology import (
    DLQ_QUEUE,
    PAYMENTS_QUEUE,
    RETRY_2_QUEUE,
    RETRY_4_QUEUE,
    declare_topology,
)


def test_main_queue_dead_letters_final_failures_to_dlq() -> None:
    assert PAYMENTS_QUEUE.arguments["x-dead-letter-exchange"] == "payments.dlx"
    assert PAYMENTS_QUEUE.arguments["x-dead-letter-routing-key"] == DLQ_QUEUE.routing_key


def test_retry_queues_return_messages_to_primary_routing_key() -> None:
    for queue in (RETRY_2_QUEUE, RETRY_4_QUEUE):
        assert queue.arguments["x-dead-letter-exchange"] == "payments"
        assert queue.arguments["x-dead-letter-routing-key"] == "payments.new"


async def test_topology_declares_then_binds_every_queue() -> None:
    calls: list[tuple[str, str, str]] = []

    class DeclaredQueue:
        def __init__(self, name: str) -> None:
            self.name = name

        async def bind(self, exchange: str, routing_key: str) -> None:
            calls.append((self.name, exchange, routing_key))

    class Broker:
        async def declare_exchange(self, exchange: object) -> str:
            return exchange.name

        async def declare_queue(self, queue: object) -> DeclaredQueue:
            return DeclaredQueue(queue.name)

    await declare_topology(Broker())

    assert calls == [
        ("payments.new", "payments", "payments.new"),
        ("payments.retry.2", "payments", "payments.retry.2"),
        ("payments.retry.4", "payments", "payments.retry.4"),
        ("payments.dlq", "payments.dlx", "payments.dead"),
    ]
