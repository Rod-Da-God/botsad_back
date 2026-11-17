# cache/base.py
from abc import ABC, abstractmethod
from typing import Any


class BaseCache(ABC):
    """
    Интерфейс для кеша WebSocket-соединений.
    Твой оригинальный код — сохранён полностью.
    """

    @abstractmethod
    async def init(self) -> None:
        """Инициализация клиента."""
        pass

    @abstractmethod
    async def add_connection(self, connection_id: str) -> None:
        """Добавить соединение в активный список."""
        pass

    @abstractmethod
    async def get_active_connections(self) -> list[str]:
        """Получить все активные соединения."""
        pass

    @abstractmethod
    async def remove_connection(self, connection_id: str) -> None:
        """Удалить соединение из списка."""
        pass

    @abstractmethod
    async def clear_connections(self) -> None:
        """Очистить все соединения."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Закрыть подключение."""
        pass


class BaseJsonStorage(ABC):
    """
    Интерфейс для работы с JSON в cache.
    """

    @abstractmethod
    async def get_all(self) -> list[dict[str, Any]]:
        """Получить весь массив."""
        pass

    @abstractmethod
    async def get_by_id(self, billboard_id: int) -> dict[str, Any] | None:
        """Получить один билборд по id."""
        pass

    @abstractmethod
    async def update_billboard(self, new_data: dict[str, Any]) -> None:
        """
        Обновить существующий билборд (id берётся из new_data).
        """
        pass

    @abstractmethod
    async def add_billboard(self, billboard: dict[str, Any]) -> None:
        """Добавить билборд в конец."""
        pass

    @abstractmethod
    async def delete_billboard(self, billboard_id: int) -> None:
        """Удалить билборд по id."""
        pass

    @abstractmethod
    async def get_by_city(self, city_slug: str) -> list[dict[str, Any]]:
        """Получить все билборды города (список без ключей id)."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Закрыть подключение к хранилищу."""
        pass
