import logging

from crm.exceptions import MonthNotAvailableException
from crm.utils.crm_utils.month_utils import get_booking_months


logger = logging.getLogger(__name__)


def validate_month_availability(billboard: dict, months: list[str]) -> None:
    """
    Проверить доступность месяцев для бронирования.

    Args:
        billboard: Данные билборда из БД
        months: Список месяцев для проверки (формат: "2025-11")
    """
    available_months = get_booking_months()
    month_field_map = {month: field for field, month in available_months}

    for month in months:
        field_name = month_field_map.get(month)

        if not field_name:
            available = ", ".join(sorted(month_field_map.keys()))
            raise ValueError(
                f"Месяц {month} не поддерживается. Доступны: {available}"
            )

        status = billboard.get(field_name, "")

        if status != "свободно":
            logger.warning(
                f"Месяц {month} недоступен: статус={status}, "
                f"billboard_id={billboard['id']}"
            )
            raise MonthNotAvailableException(month, status)

    logger.debug(f"Все месяцы {months} доступны для бронирования")


def get_month_update_fields(
    months: list[str], new_status: str
) -> dict[str, str]:
    """
    Получить словарь полей для обновления статусов месяцев.

    Args:
        months: Список месяцев (формат: "2025-11")
        new_status: Новый статус ("резерв", "занято", "свободно")

    Returns:
        Dict[str, str]: Словарь {field_name: status}
    """
    available_months = get_booking_months()
    month_field_map = {month: field for field, month in available_months}

    update_data = {}

    for month in months:
        field_name = month_field_map.get(month)
        if field_name:
            update_data[field_name] = new_status

    logger.debug(f"Подготовлены поля для обновления: {update_data}")
    return update_data
