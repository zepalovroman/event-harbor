from faststream.rabbit import ExchangeType, RabbitExchange, RabbitQueue

PAYMENTS_EXCHANGE = RabbitExchange("payments", type=ExchangeType.DIRECT, durable=True)
DLX_EXCHANGE = RabbitExchange("payments.dlx", type=ExchangeType.DIRECT, durable=True)
PAYMENTS_QUEUE = RabbitQueue(
    "payments.new",
    durable=True,
    routing_key="payments.new",
    arguments={
        "x-dead-letter-exchange": "payments.dlx",
        "x-dead-letter-routing-key": "payments.dead",
    },
)
DLQ_QUEUE = RabbitQueue("payments.dlq", durable=True, routing_key="payments.dead")
RETRY_2_QUEUE = RabbitQueue(
    "payments.retry.2",
    durable=True,
    routing_key="payments.retry.2",
    arguments={
        "x-message-ttl": 2000,
        "x-dead-letter-exchange": "payments",
        "x-dead-letter-routing-key": "payments.new",
    },
)
RETRY_4_QUEUE = RabbitQueue(
    "payments.retry.4",
    durable=True,
    routing_key="payments.retry.4",
    arguments={
        "x-message-ttl": 4000,
        "x-dead-letter-exchange": "payments",
        "x-dead-letter-routing-key": "payments.new",
    },
)


async def declare_topology(broker: object) -> None:
    """Declare every exchange and queue so relay can safely publish before consumers start."""
    payments_exchange = await broker.declare_exchange(PAYMENTS_EXCHANGE)
    dlx_exchange = await broker.declare_exchange(DLX_EXCHANGE)
    for queue in (PAYMENTS_QUEUE, RETRY_2_QUEUE, RETRY_4_QUEUE):
        declared_queue = await broker.declare_queue(queue)
        await declared_queue.bind(payments_exchange, routing_key=queue.routing_key)
    dlq = await broker.declare_queue(DLQ_QUEUE)
    await dlq.bind(dlx_exchange, routing_key=DLQ_QUEUE.routing_key)
