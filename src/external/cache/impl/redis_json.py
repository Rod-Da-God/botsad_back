import json
import logging
from typing import Any

from redis.commands.search.field import NumericField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.exceptions import ResponseError

from ..base import BaseJsonStorage
from ..config import settings
from ..redis_base import RedisBase


logger = logging.getLogger(__name__)


class RedisJsonStorage(RedisBase, BaseJsonStorage):
    """
    RedisJSON + RediSearch реализация хранилища билбордов.
    Каждый билборд хранится отдельно как billboard:{id},
    а общий список — под ключом billboards:all (пересчитывается асинхронно).
    """

    INDEX_NAME = "idx_billboards"
    CITY_KEY_PREFIX = "billboards:city:"  # billboards:city:khabarovsk
    CITIES_KEY = "billboards:cities"  # SET со списком городов
    CHANNEL_REFRESH = "billboards.refresh"

    def __init__(self):
        super().__init__(settings.cache_url)
        logger.debug(
            "RedisJsonStorage instance created (INDEX=%s)", self.INDEX_NAME
        )

    async def init(self) -> None:
        await super().init()
        # await self._ensure_search_index()
        # инициализация индекса по айди не нужна
        logger.info("RedisJsonStorage initialized")

    async def _ensure_search_index(self) -> None:
        """Создаёт RediSearch индекс для документов billboard:*
        (если не существует).
        """
        ft = self.client.ft(self.INDEX_NAME)
        try:
            await ft.info()
            logger.debug("Search index '%s' already exists", self.INDEX_NAME)
            return
        except ResponseError:
            pass

        fields = [NumericField("$.id", as_name="id")]
        definition = IndexDefinition(
            prefix=["billboard:"], index_type=IndexType.JSON
        )
        await ft.create_index(fields=fields, definition=definition)
        logger.info("Search index '%s' created", self.INDEX_NAME)

    async def get_all(self) -> list[dict[str, Any]]:
        """
        Возвращает все билборды плоским списком.
        Теперь источник — городские кеши:
        billboards:city:{city} -> {id: billboard}

        Если множество городов пустое (первый запуск/Redis очищен),
        пересобираем city-кеши из truth billboard:*.
        """
        cities = await self.client.smembers(self.CITIES_KEY)
        if not cities:
            logger.info("get_all: cities empty, rebuilding city caches...")
            await self.rebuild_city_caches()
            cities = await self.client.smembers(self.CITIES_KEY)

        cities = [
            c.decode() if isinstance(c, (bytes, bytearray)) else c
            for c in cities
        ]

        result: list[dict[str, Any]] = []
        for city in cities:
            city_key = f"{self.CITY_KEY_PREFIX}{city}"
            city_dict = await self.client.json().get(city_key) or {}
            if isinstance(city_dict, dict):
                result.extend(city_dict.values())

        logger.debug(
            "get_all: aggregated %d items from %d cities",
            len(result),
            len(cities),
        )
        return result

    async def get_by_id(self, billboard_id: int) -> dict[str, Any] | None:
        """
        Возвращает конкретный билборд по ID.

        Args:
            billboard_id (int): идентификатор билборда.

        Пример вызова:
            await storage.get_by_id(1)

        Пример результата:
        {
            "id": 1,
            "coordinates": [135.0928, 48.4802],
            "address": "ул Тихоокеанская 73",
            ...
        }
        """
        return await self.client.json().get(f"billboard:{billboard_id}")

    async def add_billboard(self, billboard: dict[str, Any]) -> None:
        """
        Добавляет новый билборд:
        - сохраняет его как отдельный документ;
        - публикует событие о необходимости пересборки кэша.

        Args:
            billboard (dict): данные нового билборда.

        Пример входных данных:
        {
            "id": 1,
            "coordinates": [135.0928, 48.4802],
            "address": "ул Тихоокеанская 73",
            ...
        }
        """
        await self._upsert_billboard(billboard, action="add")

    async def update_billboard(self, new_data: dict[str, Any]) -> None:
        """
        Обновляет существующий билборд по ID и отправляет сигнал на пересборку.

        Args:
            new_data (dict): новые данные для замены.

        Пример входных данных:
        billboard_id = 1
        new_data = {
            "id": 1,
            "address": "ул. Ленинградская 42",
            ...
        }
        """
        await self._upsert_billboard(new_data, action="update")

    async def delete_billboard(self, billboard_id: int) -> None:
        """
        Удаляет билборд из Redis и СРАЗУ обновляет городской кеш.
        Args:
            billboard_id (int): идентификатор удаляемого билборда.
        """
        key = f"billboard:{billboard_id}"

        existing = await self.client.json().get(key)
        if not existing:
            logger.warning(
                "Billboard %s not found during deletion", billboard_id
            )
            return

        slug = existing.get("slug")
        if not slug:
            logger.warning(
                "Billboard %s has no slug, cannot delete from city cache",
                billboard_id,
            )
            await self.client.delete(key)
            return

        # 1. Удаляем truth документ
        await self.client.delete(key)

        # 2. СРАЗУ удаляем из городского кеша
        city = self._city_from_slug(slug)
        city_key = f"{self.CITY_KEY_PREFIX}{city}"
        await self.client.json().delete(city_key, f"$.{billboard_id}")

        # 3. Публикуем событие
        await self.client.publish(
            self.CHANNEL_REFRESH,
            json.dumps({"action": "delete", "id": billboard_id, "slug": slug}),
        )
        logger.info("Billboard %s deleted and refresh published", billboard_id)

    async def _upsert_billboard(
        self, data: dict[str, Any], action: str
    ) -> None:
        """
        Общая логика для add/update:
        - пишет truth billboard:{id}
        - СРАЗУ обновляет городской кеш
        - публикует событие для других инстансов
        """
        billboard_id = data.get("id")
        slug = data.get("slug")
        if billboard_id is None:
            raise ValueError("Billboard must have 'id'")
        if not slug:
            raise ValueError("Billboard must have 'slug'")

        # 1. Сохраняем truth документ
        await self.client.json().set(f"billboard:{billboard_id}", "$", data)

        # 2. СРАЗУ обновляем городской кеш
        city = self._city_from_slug(slug)
        city_key = f"{self.CITY_KEY_PREFIX}{city}"

        await self.client.sadd(self.CITIES_KEY, city)

        if not await self.client.exists(city_key):
            await self.client.json().set(city_key, "$", {})

        await self.client.json().set(city_key, f"$.{billboard_id}", data)

        # 3. Публикуем событие для других инстансов
        await self.client.publish(
            self.CHANNEL_REFRESH,
            json.dumps({"action": action, "id": billboard_id, "slug": slug}),
        )
        logger.info(
            "Billboard %s upserted (action=%s) and refresh published",
            billboard_id,
            action,
        )

    async def rebuild_city_caches(self) -> None:
        """
        Полная пересборка всех city-кешей из truth billboard:*.

        Проходит по ключам billboard:*,
        определяет город из slug (первая часть до '/'),
        группирует и сохраняет:
        billboards:city:{city} = {id: billboard}
        billboards:cities (SET) пополняется найденными городами.

        Используется при первом запуске или если кеши потерялись.
        """
        keys = await self.client.keys("billboard:*")
        cities: dict[str, dict[str, Any]] = {}

        for key in keys:
            item = await self.client.json().get(key)
            if not item:
                continue

            billboard_id = item.get("id")
            slug = item.get("slug")
            if billboard_id is None or not slug:
                continue

            city = self._city_from_slug(slug)
            cities.setdefault(city, {})[str(billboard_id)] = item

        pipe = self.client.pipeline()
        for city, city_dict in cities.items():
            pipe.json().set(f"{self.CITY_KEY_PREFIX}{city}", "$", city_dict)
            pipe.sadd(self.CITIES_KEY, city)

        await pipe.execute()
        logger.info("Rebuilt city caches for %d cities", len(cities))

    async def _update_cached_list(
        self, action: str, billboard_id: int, slug: str
    ) -> None:
        """
        Инкрементально обновляет кеш конкретного города по событию.

        City определяется из slug:
        "khabarovsk/ul-serysheva-15" -> "khabarovsk"

        Структура кеша:
        billboards:city:{city} = {id: billboard}

        Действия:
        delete -> JSON.DEL $.{id}
        add/update -> JSON.SET $.{id} (upsert)
        """
        city = self._city_from_slug(slug)
        city_key = f"{self.CITY_KEY_PREFIX}{city}"

        await self.client.sadd(self.CITIES_KEY, city)

        if action == "delete":
            await self.client.json().delete(city_key, f"$.{billboard_id}")
            logger.info(
                "Removed billboard %s from city cache %s", billboard_id, city
            )
            return

        new_billboard = await self.get_by_id(billboard_id)
        if not new_billboard:
            logger.warning(
                "Billboard %s not found in truth for action '%s'",
                billboard_id,
                action,
            )
            return

        if not await self.client.exists(city_key):
            await self.client.json().set(city_key, "$", {})
            logger.debug("Created empty city cache %s", city_key)

        await self.client.json().set(
            city_key, f"$.{billboard_id}", new_billboard
        )
        logger.info(
            "Upserted billboard %s into city cache %s", billboard_id, city
        )

    async def listen_for_refresh(self):
        """
        Подписывается на канал обновлений и точечно обновляет кеши городов.
        Ожидаемый payload:
        {"action": "add|update|delete", "id": 3, "slug": "khabarovsk/..."}
        """
        pubsub = self.client.pubsub()
        await pubsub.subscribe(self.CHANNEL_REFRESH)
        logger.info(
            "Subscribed to %s for incremental city cache updates",
            self.CHANNEL_REFRESH,
        )

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            payload = json.loads(message["data"])
            action = payload.get("action")
            billboard_id = payload.get("id")
            slug = payload.get("slug")

            if not action or billboard_id is None or not slug:
                logger.warning("Invalid refresh payload: %s", payload)
                continue

            await self._update_cached_list(action, billboard_id, slug)

    async def get_by_city(self, city_slug: str) -> list[dict[str, Any]]:
        """
        Быстро отдаёт маркеры конкретного города.

        Хранилище города:
        billboards:city:khabarovsk = {"3": {...}, "8": {...}}

        Результат:
        [{...}, {...}]  # только значения, без ключей id
        """
        key = f"{self.CITY_KEY_PREFIX}{city_slug}"
        data = await self.client.json().get(key) or {}
        return list(data.values())

    def _city_from_slug(self, slug: str) -> str:
        # slug вида "khabarovsk/ul-serysheva-15"
        return slug.split("/", 1)[0]
