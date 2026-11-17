import logging

from starlette.datastructures import FormData

from crm.utils.parsers.webhook_parser import (
    WebhookParseError,
    parse_webhook_data,
)
from crm.utils.webhook.factory import WebhookEventHandlerFactory


logger = logging.getLogger(__name__)


class WebhookService:
    """
    Сервис для обработки вебхуков из Bitrix24.

    Принимает события от Bitrix24 и делегирует их обработку
    соответствующим обработчикам через фабрику.
    """

    def __init__(self, crm_sync_service, billboard_service):
        """
        Args:
            crm_sync_service: Сервис синхронизации с CRM
            billboard_service: Сервис для работы с билбордами
        """
        self.factory = WebhookEventHandlerFactory(
            crm_sync_service=crm_sync_service,
            billboard_service=billboard_service,
        )
        logger.info("WebhookService инициализирован")

    async def process_webhook(self, form_data: FormData) -> dict:
        """
        Обработать входящий вебхук от Bitrix24.

        Args:
            form_data: FormData с данными вебхука

        Returns:
            Dict с результатом обработки
        """
        try:
            event_type, item_id = parse_webhook_data(form_data)
        except WebhookParseError as e:
            return {
                "status": "error",
                "message": e.message,
                "event_type": e.event_type,
            }

        logger.info(
            "[WEBHOOK] Получен вебхук: event=%s, item_id=%d",
            event_type,
            item_id,
        )

        handler = self.factory.get_handler(event_type)

        if not handler:
            logger.warning(
                "[WEBHOOK] Неподдерживаемый тип события: %s", event_type
            )
            return {
                "status": "error",
                "message": f"Неподдерживаемый тип события: {event_type}",
                "event_type": event_type,
                "item_id": item_id,
            }

        result = await handler.handle(item_id)

        logger.info(
            "[WEBHOOK] Вебхук успешно обработан:"
            " event=%s, item_id=%d, status=%s",
            event_type,
            item_id,
            result.get("status"),
        )

        return result
