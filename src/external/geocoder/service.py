import logging
from typing import Any

from billboards.utils.translit_slug import translit_city
from external.http_client import HttpClientError

from ..districts.client import DistrictsClient
from .base import GeocoderClient


logger = logging.getLogger(__name__)


class GeocoderService:
    """
    Сервис геокодирования с бизнес-логикой.

    Инкапсулирует логику fallback'ов и дополнения данных,
    используя:
    - Районный микросервис (приоритет)
    - Yandex Geocoder (fallback)
    """

    def __init__(
        self,
        geocoder_client: GeocoderClient,
        districts_client: DistrictsClient | None = None,
        default_city: str = "Хабаровск",
        default_city_code: str = "khabarovsk",
    ):
        self.geocoder = geocoder_client
        self.districts = districts_client
        self.default_city = default_city
        self.default_city_code = default_city_code

    async def geocode_with_fallback(
        self,
        address: str,
        coords_from_crm: tuple[float, float] | None = None,
    ) -> dict[str, Any]:
        """
        Геокодирование с fallback на координаты из CRM.

        Стратегия:
        1. Попытка прямого геокодирования адреса
        2. Если нет района — запрос в районный микросервис
        3. Если микросервис недоступен — Yandex обратное геокодирование
        4. Fallback на координаты из CRM при неудаче
        5. Обратное геокодирование CRM координат если есть

        Args:
            address: Адрес для геокодирования
            coords_from_crm: Координаты из CRM (lon, lat)

        Returns:
            Dict с полями:
            - formatted_address: str
            - city: str
            - coordinates: Optional[Tuple[float, float]]
            - district: Optional[str]
            - street_name: Optional[str]
            - building_number: Optional[str]
        """
        result: dict[str, Any] = {
            "formatted_address": address,
            "city": self.default_city,
            "coordinates": coords_from_crm,
            "district": None,
            "street_name": None,
            "building_number": None,
        }

        city_for_geocoding = None if "," in address else self.default_city

        try:
            geocoded = await self.geocoder.geocode(
                address, city=city_for_geocoding
            )
        except HttpClientError as error:
            logger.error(
                "Geocoding failed for '%s' (status=%s): %s. "
                "Falling back to CRM coordinates.",
                address,
                error.status_code,
                error,
            )
            geocoded = None

        if geocoded:
            result.update(
                {
                    "formatted_address": geocoded.get(
                        "formatted_address", address
                    ),
                    "city": geocoded.get("city") or self.default_city,
                    "coordinates": geocoded.get("coordinates")
                    or coords_from_crm,
                    "district": geocoded.get("district"),
                    "street_name": geocoded.get("street_name"),
                    "building_number": geocoded.get("building_number"),
                }
            )

            if not result["district"] and result["coordinates"]:
                result["district"] = await self._fetch_district(
                    result["coordinates"], city=result.get("city")
                )

            return result

        if coords_from_crm:
            try:
                reversed_data = await self.geocoder.reverse_geocode(
                    *coords_from_crm
                )
            except HttpClientError as error:
                logger.error(
                    "Reverse geocoding failed for %s (status=%s): %s",
                    coords_from_crm,
                    error.status_code,
                    error,
                )
                reversed_data = None

            if reversed_data:
                result.update(
                    {
                        "formatted_address": reversed_data.get(
                            "formatted_address", address
                        ),
                        "city": reversed_data.get("city") or self.default_city,
                        "district": reversed_data.get("district"),
                        "street_name": reversed_data.get("street_name"),
                        "building_number": reversed_data.get(
                            "building_number"
                        ),
                    }
                )

            if not result["district"]:
                result["district"] = await self._fetch_district(
                    coords_from_crm, city=result.get("city")
                )

        return result

    async def _fetch_district(
        self, coordinates: tuple[float, float], city: str | None = None
    ) -> str | None:
        """
        Получить район по координатам.

        Приоритет:
        1. Районный микросервис (точные границы OSM)
        2. Yandex Geocoder (fallback)

        Args:
            coordinates: (lon, lat)
            city: Название города для определения city_code

        Returns:
            Название район или None
        """
        lon, lat = coordinates

        if self.districts:
            city_code = self._get_city_code(city)

            try:
                district_name = await self.districts.get_district_name(
                    lat=lat,
                    lon=lon,
                    city=city,
                    city_code=city_code,
                )

                if district_name:
                    logger.info(
                        "Районы из сервиса: '%s' (city=%s)",
                        district_name,
                        city_code,
                    )
                    return district_name

                logger.debug(
                    "Районы [%.6f, %.6f], city=%s", lon, lat, city_code
                )
            except HttpClientError as e:
                logger.error(
                    "Districts microservice failed"
                    " [%.6f, %.6f] (status=%s): %s."
                    " Falling back to Yandex.",
                    lon,
                    lat,
                    e.status_code,
                    str(e),
                )

        try:
            district_data = await self.geocoder.reverse_geocode(
                lon, lat, kind="district"
            )
        except HttpClientError as error:
            logger.error(
                "District reverse geocoding failed [%.6f, %.6f] "
                "(status=%s): %s",
                lon,
                lat,
                error.status_code,
                error,
            )
            district_data = None

        if district_data:
            district = district_data.get("district")
            if district:
                logger.info("District from Yandex: '%s'", district)
            return district

        logger.warning(
            "No district found for coordinates [%.6f, %.6f]", lon, lat
        )
        return None

    def _get_city_code(self, city: str | None) -> str:
        """
        Получить код города для микросервиса районов.

        Использует translit_city для преобразования названия города.

        Args:
            city: Название города

        Returns:
            Код города (например, "khabarovsk")
        """
        if not city:
            return self.default_city_code

        city_code = translit_city(city)
        logger.debug("City '%s' -> code '%s'", city, city_code)

        return city_code

    async def enrich_location_data(
        self,
        address: str,
        coordinates: tuple[float, float] | None = None,
    ) -> dict[str, Any]:
        """
        Дополнить данные локации всей доступной информацией.

        когда есть координаты, но нужно получить
        структурированный адрес и район.

        Args:
            address: Исходный адрес
            coordinates: Координаты (lon, lat)

        Returns:
            данные локации
        """
        if not coordinates:
            return await self.geocode_with_fallback(address)

        reversed_data = await self.geocoder.reverse_geocode(*coordinates)

        result: dict[str, Any] = {
            "formatted_address": address,
            "city": self.default_city,
            "coordinates": coordinates,
            "district": None,
            "street_name": None,
            "building_number": None,
        }

        if reversed_data:
            result.update(
                {
                    "formatted_address": reversed_data.get(
                        "formatted_address", address
                    ),
                    "city": reversed_data.get("city") or self.default_city,
                    "district": reversed_data.get("district"),
                    "street_name": reversed_data.get("street_name"),
                    "building_number": reversed_data.get("building_number"),
                }
            )

        if not result["district"]:
            result["district"] = await self._fetch_district(
                coordinates, city=result.get("city")
            )

        return result
