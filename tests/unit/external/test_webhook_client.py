"""Тесты клиента исходящих вебхуков (POST <base>/events)."""

import json
from typing import Callable

import httpx
import pytest

from external.http_client import HttpClientError
from external.seo.client import WebhookEvent, WebhookSenderClient


def make_client(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    retries: int = 0,
    backoff_factor: float = 0.0,
    timeout: float = 10.0,
) -> WebhookSenderClient:
    # Конструктор BaseHttpClient создаёт реальный AsyncClient с SSL-контекстом
    # (~0.5 c). Собираем клиент напрямую: поведение send_event от этого не
    # зависит, а тесты остаются быстрыми.
    client = object.__new__(WebhookSenderClient)
    client.base_url = "https://hook.test"
    client.timeout = timeout
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client._retries = retries
    client._backoff_factor = backoff_factor
    return client


async def test_send_event_posts_json_to_events() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    client = make_client(handler)
    event = WebhookEvent(
        type="billboard.created",
        payload={"billboard_id": 42, "location_id": 7},
    )
    try:
        assert await client.send_event(event) is None
    finally:
        await client.close()

    assert len(seen) == 1
    request = seen[0]
    assert request.method == "POST"
    assert str(request.url) == "https://hook.test/events"
    assert request.headers["content-type"] == "application/json"
    assert json.loads(request.content) == {
        "type": "billboard.created",
        "payload": {"billboard_id": 42, "location_id": 7},
    }


async def test_send_raw_dict_event() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    client = make_client(handler)
    try:
        await client.send_event({"type": "billboard.deleted", "payload": {}})
    finally:
        await client.close()

    assert json.loads(seen[0].content) == {
        "type": "billboard.deleted",
        "payload": {},
    }


async def test_client_timeout_is_applied_to_requests() -> None:
    """WEBHOOK_TIMEOUT должен попадать в HTTP-запрос, а не заменяться 10 с."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    client = make_client(handler, timeout=7.5)
    try:
        await client.send_event({"type": "billboard.created"})
    finally:
        await client.close()

    assert seen[0].extensions["timeout"]["read"] == 7.5


async def test_idempotency_and_extra_headers() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    client = make_client(handler)
    try:
        await client.send_event(
            {"type": "billboard.updated", "payload": {}},
            idempotency_key="abc-123",
            extra_headers={"X-Trace": "trace-1"},
        )
    finally:
        await client.close()

    assert seen[0].headers["idempotency-key"] == "abc-123"
    assert seen[0].headers["x-trace"] == "trace-1"


async def test_no_retries_reraises_server_error() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    client = make_client(handler, retries=0)
    try:
        with pytest.raises(HttpClientError) as error:
            await client.send_event({"type": "billboard.created"})
    finally:
        await client.close()

    assert calls == 1
    assert error.value.status_code == 500


async def test_server_error_is_retried_then_succeeds() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503)
        return httpx.Response(204)

    client = make_client(handler, retries=2, backoff_factor=0.0)
    try:
        await client.send_event({"type": "billboard.created"})
    finally:
        await client.close()

    assert calls == 2


async def test_retries_are_exhausted() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(502)

    client = make_client(handler, retries=2, backoff_factor=0.0)
    try:
        with pytest.raises(HttpClientError) as error:
            await client.send_event({"type": "billboard.created"})
    finally:
        await client.close()

    assert calls == 3  # первая попытка + 2 ретрая
    assert error.value.status_code == 502


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422])
async def test_client_errors_are_not_retried(status_code: int) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status_code)

    client = make_client(handler, retries=3, backoff_factor=0.0)
    try:
        with pytest.raises(HttpClientError) as error:
            await client.send_event({"type": "billboard.created"})
    finally:
        await client.close()

    assert calls == 1
    assert error.value.status_code == status_code


@pytest.mark.parametrize("status_code", [408, 429, 500, 503, 504])
async def test_temporary_errors_are_retried(status_code: int) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(status_code)
        return httpx.Response(204)

    client = make_client(handler, retries=1, backoff_factor=0.0)
    try:
        await client.send_event({"type": "billboard.created"})
    finally:
        await client.close()

    assert calls == 2


async def test_connection_error_is_retried_then_succeeds() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("connection refused", request=request)
        return httpx.Response(204)

    client = make_client(handler, retries=1, backoff_factor=0.0)
    try:
        await client.send_event({"type": "billboard.created"})
    finally:
        await client.close()

    assert calls == 2
