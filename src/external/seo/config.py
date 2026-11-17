import logging

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.path import ENV_FILE


logger = logging.getLogger(__name__)


class WebhookClientSettings(BaseSettings):
    webhook_base_url: AnyHttpUrl | None = Field(
        default=None,
        description="База удалённого сервиса (без /events)",
        alias="WEBHOOK_BASE_URL",
    )
    webhook_timeout: float = Field(
        default=10.0,
        alias="WEBHOOK_TIMEOUT",
    )
    webhook_retries: int = Field(
        default=0,
        ge=0,
        le=10,
        alias="WEBHOOK_RETRIES",
    )
    webhook_backoff_factor: float = Field(
        default=0.5,
        ge=0.0,
        alias="WEBHOOK_BACKOFF_FACTOR",
    )

    @field_validator("webhook_base_url", mode="before")
    @classmethod
    def empty_base_url_to_none(cls, value: object) -> object:
        """Пустой WEBHOOK_BASE_URL означает «исходящие вебхуки отключены»."""
        if isinstance(value, str) and not value.strip():
            return None

        return value

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


webhook_settings = WebhookClientSettings()
