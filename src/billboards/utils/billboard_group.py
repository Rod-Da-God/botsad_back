import logging


logger = logging.getLogger(__name__)


def group_by_location(raw_data: list[dict]) -> dict[int, list[dict]]:
    """
    Группирует данные по location_id.

    Args:
        raw_data: Сырые данные из БД

    Returns:
        Dict[int, List[Dict]]: Данные сгруппированные по location_id
    """
    grouped: dict[int, list[dict]] = {}

    for row in raw_data:
        location_id = row["location_id"]

        if location_id not in grouped:
            grouped[location_id] = []

        grouped[location_id].append(row)

    logger.debug(f"Данные сгруппированы по {len(grouped)} локациям")
    return grouped
