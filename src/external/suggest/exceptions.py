# external/suggest/exceptions.py
class SuggestError(Exception):
    """Базовое исключение для suggest-модуля"""

    pass


class SuggestAuthError(SuggestError):
    """Ошибка авторизации (неверный токен, заблокирован)"""

    pass


class SuggestAPIError(SuggestError):
    """Ошибка от API (5xx, 429, 403 и т.д.)"""

    pass


class SuggestNetworkError(SuggestError):
    """Сетевая ошибка (таймаут, нет связи)"""

    pass
