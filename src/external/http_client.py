import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any, Literal, ParamSpec, TypeVar

import httpx


logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


@dataclass
class RequestConfig:
    """Конфигурация запроса."""

    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = "GET"
    timeout: float = 30.0
    raise_for_status: bool = True
    log_request: bool = True
    log_response: bool = True


class HttpClientError(Exception):
    """Базовая ошибка HTTP клиента."""

    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


def http_request(
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = "GET",
    path: str = "",
    timeout: float | None = None,
    response_key: str | None = None,
    error_message: str = "HTTP request failed",
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Декоратор для HTTP запросов.

    Метод должен возвращать dict с ключами:
    - path_params: dict для форматирования пути (опционально)
    - params: query параметры для GET (опционально)
    - json: тело запроса для POST/PUT/PATCH (опционально)
    - headers: дополнительные заголовки (опционально)

    Args:
        method: HTTP метод
        path: Путь запроса (может содержать {placeholders})
        timeout: Таймаут запроса; если не задан, берётся таймаут клиента
        response_key: Путь к нужным данным в ответе ("result.items")
        error_message: Сообщение об ошибке
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(self, *args, **kwargs) -> Any:
            request_data = await func(self, *args, **kwargs)  # type: ignore[misc]
            if request_data is None:
                request_data = {}

            path_params = request_data.get("path_params", {})
            formatted_path = (
                path.format(**path_params) if path_params else path
            )
            url = f"{self.base_url}/{formatted_path}".rstrip("/")

            request_kwargs = {
                "timeout": (
                    timeout
                    if timeout is not None
                    else getattr(self, "timeout", 30.0)
                )
            }
            if "params" in request_data:
                request_kwargs["params"] = request_data["params"]
            if "json" in request_data:
                request_kwargs["json"] = request_data["json"]
            if "headers" in request_data:
                request_kwargs["headers"] = request_data["headers"]

            logger.debug("%s %s | params=%s", method, url, request_data)

            try:
                response = await self.client.request(
                    method, url, **request_kwargs
                )
                response.raise_for_status()
                if not response.content:
                    data = None
                else:
                    data = response.json()
                if response_key:
                    for key in response_key.split("."):
                        data = (data or {}).get(key, {})

                logger.debug("%s %s -> OK", method, url)
                return data

            except httpx.HTTPStatusError as e:
                logger.error(
                    "%s %s -> %d: %s", method, url, e.response.status_code, e
                )
                raise HttpClientError(
                    error_message, e.response.status_code
                ) from e
            except httpx.RequestError as e:
                logger.error("%s %s -> Connection error: %s", method, url, e)
                raise HttpClientError(
                    f"{error_message}: connection failed"
                ) from e

        return wrapper  # type: ignore[return-value]

    return decorator


class BaseHttpClient:
    """Базовый HTTP клиент с общей логикой."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        logger.debug(
            "%s initialized: %s", self.__class__.__name__, self.base_url
        )

    async def close(self) -> None:
        await self.client.aclose()
        logger.debug("%s closed", self.__class__.__name__)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
