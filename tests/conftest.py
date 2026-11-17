"""Общие фикстуры и настройка окружения для тестов.

Важно: ``tests/.env.test`` загружается в ``pytest_configure`` — до того,
как pytest начнёт импортировать тестовые модули и, вместе с ними, модули
``src``. Настройки приложения (pydantic-settings) читают значения из
окружения при импорте, поэтому порядок принципиален.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from dotenv import load_dotenv


TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SRC_DIR = REPO_ROOT / "src"
ENV_TEST_FILE = TESTS_DIR / ".env.test"


def pytest_configure(config: pytest.Config) -> None:
    """Загружает тестовое окружение и пути до любых импортов ``src``."""
    load_dotenv(ENV_TEST_FILE, override=True)

    for path in (str(REPO_ROOT), str(SRC_DIR)):
        if path not in sys.path:
            sys.path.insert(0, path)


class FakeWebhookClient:
    """Заглушка HTTP-клиента исходящих вебхуков.

    Записывает все вызовы ``send_event`` и позволяет управлять ошибкой,
    которую клиент должен поднять.
    """

    def __init__(self, error: Optional[BaseException] = None) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.error = error
        self.closed = False

    async def send_event(self, event: Any, **kwargs: Any) -> None:
        self.calls.append({"event": event, "kwargs": kwargs})
        if self.error is not None:
            raise self.error

    async def close(self) -> None:
        self.closed = True


class FakeApiRegistry:
    """Минимальная заглушка реестра внешних клиентов."""

    def __init__(self, webhook: Optional[FakeWebhookClient]) -> None:
        self.webhook = webhook


@pytest.fixture
def fake_webhook_client() -> FakeWebhookClient:
    return FakeWebhookClient()


@pytest.fixture
def fake_api_registry(fake_webhook_client: FakeWebhookClient) -> FakeApiRegistry:
    return FakeApiRegistry(fake_webhook_client)
