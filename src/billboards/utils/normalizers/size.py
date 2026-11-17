import logging
from decimal import Decimal


logger = logging.getLogger(__name__)


def _format_dimension(value: Decimal) -> str:
    """
    Привести размер к строке без лишних нулей: 6.0 -> "6", 6.50 -> "6,5".

    В отличие от ``str(value).rstrip("0")`` не портит целые числа
    (10 -> "10", а не "1") и корректно убирает только дробные нули.
    """
    number = Decimal(str(value))

    if number == number.to_integral_value():
        text = format(number.quantize(Decimal(1)), "f")
    else:
        text = format(number.normalize(), "f")

    return text.replace(".", ",")


def format_size_for_display(width: Decimal, height: Decimal) -> str:
    """
    Форматирует размер для отображения.
    Args:
        width: Ширина в метрах
        height: Высота в метрах

    Returns:
        str: Размер в формате "6,0x3,0" или "6x3"
    """
    width_str = _format_dimension(width)
    height_str = _format_dimension(height)

    result = f"{width_str}x{height_str}"

    logger.debug(f"Размер отформатирован: ({width}, {height}) -> '{result}'")
    return result


def format_size_from_dict(size_data: dict | None) -> str:
    """
    Форматирует размер из словаря с данными размера.

    Args:
        size_data: Словарь с полями width и height

    Returns:
        str: Отформатированный размер или "Не указан"

    """
    if not size_data:
        return "Не указан"

    width = size_data.get("width")
    height = size_data.get("height")

    if width is None or height is None:
        logger.debug("Размер не содержит width или height")
        return "Не указан"

    return format_size_for_display(width, height)
