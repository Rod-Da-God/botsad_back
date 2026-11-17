import logging
from collections.abc import Sequence
from typing import Any

from ..http_client import BaseHttpClient, http_request
from .base import CrmClient


logger = logging.getLogger(__name__)


class BitrixCrmClient(BaseHttpClient, CrmClient):
    """Клиент Bitrix24 с использованием декоратора."""

    def __init__(
        self,
        webhook_url: str,
        entity_type_id: int | None = None,
    ):
        super().__init__(webhook_url)
        self.entity_type_id = entity_type_id

    def use_entity_type(self, entity_type_id: int) -> None:
        """Задать entityTypeId смарт-процесса с конструкциями."""
        self.entity_type_id = int(entity_type_id)

    def _require_entity_type_id(self) -> int:
        if self.entity_type_id is None:
            raise RuntimeError(
                "entityTypeId смарт-процесса не определён. "
                "Сначала загрузите описание полей"
                " (bitrix_fields.ensure_loaded)"
            )
        return int(self.entity_type_id)

    @http_request(
        method="POST",
        path="crm.type.list.json",
        response_key="result.types",
        error_message="Failed to get CRM types",
    )
    async def get_spa_types(
        self, title: str | None = None
    ) -> list[dict[str, Any]]:
        """Получить смарт-процессы, при необходимости - по названию."""
        params: dict[str, Any] = {}
        if title:
            params["filter"] = {"title": title}
        return {"json": params}  # type: ignore[return-value]

    @http_request(
        method="POST",
        path="crm.item.fields.json",
        response_key="result.fields",
        error_message="Failed to get item fields",
    )
    async def get_item_fields(self, entity_type_id: int) -> dict[str, Any]:
        """Получить описание полей смарт-процесса."""
        return {
            "json": {
                "entityTypeId": int(entity_type_id),
                "useOriginalUfNames": "N",
            }
        }

    async def get_constructions(
        self, field_codes: Sequence[str] | None = None
    ) -> list[dict[str, Any]]:
        """
        Получить ВСЕ конструкции с пагинацией.

        Bitrix возвращает максимум 50 записей за раз,
        поэтому делаем несколько запросов с параметром start.

        Args:
            field_codes: коды пользовательских полей для select.
                Список берётся из резолвера полей, чтобы не хардкодить
                префикс ufCrm<id>_ в коде.
        """
        entity_type_id = self._require_entity_type_id()
        select = ["*", *(field_codes or [])]

        all_items = []
        start = 0
        limit = 50

        logger.info("Начало загрузки конструкций из Bitrix24")

        while True:
            url = f"{self.base_url}/crm.item.list.json"

            response = await self.client.request(
                "POST",
                url,
                json={
                    "entityTypeId": entity_type_id,
                    "order": {"id": "ASC"},
                    "select": select,
                    "start": start,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            result = data.get("result", {})
            items = result.get("items", [])

            if not items:
                logger.debug(f"Нет больше данных на start={start}")
                break

            all_items.extend(items)
            logger.debug(
                f"Загружено {len(items)} конструкций "
                f"(всего: {len(all_items)}, страница: {start // limit + 1})"
            )

            if len(items) < limit:
                break

            start += limit

        logger.info(
            f"Всего загружено {len(all_items)} конструкций из Bitrix24"
        )
        return all_items

    @http_request(
        method="POST",
        path="crm.item.get.json",
        response_key="result.item",
        error_message="Construction not found",
    )
    async def get_construction_by_id(self, item_id: int) -> dict[str, Any]:
        """Получить конструкцию по ID."""
        return {
            "json": {
                "entityTypeId": self._require_entity_type_id(),
                "id": item_id,
            }
        }

    @http_request(
        method="POST",
        path="crm.lead.add.json",
        response_key="result",
        error_message="Failed to create lead",
    )
    async def create_lead(
        self, fields: dict[str, Any], register_event: bool = False
    ) -> int:
        """Создать лид."""
        params: dict[str, Any] = {"fields": fields}
        if register_event:
            params["params"] = {"REGISTER_SONET_EVENT": "Y"}
        return {"json": params}  # type: ignore[return-value]
