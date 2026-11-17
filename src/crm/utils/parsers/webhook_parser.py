import logging

from starlette.datastructures import FormData


logger = logging.getLogger(__name__)


class WebhookParseError(Exception):
    """Ошибка парсинга данных вебхука"""

    def __init__(self, message: str, event_type: str | None = None):
        self.message = message
        self.event_type = event_type
        super().__init__(message)


def parse_webhook_data(form_data: FormData) -> tuple[str, int]:
    """
    Парсит данные вебхука от Bitrix24.
    Args:
        form_data: FormData из FastAPI Request

    Returns:
        Tuple[str, int]: (event_type, item_id)

    Raises:
        WebhookParseError: Если не удалось распарсить данные
    """
    raw_event = form_data.get("event")
    event_type = raw_event if isinstance(raw_event, str) else ""

    if not event_type:
        logger.error("[WEBHOOK] Отсутствует тип события в данных вебхука")
        raise WebhookParseError(
            message="Отсутствует тип события в данных вебхука"
        )

    raw_item_id = form_data.get("data[FIELDS][ID]") or form_data.get(
        "data[ID]"
    )
    item_id_str = raw_item_id if isinstance(raw_item_id, str) else ""

    if not item_id_str:
        logger.error(
            "[WEBHOOK] Отсутствует ID элемента для события %s", event_type
        )
        raise WebhookParseError(
            message="Отсутствует ID элемента в данных вебхука",
            event_type=event_type,
        )

    try:
        item_id = int(item_id_str)
        logger.debug(
            "[WEBHOOK] Распознан вебхук: event=%s, item_id=%s",
            event_type,
            item_id,
        )
        return event_type, item_id
    except ValueError:
        logger.error(
            "[WEBHOOK] Некорректный формат ID: %s для события %s",
            item_id_str,
            event_type,
        )
        raise WebhookParseError(
            message=f"Некорректный формат ID: {item_id_str}",
            event_type=event_type,
        ) from None


def extract_item_id_from_dict(data: dict) -> int | None:
    """
    Извлечь item_id из словаря данных вебхука.
    Args:
        data: Словарь с данными вебхука

    Returns:
        int | None: ID элемента или None, если не найден
    """
    item_id = data.get("ID")
    if item_id:
        return int(item_id)

    fields = data.get("FIELDS", {})
    item_id = fields.get("ID")
    if item_id:
        return int(item_id)

    logger.warning("ID не найден в данных вебхука: %s", data)
    return None
