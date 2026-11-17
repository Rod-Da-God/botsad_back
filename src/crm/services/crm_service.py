import logging
from typing import Any, cast

from pydantic import BaseModel

from billboards.utils.billboard_group import group_by_location
from billboards.utils.responce_builder import build_list_response
from crm.utils.crm_utils.cache_utils import rebuild_and_cache_billboards
from crm.utils.crm_utils.extractors import extract_address, extract_side
from crm.utils.crm_utils.field_resolver import bitrix_fields
from crm.utils.crm_utils.parallel import address_executor
from crm.utils.crm_utils.sync_helper import CrmSyncHelper
from crm.utils.parsers.crm_item import group_items_by_address
from database.repository import BillboardRepository, LocationRepository
from external.crm.bitrix import BitrixCrmClient
from external.geocoder.service import GeocoderService


logger = logging.getLogger(__name__)


class CrmSyncService:
    """
    Сервис синхронизации данных из CRM с БД.

    Публичные методы:
    - load_all_constructions(): Массовая загрузка всех конструкций
    - sync_one(item_id): Синхронизация одной конструкции
    """

    def __init__(
        self,
        crm_client: BitrixCrmClient,
        geocoder_service: GeocoderService,
    ):
        self.crm = crm_client
        self.helper = CrmSyncHelper(geocoder_service)

    async def load_all_constructions(self) -> dict[str, Any]:
        """
        Загрузить все конструкции из CRM.

        Обрабатывает несколько адресов параллельно,
        для каждого адреса фото сторон тоже грузятся параллельно.
        """
        logger.info("Начало загрузки конструкций")

        await bitrix_fields.ensure_loaded(self.crm)
        items = await self.crm.get_constructions(bitrix_fields.codes())

        if not items:
            return {
                "status": "warning",
                "message": "Нет данных от CRM",
                "loaded": 0,
                "errors": [],
            }

        logger.info(f"Получено {len(items)} конструкций")

        grouped = group_items_by_address(items)
        addresses = list(grouped.keys())
        logger.debug(f"Сгруппировано: {len(addresses)} адресов")

        results = await address_executor.map(
            func=lambda addr: self.helper.sync_location_with_sides(
                addr, grouped[addr]
            ),
            items=addresses,
            on_error=lambda e, addr: {"address": addr, "error": str(e)},
        )

        loaded = 0
        errors = []

        for result in results:
            if isinstance(result, dict) and "error" in result:
                errors.append(result)
            else:
                loaded += cast(int, result)

        logger.info(
            f"Загрузка завершена: {loaded} конструкций, {len(errors)} ошибок"
        )

        if loaded > 0:
            await rebuild_and_cache_billboards(
                billboard_repository=BillboardRepository,
                group_by_location_func=group_by_location,
                build_list_response_func=build_list_response,
            )

        return {
            "status": "success" if not errors else "partial",
            "loaded": loaded,
            "total": len(items),
            "errors": errors[:10],
        }

    async def sync_one(self, item_id: int) -> dict[str, Any] | None:
        """
        Синхронизировать одну конструкцию.

        Args:
            item_id: ID конструкции

        Returns:
            Dict с результатом или None при ошибке
        """
        logger.debug(f"Синхронизация ID={item_id}")

        await bitrix_fields.ensure_loaded(self.crm)
        item = await self.crm.get_construction_by_id(item_id)

        address = extract_address(item)
        side = extract_side(item)

        if not address:
            logger.error(f"ID={item_id} без адреса")
            return None

        existing = await BillboardRepository.find_by_bitrix_id_or_address(
            bitrix_id=item_id,
            address=address,
            side=side,
            location_repo=LocationRepository,
        )

        if existing:
            update_data = await self.helper.prepare_billboard_update(item)

            if existing.get("bitrix_id") != item_id:
                update_data["bitrix_id"] = item_id

            await BillboardRepository.update(
                id=existing["id"], values=update_data
            )

            logger.info(f"Билборд обновлён: ID={existing['id']}")

            return {
                "status": "updated",
                "billboard_id": existing["id"],
                "location_id": existing["location_id"],
            }

        billboard_id = await self.helper.create_billboard_from_item(item)
        created = await BillboardRepository.get_one(id=billboard_id)

        return {
            "status": "created",
            "billboard_id": billboard_id,
            "location_id": created["location_id"],
        }

    async def delete_by_bitrix_id(
        self, bitrix_id: int
    ) -> dict[str, Any] | None:
        """
        Удалить билборд по Bitrix ID.

        Args:
            bitrix_id: ID конструкции в Bitrix24

        Returns:
            Dict с информацией об удалённом билборде или None
        """

        class BitrixFilter(BaseModel):
            bitrix_id: int

        billboard = await BillboardRepository.get_one(
            filters=BitrixFilter(bitrix_id=bitrix_id)
        )

        if not billboard:
            logger.warning(f"Билборд с bitrix_id={bitrix_id} не найден")
            return None

        billboard_id = billboard["id"]
        location_id = billboard["location_id"]

        await BillboardRepository.delete(id=billboard_id)

        logger.info(
            f"Билборд удалён: ID={billboard_id}, bitrix_id={bitrix_id}"
        )

        return {
            "billboard_id": billboard_id,
            "location_id": location_id,
        }
