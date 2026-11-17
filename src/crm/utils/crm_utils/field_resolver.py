"""Сопоставление полей Bitrix24 с конфигом приложения.

Модуль избавляет от хардкода идентификаторов полей и вариантов списков:
при старте приложения названия из ``crm.config`` ищутся в ответе
``crm.item.fields``, после чего код работает с полученными кодами.

Идентификаторы вариантов списков уникальны для каждого портала
Битрикс24, поэтому их нельзя хранить в коде - они тоже резолвятся
из описания полей.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from crm.config import (
    BITRIX_FIELD_TITLES,
    BITRIX_REQUIRED_FIELDS,
    crm_settings,
)


if TYPE_CHECKING:
    from external.crm.bitrix import BitrixCrmClient


logger = logging.getLogger(__name__)


# Как часто перезапрашивать описание полей у Bitrix24 (в секундах).
FIELD_MAP_TTL = 6 * 60 * 60


class FieldResolutionError(RuntimeError):
    """Не удалось сопоставить поля Bitrix24 с конфигом."""


def normalize_label(value: Any) -> str:
    """Привести название поля или варианта к сравнимому виду."""
    text = str(value or "").casefold().replace("ё", "е")
    return " ".join(text.split())


def _enum_items(field: dict[str, Any]) -> dict[str, str]:
    """Собрать варианты списка в формате {id: значение}.

    ``crm.item.fields`` отдаёт элементы списка в camelCase, а методы
    предыдущей версии (``crm.deal.fields``) - в верхнем регистре,
    поэтому поддерживаем оба варианта ключей.
    """
    items = field.get("items") or []
    result: dict[str, str] = {}

    if not isinstance(items, (list, tuple)):
        return result

    for item in items:
        if not isinstance(item, dict):
            continue

        item_id = item.get("ID", item.get("id"))
        value = item.get("VALUE", item.get("value"))

        if item_id is None or value is None:
            continue

        result[str(item_id)] = str(value)

    return result


class BitrixFieldMap:
    """Резолвер кодов полей и вариантов списков смарт-процесса."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._loaded_at = 0.0
        self._codes: dict[str, str] = {}
        self._titles: dict[str, str] = {}
        self._field_types: dict[str, str] = {}
        self._enum_labels: dict[str, dict[str, str]] = {}
        self._enum_ids: dict[str, dict[str, str]] = {}
        self.spa_id: int | None = None
        self.entity_type_id: int | None = None

    @property
    def ready(self) -> bool:
        return bool(self._codes)

    def _is_fresh(self) -> bool:
        return (
            self.ready and (time.monotonic() - self._loaded_at) < FIELD_MAP_TTL
        )

    async def ensure_loaded(
        self, client: BitrixCrmClient, force: bool = False
    ) -> None:
        """Загрузить описание полей, если оно ещё не загружено."""
        if not force and self._is_fresh():
            return

        async with self._lock:
            if not force and self._is_fresh():
                return

            await self._load(client)

    async def reload(self, client: BitrixCrmClient) -> None:
        """Принудительно перечитать описание полей из Bitrix24."""
        await self.ensure_loaded(client, force=True)

    async def _load(self, client: BitrixCrmClient) -> None:
        entity_type_id = await self._resolve_entity_type_id(client)
        fields = await client.get_item_fields(entity_type_id)

        if not fields:
            raise FieldResolutionError(
                "Bitrix24 вернул пустое описание полей смарт-процесса "
                f"entityTypeId={entity_type_id}"
            )

        self._build(fields)
        self.entity_type_id = entity_type_id
        client.use_entity_type(entity_type_id)
        self._loaded_at = time.monotonic()

        logger.info(
            "Поля смарт-процесса сопоставлены: entityTypeId=%s, "
            "полей в конфиге=%d",
            entity_type_id,
            len(self._codes),
        )
        logger.debug("Соответствие полей: %s", self._codes)

    async def _resolve_entity_type_id(self, client: BitrixCrmClient) -> int:
        """Найти entityTypeId смарт-процесса по названию."""
        title = crm_settings.bitrix_spa_title
        wanted = normalize_label(title)

        # Сначала пробуем серверный фильтр, затем - полный список:
        # crm.type.list может игнорировать фильтр по title или
        # возвращать неполное совпадение.
        types = await self._get_spa_types(client, title)
        spa = self._pick_spa(types, wanted)

        if spa is None:
            types = await self._get_spa_types(client, None)
            spa = self._pick_spa(types, wanted)

        if spa is not None:
            self.spa_id = int(spa["id"])
            entity_type_id = int(spa["entityTypeId"])
            logger.info(
                "Найден смарт-процесс '%s': id=%s, entityTypeId=%s",
                spa.get("title") or title,
                self.spa_id,
                entity_type_id,
            )
            return entity_type_id

        fallback = crm_settings.bitrix_entity_type_id
        if fallback is None:
            raise FieldResolutionError(
                f"Смарт-процесс '{title}' не найден через crm.type.list. "
                "Проверьте название в BITRIX_SPA_TITLE или задайте "
                "BITRIX_ENTITY_TYPE_ID"
            )

        logger.warning(
            "Смарт-процесс '%s' не найден, используем "
            "BITRIX_ENTITY_TYPE_ID=%s",
            title,
            fallback,
        )
        return int(fallback)

    @staticmethod
    async def _get_spa_types(
        client: BitrixCrmClient, title: str | None
    ) -> list[dict[str, Any]]:
        """Запросить смарт-процессы, не прерывая работу при ошибке."""
        try:
            return await client.get_spa_types(title)
        except Exception as error:  # noqa: BLE001
            logger.warning(
                "Не удалось получить список смарт-процессов "
                "(crm.type.list): %s",
                error,
            )
            return []

    @staticmethod
    def _pick_spa(
        types: Iterable[dict[str, Any]], wanted: str
    ) -> dict[str, Any] | None:
        """Выбрать смарт-процесс по точному, затем частичному названию."""
        partial: dict[str, Any] | None = None

        for spa in types or []:
            if not isinstance(spa, dict):
                continue
            if spa.get("id") is None or spa.get("entityTypeId") is None:
                continue

            current = normalize_label(spa.get("title"))
            if current == wanted:
                return spa
            if (
                partial is None
                and wanted
                and (wanted in current or current in wanted)
            ):
                partial = spa

        return partial

    def _build(self, fields: dict[str, dict[str, Any]]) -> None:
        """Построить карты код поля и вариантов списка по названиям."""
        by_title: dict[str, str] = {}

        for code, description in fields.items():
            if not isinstance(description, dict):
                continue

            title = description.get("title") or description.get("formLabel")
            if title:
                by_title[normalize_label(title)] = code

        codes: dict[str, str] = {}
        titles: dict[str, str] = {}
        field_types: dict[str, str] = {}
        enum_labels: dict[str, dict[str, str]] = {}
        enum_ids: dict[str, dict[str, str]] = {}

        for semantic, aliases in BITRIX_FIELD_TITLES.items():
            found_code = self._find_code(aliases, by_title)
            if found_code is None:
                continue
            code = str(found_code)

            description = fields[code]
            codes[semantic] = code
            titles[semantic] = str(
                description.get("title") or description.get("formLabel") or ""
            )
            field_types[semantic] = str(description.get("type") or "")

            items = _enum_items(description)
            if items:
                enum_labels[semantic] = items
                enum_ids[semantic] = {
                    normalize_label(label): item_id
                    for item_id, label in items.items()
                }

        missing = [
            semantic
            for semantic in BITRIX_FIELD_TITLES
            if semantic not in codes
        ]
        required_missing = [
            semantic
            for semantic in missing
            if semantic in BITRIX_REQUIRED_FIELDS
        ]

        if required_missing:
            expected = {
                semantic: BITRIX_FIELD_TITLES[semantic][0]
                for semantic in required_missing
            }
            raise FieldResolutionError(
                "В смарт-процессе не найдены обязательные поля: "
                f"{expected}. Проверьте названия полей в Bitrix24"
            )

        if missing:
            logger.warning(
                "Не найдены необязательные поля Bitrix24: %s",
                {
                    semantic: BITRIX_FIELD_TITLES[semantic][0]
                    for semantic in missing
                },
            )

        self._codes = codes
        self._titles = titles
        self._field_types = field_types
        self._enum_labels = enum_labels
        self._enum_ids = enum_ids

    @staticmethod
    def _find_code(
        aliases: Iterable[str], by_title: dict[str, str]
    ) -> str | None:
        for alias in aliases:
            code = by_title.get(normalize_label(alias))
            if code is not None:
                return code
        return None

    def reset(self) -> None:
        """Сбросить загруженное описание полей."""
        self._loaded_at = 0.0
        self._codes = {}
        self._titles = {}
        self._field_types = {}
        self._enum_labels = {}
        self._enum_ids = {}
        self.spa_id = None
        self.entity_type_id = None

    def code(self, semantic: str) -> str:
        """Код поля Bitrix24 по смыслу."""
        code = self._codes.get(semantic)
        if code is None:
            raise FieldResolutionError(
                f"Поле '{semantic}' не сопоставлено с полем Bitrix24. "
                "Проверьте BITRIX_FIELD_TITLES в crm/config.py"
            )
        return code

    def code_optional(self, semantic: str) -> str | None:
        """Код необязательного поля Bitrix24 по смыслу."""
        return self._codes.get(semantic)

    def codes(self) -> list[str]:
        """Все сопоставленные коды полей."""
        return list(self._codes.values())

    def title(self, semantic: str) -> str:
        """Название поля в карточке Bitrix24."""
        return self._titles.get(semantic, "")

    def field_type(self, semantic: str) -> str:
        """Тип поля в Bitrix24 (string, enumeration, money, address...)."""
        return self._field_types.get(semantic, "")

    def enum_label(self, semantic: str, raw_value: Any) -> str | None:
        """Название варианта списка по значению из элемента CRM."""
        if raw_value is None or raw_value == "" or raw_value == []:
            return None

        if isinstance(raw_value, (list, tuple)):
            return (
                self.enum_label(semantic, raw_value[0]) if raw_value else None
            )

        if isinstance(raw_value, dict):
            for key in ("VALUE", "value", "TITLE", "title"):
                if raw_value.get(key) is not None:
                    return self.enum_label(semantic, raw_value[key])
            return None

        labels = self._enum_labels.get(semantic, {})
        if not labels:
            return str(raw_value)

        label = labels.get(str(raw_value))
        if label is not None:
            return label

        logger.warning(
            "Неизвестный вариант списка '%s' в поле '%s' (код %s). "
            "Проверьте, что варианты в Bitrix24 называются как в "
            "crm/config.py",
            raw_value,
            semantic,
            self._codes.get(semantic),
        )
        return None

    def enum_values(self, semantic: str) -> dict[str, str]:
        """Все варианты списка в формате {id: значение}."""
        return dict(self._enum_labels.get(semantic, {}))

    def enum_id(self, semantic: str, label: str) -> str | None:
        """ID варианта списка по его названию."""
        ids = self._enum_ids.get(semantic, {})
        return ids.get(normalize_label(label))

    def describe(self) -> dict[str, dict[str, Any]]:
        """Текущее соответствие полей для диагностики."""
        return {
            semantic: {
                "code": code,
                "title": self._titles.get(semantic, ""),
                "type": self._field_types.get(semantic, ""),
                "enum": self._enum_labels.get(semantic, {}),
            }
            for semantic, code in self._codes.items()
        }


bitrix_fields = BitrixFieldMap()
