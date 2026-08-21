from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    api_key: str = "change-me"
    database_url: str = "postgresql+asyncpg://payments:payments@postgres:5432/payments"
    rabbit_url: str = "amqp://guest:guest@rabbitmq:5672/"
    outbox_poll_interval: float = 1.0
    outbox_batch_size: int = 20
    webhook_timeout_seconds: float = 5.0

    model_config = SettingsConfigDict(env_file=".env", env_prefix="PAYMENTS_", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
