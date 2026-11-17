from __future__ import annotations

from typing import TYPE_CHECKING

from geoalchemy2 import Geometry
from sqlalchemy import ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base, id_field


if TYPE_CHECKING:
    from .billboard_model import BillboardConstruction
    from .district_model import District


class Location(Base):
    """Адреса размещения билбордов с географическими координатами"""

    id: Mapped[id_field]
    district_id: Mapped[int | None] = mapped_column(
        ForeignKey("districts.id", ondelete="SET NULL")
    )

    geom: Mapped[str] = mapped_column(
        Geometry("POINT", srid=4326), nullable=False, index=True
    )

    city: Mapped[str] = mapped_column(
        String(100),
        server_default="Хабаровск",
        nullable=True,
        index=True,
        comment="Город размещения билборда",
    )

    slug_city: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
        index=True,
        comment="Транслитерированное название города для URL",
    )

    street_name: Mapped[str | None] = mapped_column(String(200))
    building_number: Mapped[str | None] = mapped_column(String(20))
    landmark: Mapped[str | None] = mapped_column(Text)

    district: Mapped[District | None] = relationship(
        back_populates="locations"
    )
    billboards: Mapped[list[BillboardConstruction]] = relationship(
        back_populates="location", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index(
            "idx_locations_unique_coords",
            func.round(func.ST_X(func.cast(geom, Geometry)).cast(Numeric), 6),
            func.round(func.ST_Y(func.cast(geom, Geometry)).cast(Numeric), 6),
            unique=True,
        ),
    )
