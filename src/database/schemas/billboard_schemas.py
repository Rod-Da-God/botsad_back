import re
from decimal import Decimal

from pydantic import BaseModel, Field, field_serializer, field_validator


class SizeCreate(BaseModel):
    """Схема для создания размера с парсингом строк"""

    width: Decimal = Field(gt=0, description="Ширина в метрах")
    height: Decimal = Field(gt=0, description="Высота в метрах")

    @field_validator("width", "height", mode="before")
    @classmethod
    def parse_dimension(cls, v) -> Decimal:
        """
        Парсит размеры
        """
        if isinstance(v, (int, float, Decimal)):
            return Decimal(str(v))

        if isinstance(v, str):
            v = v.replace(",", ".")
            return Decimal(v)

        return Decimal(str(v))

    @classmethod
    def from_size_string(cls, size_str: str) -> "SizeCreate":
        """
        Создать размер из строки формата "6x3", "6х3", "6*3" и т.д.

        Поддерживает разделители: x, X, х (русская), ×, *
        Поддерживает как точку, так и запятую для десятичных чисел.

        Args:
            size_str: Строка размера типа "6x3", "6,0х3,0", "6*3"

        Returns:
            SizeCreate: Экземпляр с распарсенными размерами
        """
        size_normalized = (
            size_str.replace("х", "*")
            .replace("X", "*")
            .replace("x", "*")
            .replace("×", "*")
            .replace(",", ".")
        )

        match = re.search(r"(\d+\.?\d*)\s*\*\s*(\d+\.?\d*)", size_normalized)

        if not match:
            return cls(width=Decimal("0"), height=Decimal("0"))

        width = Decimal(match.group(1))
        height = Decimal(match.group(2))

        return cls(width=width, height=height)


class MaterialCreate(BaseModel):
    """Схема для создания материала"""

    name: str = Field(min_length=1, max_length=100)
    price_per_sqm: Decimal | None = Field(None, ge=0)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_material_name(cls, v: str) -> str:
        """
        Нормализует название материала: капитализирует первую букву.
        """
        if not v:
            return ""

        return v.capitalize()


class LocationCreate(BaseModel):
    """Схема для создания локации"""

    district_id: int | None = None
    geom: str = Field(description="WKT формат: POINT(longitude latitude)")
    city: str = Field(
        default="Хабаровск",
        min_length=1,
        max_length=100,
        description="Город размещения",
    )
    slug_city: str | None = Field(
        None, max_length=150, description="Транслитерированное название города"
    )
    street_name: str | None = Field(None, max_length=200)
    building_number: str | None = Field(None, max_length=20)
    landmark: str | None = None


class DistrictCreate(BaseModel):
    name: str
    boundary: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_district_name(cls, v: str) -> str:
        """
        Нормализует название района: убирает " район" в конце.
        """
        if not v:
            return ""

        normalized = v.strip()

        if normalized.lower().endswith(" район"):
            normalized = normalized[:-6].strip()

        return normalized


class BillboardCreate(BaseModel):
    """Схема для создания конструкции с динамическими месяцами"""

    bitrix_id: int | None = Field(
        None, description="ID конструкции в Bitrix24"
    )
    location_id: int
    size_id: int
    material_id: int | None = None
    side: str = Field(pattern=r"^[АБВГ]$")
    has_lighting: bool = False

    status: str = Field(
        default="свободно", pattern=r"^(свободно|занято|резерв)$"
    )

    status_month1: str = Field(
        default="свободно", pattern=r"^(свободно|занято|резерв)$"
    )
    status_month2: str = Field(
        default="свободно", pattern=r"^(свободно|занято|резерв)$"
    )
    status_month3: str = Field(
        default="свободно", pattern=r"^(свободно|занято|резерв)$"
    )
    status_month4: str = Field(
        default="свободно", pattern=r"^(свободно|занято|резерв)$"
    )
    status_month5: str = Field(
        default="свободно", pattern=r"^(свободно|занято|резерв)$"
    )
    status_month6: str = Field(
        default="свободно", pattern=r"^(свободно|занято|резерв)$"
    )

    photo_url: str | None = None

    rental_price: Decimal = Field(ge=0)
    mounting_price: Decimal = Field(ge=0)
    production_price: Decimal = Field(ge=0)

    @field_validator("side")
    @classmethod
    def validate_side(cls, v: str) -> str:
        return v.upper()

    @field_validator(
        "rental_price", "mounting_price", "production_price", mode="before"
    )
    @classmethod
    def parse_price_fields(cls, v) -> Decimal:
        """Парсит цены из различных форматов"""
        if v is None or v == "":
            return Decimal("0")

        if isinstance(v, (int, float, Decimal)):
            return Decimal(str(v))

        v_str = str(v).strip()

        if "|" in v_str:
            price_part = v_str.split("|")[0].strip()
        else:
            price_part = v_str

        try:
            return Decimal(price_part)
        except Exception:
            return Decimal("0")


class SideBasicInfo(BaseModel):
    """Базовая информация о стороне для списка /banners/"""

    id: str = Field(
        description="Составной ID: location_id-сторона (например '1-A')"
    )
    price: float = Field(description="Цена аренды")
    installationDemounting: float = Field(description="Монтаж/Демонтаж")
    manufacturing: float = Field(description="Производство")
    images: list[str] = Field(
        default_factory=list, description="URL фотографий"
    )
    statuses: dict[str, str] = Field(description="Статусы по месяцам")

    @field_serializer("statuses")
    def capitalize_statuses(self, statuses: dict[str, str]) -> dict[str, str]:
        """Капитализирует значения статусов при сериализации"""
        return {
            month: status.capitalize() for month, status in statuses.items()
        }


class SideDetailedInfo(BaseModel):
    """Детальная информация о стороне для /banners/{id}"""

    id: str = Field(description="Составной ID: location_id-сторона")
    price: float = Field(description="Цена аренды")
    images: list[str] = Field(
        default_factory=list, description="URL фотографий"
    )

    hasElectricity: bool = Field(description="Наличие подсветки")
    installationDemounting: float = Field(description="Монтаж/Демонтаж")
    manufacturing: float = Field(description="Производство")
    material: str | None = Field(None, description="Материал")

    statuses: dict[str, str] = Field(description="Статусы по месяцам")

    @field_serializer("statuses")
    def capitalize_statuses(self, statuses: dict[str, str]) -> dict[str, str]:
        """Капитализирует значения статусов при сериализации"""
        return {
            month: status.capitalize() for month, status in statuses.items()
        }


class BillboardListResponse(BaseModel):
    """Ответ для списка билбордов /banners/"""

    id: int = Field(description="ID локации")
    slug: str = Field(description="хуйня для сео")
    slug_city: str | None = Field(
        None, description="Транслитерированный город"
    )
    coordinates: list[float] = Field(description="[longitude, latitude]")
    address: str = Field(description="Адрес")
    city: str = Field(description="Город")
    district: str | None = Field(None, description="Район города")
    constructionType: str = Field(
        description="Размер конструкции (например '6,0x3,0')"
    )
    sides: dict[str, SideBasicInfo] = Field(
        description="Информация по сторонам"
    )

    @field_serializer("constructionType")
    def format_construction_type_with_comma(self, v: str) -> str:
        """
        Форматирует размер конструкции с запятой вместо точки.
        Например: "6.0x3.0" -> "6,0x3,0"
        """
        return v.replace(".", ",")


class BillboardDetailResponse(BaseModel):
    """Детальная информация о билборде /banners/{id}"""

    id: int = Field(description="ID локации")
    coordinates: list[float] = Field(description="[longitude, latitude]")
    address: str = Field(description="Адрес")
    slug: str = Field(description="хуйня для сео")
    slug_city: str | None = Field(
        None, description="Транслитерированный город"
    )
    constructionType: str = Field(
        description="Размер конструкции (например '6,0x3,0')"
    )

    city: str = Field(description="Город")
    district: str | None = Field(None, description="Район города")

    sides: dict[str, SideDetailedInfo] = Field(
        description="Детальная информация по сторонам"
    )

    @field_serializer("constructionType")
    def format_construction_type_with_comma(self, v: str) -> str:
        """
        Форматирует размер конструкции с запятой вместо точки.
        Например: "6.0x3.0" -> "6,0x3,0"
        """
        return v.replace(".", ",")


class BillboardUpdate(BaseModel):
    """Схема для обновления билборда с динамическими месяцами"""

    bitrix_id: int | None = None
    size_id: int
    material_id: int | None
    has_lighting: bool
    status: str
    status_month1: str
    status_month2: str
    status_month3: str
    status_month4: str
    status_month5: str
    status_month6: str
    photo_url: str
    rental_price: Decimal
    mounting_price: Decimal
    production_price: Decimal

    @field_validator(
        "rental_price", "mounting_price", "production_price", mode="before"
    )
    @classmethod
    def parse_price_fields(cls, v) -> Decimal:
        """Парсит цены из различных форматов"""
        if v is None or v == "":
            return Decimal("0")

        if isinstance(v, (int, float, Decimal)):
            return Decimal(str(v))

        v_str = str(v).strip()

        if "|" in v_str:
            price_part = v_str.split("|")[0].strip()
        else:
            price_part = v_str

        return Decimal(price_part)


class BillboardStatusUpdate(BaseModel):
    """Схема для обновления статусов месяцев"""

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
