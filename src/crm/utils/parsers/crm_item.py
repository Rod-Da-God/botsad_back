import logging

from crm.utils.crm_utils.extractors import (
    extract_address,
    extract_lighting,
    extract_month_statuses,
    extract_mounting_price,
    extract_production_price,
    extract_rental_price,
    extract_side,
)
from database.schemas.billboard_schemas import BillboardCreate, BillboardUpdate


logger = logging.getLogger(__name__)


def parse_crm_item_to_billboard_data(
    crm_item: dict,
    location_id: int,
    size_id: int,
    material_id: int | None,
    photo_url: str = "",
) -> BillboardCreate:
    """
    Преобразовать CRM item в схему БД BillboardCreate.

    Args:
        crm_item: Элемент конструкции из CRM
        location_id: ID локации
        size_id: ID размера
        material_id: ID материала
        photo_url: URL фото

    Returns:
        BillboardCreate схема для создания в БД
    """
    bitrix_id = crm_item.get("id")
    side = extract_side(crm_item)
    has_lighting = extract_lighting(crm_item)

    logger.debug(
        f"Парсинг CRM item: bitrix_id={bitrix_id}, side={side}, "
        f"lighting={has_lighting}"
    )

    statuses = extract_month_statuses(crm_item)

    rental = extract_rental_price(crm_item)
    mounting = extract_mounting_price(crm_item)
    production = extract_production_price(crm_item)

    main_status = statuses["status_month1"]

    billboard_data = BillboardCreate(
        bitrix_id=int(bitrix_id) if bitrix_id else None,
        location_id=location_id,
        size_id=size_id,
        material_id=material_id,
        side=side,
        has_lighting=has_lighting,
        status=main_status,
        status_month1=statuses["status_month1"],
        status_month2=statuses["status_month2"],
        status_month3=statuses["status_month3"],
        status_month4=statuses["status_month4"],
        status_month5=statuses["status_month5"],
        status_month6=statuses["status_month6"],
        photo_url=photo_url,
        rental_price=rental,
        mounting_price=mounting,
        production_price=production,
    )

    logger.debug(
        f"BillboardCreate схема создана: location_id={location_id}, "
        f"side={side}, status={main_status}"
    )

    return billboard_data


def parse_crm_item_to_billboard_update(
    crm_item: dict,
    size_id: int,
    material_id: int | None,
    photo_url: str = "",
) -> BillboardUpdate:
    """
    Преобразовать CRM item в схему обновления BillboardUpdate.

    Args:
        crm_item: Элемент конструкции из CRM
        size_id: ID размера
        material_id: ID материала
        photo_url: URL фото

    Returns:
        BillboardUpdate схема для обновления в БД
    """
    bitrix_id = crm_item.get("id")
    has_lighting = extract_lighting(crm_item)

    statuses = extract_month_statuses(crm_item)

    rental = extract_rental_price(crm_item)
    mounting = extract_mounting_price(crm_item)
    production = extract_production_price(crm_item)

    main_status = statuses["status_month1"]

    logger.debug(
        f"Парсинг для обновления: bitrix_id={bitrix_id}, "
        f"lighting={has_lighting}, status={main_status}"
    )

    return BillboardUpdate(
        bitrix_id=int(bitrix_id) if bitrix_id else None,
        size_id=size_id,
        material_id=material_id,
        has_lighting=has_lighting,
        status=main_status,
        status_month1=statuses["status_month1"],
        status_month2=statuses["status_month2"],
        status_month3=statuses["status_month3"],
        status_month4=statuses["status_month4"],
        status_month5=statuses["status_month5"],
        status_month6=statuses["status_month6"],
        photo_url=photo_url,
        rental_price=rental,
        mounting_price=mounting,
        production_price=production,
    )


def group_items_by_address(items: list[dict]) -> dict[str, list[dict]]:
    """
    Сгруппировать конструкции по адресам.

    Args:
        items: Список элементов конструкций из CRM

    Returns:
        Dict где ключ — адрес, значение — список элементов
    """
    grouped: dict[str, list[dict]] = {}
    skipped = 0

    for item in items:
        address = extract_address(item)

        if not address:
            skipped += 1
            logger.warning(f"Пропуск ID={item.get('id')}: нет адреса")
            continue

        if address not in grouped:
            grouped[address] = []

        grouped[address].append(item)

    if skipped > 0:
        logger.info(f"Пропущено {skipped} конструкций без адреса")

    logger.debug(
        f"Группировка завершена: {len(grouped)} адресов, "
        f"{sum(len(v) for v in grouped.values())} конструкций"
    )

    return grouped
