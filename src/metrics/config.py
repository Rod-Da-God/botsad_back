from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.path import ENV_FILE


class AnalyticsDatabaseSettings(BaseSettings):
    DB_DIALECT: str = Field("postgresql")
    DB_DRIVER: str = Field("asyncpg")

    # новый способ — один DSN целиком
    ANALYTICS_DB_DSN: str | None = Field(default=None)

    # старые поля (fallback)
    ANALYTICS_DB_USER: str | None = Field(default=None)
    ANALYTICS_DB_PASSWORD: SecretStr | None = Field(default=None)
    ANALYTICS_DB_HOST: str = Field("localhost")
    ANALYTICS_DB_PORT: int = Field(5432)
    ANALYTICS_DB_NAME: str | None = Field(default=None)

    ANALYTICS_DB_POOL_SIZE: int = Field(5)
    ANALYTICS_DB_CONNECT_TIMEOUT: int = Field(30)

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_configured(self) -> bool:
        """Настроена ли БД аналитики (DSN или полный набор полей)."""
        if self.ANALYTICS_DB_DSN:
            return True

        return bool(self.ANALYTICS_DB_USER and self.ANALYTICS_DB_NAME)

    @property
    def asyncpg_dsn(self) -> str:
        # приоритет DSN из env
        if self.ANALYTICS_DB_DSN:
            return self.ANALYTICS_DB_DSN

        password = (
            self.ANALYTICS_DB_PASSWORD.get_secret_value()
            if self.ANALYTICS_DB_PASSWORD
            else ""
        )
        return (
            f"{self.DB_DIALECT}://{self.ANALYTICS_DB_USER}:{password}"
            f"@{self.ANALYTICS_DB_HOST}:{self.ANALYTICS_DB_PORT}/{self.ANALYTICS_DB_NAME}"
        )


analytics_db_settings = AnalyticsDatabaseSettings()
