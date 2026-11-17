"""
Роутер для API billboards.

Обрабатывает запросы и преобразует исключения в HTTP ответы.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from billboards.dependens import get_billboard_service
from billboards.exceptions import BillboardNotFoundError
from billboards.services.billboard_service import BillboardService
from database.schemas.billboard_schemas import (
    BillboardDetailResponse,
    BillboardListResponse,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/banners", tags=["Billboards"])


@router.get(
    "",
    response_model=list[BillboardListResponse],
    status_code=status.HTTP_200_OK,
    summary="Получить список билбордов",
    description=(
        "Возвращает список всех билбордов с группировкой по адресам.\n\n"
        "**Фильтры:**\n"
        "- `city` - фильтр по городу"
        " (если не указан, возвращаются все города)\n\n"
        "**Формат ответа:**\n"
        "- Каждый билборд содержит координаты, адрес, район"
        " и информацию по сторонам\n"
        "- Для каждой стороны указаны статусы по месяцам, цена и фотографии\n"
        "- ID стороны имеет формат `location_id-сторона` (например `42-А`)"
    ),
)
async def get_all_banners(
    billboard_service: Annotated[
        BillboardService, Depends(get_billboard_service)
    ],
    city: Annotated[
        str | None,
        Query(
            description=(
                "Фильтр по городу (если не указан, возвращаются все города)"
            ),
        ),
    ] = None,
) -> list[BillboardListResponse]:
    """
    Получить список всех билбордов.

    Args:
        city: Опциональный фильтр по городу
            (если None, возвращаются все города)
        billboard_service: Сервис билбордов (DI)

    Returns:
        List[BillboardListResponse]: Список билбордов
    """
    logger.info(
        "Запрос списка билбордов, фильтр: city=%s",
        city if city else "все города",
    )

    result = await billboard_service.get_all_billboards(status="", city=city)

    logger.info(f"Возвращено {len(result)} билбордов")
    return result


@router.get(
    "/{location_id}",
    response_model=BillboardDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Получить детальную информацию о билборде",
    description=(
        "Возвращает полную информацию о билборде по ID локации.\n\n"
        "**Включает:**\n"
        "- Адрес, координаты, город и район\n"
        "- Размер конструкции\n"
        "- Детальную информацию по каждой стороне:\n"
        "  - Цены (аренда, монтаж/демонтаж, производство)\n"
        "  - Наличие электричества\n"
        "  - Материал\n"
        "  - Статусы по месяцам\n"
        "  - Фотографии"
    ),
)
async def get_banner_details(
    location_id: int,
    billboard_service: Annotated[
        BillboardService, Depends(get_billboard_service)
    ],
) -> BillboardDetailResponse:
    """
    Получить детальную информацию о билборде.

    Args:
        location_id: ID локации билборда
        billboard_service: Сервис билбордов (DI)

    Returns:
        BillboardDetailResponse: Детальная информация
    """
    try:
        logger.info(f"Запрос деталей билборда location_id={location_id}")

        result = await billboard_service.get_billboard_details(location_id)

        logger.info(f"Детали билборда location_id={location_id} возвращены")
        return result

    except BillboardNotFoundError as e:
        logger.warning(f"Билборд не найден: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Билборд с ID {location_id} не найден",
        ) from e


# @router.get(
#     "/district/{district_name}",
#     response_model=List[int],
#     status_code=status.HTTP_200_OK,
#     summary="Получить билборды района",
#     description=(
#         "Возвращает список ID локаций билбордов в указанном районе.\n\n"
#         "**Параметры:**\n"
#         "- `district_name` - название района (например 'Индустриальный')\n\n"
#         "**Возвращает:**\n"
#         "- Массив location_id билбордов, находящихся в районе"
#     ),
# )
# async def get_banners_by_district(
#     district_name: str,
#     billboard_service: BillboardService = Depends(get_billboard_service),
# ) -> List[int]:
#     """
#     Получить билборды в районе.

#     Args:
#         district_name: Название района
#         billboard_service: Сервис билбордов (DI)

#     Returns:
#         List[int]: Список location_id
#     """
#     try:
#         logger.info(f"Запрос билбордов для района '{district_name}'")

#         result = await billboard_service.get_billboards_by_district(
#             district_name
#         )

#         logger.info(
#             f"Найдено {len(result)} билбордов в районе '{district_name}'"
#         )
#         return result

#     except InvalidDistrictError as e:
#         logger.warning(f"Район не найден: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail=f"Район '{district_name}' не найден",
#         )
