import logging

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.material_model import Material
from database.repository.postgre_repo import PostgreRepository
from database.schemas.billboard_schemas import MaterialCreate


logger = logging.getLogger(__name__)


class MaterialRepository(PostgreRepository[Material]):
    model = Material

    @classmethod
    async def get_or_create_by_name(
        cls,
        name: str,
        session: AsyncSession | None = None,
    ) -> int:
        """Получить или создать материал по названию."""

        material_data = MaterialCreate(name=name, price_per_sqm=None)
        normalized_name = material_data.name

        class MaterialFilter(BaseModel):
            name: str

        material_filter = MaterialFilter(name=normalized_name)
        existing = await cls.get_one(filters=material_filter)

        if existing:
            return existing["id"]

        await cls.create(values=material_data)
        logger.debug(f"Материал создан: '{normalized_name}'")

        new_material = await cls.get_one(filters=material_filter)
        return new_material["id"]
