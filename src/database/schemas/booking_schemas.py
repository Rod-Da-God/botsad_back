from decimal import Decimal
from typing import Annotated

import phonenumbers
from pydantic import BaseModel, Field, field_validator
from pydantic_extra_types.phone_numbers import PhoneNumberValidator

from crm.utils.crm_utils.month_utils import (
    validate_booking_months,
)


RussianPhoneNumber = Annotated[
    str | phonenumbers.PhoneNumber,
    PhoneNumberValidator(
        default_region="RU", number_format="E164", supported_regions=["RU"]
    ),
]


class BookingCreate(BaseModel):
    """Схема для создания бронирования с динамической валидацией месяцев"""

    billboard_id: str = Field(
        ..., description="ID конкретной стороны билборда"
    )
    months: list[str] = Field(
        ...,
        description="Список месяцев для бронирования в формате YYYY-MM",
        examples=[["2025-11", "2025-12"]],
    )

    client_name: str = Field(
        ..., min_length=2, max_length=200, description="ФИО клиента"
    )
    client_phone: RussianPhoneNumber = Field(
        ..., description="Телефон клиента"
    )

    company: str | None = Field(
        None, max_length=300, description="Название компании клиента"
    )

    selected_services: list[str] = Field(
        default_factory=list,
        description="Список выбранных дополнительных услуг",
        examples=[["installationDemounting", "manufacturing"]],
    )

    @field_validator("billboard_id")
    @classmethod
    def validate_billboard_id(cls, v: str) -> str:
        """Валидация составного ID формата 'location_id-сторона'"""
        parts = v.split("-")

        if len(parts) != 2:
            raise ValueError(
                "billboard_id должен быть в формате"
                " 'location_id-сторона' (например '42-А')"
            )

        location_id_str, side = parts

        try:
            int(location_id_str)
        except ValueError as err:
            raise ValueError(
                "Некорректный location_id в billboard_id:"
                f" '{location_id_str}' не является числом"
            ) from err

        if side not in ["А", "Б", "В"]:
            raise ValueError(
                f"Некорректная сторона в billboard_id: '{side}'."
                " Допустимы: А, Б, В"
            )

        return v

    @field_validator("client_name")
    @classmethod
    def validate_client_name(cls, v: str) -> str:
        """Валидация ФИО: минимум 2 слова"""
        stripped = v.strip()
        parts = stripped.split()

        if len(parts) < 2:
            raise ValueError(
                "ФИО должно содержать минимум 2 слова"
                " (Имя Фамилия или Фамилия Имя)"
            )

        if not all(word.replace("-", "").isalpha() for word in parts):
            raise ValueError(
                "ФИО должно содержать только буквы, пробелы и дефисы"
            )

        return stripped

    @field_validator("months")
    @classmethod
    def validate_months(cls, v: list[str]) -> list[str]:
        """Динамическая валидация месяцев на основе текущей даты"""
        if not v:
            raise ValueError("Необходимо указать хотя бы один месяц")

        if len(v) != len(set(v)):
            raise ValueError("Месяцы не должны повторяться")

        try:
            return validate_booking_months(v)
        except ValueError as e:
            raise ValueError(str(e)) from e

    @field_validator("selected_services")
    @classmethod
    def validate_selected_services(cls, v: list[str]) -> list[str]:
        """Валидация списка услуг"""
        allowed_services = {"installationDemounting", "manufacturing"}

        for service in v:
            if service not in allowed_services:
                raise ValueError(
                    f"Недопустимая услуга: '{service}'."
                    f" Допустимы: {', '.join(allowed_services)}"
                )

        return list(set(v))

    @property
    def include_mounting(self) -> bool:
        """Для обратной совместимости"""
        return "installationDemounting" in self.selected_services

    @property
    def include_printing(self) -> bool:
        """Для обратной совместимости"""
        return "manufacturing" in self.selected_services


class BookingResponse(BaseModel):
    """Ответ на создание бронирования"""

    success: bool
    message: str
    billboard_id: str
    booked_months: list[str]

    address: str
    side: str
    size: str

    rental_price: Decimal = Field(description="Цена аренды за все месяцы")

    mounting_price: Decimal | None = Field(
        None, description="Стоимость монтажа/демонтажа"
    )
    printing_price: Decimal | None = Field(
        None, description="Стоимость печати"
    )
    total_price: Decimal = Field(
        description="Общая стоимость (аренда + услуги)"
    )

    bitrix_lead_id: int | None = Field(
        None, description="ID созданного лида в Bitrix24"
    )


class BillboardStatusUpdate(BaseModel):
    """Схема для обновления статусов месяцев билборда"""

    status_month1: str | None = None
    status_month2: str | None = None
    status_month3: str | None = None
    status_month4: str | None = None
    status_month5: str | None = None
    status_month6: str | None = None

    @field_validator(
        "status_month1",
        "status_month2",
        "status_month3",
        "status_month4",
        "status_month5",
        "status_month6",
    )
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in ("свободно", "занято", "резерв"):
            raise ValueError(f"Недопустимый статус: {v}")
        return v
