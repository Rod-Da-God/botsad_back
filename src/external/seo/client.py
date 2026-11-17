from __future__ import annotations

import asyncio
import logging
from typing import Any

from pydantic import BaseModel, Field

from ..http_client import BaseHttpClient, HttpClientError, http_request


logger = logging.getLogger(__name__)


class WebhookEvent(BaseModel):
    """
    Минимальная схема вебхука.
    Совместима с вашим endpoint'ом:
      { "type": "...", "payload": {...} }
    """

    type: str = Field(..., description="Тип события")
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Данные события"
    )


class WebhookSenderClient(BaseHttpClient):
    """
    Чистый HTTP клиент для отправки вебхуков на /events.

    - Никакой бизнес-логики кроме опциональных ретраев.
    - Ожидается ответ 204.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
        retries: int = 0,
        backoff_factor: float = 0.5,
    ):
        super().__init__(base_url, timeout=timeout)
        self._retries = retries
        self._backoff_factor = backoff_factor

    @http_request(
        method="POST",
        path="events",
        response_key=None,  # 204 NO CONTENT
        error_message="Webhook sending failed",
    )
    async def _raw_send_event(
        self,
        event: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return {
            "json": event,
            "headers": {
                "Content-Type": "application/json",
                **(headers or {}),
            },
        }

    async def send_event(
        self,
        event: WebhookEvent | dict[str, Any],
        *,
        idempotency_key: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        """
        Публичная отправка вебхука.

        Args:
            event: WebhookEvent или сырой dict
            idempotency_key: опциональный заголовок идемпотентности
            extra_headers: дополнительные заголовки

        Raises:
            HttpClientError
        """
        payload = (
            event.model_dump() if isinstance(event, WebhookEvent) else event
        )

        headers = dict(extra_headers or {})
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        attempt = 0
        while True:
            try:
                await self._raw_send_event(payload, headers=headers)
                logger.info("Webhook sent to %s/events", self.base_url)
                return

            except HttpClientError as e:
                attempt += 1

                # ретраи только на временных ошибках / сетевых
                retriable_statuses = {408, 429, 500, 502, 503, 504}
                is_retriable = (
                    e.status_code in retriable_statuses
                ) or e.status_code is None

                if attempt > self._retries or not is_retriable:
                    logger.error(
                        "Webhook failed after %d attempts: %s", attempt, e
                    )
                    raise

                sleep_s = self._backoff_factor * (2 ** (attempt - 1))
                logger.warning(
                    "Webhook failed (attempt %d/%d, status=%s)."
                    " Retry in %.2fs",
                    attempt,
                    self._retries,
                    e.status_code,
                    sleep_s,
                )
                await asyncio.sleep(sleep_s)
