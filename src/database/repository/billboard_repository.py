import logging
from typing import Any

from geoalchemy2 import Geometry
from geoalchemy2.functions import ST_X, ST_Y
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.core.connection import connection
from database.models.billboard_model import BillboardConstruction
from database.models.district_model import District
from database.models.location_model import Location
from database.models.material_model import Material
from database.models.size_model import Size
from database.repository.postgre_repo import PostgreRepository


logger = logging.getLogger(__name__)


class BillboardRepository(PostgreRepository[BillboardConstruction]):
    model = BillboardConstruction

    @classmethod
    @connection()
    async def get_grouped_billboards(
        cls,
        session: AsyncSession,
        status: str | None = None,
        city: str | None = None,
    ) -> list[dict[str, Any]]:
        """Получить все конструкции с группировкой по адресам"""
        longitude = ST_X(func.cast(Location.geom, Geometry)).label("longitude")
        latitude = ST_Y(func.cast(Location.geom, Geometry)).label("latitude")

        query = (
            select(
                Location.id.label("location_id"),
                Location.city,
                Location.slug_city,
                Location.landmark,
                Location.street_name,
                Location.building_number,
                Size.width.label("width"),
                Size.height.label("height"),
                BillboardConstruction.rental_price.label("price"),
                BillboardConstruction.mounting_price,
                BillboardConstruction.production_price,
                BillboardConstruction.side,
                BillboardConstruction.photo_url,
                BillboardConstruction.status_month1,
                BillboardConstruction.status_month2,
                BillboardConstruction.status_month3,
                BillboardConstruction.status_month4,
                BillboardConstruction.status_month5,
                BillboardConstruction.status_month6,
                District.name.label("district_name"),
                longitude,
                latitude,
            )
            .select_from(BillboardConstruction)
            .join(Location, BillboardConstruction.location_id == Location.id)
            .join(Size, BillboardConstruction.size_id == Size.id)
            .outerjoin(District, Location.district_id == District.id)
        )

        if status:
            query = query.where(
                or_(
                    BillboardConstruction.status_month1 == status,
                    BillboardConstruction.status_month2 == status,
                    BillboardConstruction.status_month3 == status,
                    BillboardConstruction.status_month4 == status,
                    BillboardConstruction.status_month5 == status,
                    BillboardConstruction.status_month6 == status,
                )
            )
            logger.debug(f"Применен фильтр по статусу: '{status}'")

        if city:
            query = query.where(Location.city == city)
            logger.debug(f"Применен фильтр по городу: '{city}'")

        query = query.order_by(Location.id, BillboardConstruction.side)

        result = await session.execute(query)
        rows = result.mappings().all()
        results = [dict(row) for row in rows]

        logger.info(f"Найдено {len(results)} конструкций в БД")
        return results

    @classmethod
    @connection()
    async def get_billboard_full_info(
        cls, location_id: int, session: AsyncSession
    ) -> list[dict[str, Any]] | None:
        """Получить полную информацию о билборде"""
        longitude = ST_X(func.cast(Location.geom, Geometry)).label("longitude")
        latitude = ST_Y(func.cast(Location.geom, Geometry)).label("latitude")

        query = (
            select(
                Location.id.label("location_id"),
                Location.street_name,
                Location.building_number,
                Location.landmark,
                Location.city,
                Location.slug_city,
                longitude,
                latitude,
                District.id.label("district_id"),
                District.name.label("district_name"),
                BillboardConstruction.id.label("billboard_id"),
                BillboardConstruction.side,
                BillboardConstruction.status,
                BillboardConstruction.status_month1,
                BillboardConstruction.status_month2,
                BillboardConstruction.status_month3,
                BillboardConstruction.status_month4,
                BillboardConstruction.status_month5,
                BillboardConstruction.status_month6,
                BillboardConstruction.has_lighting,
                BillboardConstruction.photo_url,
                BillboardConstruction.rental_price,
                BillboardConstruction.mounting_price,
                BillboardConstruction.production_price,
                Size.id.label("size_id"),
                Size.width,
                Size.height,
                Size.area,
                Material.id.label("material_id"),
                Material.name.label("material_name"),
                Material.price_per_sqm.label("material_price_per_sqm"),
            )
            .select_from(Location)
            .outerjoin(District, Location.district_id == District.id)
            .join(
                BillboardConstruction,
                BillboardConstruction.location_id == Location.id,
            )
            .join(Size, BillboardConstruction.size_id == Size.id)
            .outerjoin(
                Material, BillboardConstruction.material_id == Material.id
            )
            .where(Location.id == location_id)
            .order_by(BillboardConstruction.side)
        )

        result = await session.execute(query)
        rows = result.mappings().all()
        results = [dict(row) for row in rows]

        if not results:
            logger.warning(f"Билборд с location_id={location_id} не найден")
            return None

        logger.info(
            f"Найдено {len(results)} сторон для location_id={location_id}"
        )
        return results

    @classmethod
    async def find_by_address_and_side(
        cls,
        address: str,
        side: str,
        location_repo,
    ) -> dict | None:
        """Найти билборд по адресу и стороне."""

        class LocationFilter(BaseModel):
            landmark: str

        location = await location_repo.get_one(
            filters=LocationFilter(landmark=address),
        )

        if not location:
            return None

        class BillboardFilter(BaseModel):
            location_id: int
            side: str

        billboard = await cls.get_one(
            filters=BillboardFilter(location_id=location["id"], side=side),
        )
        return billboard

    @classmethod
    async def create_and_return_id(
        cls,
        values: Any,
        session: AsyncSession | None = None,
    ) -> int:
        """
        Создать билборд и вернуть его ID.
        Защищен от race condition с unique_location_side constraint.
        """
        try:
            await cls.create(values=values)
            logger.debug(
                "Билборд создан: location_id=%s, сторона=%s",
                values.location_id,
                values.side,
            )
        except IntegrityError as e:
            if "unique_location_side" in str(e):
                logger.warning(
                    "Race condition при создании:"
                    " location_id=%s, side=%s уже существует."
                    " Получаем существующий билборд.",
                    values.location_id,
                    values.side,
                )
            else:
                raise

        class BillboardFilter(BaseModel):
            location_id: int
            side: str

        created = await cls.get_one(
            filters=BillboardFilter(
                location_id=values.location_id, side=values.side
            ),
        )

        if not created:
            raise RuntimeError(
                f"Не удалось создать или получить билборд: "
                f"location_id={values.location_id}, side={values.side}"
            )

        logger.info(
            f"Билборд получен: ID={created['id']}, "
            f"location_id={values.location_id}, сторона={values.side}"
        )
        return created["id"]

    @classmethod
    async def find_by_bitrix_id_or_address(
        cls,
        bitrix_id: int,
        address: str,
        side: str,
        location_repo,
    ) -> dict[str, Any] | None:
        """
        Найти билборд по bitrix_id или по адресу+сторона (fallback).

        Args:
            bitrix_id: ID в Bitrix24
            address: Адрес локации
            side: Сторона конструкции
            location_repo: Репозиторий локаций

        Returns:
            Dict с данными билборда или None
        """

        class BitrixIdFilter(BaseModel):
            bitrix_id: int

        billboard = await cls.get_one(
            filters=BitrixIdFilter(bitrix_id=bitrix_id),
        )
        if billboard:
            logger.debug(
                "Билборд найден по bitrix_id=%s, ID=%s",
                bitrix_id,
                billboard["id"],
            )
            return billboard

        billboard = await cls.find_by_address_and_side(
            address=address,
            side=side,
            location_repo=location_repo,
        )

        if billboard:
            logger.debug(
                f"Билборд найден по адресу+сторона, ID={billboard['id']}"
            )

        return billboard
