import logging
from decimal import Decimal
from typing import Any

from crm.config import (
    BITRIX_DEFAULT_PRICE,
    BITRIX_DEFAULT_SIDE,
    BITRIX_DEFAULT_SIZE,
    BITRIX_DEFAULT_STATUS,
    BITRIX_LIGHTING_LABELS,
    BITRIX_SIDE_LABELS,
    BITRIX_STATUS_LABELS,
)

from .field_resolver import bitrix_fields, normalize_label


logger = logging.getLogger(__name__)


_MONEY_AMOUNT_KEYS = ("AMOUNT", "VALUE", "PRICE")
_MONEY_CURRENCY_KEYS = ("CURRENCY_ID", "CURRENCY")

_LIGHTING_ALIASES = {
    value: {normalize_label(alias) for alias in aliases}
    for value, aliases in BITRIX_LIGHTING_LABELS.items()
}


def _get_field(item: dict, semantic: str) -> Any:
    """Получить значение поля CRM по его смыслу."""
    return item.get(bitrix_fields.code(semantic))


def _stringify_money(raw_value: Any) -> str:
    """Привести значение поля-денег к формату ``сумма|валюта``."""
    if raw_value is None or raw_value == "":
        return BITRIX_DEFAULT_PRICE

    if isinstance(raw_value, (int, float, Decimal)):
        return f"{raw_value}|RUB"

    if isinstance(raw_value, dict):
        normalized = {
            str(key).upper(): value for key, value in raw_value.items()
        }
        amount = next(
            (
                normalized[key]
                for key in _MONEY_AMOUNT_KEYS
                if normalized.get(key) not in (None, "")
            ),
            None,
        )
        if amount is None:
            return BITRIX_DEFAULT_PRICE

        currency = next(
            (
                normalized[key]
                for key in _MONEY_CURRENCY_KEYS
                if normalized.get(key)
            ),
            "RUB",
        )
        return f"{amount}|{currency}"

    if isinstance(raw_value, (list, tuple)):
        return (
            _stringify_money(raw_value[0])
            if raw_value
            else (BITRIX_DEFAULT_PRICE)
        )

    text = str(raw_value).strip()
    if "|" in text:
        return text
    return f"{text}|RUB"


def extract_address(item: dict) -> str:
    """
    Извлечь адрес из элемента CRM.

    Формат поля в Bitrix: "адрес|координаты|zoom"
    Fallback: поле "title"

    Args:
        item: Элемент конструкции из CRM

    Returns:
        Адрес (строка)

    """
    field = _get_field(item, "address")

    if isinstance(field, str) and "|" in field:
        return field.split("|")[0].strip()

    return str(item.get("title") or "").strip()


def extract_coordinates(item: dict) -> tuple[float, float] | None:
    """
    Извлечь координаты из элемента CRM.

    Формат в Bitrix: "адрес|lat;lon|zoom"

    Args:
        item: Элемент конструкции из CRM

    Returns:
        Кортеж (longitude, latitude) или None

    """
    field = _get_field(item, "address")

    if not isinstance(field, str) or "|" not in field:
        return None

    parts = field.split("|")
    if len(parts) >= 2:
        coords_part = parts[1].strip()
        if not coords_part or coords_part == ";" or ";" not in coords_part:
            return None
        lat_str, lon_str = coords_part.split(";")
        if lat_str and lon_str:
            return (float(lon_str), float(lat_str))
    return None


def extract_size(item: dict) -> str:
    """
    Извлечь размер конструкции из элемента CRM.

    Возвращает название варианта списка "Тип конструкции",
    например "6x3". Дальше строка парсится в SizeCreate.

    Args:
        item: Элемент конструкции из CRM

    Returns:
        Строка размера (например, "6x3")

    """
    label = bitrix_fields.enum_label(
        "construction_type", _get_field(item, "construction_type")
    )
    return label.strip() if label else BITRIX_DEFAULT_SIZE


def extract_side(item: dict) -> str:
    """
    Извлечь сторону конструкции из элемента CRM.

    Args:
        item: Элемент конструкции из CRM

    Returns:
        Сторона (А, Б, В или Г)

    """
    label = bitrix_fields.enum_label("side", _get_field(item, "side"))
    if not label:
        return BITRIX_DEFAULT_SIDE

    side = label.strip().upper()[:1]
    return side if side in BITRIX_SIDE_LABELS else BITRIX_DEFAULT_SIDE


def extract_lighting(item: dict) -> bool:
    """
    Извлечь информацию об освещении из элемента CRM.

    Args:
        item: Элемент конструкции из CRM

    Returns:
        True если есть подсветка, иначе False

    """
    raw_value = _get_field(item, "lighting")
    if isinstance(raw_value, bool):
        return raw_value

    label = bitrix_fields.enum_label("lighting", raw_value)
    if not label:
        return False

    normalized = normalize_label(label)
    for value, aliases in _LIGHTING_ALIASES.items():
        if normalized in aliases:
            return value

    logger.warning("Неизвестный вариант подсветки: %s", label)
    return False


def extract_material(item: dict) -> str:
    """
    Извлечь материал из элемента CRM.

    Args:
        item: Элемент конструкции из CRM

    Returns:
        Название материала (может быть пустой строкой)

    """
    code = bitrix_fields.code_optional("material")
    if code is None:
        return ""

    raw_value = item.get(code)
    if raw_value is None:
        return ""

    if isinstance(raw_value, dict):
        raw_value = raw_value.get("VALUE", raw_value.get("value", ""))

    if isinstance(raw_value, (list, tuple)):
        return str(raw_value[0]) if raw_value else ""

    return str(raw_value).strip()


def extract_rental_price(item: dict) -> str:
    """
    Извлечь цену аренды из элемента CRM.

    Args:
        item: Элемент конструкции из CRM

    Returns:
        Строка цены в формате "10000|RUB"

    """
    return _stringify_money(_get_field(item, "rental_price"))


def extract_mounting_price(item: dict) -> str:
    """
    Извлечь цену монтажа из элемента CRM.

    Args:
        item: Элемент конструкции из CRM

    Returns:
        Строка цены в формате "10000|RUB"

    """
    return _stringify_money(_get_field(item, "mounting_price"))


def extract_production_price(item: dict) -> str:
    """
    Извлечь цену производства из элемента CRM.

    Args:
        item: Элемент конструкции из CRM

    Returns:
        Строка цены в формате "10000|RUB"

    """
    return _stringify_money(_get_field(item, "production_price"))


def extract_photo(crm_item: dict) -> list[dict]:
    photo_data = crm_item.get(bitrix_fields.code("photo"), [])

    if isinstance(photo_data, dict):
        return [photo_data]

    if isinstance(photo_data, list):
        return photo_data

    return []


def _normalize_status(label: str | None) -> str:
    """Привести название варианта статуса к значению для БД."""
    if not label:
        return BITRIX_DEFAULT_STATUS

    normalized = normalize_label(label)
    return (
        normalized
        if normalized in BITRIX_STATUS_LABELS
        else BITRIX_DEFAULT_STATUS
    )


def extract_month_statuses(item: dict) -> dict[str, str]:
    """
    Извлечь статусы по месяцам из отдельных полей Bitrix.

    Args:
        item: Элемент конструкции из CRM

    Returns:
        Dict со статусами для каждого месяца:
        {'status_month1': 'свободно', ...}

    """
    result: dict[str, str] = {}

    for index in range(1, 7):
        semantic = f"status{index}"
        label = bitrix_fields.enum_label(semantic, _get_field(item, semantic))
        result[f"status_month{index}"] = _normalize_status(label)

    logger.debug(
        "Статусы извлечены: месяц1=%s, месяц2=%s",
        result["status_month1"],
        result["status_month2"],
    )

    return result
