from .base import BaseSuggestClient
from .impl.dadata import DadataSuggest


class Suggest:
    """Единая точка входа. Легко заменить реализацию"""

    _client: BaseSuggestClient = DadataSuggest()

    @classmethod
    async def suggest_address(
        cls,
        query: str,
        count: int | None = None,
    ) -> list[dict[str, str | float]]:
        return await cls._client.suggest_address(query, count)
