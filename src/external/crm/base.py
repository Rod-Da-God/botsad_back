from abc import ABC, abstractmethod
from typing import Any


class CrmClient(ABC):
    """
    Абстрактный клиент для работы с CRM системами.
    """

    @abstractmethod
    async def get_constructions(self) -> list[dict[str, Any]]:
        """
        Получить все конструкции из CRM.

        Returns:
            Dict с результатом запроса
        """
        pass

    @abstractmethod
    async def get_construction_by_id(self, item_id: int) -> dict[str, Any]:
        """
        Получить конкретную конструкцию по ID.

        Args:
            item_id: ID конструкции в CRM

        Returns:
            Dict с данными конструкции
        """
        pass

    @abstractmethod
    async def create_lead(
        self, fields: dict[str, Any], register_event: bool = False
    ) -> int:
        """
        Создать лид в CRM.

        Args:
            fields: Поля лида
            register_event: Регистрировать событие

        Returns:
            ID созданного лида
        """
        pass
