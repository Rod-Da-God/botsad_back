import logging

from crm.utils.webhook import register_handler
from external.webhooks import BILLBOARD_UPDATED, notify_billboard_event

from ..handler import WebhookEventHandler


logger = logging.getLogger(__name__)


@register_handler("ONCRMDYNAMICITEMUPDATE")
class UpdateEventHandler(WebhookEventHandler):
    """
    Обработчик обновления конструкции в Bitrix24.

    Синхронизирует изменения из CRM в локальную БД.
    """

    async def handle(self, item_id: int) -> dict:
        """
        Обработать обновление конструкции.

        Args:
            item_id: ID конструкции в Bitrix24

        Returns:
            Dict с результатом операции
        """
        logger.debug(
            "[UPDATE] Обработка обновления конструкции ID=%d", item_id
        )

        result = await self.crm_sync_service.sync_one(item_id)

        if not result:
            logger.warning(
                "[UPDATE] Не удалось синхронизировать конструкцию ID=%d",
                item_id,
            )
            return {
                "status": "error",
                "item_id": item_id,
                "message": "Не удалось синхронизировать конструкцию",
            }

        location_id = result.get("location_id")
        billboard_id = result.get("billboard_id")

        logger.info(
            "[UPDATE] Конструкция обновлена:"
            " item_id=%d, billboard_id=%d, location_id=%d",
            item_id,
            billboard_id,
            location_id,
        )

        # Сбой кэша/рассылки не должен мешать исходящему уведомлению:
        # запись в БД уже успешна, а данные догрузятся при следующем запросе.
        try:
            await self.broadcast_billboard(location_id, "update")
        except Exception:
            logger.exception(
                "[UPDATE] Не удалось обновить кэш/разослать обновление"
            )

        await notify_billboard_event(
            BILLBOARD_UPDATED,
            {
                "billboard_id": billboard_id,
                "location_id": location_id,
                "crm_item_id": item_id,
            },
        )

        return {
            "status": "updated",
            "item_id": item_id,
            "billboard_id": billboard_id,
            "location_id": location_id,
            "message": f"Конструкция {item_id} обновлена",
        }
