from pydantic import Field

from config.settings.base import BaseAppSettings


class LoggerSettings(BaseAppSettings):
    log_level: str = Field(default="DEBUG")
    log_to_console: bool = Field(default=True)
    log_to_file: bool = Field(default=True)
    log_file: str = Field(default="app.log")
    log_rotation: str = Field(default="10 MB")
    log_retention: str = Field(default="10 days")
    log_compression: str = Field(default="zip")
