from abc import ABC, abstractmethod


class BaseSuggestClient(ABC):
    """Абстрактный клиент для автодополнения адресов"""

    @abstractmethod
    async def suggest_address(
        self,
        query: str,
        count: int | None = None,
    ) -> list[dict[str, str | float]]:
        """
        Возвращает список подсказок с координатами.

        Returns:
            [
                {
                    "address": "г Москва, ул Хабаровская, д 15",
                    "lon": 37.7181,
                    "lat": 55.8231,
                },
                ...
            ]
        """
        pass
