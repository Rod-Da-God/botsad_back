import logging

from . import get_handler_class
from .handler import WebhookEventHandler


logger = logging.getLogger(__name__)


class WebhookEventHandlerFactory:
    """
    Фабрика для создания экземпляров обработчиков событий.

    Создаёт обработчики с нужными зависимостями на основе
    автоматически зарегистрированных классов.
    """

    def __init__(self, crm_sync_service, billboard_service):
        """
        Args:
            crm_sync_service: Сервис синхронизации
            billboard_service: Сервис билбордов
        """
        self.crm_sync_service = crm_sync_service
        self.billboard_service = billboard_service

    def get_handler(self, event_type: str) -> WebhookEventHandler | None:
        """
        Получить обработчик для типа события.

        Главный метод — по имени события возвращает готовый обработчик
        с внедрёнными зависимостями.

        Args:
            event_type: Тип события из Bitrix24 ("ONCRMDYNAMICITEMADD")

        Returns:
            Экземпляр обработчика или None, если тип не поддерживается
        """
        handler_class = get_handler_class(event_type)

        if not handler_class:
            logger.warning(f"Обработчик для события {event_type} не найден")
            return None

        return handler_class(self.crm_sync_service, self.billboard_service)
