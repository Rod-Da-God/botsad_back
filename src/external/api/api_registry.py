from __future__ import annotations

import logging
from dataclasses import dataclass

from ..seo.client import WebhookSenderClient
from ..seo.config import webhook_settings


logger = logging.getLogger(__name__)


@dataclass
class ApiRegistry:
    webhook: WebhookSenderClient | None = None

    async def startup(self) -> None:
        if webhook_settings.webhook_base_url is None:
            self.webhook = None
            logger.debug(
                "WEBHOOK_BASE_URL не задан — исходящие вебхуки отключены"
            )
            return

        self.webhook = WebhookSenderClient(
            base_url=str(webhook_settings.webhook_base_url),
            timeout=webhook_settings.webhook_timeout,
            retries=webhook_settings.webhook_retries,
            backoff_factor=webhook_settings.webhook_backoff_factor,
        )

    async def shutdown(self) -> None:
        if self.webhook:
            await self.webhook.close()
            self.webhook = None


api_registry = ApiRegistry()
