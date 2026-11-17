import logging

from billboards.utils.normalizers.size import format_size_from_dict
from billboards.utils.parsers.address import format_billboard_address
from billboards.utils.translit_slug import translit_address
from crm.utils.crm_utils.month_utils import get_booking_months
from database.schemas.billboard_schemas import (
    BillboardDetailResponse,
    BillboardListResponse,
    SideBasicInfo,
    SideDetailedInfo,
)


logger = logging.getLogger(__name__)


def build_statuses_dict(side_data: dict) -> dict[str, str]:
    """
    Построить словарь статусов с реальными датами месяцев.

    Args:
        side_data: Данные стороны из БД со статусами status_month1-6

    Returns:
        Dict[str, str]: Словарь {"2025-11": "свободно", ...}
    """
    booking_months = get_booking_months()
    statuses = {}

    for i, (_field_name, month_format) in enumerate(booking_months, 1):
        db_field = f"status_month{i}"
        status = side_data.get(db_field, "свободно")
        statuses[month_format] = status

    return statuses


def build_list_response(
    location_id: int, sides_data: list[dict]
) -> BillboardListResponse:
    """
    Формирует BillboardListResponse из данных сторон.

    Args:
        location_id: ID локации
        sides_data: Данные всех сторон

    Returns:
        BillboardListResponse: Сформированный response
    """
    first_side = sides_data[0]

    location_data = {
        "landmark": first_side.get("landmark"),
        "street_name": first_side.get("street_name"),
        "building_number": first_side.get("building_number"),
    }
    address = format_billboard_address(location_data)

    city = str(first_side.get("city") or "")
    slug_city = first_side.get("slug_city")
    slug = translit_address(city, address)

    coordinates = [
        float(first_side["longitude"]),
        float(first_side["latitude"]),
    ]

    size_data = {
        "width": first_side.get("width"),
        "height": first_side.get("height"),
    }

    construction_type = format_size_from_dict(size_data)
    district = first_side.get("district_name")

    sides = {}
    for side_data in sides_data:
        side_key = side_data["side"]

        statuses = build_statuses_dict(side_data)

        images = [side_data["photo_url"]] if side_data.get("photo_url") else []
        composite_id = f"{location_id}-{side_key}"

        side_info = SideBasicInfo(
            id=composite_id,
            price=float(side_data["price"]),
            installationDemounting=float(side_data["mounting_price"]),
            manufacturing=float(side_data["production_price"]),
            images=images,
            statuses=statuses,
        )

        sides[side_key] = side_info

    return BillboardListResponse(
        id=location_id,
        slug=slug,
        slug_city=slug_city,
        coordinates=coordinates,
        city=city,
        address=address,
        district=district,
        constructionType=construction_type,
        sides=sides,
    )


def build_detail_response(
    location_id: int, raw_data: list[dict]
) -> BillboardDetailResponse:
    """
    Формирует BillboardDetailResponse из детальных данных.

    Args:
        location_id: ID локации
        raw_data: Детальные данные всех сторон

    Returns:
        BillboardDetailResponse: Сформированный response
    """
    first_side = raw_data[0]

    location_data = {
        "landmark": first_side.get("landmark"),
        "street_name": first_side.get("street_name"),
        "building_number": first_side.get("building_number"),
    }
    address = format_billboard_address(location_data)
    city = str(first_side.get("city") or "")
    coordinates = [
        float(first_side["longitude"]),
        float(first_side["latitude"]),
    ]
    slug = translit_address(city, address)
    slug_city = first_side.get("slug_city")
    size_data = {
        "width": first_side["width"],
        "height": first_side["height"],
    }
    construction_type = format_size_from_dict(size_data)

    district = first_side.get("district_name")

    sides = {}
    for side_data in raw_data:
        side_key = side_data["side"]

        statuses = build_statuses_dict(side_data)

        images = [side_data["photo_url"]] if side_data.get("photo_url") else []
        composite_id = f"{location_id}-{side_key}"
        material = side_data.get("material_name")

        side_info = SideDetailedInfo(
            id=composite_id,
            price=float(side_data["rental_price"]),
            images=images,
            hasElectricity=side_data["has_lighting"],
            installationDemounting=float(side_data["mounting_price"]),
            manufacturing=float(side_data["production_price"]),
            material=material,
            statuses=statuses,
        )

        sides[side_key] = side_info

    return BillboardDetailResponse(
        id=location_id,
        coordinates=coordinates,
        address=address,
        slug=slug,
        slug_city=slug_city,
        constructionType=construction_type,
        city=city,
        district=district,
        sides=sides,
    )
