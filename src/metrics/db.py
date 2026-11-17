import json
from collections.abc import Mapping
from typing import Any

import asyncpg
from loguru import logger

from .config import analytics_db_settings


class AnalyticsDB:
    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    async def init(self) -> None:
        """
        Создать пул подключений к БД аналитики.

        Аналитика опциональна: если переменные не заданы, приложение
        продолжает работать, а события аналитики просто не сохраняются.
        """
        if not analytics_db_settings.is_configured:
            logger.info(
                "Analytics DB не настроена — сбор событий аналитики отключён"
            )
            self._pool = None
            return

        dsn = analytics_db_settings.asyncpg_dsn

        logger.info("Connecting analytics DB: {}", dsn.split("@")[-1])

        self._pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=1,
            max_size=analytics_db_settings.ANALYTICS_DB_POOL_SIZE,
            timeout=analytics_db_settings.ANALYTICS_DB_CONNECT_TIMEOUT,
            ssl="require",
        )

        logger.info("Analytics DB pool created")

    async def insert_events_raw(self, rows: list[Mapping[str, Any]]) -> None:
        """
        Вставляет батч сырых событий в analytics.events.
        Fire-and-forget обеспечим уровнем выше (очередь), тут просто insert.
        """
        if not rows or self._pool is None:
            return

        sql = """
        INSERT INTO analytics.events (
            event_id, event_name, event_ts, received_ts,
            session_id, client_id, viewer_id,
            entity_type, entity_id,
            context, properties
        )
        VALUES (
            $1, $2, $3, now(),
            $4, $5, $6,
            $7, $8,
            $9::jsonb, $10::jsonb
        )
        ON CONFLICT (event_id) DO NOTHING;
        """

        values = [
            (
                r["event_id"],
                r["event_name"],
                r["event_ts"],
                r["session_id"],
                r["client_id"],
                r["viewer_id"],
                r["entity_type"],
                r["entity_id"],
                json.dumps(r.get("context") or {}),  # <-- строка JSON
                json.dumps(r.get("properties") or {}),  # <--
            )
            for r in rows
        ]

        try:
            async with self.pool.acquire() as conn:
                await conn.executemany(sql, values)
        except Exception as e:
            # тебе не важен результат — просто логируем
            logger.exception("Failed to insert analytics events batch: {}", e)

    async def close(self):
        if self._pool:
            await self._pool.close()
            logger.info("Analytics DB pool closed")

    @property
    def pool(self) -> asyncpg.Pool:
        if not self._pool:
            raise RuntimeError("Analytics DB not initialized")
        return self._pool


analytics_db = AnalyticsDB()
