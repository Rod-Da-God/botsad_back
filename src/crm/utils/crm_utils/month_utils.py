import logging
from datetime import datetime

from dateutil.relativedelta import relativedelta


logger = logging.getLogger(__name__)


def get_booking_months(
    start_date: datetime | None = None,
) -> list[tuple[str, str]]:
    """
    Получить список из 5 месяцев начиная с текущего.

    Args:
        start_date: Начальная дата (по умолчанию текущая)

    Returns:
        List[Tuple[str, str]]: Список кортежей (поле_в_БД, формат_YYYY-MM)
    """
    if start_date is None:
        start_date = datetime.now()

    months = []
    current = start_date

    for i in range(1, 7):
        field_name = f"status_month{i}"
        month_format = current.strftime("%Y-%m")
        months.append((field_name, month_format))

        current = current + relativedelta(months=1)

    logger.debug(f"Месяцы для бронирования: {[m[1] for m in months]}")
    return months


def validate_booking_months(requested_months: list[str]) -> list[str]:
    """
    Валидировать запрошенные месяцы для бронирования.

    Args:
        requested_months: Список месяцев в формате ["2025-11", "2025-12"]

    Returns:
        List[str]: Валидные месяцы

    Raises:
        ValueError: Если хотя бы один месяц недоступен
    """
    available_months = get_booking_months()
    available_set = {month[1] for month in available_months}

    invalid_months = [m for m in requested_months if m not in available_set]

    if invalid_months:
        available_str = ", ".join(sorted(available_set))
        invalid_str = ", ".join(invalid_months)
        raise ValueError(
            f"Недоступные месяцы для бронирования: {invalid_str}. "
            f"Доступны: {available_str}"
        )

    return requested_months
