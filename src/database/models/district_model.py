from __future__ import annotations

from typing import TYPE_CHECKING

from geoalchemy2 import Geometry
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base, id_field


if TYPE_CHECKING:
    from .location_model import Location


class District(Base):
    """Районы города с границами для геоанализа"""

    id: Mapped[id_field]
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    boundary: Mapped[str | None] = mapped_column(
        Geometry("POLYGON", srid=4326)
    )

    locations: Mapped[list[Location]] = relationship(back_populates="district")
