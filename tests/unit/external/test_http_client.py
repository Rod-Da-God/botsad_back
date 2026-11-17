"""Тесты базового HTTP-клиента на httpx.MockTransport (без сети)."""

from typing import Callable

import httpx
import pytest

from external.http_client import BaseHttpClient, HttpClientError, http_request


class DemoClient(BaseHttpClient):
    @http_request(
        method="GET",
        path="items",
        response_key="result.items",
        error_message="items failed",
    )
    async def get_items(self, params: dict | None = None):
        return {"params": params} if params is not None else {}

    @http_request(
        method="POST",
        path="items/{item_id}",
        error_message="create failed",
    )
    async def create_item(self, item_id: int, payload: dict):
        return {"path_params": {"item_id": item_id}, "json": payload}

    @http_request(method="GET", path="empty", error_message="empty failed")
    async def get_empty(self):
        return {}

    @http_request(method="GET", path="plain", error_message="plain failed")
    async def get_plain(self):
        return {}


def make_client(handler: Callable[[httpx.Request], httpx.Response]) -> DemoClient:
    # Не создаём реальный AsyncClient: его конструктор строит SSL-контекст
    # (~0.5 c на Windows). Для тестов достаточно публичных атрибутов клиента.
    client = object.__new__(DemoClient)
    client.base_url = "https://api.test"
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return client


async def test_get_success_returns_nested_data() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"result": {"items": [1, 2, 3]}})

    client = make_client(handler)
    try:
        result = await client.get_items()
    finally:
        await client.close()

    assert result == [1, 2, 3]
    assert len(seen) == 1
    assert seen[0].method == "GET"
    assert str(seen[0].url) == "https://api.test/items"


async def test_query_parameters_are_forwarded() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"result": {"items": []}})

    client = make_client(handler)
    try:
        await client.get_items(params={"city": "Хабаровск", "page": "2"})
    finally:
        await client.close()

    assert seen[0].url.params["city"] == "Хабаровск"
    assert seen[0].url.params["page"] == "2"


async def test_post_path_params_and_json_body() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    client = make_client(handler)
    try:
        result = await client.create_item(42, {"name": "test"})
    finally:
        await client.close()

    assert result == {"ok": True}
    assert seen[0].method == "POST"
    assert str(seen[0].url) == "https://api.test/items/42"
    assert seen[0].content == b'{"name":"test"}'


async def test_no_content_response_returns_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    client = make_client(handler)
    try:
        assert await client.get_empty() is None
    finally:
        await client.close()


async def test_plain_response_without_key_returns_dict() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"a": 1})

    client = make_client(handler)
    try:
        assert await client.get_plain() == {"a": 1}
    finally:
        await client.close()


@pytest.mark.parametrize("status_code", [400, 404, 500, 503])
async def test_error_status_raises_http_client_error(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code)

    client = make_client(handler)
    try:
        with pytest.raises(HttpClientError) as error:
            await client.get_plain()
    finally:
        await client.close()

    assert error.value.status_code == status_code


async def test_connection_error_raises_http_client_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = make_client(handler)
    try:
        with pytest.raises(HttpClientError) as error:
            await client.get_plain()
    finally:
        await client.close()

    assert error.value.status_code is None


async def test_timeout_raises_http_client_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = make_client(handler)
    try:
        with pytest.raises(HttpClientError):
            await client.get_plain()
    finally:
        await client.close()


async def test_context_manager_closes_client() -> None:
    client = make_client(lambda request: httpx.Response(204))

    async with client as entered:
        assert entered is client

    assert client.client.is_closed
