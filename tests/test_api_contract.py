from fastapi.testclient import TestClient

from app.api.main import app
from app.db.session import get_session


class EmptySession:
    async def get(self, _: object, __: object) -> None:
        return None


async def fake_session() -> EmptySession:
    yield EmptySession()


def test_api_rejects_missing_or_invalid_key() -> None:
    client = TestClient(app)
    assert client.get("/health").status_code == 401
    assert client.get("/health", headers={"X-API-Key": "wrong"}).status_code == 401


def test_create_validates_request_and_idempotency_key() -> None:
    client = TestClient(app)
    headers = {"X-API-Key": "change-me"}
    response = client.post("/api/v1/payments", headers=headers, json={})
    assert response.status_code == 422

    response = client.post(
        "/api/v1/payments",
        headers=headers,
        json={
            "amount": "10.00",
            "currency": "RUB",
            "description": "order",
            "metadata": {},
            "webhook_url": "https://example.test/hook",
        },
    )
    assert response.status_code == 422


def test_unknown_payment_returns_404() -> None:
    app.dependency_overrides[get_session] = fake_session
    try:
        client = TestClient(app)
        response = client.get(
            "/api/v1/payments/00000000-0000-0000-0000-000000000001",
            headers={"X-API-Key": "change-me"},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
