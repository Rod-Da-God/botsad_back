"""Исходящие вебхуки о событиях конструкций."""

import logging
from typing import Any

from external.api.api_registry import api_registry
from external.seo.client import WebhookEvent


logger = logging.getLogger(__name__)

BILLBOARD_CREATED = "billboard.created"
BILLBOARD_UPDATED = "billboard.updated"
BILLBOARD_DELETED = "billboard.deleted"

BILLBOARD_EVENTS = frozenset(
    {BILLBOARD_CREATED, BILLBOARD_UPDATED, BILLBOARD_DELETED}
)


async def notify_billboard_event(
    event_type: str, payload: dict[str, Any]
) -> bool:
    """
    Отправить исходящий вебхук о событии конструкции.

    Уведомление не должно ломать обработку входящего события Bitrix24,
    поэтому любые ошибки отправки только логируются.

    Returns:
        True — событие отправлено, False — отправка пропущена или упала.
    """
    if event_type not in BILLBOARD_EVENTS:
        logger.warning("Неизвестный тип события вебхука: %s", event_type)
        return False

    if api_registry.webhook is None:
        logger.debug(
            "Вебхук не сконфигурирован, событие %s пропущено", event_type
        )
        return False

    try:
        await api_registry.webhook.send_event(
            WebhookEvent(type=event_type, payload=payload)
        )
    except Exception:
        logger.exception("Не удалось отправить вебхук %s", event_type)
        return False

    return True
