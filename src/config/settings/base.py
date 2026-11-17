import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

from config.path import ENV_FILE


logger = logging.getLogger(__name__)


class BaseAppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
