from abc import ABC, abstractmethod


class GeocoderClient(ABC):
    """
    Абстрактный клиент для геокодирования адресов.
    """

    @abstractmethod
    async def geocode(
        self,
        address: str,
        city: str | None = "Хабаровск",
        kind: str | None = None,
    ) -> dict | None:
        """
        Прямое геокодирование

        Args:
            address: Адрес для геокодирования
            city: Город (по умолчанию "Хабаровск")
            kind: Тип объекта ('house', 'street', 'district'...)

        Returns:
            Dict с полями:
            - coordinates: Tuple[float, float] (lon, lat)
            - formatted_address: str
            - street_name: Optional[str]
            - building_number: Optional[str]
            - district: Optional[str]

            Или None если адрес не найден
        """
        pass

    @abstractmethod
    async def reverse_geocode(
        self,
        lon: float,
        lat: float,
        kind: str | None = None,
    ) -> dict | None:
        """
        Обратное геокодирование

        Args:
            lon: Долгота
            lat: Широта
            kind: Тип объекта для фильтрации результата

        Returns:
            Dict с полями:
            - formatted_address: str
            - street_name: Optional[str]
            - building_number: Optional[str]
            - district: Optional[str]

            Или None если адрес не найден
        """
        pass

    @staticmethod
    def coordinates_to_wkt(lon: float, lat: float) -> str:
        """
        Преобразовать координаты в WKT формат для PostGIS

        Args:
            lon
            lat

        Returns:
            WKT строка
        """
        return f"POINT({lon} {lat})"
