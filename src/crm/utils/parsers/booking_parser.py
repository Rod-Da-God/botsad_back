import logging


logger = logging.getLogger(__name__)


def parse_composite_id(composite_id: str) -> tuple[int, str]:
    """
    Парсит составной ID формата "location_id-сторона".

    Args:
        composite_id: Строка вида "42-А"

    Returns:
        Tuple[int, str]: (location_id, сторона)
    """
    parts = composite_id.split("-")

    if len(parts) != 2:
        raise ValueError(
            f"Некорректный формат billboard_id: '{composite_id}'. "
            f"Ожидается 'location_id-сторона'"
        )

    location_id = int(parts[0])

    side = parts[1]

    logger.debug(
        f"Распознан composite_id: location_id={location_id}, сторона={side}"
    )

    return (location_id, side)


def format_address(location: dict) -> str:
    """
    Форматирует адрес из данных локации.

    Args:
        location: Словарь с данными локации

    Returns:
        str: Отформатированный адрес
    """
    if location.get("landmark"):
        return location["landmark"]

    street = location.get("street_name", "").strip()
    building = location.get("building_number", "").strip()

    if street or building:
        return f"{street} {building}".strip()

    return "Адрес не указан"


def format_size(size: dict) -> str:
    """
    Форматирует размер билборда.

    Args:
        size: Словарь с данными размера (width, height)

    Returns:
        str: Размер в формате "6x3" или "Не указан"
    """
    if not size:
        return "Не указан"

    width = size.get("width")
    height = size.get("height")

    if width is not None and height is not None:
        return f"{width}x{height}"

    return "Не указан"
