import logging
from typing import Any

from database.schemas.billboard_schemas import BillboardListResponse
from external.cache.cache import Cache


logger = logging.getLogger(__name__)


async def rebuild_and_cache_billboards(
    billboard_repository,
    group_by_location_func,
    build_list_response_func,
    status: str | None = None,
    city: str | None = None,
) -> None:
    """
    Получает баннеры из БД, группирует и кеширует их.

    Args:
        billboard_repository: Репозиторий для получения данных из БД
        group_by_location_func: Функция группировки по локациям
        build_list_response_func: Функция построения ответа
        city: Фильтр по городу (опционально)
    """

    logger.info("Начало кеширования загруженных баннеров")

    raw_data = await billboard_repository.get_grouped_billboards(
        status=status, city=city
    )
    grouped_data = group_by_location_func(raw_data)

    billboards = []
    for location_id, sides_data in grouped_data.items():
        billboard_response = build_list_response_func(location_id, sides_data)
        billboards.append(billboard_response)

    await cache_all_billboards(billboards)
    logger.info(f"Успешно закешировано {len(billboards)} баннеров")


async def cache_all_billboards(
    billboards: list[BillboardListResponse],
) -> None:
    """
    Кеширует все баннеры после загрузки из Битрикса.

    Args:
        billboards: Список баннеров в формате BillboardListResponse
    """

    logger.info(f"Начало кеширования {len(billboards)} баннеров")

    for billboard in billboards:
        billboard_dict = billboard.model_dump(mode="json")
        await Cache.add_billboard(billboard_dict)

    logger.info(f"Успешно закешировано {len(billboards)} баннеров")


async def get_billboards_from_cache() -> list[dict[str, Any]]:
    """
    Получить все баннеры из кеша.

    Returns:
        List[Dict[str, Any]]: Список баннеров из кеша или пустой список
    """

    billboards = await Cache.get_all_billboards()
    logger.debug(f"Получено {len(billboards)} баннеров из кеша")
    return billboards


async def parse_cached_billboards(
    cached_data: list[dict[str, Any]],
) -> list[BillboardListResponse]:
    """
    Преобразует данные из кеша в список BillboardListResponse.

    Args:
        cached_data: Данные из кеша

    Returns:
        List[BillboardListResponse]: Список баннеров
    """

    return [BillboardListResponse(**item) for item in cached_data]
