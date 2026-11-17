# cache/redis_base.py
import logging
from abc import ABC
from typing import Any, cast

from redis.asyncio import ConnectionError, Redis

from .config import settings


logger = logging.getLogger(__name__)


class RedisBase(ABC):
    """
    Базовый класс для всех Redis-реализаций.

    Создает клиента и подключение к бд по url для конкретной реализации
    """

    _client: Redis | None = None
    _db_url: str

    def __init__(self, db_url: str):
        """
        Args:
            db_url: Полный URL Redis (например, redis://localhost:6379/0)
        """
        self._db_url = db_url

    async def init(self) -> None:
        """Инициализирует клиент и проверяет подключение."""
        if self._client is not None:
            logger.debug(
                "%s: Redis client already initialized", self.__class__.__name__
            )
            return

        try:
            logger.debug(
                "Initializing Redis client for %s: %s",
                self.__class__.__name__,
                self._db_url,
            )
            self._client = Redis.from_url(
                self._db_url,
                decode_responses=settings.cache_decode_responses,
                max_connections=settings.cache_max_connections,
                socket_timeout=settings.cache_socket_timeout,
                socket_connect_timeout=settings.cache_socket_connect_timeout,
            )
            await cast(Any, self._client).ping()
            logger.info(
                "Redis client initialized: %s", self.__class__.__name__
            )
        except ConnectionError as e:
            logger.critical(
                "Failed to connect to Redis (%s): %s", self._db_url, e
            )

    async def close(self) -> None:
        """Закрывает подключение к Redis."""
        if self._client:
            await self._client.close()
            logger.info("Redis client closed: %s", self.__class__.__name__)
            self._client = None

    @property
    def client(self) -> Any:
        """Возвращает клиент. Вызывает ошибку, если не инициализирован.

        Тип возврата — Any: в redis-py asyncio-методы размечены
        как ``Awaitable[X] | X``, из-за чего mypy ошибочно
        отклоняет ``await``. Поведение в рантайме не меняется.
        """
        if self._client is None:
            raise RuntimeError(
                f"{self.__class__.__name__} not initialized."
                " Call init() first."
            )
        return self._client

    def __del__(self):
        """Предупреждение: не полагайся на __del__, используй close()."""
        if self._client:
            logger.warning(
                "%s: Redis client was not closed explicitly."
                " Call close() in shutdown.",
                self.__class__.__name__,
            )
