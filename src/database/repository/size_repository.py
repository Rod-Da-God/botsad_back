import logging
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.size_model import Size
from database.repository.postgre_repo import PostgreRepository
from database.schemas.billboard_schemas import SizeCreate


logger = logging.getLogger(__name__)


class SizeRepository(PostgreRepository[Size]):
    model = Size

    @classmethod
    async def get_or_create_by_dimensions(
        cls,
        width: Decimal,
        height: Decimal,
        session: AsyncSession | None = None,
    ) -> int:
        size_filter = SizeCreate(width=width, height=height)

        existing = await cls.get_one(filters=size_filter)

        if existing:
            return existing["id"]

        await cls.create(values=size_filter)
        logger.debug(f"Размер создан: {width}x{height}")

        new_size = await cls.get_one(filters=size_filter)
        return new_size["id"]
