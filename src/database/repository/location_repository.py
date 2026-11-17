import logging
from typing import Any

from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from billboards.utils.translit_slug import translit_city
from database.core.connection import connection
from database.models.location_model import Location
from database.repository.postgre_repo import PostgreRepository
from database.schemas.billboard_schemas import LocationCreate


logger = logging.getLogger(__name__)


class LocationRepository(PostgreRepository[Location]):
    model = Location

    @classmethod
    async def get_or_create_by_address(
        cls,
        address: str,
        coords: tuple[float, float],
        city: str,
        street_name: str | None,
        building_number: str | None,
        district_name: str | None,
        district_repo,
        session: AsyncSession | None = None,
    ) -> int:
        """Получить или создать локацию по адресу (thread-safe)."""

        lon, lat = coords

        existing_by_coords = await cls.find_by_coordinates(
            longitude=lon, latitude=lat
        )

        if existing_by_coords:
            logger.debug(
                "Локация найдена по координатам: '%s', ID=%s",
                address,
                existing_by_coords["id"],
            )
            return existing_by_coords["id"]

        class LocationFilter(BaseModel):
            landmark: str

        existing_by_address = await cls.get_one(
            filters=LocationFilter(landmark=address),
        )

        if existing_by_address:
            logger.debug(
                "Локация найдена по адресу: '%s', ID=%s",
                address,
                existing_by_address["id"],
            )
            return existing_by_address["id"]

        district_id = None
        if district_name:
            district_id = await district_repo.get_or_create_by_name(
                name=district_name,
            )

        wkt_geom = f"POINT({lon} {lat})"
        slug_city_value = translit_city(city)

        location_data = LocationCreate(
            district_id=district_id,
            geom=wkt_geom,
            city=city,
            slug_city=slug_city_value,
            street_name=street_name,
            building_number=building_number,
            landmark=address,
        )

        try:
            await cls.create(values=location_data)
            logger.info(f"Локация создана: '{address}'")
        except IntegrityError as e:
            logger.warning(
                f"Race condition при создании локации '{address}': {e}"
            )

        final_location = await cls.find_by_coordinates(
            longitude=lon, latitude=lat
        )

        if final_location:
            return final_location["id"]

        final_by_address = await cls.get_one(
            filters=LocationFilter(landmark=address),
        )

        if final_by_address:
            return final_by_address["id"]

        raise RuntimeError(f"Не удалось найти или создать локацию '{address}'")

    @classmethod
    @connection()
    async def find_by_coordinates(
        cls,
        session: AsyncSession,
        longitude: float,
        latitude: float,
        tolerance: float = 0.001,
    ) -> dict[str, Any] | None:
        """
        Найти локацию по координатам используя PostGIS ST_DWithin.

        Если найдено несколько локаций (дубликаты),
        возвращает ту, у которой минимальный ID.
        """
        point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)

        query = (
            select(Location)
            .where(ST_DWithin(Location.geom, point, tolerance))
            .order_by(Location.id)
            .limit(1)
        )

        logger.debug(
            f"Поиск локации по координатам: lon={longitude}, lat={latitude}"
        )

        result = await session.execute(query)
        location = result.scalar_one_or_none()

        if location:
            logger.debug(f"Локация найдена: ID={location.id}")
            return {
                "id": location.id,
                "district_id": location.district_id,
                "city": location.city,
                "slug_city": location.slug_city,
                "street_name": location.street_name,
                "building_number": location.building_number,
                "landmark": location.landmark,
            }

        logger.debug("Локация не найдена по координатам")
        return None
