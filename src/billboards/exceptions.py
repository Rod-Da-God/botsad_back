class BillboardException(Exception):
    """Базовое исключение для модуля billboards"""

    pass


class BillboardNotFoundError(BillboardException):
    """Билборд не найден"""

    def __init__(self, location_id: int):
        self.location_id = location_id
        super().__init__(f"Билборд с location_id={location_id} не найден")


class InvalidDistrictError(BillboardException):
    """Некорректный район"""

    def __init__(self, district_name: str):
        self.district_name = district_name
        super().__init__(f"Район '{district_name}' не найден")
