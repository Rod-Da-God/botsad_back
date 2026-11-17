import logging

from crm.utils.webhook import register_handler
from crm.utils.webhook.handler import WebhookEventHandler
from external.webhooks import BILLBOARD_DELETED, notify_billboard_event


logger = logging.getLogger(__name__)


@register_handler("ONCRMDYNAMICITEMDELETE")
class DeleteEventHandler(WebhookEventHandler):
    """
    Обработчик удаления конструкции в Bitrix24.

    Удаляет конструкцию из локальной БД при удалении в CRM.
    """

    async def handle(self, item_id: int) -> dict:
        """
        Обработать удаление конструкции.

        Args:
            item_id: ID конструкции в Bitrix24

        Returns:
            Dict с результатом операции
        """
        logger.debug("[DELETE] Обработка удаления конструкции ID=%d", item_id)

        result = await self.crm_sync_service.delete_by_bitrix_id(item_id)

        if not result:
            logger.warning(
                "[DELETE] Конструкция ID=%d не найдена для удаления", item_id
            )
            return {
                "status": "not_found",
                "item_id": item_id,
                "message": f"Конструкция {item_id} не найдена в БД",
            }

        location_id = result.get("location_id")
        billboard_id = result.get("billboard_id")

        logger.info(
            "[DELETE] Конструкция удалена:"
            " item_id=%d, billboard_id=%d, location_id=%d",
            item_id,
            billboard_id,
            location_id,
        )

        # Сбой кэша/рассылки не должен мешать исходящему уведомлению:
        # запись в БД уже успешна, а данные догрузятся при следующем запросе.
        try:
            await self.broadcast_billboard(location_id, "delete")
        except Exception:
            logger.exception(
                "[DELETE] Не удалось обновить кэш/разослать обновление"
            )

        await notify_billboard_event(
            BILLBOARD_DELETED,
            {
                "billboard_id": billboard_id,
                "location_id": location_id,
                "crm_item_id": item_id,
            },
        )

        return {
            "status": "deleted",
            "item_id": item_id,
            "billboard_id": billboard_id,
            "location_id": location_id,
            "message": f"Конструкция {item_id} удалена",
        }
