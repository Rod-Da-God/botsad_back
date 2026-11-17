class CrmException(Exception):
    """Базовое исключение для CRM модуля"""

    pass


class MonthNotAvailableException(CrmException):
    """Месяц недоступен для бронирования"""

    def __init__(self, month: str, current_status: str):
        self.month = month
        self.current_status = current_status
        super().__init__(
            f"Месяц {month} недоступен (статус: {current_status})"
        )
