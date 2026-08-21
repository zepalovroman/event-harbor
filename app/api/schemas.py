from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: Literal["RUB", "USD", "EUR"]
    description: str = Field(min_length=1, max_length=255)
    metadata: dict[str, Any]
    webhook_url: AnyHttpUrl

    @field_validator("amount")
    @classmethod
    def amount_has_at_most_two_decimal_places(cls, value: Decimal) -> Decimal:
        if value.as_tuple().exponent < -2:
            raise ValueError("amount must have at most two decimal places")
        return value.quantize(Decimal("0.01"))


class PaymentAccepted(BaseModel):
    payment_id: UUID
    status: str
    created_at: datetime


class PaymentDetails(PaymentAccepted):
    model_config = ConfigDict(from_attributes=True)

    amount: Decimal
    currency: str
    description: str
    metadata: dict[str, Any]
    webhook_url: str
    processed_at: datetime | None
    webhook_delivered_at: datetime | None
