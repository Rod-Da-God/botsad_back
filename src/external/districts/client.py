import logging
from typing import Any

from ..http_client import BaseHttpClient, http_request


logger = logging.getLogger(__name__)


class DistrictsClient(BaseHttpClient):
    """
    Клиент для работы с микросервисом районов.

    Использует OSM-данные для точного определения районов по координатам.
    """

    def __init__(self, base_url: str, timeout: float = 10.0):
        super().__init__(base_url, timeout)
        logger.info("DistrictsClient initialized: %s", base_url)

    @http_request(
        method="GET",
        path="districts/resolve",
        timeout=10.0,
        error_message="Failed to resolve district",
    )
    async def resolve_district(
        self,
        lat: float,
        lon: float,
        city_code: str = "khabarovsk",
        city_name: str | None = None,
        fallback_nearest: bool = True,
    ) -> dict[str, Any]:
        """
        Определить район по координатам.

        Args:
            lat: Широта (-90 до 90)
            lon: Долгота (-180 до 180)
            city_code: Код города (например, "khabarovsk")
            city_name: Название города (опционально)
            fallback_nearest: Использовать ближайший район,
                если точка вне границ

        Returns:
            Dict с полями:
            - city: {id, code, name}
            - district: {id, name}
            - match_type: "contains" | "nearest"
            - distance_m: расстояние в метрах (для nearest)

        Raises:
            HttpClientError: При ошибках API (400, 404, 502)
        """
        params = {
            "lat": lat,
            "lon": lon,
            "city_code": city_code,
            "fallback_nearest": fallback_nearest,
        }

        if city_name:
            params["city_name"] = city_name

        logger.debug(
            "Resolving district: lat=%.6f, lon=%.6f, city=%s",
            lat,
            lon,
            city_code,
        )

        return {"params": params}

    @http_request(
        method="GET",
        path="districts/cities",
        timeout=15.0,
        error_message="Failed to fetch cities",
    )
    async def get_cities(self) -> dict[str, Any]:
        """
        Получить список всех городов с районами.

        Returns:
            Dict вида:
            {
                "khabarovsk": [
                    {"id": "...", "name": "Центральный", ...},
                    ...
                ]
            }

        Raises:
            HttpClientError: При ошибках API (500)
        """
        logger.debug("Fetching cities list")
        return {}

    async def get_district_name(
        self,
        lat: float,
        lon: float,
        city_code: str = "khabarovsk",
        city: str | None = "Хабаровск",
    ) -> str | None:
        """
        Получить только название района (удобный хелпер).

        Args:
            lat: Широта
            lon: Долгота
            city_code: Код города

        Returns:
            Название района или None при ошибке
        """
        result = await self.resolve_district(
            lat=lat,
            lon=lon,
            city_code=city_code,
            city_name=city,
            fallback_nearest=True,
        )

        district = result.get("district", {})
        district_name = district.get("name")

        if district_name:
            match_type = result.get("match_type", "unknown")
            logger.info(
                "District resolved: '%s' (match_type=%s)",
                district_name,
                match_type,
            )
            return district_name

        logger.warning("No district in response: %s", result)
        return None
