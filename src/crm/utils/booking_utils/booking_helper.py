import logging
from decimal import Decimal

from pydantic import BaseModel

from crm.utils.parsers.booking_parser import format_address, format_size
from database.repository import (
    BillboardRepository,
    LocationRepository,
    SizeRepository,
)
from database.schemas.booking_schemas import (
    BillboardStatusUpdate,
    BookingCreate,
    BookingResponse,
)
from external.cache.cache import Cache
from external.crm.bitrix import BitrixCrmClient

from .booking_validator import get_month_update_fields


logger = logging.getLogger(__name__)


class BillboardFilter(BaseModel):
    """Фильтр для поиска билборда по локации и стороне."""

    location_id: int
    side: str


async def get_billboard_by_location_and_side(
    location_id: int, side: str
) -> dict:
    """
    Получить билборд по location_id и стороне.

    Args:
        location_id: ID локации
        side: Сторона (А, Б, В, Г)

    Returns:
        Dict с данными билборда

    Raises:
        ValueError: Если билборд не найден
    """
    billboard = await BillboardRepository.get_one(
        filters=BillboardFilter(location_id=location_id, side=side)
    )

    if billboard is None:
        logger.error(
            f"Билборд не найден: location_id={location_id}, сторона={side}"
        )
        raise ValueError(
            f"Билборд не найден для локации {location_id} и стороны {side}"
        )

    logger.debug(
        f"Билборд найден: id={billboard['id']}, "
        f"location_id={billboard['location_id']}, сторона={billboard['side']}"
    )

    return billboard


async def update_billboard_statuses(
    billboard_id: int,
    months: list[str],
    new_status: str,
) -> None:
    """
    Обновить статусы месяцев билборда в БД и кеше.

    Args:
        billboard_id: ID билборда
        months: Список месяцев для обновления
        new_status: Новый статус ("резерв", "занято", "свободно")
    """
    billboard = await BillboardRepository.get_one(id=billboard_id)

    if not billboard:
        logger.error(f"Билборд id={billboard_id} не найден в БД")
        return

    location_id = billboard.get("location_id")
    side = billboard.get("side")

    if not location_id or not side:
        logger.error(
            f"У билборда id={billboard_id} отсутствует location_id или side"
        )
        return

    update_fields = get_month_update_fields(months, new_status)
    update_instance = BillboardStatusUpdate(**update_fields)
    await BillboardRepository.update(id=billboard_id, values=update_instance)

    logger.debug(
        f"Обновлены статусы в БД для billboard_id={billboard_id}: "
        f"{months} -> {new_status}"
    )

    all_billboards = await Cache.get_all_billboards()

    target_location = None
    for location_data in all_billboards:
        if location_data.get("id") == location_id:
            target_location = location_data
            break

    if not target_location:
        logger.warning(
            f"Location id={location_id} не найдена в кеше. "
            f"Обновление кеша пропущено."
        )
        return

    if "slug" not in target_location:
        logger.warning(f"У location id={location_id} отсутствует slug в кеше")
        return

    if "sides" in target_location and side in target_location["sides"]:
        side_data = target_location["sides"][side]

        if "statuses" in side_data:
            for month in months:
                if month in side_data["statuses"]:
                    side_data["statuses"][month] = new_status.capitalize()
                    logger.debug(
                        f"Обновлен статус в кеше: location={location_id}, "
                        f"сторона={side}, месяц={month} -> {new_status}"
                    )
        else:
            logger.warning(
                f"У стороны {side} отсутствует поле statuses в кеше"
            )
            return
    else:
        logger.warning(
            f"Сторона {side} не найдена в кеше для location={location_id}"
        )
        return

    await Cache.update_billboard(target_location)

    logger.info(
        f"Кеш обновлён для location_id={location_id}, сторона={side}, "
        f"месяцы={months} -> {new_status}"
    )


async def create_bitrix_lead(
    bitrix_client: BitrixCrmClient,
    booking_data: BookingCreate,
    billboard: dict,
    location: dict,
    size: dict,
) -> int | None:
    """
    Создать лид в Bitrix24.

    Args:
        bitrix_client: Клиент Bitrix24
        booking_data: Данные бронирования
        billboard: Данные билборда
        location: Данные локации
        size: Данные размера

    Returns:
        ID созданного лида или None
    """
    address = format_address(location)
    size_formatted = format_size(size)

    rental_price = Decimal(str(billboard.get("rental_price", 0)))
    total_rental = rental_price * len(booking_data.months)

    mounting_price = Decimal(str(billboard.get("mounting_price", 0)))
    production_price = Decimal(str(billboard.get("production_price", 0)))

    services = []
    total_services = Decimal("0")

    if booking_data.include_mounting:
        services.append(f"Монтаж/Демонтаж: {mounting_price} руб.")
        total_services += mounting_price

    if booking_data.include_printing:
        services.append(f"Печать: {production_price} руб.")
        total_services += production_price

    total_price = total_rental + total_services

    comments_parts = [
        f"Адрес: {address}",
        f"Сторона: {billboard['side']}",
        f"Размер: {size_formatted}",
        f"Месяцы: {', '.join(booking_data.months)}",
        f"Цена за месяц: {rental_price} руб.",
        f"Аренда ({len(booking_data.months)} мес.): {total_rental} руб.",
    ]

    if services:
        comments_parts.append("\nДополнительные услуги:")
        comments_parts.extend(services)
        comments_parts.append(f"Услуги итого: {total_services} руб.")

    comments_parts.append(f"\nИТОГО К ОПЛАТЕ: {total_price} руб.")

    fields = {
        "TITLE": f"Бронирование {address} (сторона {billboard['side']})",
        "NAME": booking_data.client_name,
        "OPPORTUNITY": float(total_price),
        "PHONE": [
            {"VALUE": str(booking_data.client_phone), "VALUE_TYPE": "WORK"}
        ],
        "COMMENTS": "\n".join(comments_parts),
    }

    lead_id = await bitrix_client.create_lead(
        fields=fields, register_event=True
    )
    logger.info(f"Лид создан в Bitrix24: ID={lead_id}")
    return lead_id


async def fetch_location_and_size(billboard: dict) -> tuple[dict, dict]:
    """
    Получить данные локации и размера для билборда.

    Args:
        billboard: Данные билборда

    Returns:
        Tuple[Dict, Dict]: (location, size)
    """
    location = await LocationRepository.get_one(id=billboard["location_id"])
    size = await SizeRepository.get_one(id=billboard["size_id"])
    return location, size


def build_booking_response(
    booking_data: BookingCreate,
    billboard: dict,
    location: dict,
    size: dict,
    bitrix_lead_id: int | None,
) -> BookingResponse:
    """
    Сформировать ответ после успешного бронирования.

    Args:
        booking_data: Исходные данные бронирования
        billboard: Данные билборда
        location: Данные локации
        size: Данные размера
        bitrix_lead_id: ID созданного лида

    Returns:
        BookingResponse: Сформированный ответ
    """
    address = format_address(location)
    size_formatted = format_size(size)

    rental_price = Decimal(str(billboard.get("rental_price", 0)))
    total_rental = rental_price * len(booking_data.months)

    mounting_price = None
    printing_price = None
    total_services = Decimal("0")

    if booking_data.include_mounting:
        mounting_price = Decimal(str(billboard.get("mounting_price", 0)))
        total_services += mounting_price

    if booking_data.include_printing:
        printing_price = Decimal(str(billboard.get("production_price", 0)))
        total_services += printing_price

    total_price = total_rental + total_services

    services_count = sum(
        [booking_data.include_mounting, booking_data.include_printing]
    )
    message_parts = [
        f"Бронирование успешно создано на {len(booking_data.months)} мес."
    ]

    if services_count > 0:
        message_parts.append(f"Включено услуг: {services_count}")

    return BookingResponse(
        success=True,
        message=" ".join(message_parts),
        billboard_id=booking_data.billboard_id,
        booked_months=booking_data.months,
        address=address,
        side=billboard["side"],
        size=size_formatted,
        rental_price=total_rental,
        mounting_price=mounting_price,
        printing_price=printing_price,
        total_price=total_price,
        bitrix_lead_id=bitrix_lead_id,
    )
