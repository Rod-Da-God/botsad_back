import logging

from billboards.exceptions import BillboardNotFoundError
from billboards.utils.billboard_group import group_by_location
from billboards.utils.responce_builder import (
    build_detail_response,
    build_list_response,
)
from billboards.utils.translit_slug import translit_city
from database.repository import BillboardRepository
from database.schemas.billboard_schemas import (
    BillboardDetailResponse,
    BillboardListResponse,
)
from external.cache.cache import Cache


logger = logging.getLogger(__name__)


class BillboardService:
    """
    Сервис для работы с билбордами.
    """

    async def get_all_billboards(
        self, status: str | None = None, city: str | None = None
    ) -> list[BillboardListResponse]:
        """
        Получить все билборды с группировкой по локациям.

        Args:
            city: Опциональный фильтр по городу
                (если None, возвращаются все города)

        Returns:
            List[BillboardListResponse]: Список билбордов
        """

        if not status and not city:
            cached = await Cache.get_all_billboards()
            if cached:
                logger.debug(f"Возвращено {len(cached)} билбордов из кеша")
                return [BillboardListResponse(**item) for item in cached]

        if city:
            city_slug = translit_city(city)
            cached_by_city = await Cache.get_billboards_by_city(city_slug)
            if cached_by_city:
                logger.debug(
                    "Возвращено %d билбордов из кеша для города %s (slug: %s)",
                    len(cached_by_city),
                    city,
                    city_slug,
                )
                return [
                    BillboardListResponse(**item) for item in cached_by_city
                ]
        logger.info(
            "Получение всех билбордов: status=%s, city=%s",
            status,
            city if city else "все города",
        )

        raw_data = await BillboardRepository.get_grouped_billboards(
            status=status, city=city
        )

        logger.debug(f"Получено {len(raw_data)} записей из БД")

        grouped = group_by_location(raw_data)

        result = []
        for location_id, sides_data in grouped.items():
            billboard_response = build_list_response(location_id, sides_data)
            result.append(billboard_response)

        logger.info(f"Сформировано {len(result)} билбордов")
        return result

    async def get_billboard_details(
        self, location_id: int
    ) -> BillboardDetailResponse:
        """
        Получить детальную информацию о билборде.

        Args:
            location_id: ID локации

        Returns:
            BillboardDetailResponse: Детальная информация

        Raises:
            BillboardNotFoundError: Если билборд не найден
        """
        logger.info(f"Получение деталей билборда location_id={location_id}")

        raw_data = await BillboardRepository.get_billboard_full_info(
            location_id=location_id
        )

        if not raw_data:
            logger.warning(f"Билборд location_id={location_id} не найден")
            raise BillboardNotFoundError(location_id)

        logger.debug(
            f"Получено {len(raw_data)} сторон для location_id={location_id}"
        )

        response = build_detail_response(location_id, raw_data)

        logger.info(f"Детали билборда location_id={location_id} сформированы")
        return response
