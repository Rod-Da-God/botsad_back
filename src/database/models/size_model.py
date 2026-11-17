from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Computed, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base, id_field


if TYPE_CHECKING:
    from .billboard_model import BillboardConstruction


class Size(Base):
    """Справочник размеров билбордов"""

    id: Mapped[id_field]
    width: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    height: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    area: Mapped[Decimal | None] = mapped_column(
        Numeric(7, 2), Computed("(width * height)")
    )

    billboards: Mapped[list[BillboardConstruction]] = relationship(
        back_populates="size"
    )

    __table_args__ = (
        UniqueConstraint("width", "height", name="unique_width_height"),
    )
