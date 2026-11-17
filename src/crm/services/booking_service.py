import logging

from crm.utils.booking_utils.booking_helper import (
    build_booking_response,
    create_bitrix_lead,
    fetch_location_and_size,
    get_billboard_by_location_and_side,
    update_billboard_statuses,
)
from crm.utils.booking_utils.booking_validator import (
    validate_month_availability,
)
from crm.utils.parsers.booking_parser import parse_composite_id
from database.schemas.booking_schemas import BookingCreate, BookingResponse
from external.crm.bitrix import BitrixCrmClient


logger = logging.getLogger(__name__)


class BookingService:
    def __init__(self, bitrix_client: BitrixCrmClient):
        self.bitrix_client = bitrix_client

    async def create_booking(
        self, booking_data: BookingCreate
    ) -> BookingResponse:
        """
        Создать бронирование билборда.

        Args:
            booking_data: Данные бронирования

        Returns:
            BookingResponse: Результат бронирования
        """
        logger.info(
            "Создание бронирования: billboard_id=%s, месяцы=%s, клиент=%s",
            booking_data.billboard_id,
            booking_data.months,
            booking_data.client_name,
        )

        location_id, side = parse_composite_id(booking_data.billboard_id)

        billboard = await get_billboard_by_location_and_side(location_id, side)

        validate_month_availability(billboard, booking_data.months)

        await update_billboard_statuses(
            billboard["id"], booking_data.months, "резерв"
        )

        location, size = await fetch_location_and_size(billboard)

        bitrix_lead_id = await create_bitrix_lead(
            bitrix_client=self.bitrix_client,
            booking_data=booking_data,
            billboard=billboard,
            location=location,
            size=size,
        )

        response = build_booking_response(
            booking_data=booking_data,
            billboard=billboard,
            location=location,
            size=size,
            bitrix_lead_id=bitrix_lead_id,
        )

        logger.info(
            f"Бронирование создано: billboard_id={billboard['id']}, "
            f"lead_id={bitrix_lead_id}"
        )

        return response
