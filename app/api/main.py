import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.openapi.utils import get_openapi
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import PaymentAccepted, PaymentCreate, PaymentDetails
from app.config import Settings, get_settings
from app.db.models import Payment
from app.db.session import get_session
from app.services.payment import canonical_request_hash, create_payment_with_outbox


def require_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    if x_api_key is None or not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid API key")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield


app = FastAPI(
    title="Payment Processor",
    version="1.0.0",
    license_info={"name": "MIT"},
    servers=[{"url": "http://localhost:8000", "description": "Local Compose"}],
    lifespan=lifespan,
)


def custom_openapi() -> dict:
    schema = app.openapi_schema
    if schema is None:
        schema = get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
            servers=app.servers,
            license_info=app.license_info,
        )
        schema.setdefault("components", {}).setdefault("securitySchemes", {})["ApiKeyAuth"] = {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        }
        schema["security"] = [{"ApiKeyAuth": []}]
        app.openapi_schema = schema
    return schema


app.openapi = custom_openapi


@app.get("/health", dependencies=[Depends(require_api_key)])
async def health(session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/api/v1/payments", response_model=PaymentAccepted, status_code=status.HTTP_202_ACCEPTED)
async def create_payment(
    body: PaymentCreate,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    _: None = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> PaymentAccepted:
    if not idempotency_key or len(idempotency_key) > 255:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Idempotency-Key is required"
        )
    raw = body.model_dump(mode="json")
    request_hash = canonical_request_hash(raw)
    try:
        async with session.begin():
            payment = await create_payment_with_outbox(
                session,
                amount=body.amount,
                currency=body.currency,
                description=body.description,
                metadata=body.metadata,
                webhook_url=str(body.webhook_url),
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
    except IntegrityError:
        existing = await session.scalar(
            select(Payment).where(Payment.idempotency_key == idempotency_key)
        )
        if existing is None:
            raise
        if not secrets.compare_digest(existing.request_hash, request_hash):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="idempotency key reused with different payload",
            )
        payment = existing
    return PaymentAccepted(
        payment_id=payment.id, status=payment.status, created_at=payment.created_at
    )


@app.get(
    "/api/v1/payments/{payment_id}",
    response_model=PaymentDetails,
    dependencies=[Depends(require_api_key)],
)
async def get_payment(
    payment_id: UUID, session: Annotated[AsyncSession, Depends(get_session)]
) -> PaymentDetails:
    payment = await session.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payment not found")
    return PaymentDetails(
        payment_id=payment.id,
        status=payment.status,
        created_at=payment.created_at,
        amount=payment.amount,
        currency=payment.currency,
        description=payment.description,
        metadata=payment.metadata_,
        webhook_url=payment.webhook_url,
        processed_at=payment.processed_at,
        webhook_delivered_at=payment.webhook_delivered_at,
    )
