# external/suggest/config.py
import logging

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.path import ENV_FILE


logger = logging.getLogger(__name__)


class SuggestSettings(BaseSettings):
    suggest_api_key: str = Field(..., description="Suggest API token")
    suggest_base_url: str = Field(
        default="https://suggestions.dadata.ru/suggestions/api/4_1/rs",
        description="Suggest base URL",
    )
    suggest_timeout: float = Field(
        default=10.0, description="Request timeout in seconds"
    )
    suggest_max_suggestions: int = Field(
        default=10, ge=1, le=20, description="Max suggestions count"
    )

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


settings = SuggestSettings()
