# Payment Processor

Небольшой асинхронный сервис обработки платежей на Python 3.12. Он создаёт платёж и outbox-событие в одной PostgreSQL-транзакции, после чего отдельный relay публикует его в RabbitMQ. Consumer эмулирует шлюз и доставляет webhook.

## Запуск

```bash
PAYMENTS_API_KEY=local-secret docker compose --profile test up --build
```

API доступен на `http://localhost:8000`, OpenAPI — `/docs`, RabbitMQ UI — `http://localhost:15672` (`guest` / `guest`). Test profile добавляет receiver на `http://localhost:8081`.

```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H 'X-API-Key: local-secret' \
  -H 'Idempotency-Key: order-1001' \
  -H 'Content-Type: application/json' \
  -d '{"amount":"125.50","currency":"RUB","description":"Order #1001","metadata":{"order_id":1001},"webhook_url":"http://webhook-receiver:8080/"}'
```

Ответ `202` содержит `payment_id`. Повторите тот же запрос с тем же ключом — будет возвращён тот же платёж; другое тело с тем же ключом вернёт `409`. Проверка состояния:

```bash
curl http://localhost:8000/api/v1/payments/<payment_id> -H 'X-API-Key: local-secret'
```

## Доставка и retries

- Relay ставит `published_at` только после RabbitMQ publisher confirm. Повторная публикация после сбоя между confirm и commit допустима: доставка **at-least-once**.
- Consumer подтверждает исходное сообщение только после подтверждённой постановки retry-сообщения. Попыток webhook ровно три: исходная, через 2 сек., через 4 сек.; затем сообщение попадёт в `payments.dlq`.
- Шлюз вызывается только для `pending`. Для terminal-платежа повторяется только недоставленный webhook. После HTTP 2xx timestamp сохраняется до ack; повтор callback при сбое в этом окне возможен и должен дедуплицироваться получателем по `Idempotency-Key` (`event_id`).
- `failed` — нормальный результат шлюза, не технический retry.

## Переменные

`PAYMENTS_API_KEY`, `PAYMENTS_DATABASE_URL`, `PAYMENTS_RABBIT_URL`, `PAYMENTS_OUTBOX_POLL_INTERVAL`, `PAYMENTS_OUTBOX_BATCH_SIZE`, `PAYMENTS_WEBHOOK_TIMEOUT_SECONDS`.

## Проверка

```bash
uv sync --all-groups
uv run ruff check .
uv run ruff format --check .
uv run pytest
docker compose config
```
