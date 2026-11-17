import logging

from external.suggest.suggest import Suggest


logger = logging.getLogger(__name__)


class SuggestService:
    """Домен-сервис — обёртка над внешним suggest-клиентом"""

    async def suggest_address(
        self,
        query: str,
        count: int | None = None,
    ) -> list[dict[str, str | float]]:
        """
        Возвращает подсказки адресов с координатами.
        """
        if not query or not query.strip():
            logger.warning(
                "Empty query in suggest_address, returning empty list"
            )
            return []

        logger.debug(
            "Suggest address request: query='%s', count=%s",
            query,
            count or "default",
        )
        result = await Suggest.suggest_address(query.strip(), count)
        logger.info(
            "Suggest success: query='%s' → %d results",
            query.strip(),
            len(result),
        )
        return result
