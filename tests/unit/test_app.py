"""Юнит-тесты фабрики приложения и состава маршрутов."""

import re
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from app import create_app


SRC_DIR = Path(__file__).resolve().parents[2] / "src"


@pytest.fixture(scope="module")
def app() -> FastAPI:
    """Создать приложение, не запуская lifespan (без БД/Redis)."""
    return create_app()


def _routes(app: FastAPI) -> set[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        if not path:
            continue
        for method in getattr(route, "methods", None) or set():
            result.add((path, method))
    return result


async def test_health_returns_204_without_lifespan(app: FastAPI) -> None:
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 204
    assert response.content == b""


def test_expected_routes_are_registered(app: FastAPI) -> None:
    routes = _routes(app)

    assert ("/api/webhook", "POST") in routes
    assert ("/api/banners", "GET") in routes

    detail_routes = {
        path
        for path, method in routes
        if method == "GET"
        and re.fullmatch(r"/api/banners/\{[^/{}]+\}", path)
    }
    assert detail_routes, "не найден GET-маршрут карточки билборда"


def test_source_has_no_kafka_integration() -> None:
    """В новом сервисе не должно остаться Kafka-зависимостей."""
    forbidden = ("aiokafka", "external.kafka", "external import kafka")
    offenders: list[tuple[str, str]] = []

    for path in SRC_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in forbidden:
            if token in text:
                offenders.append((str(path.relative_to(SRC_DIR)), token))

    assert not offenders, f"Найдены Kafka-зависимости: {offenders}"
