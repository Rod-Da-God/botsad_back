from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base, id_field


if TYPE_CHECKING:
    from .location_model import Location
    from .material_model import Material
    from .size_model import Size


class BillboardConstruction(Base):
    """Рекламные конструкции с динамическими месяцами бронирования"""

    id: Mapped[id_field]

    bitrix_id: Mapped[int | None] = mapped_column(
        Integer, unique=True, nullable=True, index=True
    )
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"), nullable=False
    )
    size_id: Mapped[int] = mapped_column(
        ForeignKey("sizes.id", ondelete="RESTRICT"), nullable=False
    )
    material_id: Mapped[int | None] = mapped_column(
        ForeignKey("materials.id", ondelete="SET NULL")
    )

    side: Mapped[str] = mapped_column(String(1), nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), default="свободно", index=True
    )

    status_month1: Mapped[str] = mapped_column(String(20), default="свободно")
    status_month2: Mapped[str] = mapped_column(String(20), default="свободно")
    status_month3: Mapped[str] = mapped_column(String(20), default="свободно")
    status_month4: Mapped[str] = mapped_column(String(20), default="свободно")
    status_month5: Mapped[str] = mapped_column(String(20), default="свободно")
    status_month6: Mapped[str] = mapped_column(String(20), default="свободно")

    has_lighting: Mapped[bool] = mapped_column(Boolean, default=False)

    photo_url: Mapped[str | None] = mapped_column(Text)

    rental_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    mounting_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    production_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )

    location: Mapped[Location] = relationship(back_populates="billboards")
    size: Mapped[Size] = relationship(back_populates="billboards")
    material: Mapped[Material | None] = relationship(
        back_populates="billboards"
    )

    __table_args__ = (
        CheckConstraint("side IN ('А', 'Б', 'В', 'Г')", name="check_side"),
        CheckConstraint(
            "status IN ('свободно', 'занято', 'резерв')", name="check_status"
        ),
        UniqueConstraint("location_id", "side", name="unique_location_side"),
    )
