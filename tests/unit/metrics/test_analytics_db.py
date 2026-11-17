"""Тесты опциональной БД аналитики.

Аналитика не должна быть обязательной для старта приложения: без DSN
или учётных данных пул не создаётся, а запись событий — no-op.
"""

import pytest

import metrics.db as db_module
from metrics.config import AnalyticsDatabaseSettings
from metrics.db import AnalyticsDB


def _settings(**kwargs: object) -> AnalyticsDatabaseSettings:
    defaults: dict[str, object] = {
        "_env_file": None,
        "ANALYTICS_DB_DSN": None,
        "ANALYTICS_DB_USER": None,
        "ANALYTICS_DB_NAME": None,
    }
    defaults.update(kwargs)
    return AnalyticsDatabaseSettings(**defaults)  # type: ignore[arg-type]


def test_settings_without_dsn_or_credentials_is_not_configured() -> None:
    assert _settings().is_configured is False


def test_settings_with_empty_strings_is_not_configured() -> None:
    settings = _settings(
        ANALYTICS_DB_DSN="",
        ANALYTICS_DB_USER="",
        ANALYTICS_DB_NAME="",
    )

    assert settings.is_configured is False


def test_settings_with_dsn_is_configured() -> None:
    settings = _settings(
        ANALYTICS_DB_DSN="postgresql://user:pass@localhost/analytics"
    )

    assert settings.is_configured is True


def test_settings_with_credentials_is_configured() -> None:
    settings = _settings(
        ANALYTICS_DB_USER="user",
        ANALYTICS_DB_NAME="analytics",
    )

    assert settings.is_configured is True


async def test_init_without_configuration_does_not_create_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(db_module, "analytics_db_settings", _settings())
    database = AnalyticsDB()

    await database.init()

    assert database._pool is None


async def test_insert_is_noop_without_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(db_module, "analytics_db_settings", _settings())
    database = AnalyticsDB()
    await database.init()

    # Без пула запись молча пропускается и не поднимает исключение.
    await database.insert_events_raw([{"event_id": "event-1"}])
