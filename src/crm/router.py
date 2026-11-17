import logging
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request, status

from crm.depends import get_booking_service, get_webhook_service
from crm.services.booking_service import BookingService
from crm.services.webhook_service import WebhookService
from database.schemas.booking_schemas import BookingCreate, BookingResponse


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.post(
    "/booking",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать бронирование",
    description=(
        "Создаёт бронирование билборда на указанные месяцы"
        "**Процесс:**\n"
        "1. Проверяет доступность месяцев\n"
        "2. Устанавливает статус 'резерв'\n"
        "3. Создаёт лид в Bitrix24\n"
        "4. Возвращает детали бронирования\n"
        "**billboard_id** имеет формат `location_id-сторона`, например `42-А`"
    ),
)
async def create_booking(
    booking_data: Annotated[BookingCreate, Body()],
    booking_service: Annotated[BookingService, Depends(get_booking_service)],
) -> BookingResponse:
    """
    Создать бронирование билборда.
    Args:
        booking_data: Данные бронирования

    Returns:
        BookingResponse: Результат бронирования с деталями
    """

    result = await booking_service.create_booking(booking_data)

    logger.info(f"Бронирование создано: {booking_data.billboard_id}, ")

    return result


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Обработать вебхук от Bitrix24",
)
async def process_webhook(
    request: Request,
    webhook_service: Annotated[WebhookService, Depends(get_webhook_service)],
) -> dict:
    """
    Обработать входящий вебхук от Bitrix24.

    Args:
        request: Входящий запрос (для парсинга form или json)
        webhook_service: Зависимость для WebhookService

    Returns:
        Dict с результатом обработки
    """

    form_data = await request.form()

    result = await webhook_service.process_webhook(form_data)

    return result
