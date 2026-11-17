import logging

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.path import ENV_FILE


logger = logging.getLogger(__name__)


class S3Settings(BaseSettings):
    s3_endpoint: str = Field(..., alias="S3_ENDPOINT")
    s3_bucket: str = Field(..., alias="S3_BUCKET")
    aws_access_key: str = Field(..., alias="AWS_ACCESS_KEY")
    aws_secret_key: str = Field(..., alias="AWS_SECRET_KEY")
    s3_region: str = Field(
        "", alias="S3_REGION"
    )  # Опционально, для Yandex/VK не обязательно

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


# Создаём экземпляр
s3_settings = S3Settings()
