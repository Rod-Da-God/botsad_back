import logging
from typing import Any

from ..http_client import BaseHttpClient, http_request
from .base import GeocoderClient


logger = logging.getLogger(__name__)


class YandexGeocoderClient(BaseHttpClient, GeocoderClient):
    """
    Чистый клиент Yandex Geocoder API.

    Содержит только базовые методы геокодирования без бизнес-логики.
    """

    def __init__(self, api_key: str):
        super().__init__("https://geocode-maps.yandex.ru/1.x", timeout=10.0)
        self.api_key = api_key

    @http_request(
        method="GET",
        path="",
        response_key="response.GeoObjectCollection.featureMember",
        error_message="Geocoding failed",
    )
    async def _raw_geocode(
        self, geocode: str, kind: str | None = None
    ) -> list[dict[str, Any]]:
        """Сырой запрос к Yandex API."""
        params = {
            "apikey": self.api_key,
            "geocode": geocode,
            "format": "json",
            "results": 1,
        }
        if kind:
            params["kind"] = kind
        return {"params": params}  # type: ignore[return-value]

    async def geocode(
        self,
        address: str,
        city: str | None = "Хабаровск",
        kind: str | None = None,
    ) -> dict | None:
        """
        Прямое геокодирование адреса.

        Args:
            address: Адрес для геокодирования
            city: Город (по умолчанию "Хабаровск")
            kind: Тип объекта ('house', 'street', 'district'...)

        Returns:
            Dict с полями:
            - coordinates: Tuple[float, float] (lon, lat)
            - formatted_address: str
            - city: Optional[str]
            - street_name: Optional[str]
            - building_number: Optional[str]
            - district: Optional[str]

            Или None если адрес не найден
        """
        full_address = f"{city}, {address}" if city else address
        logger.debug("Geocoding: '%s'", full_address)

        features = await self._raw_geocode(full_address, kind)
        if not features:
            logger.warning("Address not found: '%s'", full_address)
            return None

        geo_object = features[0].get("GeoObject")
        return self._parse_geo_object(geo_object) if geo_object else None

    async def reverse_geocode(
        self,
        lon: float,
        lat: float,
        kind: str | None = None,
    ) -> dict | None:
        """
        Обратное геокодирование координат.

        Args:
            lon: Долгота
            lat: Широта
            kind: Тип объекта для фильтрации результата

        Returns:
            Dict с полями:
            - formatted_address: str
            - city: Optional[str]
            - street_name: Optional[str]
            - building_number: Optional[str]
            - district: Optional[str]

            Или None если адрес не найден
        """
        logger.debug("Reverse geocoding: [%f, %f]", lon, lat)

        features = await self._raw_geocode(f"{lon},{lat}", kind)
        if not features:
            logger.warning("No address for coords: [%f, %f]", lon, lat)
            return None

        geo_object = features[0].get("GeoObject")
        return (
            self._parse_geo_object(geo_object, include_coords=False)
            if geo_object
            else None
        )

    def _parse_geo_object(
        self, geo_object: dict, include_coords: bool = True
    ) -> dict:
        """
        Парсинг GeoObject в унифицированный формат.

        Args:
            geo_object: Объект из Yandex API
            include_coords: Включать ли координаты в результат

        Returns:
            Унифицированный словарь с данными
        """
        result = {"formatted_address": geo_object.get("name", "")}

        if include_coords:
            point_str = geo_object.get("Point", {}).get("pos", "")
            if point_str:
                lon, lat = point_str.split()
                result["coordinates"] = (float(lon), float(lat))

        metadata = geo_object.get("metaDataProperty", {}).get(
            "GeocoderMetaData", {}
        )
        components = metadata.get("Address", {}).get("Components", [])

        result.update(
            {
                "city": None,
                "street_name": None,
                "building_number": None,
                "district": None,
            }
        )

        kind_map = {
            "locality": "city",
            "street": "street_name",
            "house": "building_number",
            "district": "district",
        }

        for comp in components:
            field = kind_map.get(comp.get("kind"))
            if field:
                result[field] = comp.get("name")

        return result
