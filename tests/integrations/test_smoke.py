"""Безопасный smoke-тест приложения: без запуска lifespan и без сети."""

import httpx

from app import create_app


async def test_health_returns_204() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 204
