import logging

from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.district_model import District
from database.repository.postgre_repo import PostgreRepository
from database.schemas.billboard_schemas import DistrictCreate


logger = logging.getLogger(__name__)


class DistrictRepository(PostgreRepository[District]):
    model = District

    @classmethod
    async def get_or_create_by_name(
        cls,
        name: str,
        session: AsyncSession | None = None,
    ) -> int:
        """Получить или создать район по названию (thread-safe)."""

        district_data = DistrictCreate(name=name, boundary=None)
        normalized_name = district_data.name

        class DistrictFilter(BaseModel):
            name: str

        district_filter = DistrictFilter(name=normalized_name)

        existing = await cls.get_one(filters=district_filter)
        if existing:
            logger.debug(
                f"Район найден: '{normalized_name}', ID={existing['id']}"
            )
            return existing["id"]

        try:
            await cls.create(values=district_data)
            logger.debug(f"Район создан: '{normalized_name}'")
        except IntegrityError as e:
            logger.debug(
                "Район '%s' уже существует (создан другим потоком): %s",
                normalized_name,
                e,
            )

        new_district = await cls.get_one(filters=district_filter)

        if not new_district:
            raise RuntimeError(
                f"Не удалось найти или создать район '{normalized_name}'"
            )

        logger.debug(
            f"Район получен: '{normalized_name}', ID={new_district['id']}"
        )
        return new_district["id"]
