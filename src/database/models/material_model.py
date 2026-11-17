from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base, id_field


if TYPE_CHECKING:
    from .billboard_model import BillboardConstruction


class Material(Base):
    """Справочник материалов для производства рекламы"""

    id: Mapped[id_field]
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    price_per_sqm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    billboards: Mapped[list[BillboardConstruction]] = relationship(
        back_populates="material"
    )
