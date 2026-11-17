import json
import logging
from collections.abc import AsyncGenerator
from typing import Any, Optional, cast

from broadcaster import Broadcast as BroadcasterLib

from external.cache.config import settings


logger = logging.getLogger(__name__)


class TOPICS:
    UPDATES = "billboards.updates"


class Broadcast:
    """
    Класс-обёртка для управления Pub/Sub через Redis.
    Инициализирует подключение к Redis,
    предоставляет методы публикации и подписки.
    """

    _instance: Optional["Broadcast"] = None
    broadcast: BroadcasterLib | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            return cls._instance

    @classmethod
    async def setup_broadcast(cls):
        """
        Инициализация PubSubEndpoint и подключение к Redis.

        # Подключаемся к Redis
        """
        if cls.broadcast is not None:
            logger.warning("Broadcast already setup, skipping initialize")
            return

        try:
            logger.debug("Initializing Broadcaster with Redis...")
            cls.broadcast = BroadcasterLib(settings.broadcast_url)
            await cls.broadcast.connect()
            logger.info("Broadcaster with Redis successfully initialized")
        except (ConnectionError, TimeoutError) as e:
            logger.critical("Redis connection failed: %s", e)

    @classmethod
    async def unmount_broadcast(cls):
        """
        Отключение от Redis при завершении приложения.
        """
        if cls.broadcast is not None:
            await cls.broadcast.disconnect()
            logger.info("Broadcaster disconnected from Redis")
            cls.broadcast = None

    @classmethod
    async def publish(cls, topic: str, message: dict[str, Any], action: str):
        """
        Публикует сообщение в Redis-топик.
        Формат: {"topic": "news", "data": {...}}
        """
        if cls.broadcast is None:
            raise RuntimeError(
                "Broadcaster not initialized. Call setup_broadcast() first."
            )

        payload = {"topic": topic, "billboard": message, "type": action}

        await cls.broadcast.publish(channel=topic, message=json.dumps(payload))
        logger.debug(f"Published to topic '{topic}': {action}-{payload}")

    @classmethod
    async def subscribe(cls, topic: str) -> AsyncGenerator[dict[str, Any]]:
        """
        Асинхронная подписка на топик.
        Использовать как:
            async for msg in Broadcast.subscribe(Broadcast.TOPICS.NEWS):
                ...
        """
        if cls.broadcast is None:
            raise RuntimeError(
                "Broadcast not initialized. Call setup() first."
            )

        async with cls.broadcast.subscribe(channel=topic) as subscriber:
            if subscriber is None:
                raise RuntimeError(f"Не удалось подписаться на топик {topic}")
            logger.debug("New subcriber in %s", topic)
            async for event in cast(Any, subscriber):
                if event is None:
                    continue
                try:
                    payload = json.loads(event.message)
                    yield payload
                except json.JSONDecodeError:
                    logger.warning(
                        f"Invalid JSON in topic {topic}: {event.message}"
                    )
