import logging
from abc import ABC, abstractmethod

from external.cache.cache import Cache
from ws.broadcast import TOPICS, Broadcast


logger = logging.getLogger(__name__)


class WebhookEventHandler(ABC):
    """
    Базовый класс для всех обработчиков webhook событий.
    """

    def __init__(self, crm_sync_service, billboard_service):
        self.crm_sync_service = crm_sync_service
        self.billboard_service = billboard_service

    @abstractmethod
    async def handle(self, item_id: int) -> dict:
        """
        Обработать событие webhook.

        Args:
            item_id: ID элемента в Bitrix24

        Returns:
            Dict с результатом обработки
        """
        pass

    async def broadcast_billboard(self, location_id: int, action: str):
        """
        Отправка broadcast-сообщения о билборде.

        Args:
            location_id: ID локации билборда
            action: Тип действия ('create', 'update', 'delete')
        """

        await self.update_cache(location_id, action)

        if action == "delete":
            await Broadcast.publish(
                topic=TOPICS.UPDATES,
                message={"id": location_id},
                action="delete",
            )
            logger.info(
                f"[BROADCAST] delete отправлен (location_id={location_id})"
            )
            return

        billboard = await self.billboard_service.get_billboard_details(
            location_id
        )

        if not billboard:
            logger.warning(
                "[BROADCAST] Нет данных билборда для location_id=%s",
                location_id,
            )
            return

        billboard_json = billboard.model_dump()

        await Broadcast.publish(
            topic=TOPICS.UPDATES, message=billboard_json, action=action
        )

        logger.info(
            f"[BROADCAST] {action} отправлен (location_id={location_id})"
        )

    async def update_cache(self, location_id: int, action: str):
        """
        Обновляет Redis-кеш билбордов в зависимости от действия.

        Args:
            location_id: ID локации билборда
            action: Тип действия ('create', 'update', 'delete')
        """

        if action == "delete":
            await Cache.delete_billboard(location_id)
            logger.info(f"[CACHE] DELETE location_id={location_id}")
            return

        billboard_data = await self.billboard_service.get_billboard_details(
            location_id
        )

        if not billboard_data:
            logger.warning(
                f"[CACHE] нет данных билборда для location_id={location_id}"
            )
            return

        billboard_dict = billboard_data.model_dump(by_alias=True)

        if action == "create":
            await Cache.add_billboard(billboard_dict)
            logger.info(f"[CACHE] CREATE location_id={location_id}")

        elif action == "update":
            await Cache.update_billboard(billboard_dict)
            logger.info(f"[CACHE] UPDATE location_id={location_id}")
