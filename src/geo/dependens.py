from .services.suggest_service import SuggestService


def get_suggest_service() -> SuggestService:
    return SuggestService()
