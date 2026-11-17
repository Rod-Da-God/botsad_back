import logging


logger = logging.getLogger(__name__)


def format_billboard_address(location_data: dict[str, str | None]) -> str:
    """
    Форматирует адрес билборда из данных локации.

    Args:
        location_data: Словарь с полями:
            - landmark: str | None - ориентир/полный адрес
            - street_name: str | None - название улицы
            - building_number: str | None - номер дома

    Returns:
        str: Отформатированный адрес
    """
    landmark = location_data.get("landmark")
    street_name = location_data.get("street_name")
    building_number = location_data.get("building_number")

    if landmark and landmark.strip():
        address = landmark.strip()
        logger.debug(f"Адрес из landmark: '{address}'")
        return address

    if street_name and street_name.strip():
        street = street_name.strip()

        if building_number and building_number.strip():
            address = f"{street} {building_number.strip()}"
        else:
            address = street

        logger.debug(f"Адрес из street_name + building_number: '{address}'")
        return address

    logger.debug("Адрес не найден, возвращаем placeholder")
    return "Адрес не указан"
