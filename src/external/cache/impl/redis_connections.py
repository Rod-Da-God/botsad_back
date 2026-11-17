import logging

from ..base import BaseCache
from ..config import settings
from ..redis_base import RedisBase


logger = logging.getLogger(__name__)

ACTIVE_CONNECTIONS_KEY = "active_connections"


class RedisConnections(RedisBase, BaseCache):
    """
    Управление WebSocket-соединениями через Redis.

    Использует Redis множество (set) под ключом ACTIVE_CONNECTIONS_KEY.
    Все connection_id — UUID4.
    """

    def __init__(self):
        """
        Инициализация с использованием базового Redis URL из конфига.
        """
        super().__init__(settings.cache_url)
        logger.debug(
            "RedisConnections created with Redis URL: %s", settings.cache_url
        )

    async def init(self) -> None:
        """
        Инициализация Redis клиента (через RedisBase).
        """

        await super().init()
        logger.info("RedisConnections successfully initialized")

    async def add_connection(self, connection_id: str) -> None:
        """Добавляет соединение в множество активных."""
        await self.client.sadd(ACTIVE_CONNECTIONS_KEY, connection_id)
        logger.debug("Connection %s added", connection_id)

    async def remove_connection(self, connection_id: str) -> None:
        """Удаляет соединение из множества активных."""
        await self.client.srem(ACTIVE_CONNECTIONS_KEY, connection_id)
        logger.debug("Connection %s removed", connection_id)

    async def get_active_connections(self) -> list[str]:
        """Возвращает список всех активных соединений."""
        connections = await self.client.smembers(ACTIVE_CONNECTIONS_KEY)
        logger.debug("Fetched %d active connections", len(connections))
        return list(connections)

    async def clear_connections(self) -> None:
        """Очищает все активные соединения."""
        await self.client.delete(ACTIVE_CONNECTIONS_KEY)
        logger.info("Cleared all active connections")
