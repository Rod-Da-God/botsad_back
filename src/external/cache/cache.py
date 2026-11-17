import asyncio
import logging
from typing import Any

from .base import BaseCache, BaseJsonStorage
from .impl.redis_json import RedisJsonStorage


logger = logging.getLogger(__name__)


class Cache:
    """
    Фасад для управления кэшем приложения:
    - хранение WebSocket-соединений;
    - работа с JSON-билбордами в Redis.
    """

    _connections: BaseCache | None = None
    _json_storage: BaseJsonStorage | None = None
    _listener_task: asyncio.Task | None = None

    @classmethod
    async def init(cls) -> None:
        """
        Инициализация всех подсистем кэша:
        - RedisConnections (WebSocket)
        - RedisJsonStorage (билборды)
        """
        if cls._connections is not None or cls._json_storage is not None:
            logger.warning(
                "Cache already initialized — skipping reinitialization."
            )
            return

        # cls._connections = RedisConnections() Не используется
        cls._json_storage = RedisJsonStorage()

        # await cls._connections.init()
        await cls._json_storage.init()

        cls._listener_task = asyncio.create_task(
            cls._json_storage.listen_for_refresh()
        )
        logger.info("Cache listener for billboard updates started")

        logger.info(
            "Cache initialized with backend: %s",
            cls._json_storage.__class__.__name__,
        )

    @classmethod
    def get_connections(cls) -> BaseCache:
        """Возвращает инициализированные соединения."""
        if cls._connections is None:
            raise RuntimeError(
                "RedisConnections not initialized. Call Cache.init()."
            )
        return cls._connections

    @classmethod
    def get_json_storage(cls) -> BaseJsonStorage:
        """Возвращает инициализированное JSON-хранилище."""
        if cls._json_storage is None:
            raise RuntimeError(
                "RedisJsonStorage not initialized. Call Cache.init()."
            )
        return cls._json_storage

    @classmethod
    async def close(cls) -> None:
        """Закрывает все активные клиенты Redis."""
        if cls._listener_task:
            cls._listener_task.cancel()
            try:
                await cls._listener_task
            except asyncio.CancelledError:
                logger.info("Cache listener task cancelled")
        cls._listener_task = None
        if cls._connections:
            await cls._connections.close()
            logger.info("Cache: RedisConnections closed.")
            cls._connections = None

        if cls._json_storage:
            await cls._json_storage.close()
            logger.info("Cache: RedisJsonStorage closed.")
            cls._json_storage = None

    @classmethod
    async def add_connection(cls, connection_id: str) -> None:
        connections = cls.get_connections()
        await connections.add_connection(connection_id)
        logger.debug("Cache: added WS connection %s", connection_id)

    @classmethod
    async def remove_connection(cls, connection_id: str) -> None:
        connections = cls.get_connections()
        await connections.remove_connection(connection_id)
        logger.debug("Cache: removed WS connection %s", connection_id)

    @classmethod
    async def get_active_connections(cls) -> list[str]:
        connections = cls.get_connections()
        return await connections.get_active_connections()

    @classmethod
    async def clear_connections(cls) -> None:
        connections = cls.get_connections()
        await connections.clear_connections()
        logger.info("Cache: all WS connections cleared")

    @classmethod
    async def get_all_billboards(cls) -> list[dict[str, Any]]:
        """Получает весь список билбордов из Redis.

        Returns:
            List[Dict[str, Any]]: список объектов билбордов.

        Пример результата:
        [
            {"id": 1, "address": "ул Тихоокеанская 73",
             "district": "Ленинский"},
            {"id": 2, "address": "ул Ленина 15", "district": "Кировский"}
        ]

        """
        storage = cls.get_json_storage()
        data = await storage.get_all()
        logger.debug("Cache: fetched %d billboards", len(data))
        return data

    @classmethod
    async def get_billboards_by_city(
        cls, city_slug: str
    ) -> list[dict[str, Any]]:
        """Получает список билбордов конкретного города.

        Args:
            city_slug (str): ключ города (транслит), например "khabarovsk".

        Returns:
            List[Dict[str, Any]]: список билбордов города.

        Хранилище города:
            billboards:city:khabarovsk = {"3": {...}, "8": {...}}

        Пример результата:
        [
            {"id": 3, "slug": "khabarovsk/ul-serysheva-15", ...},
            {"id": 8, "slug": "khabarovsk/ul-lenina-1", ...}
        ]
        """
        storage = cls.get_json_storage()
        data = await storage.get_by_city(city_slug)
        logger.debug(
            "Cache: fetched %d billboards for city=%s", len(data), city_slug
        )
        return data

    @classmethod
    async def add_billboard(cls, billboard: dict[str, Any]) -> None:
        """Добавляет новый билборд в Redis.

        Args:
            billboard (dict): объект нового билборда.

        Пример входных данных:
        {
            "id": 1,
            "coordinates": [135.0928, 48.4802],
            "address": "ул Тихоокеанская 73",
            ...
        }

        """
        storage = cls.get_json_storage()
        await storage.add_billboard(billboard)
        logger.info("Cache: added billboard %s", billboard.get("id"))

    @classmethod
    async def update_billboard(cls, new_data: dict[str, Any]) -> None:
        """Обновляет существующий билборд.

        Args:
            new_data (dict): обновлённый объект билборда.

        Пример входных данных:
        new_data = {
            "id": 1,
            "address": "ул. Ленинградская 42",
            ...
        }
        """
        storage = cls.get_json_storage()
        await storage.update_billboard(new_data)
        logger.info("Cache: updated billboard %s", new_data.get("id"))

    @classmethod
    async def delete_billboard(cls, billboard_id: int) -> None:
        """Удаляет билборд по ID.

        Args:
            billboard_id (int): идентификатор удаляемого билборда.
        """
        storage = cls.get_json_storage()
        await storage.delete_billboard(billboard_id)
        logger.info("Cache: deleted billboard %s", billboard_id)
