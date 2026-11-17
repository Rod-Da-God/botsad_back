import logging

from billboards.services.billboard_service import BillboardService


logger = logging.getLogger(__name__)


_billboard_service: BillboardService | None = None


def get_billboard_service() -> BillboardService:
    """
    Получить синглтон-инстанс BillboardService.

    Returns:
        BillboardService: Сервис для работы с билбордами
    """
    global _billboard_service

    if _billboard_service is None:
        logger.debug("Создание BillboardService")
        _billboard_service = BillboardService()
        logger.info("BillboardService инициализирован")

    return _billboard_service
