import logging
from collections.abc import Callable
from functools import wraps

import httpx

from ..base import BaseSuggestClient
from ..config import settings
from ..exceptions import SuggestAPIError, SuggestAuthError, SuggestNetworkError


logger = logging.getLogger(__name__)


def dadata_client(func: Callable) -> Callable:
    """Декоратор — создаёт httpx.AsyncClient
    с заголовками и таймаутами DaData.
    """

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        headers = {
            "Authorization": f"Token {settings.suggest_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        timeout = httpx.Timeout(settings.suggest_timeout)

        async with httpx.AsyncClient(
            base_url=settings.suggest_base_url,
            headers=headers,
            timeout=timeout,
        ) as client:
            return await func(self, client, *args, **kwargs)

    return wrapper


class DadataSuggest(BaseSuggestClient):
    """Конкретная реализация автодополнения адресов через DaData"""

    @dadata_client
    async def suggest_address(
        self,
        client: httpx.AsyncClient,
        query: str,
        count: int | None = None,
    ) -> list[dict[str, str | float]]:
        """
        Возвращает список подсказок адресов с координатами.

        Формат результата:
            [
                {
                    "address": "г Москва, ул Хабаровская",
                    "lat": 55.821168,
                    "lon": 37.82608
                },
                ...
            ]
        """
        if not query or not query.strip():
            return []

        payload = {
            "query": query.strip(),
            "count": count,
        }

        try:
            response = await client.post("/suggest/address", json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            text = exc.response.text[:500]
            logger.error("DaData API error %s: %s", status, text)

            if status == 401:
                raise SuggestAuthError(
                    "Invalid or missing DaData API key"
                ) from exc
            if status == 403:
                raise SuggestAuthError(
                    "DaData: access denied (blocked token or quota exceeded)"
                ) from exc
            if status >= 500:
                raise SuggestAPIError(
                    "DaData service temporarily unavailable"
                ) from exc
            raise SuggestAPIError(f"DaData returned HTTP {status}") from exc
        except httpx.RequestError as exc:
            logger.exception("Network error while calling DaData")
            raise SuggestNetworkError(
                "Failed to connect to DaData API"
            ) from exc

        data = response.json()
        suggestions = data.get("suggestions", [])

        results = []
        for item in suggestions:
            value = item.get("value")
            data_block = item.get("data", {})

            geo_lat = data_block.get("geo_lat")
            geo_lon = data_block.get("geo_lon")

            if not value or geo_lat is None or geo_lon is None:
                continue

            try:
                lat = float(geo_lat)
                lon = float(geo_lon)
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid coordinates in DaData response: lat=%s, lon=%s",
                    geo_lat,
                    geo_lon,
                )
                continue

            results.append(
                {
                    "address": value.strip(),
                    "lat": lat,
                    "lon": lon,
                }
            )

        logger.debug(
            "DaData suggest success: query='%s' → %d results (out of %d raw)",
            query.strip(),
            len(results),
            len(suggestions),
        )
        return results
