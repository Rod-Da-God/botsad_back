import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.param_functions import Query

from external.suggest.exceptions import (
    SuggestAPIError,
    SuggestAuthError,
    SuggestNetworkError,
)

from .dependens import get_suggest_service
from .services.suggest_service import SuggestService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/suggest", tags=["suggest"])


@router.get(
    "/address",
    summary="Подсказки адресов с координатами",
    response_description="Список адресов с lat/lon",
)
async def suggest_address(
    service: Annotated[SuggestService, Depends(get_suggest_service)],
    q: Annotated[str, Query(min_length=2, description="Поисковый запрос")],
    limit: Annotated[
        int, Query(ge=1, le=20, description="Максимум результатов")
    ] = 5,
) -> list[dict[str, str | float]]:
    try:
        return await service.suggest_address(q, count=limit)
    except SuggestAuthError as exc:
        logger.exception(
            "Suggest: authentication failed | query=%s | limit=%s | error=%s",
            q,
            limit,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Address suggestion service: authentication failed",
        ) from exc
    except SuggestAPIError as exc:
        logger.exception(
            "Suggest: external API error | query=%s | limit=%s | error=%s",
            q,
            limit,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Address suggestion service temporarily unavailable",
        ) from exc
    except SuggestNetworkError as exc:
        # warning, а не exc — это внешняя проблема, не наш баг
        logger.warning(
            "Suggest: network issue (timeout/unreachable)"
            " | query=%s | limit=%s | error=%s",
            q,
            limit,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Address suggestion service timeout or unreachable",
        ) from exc
