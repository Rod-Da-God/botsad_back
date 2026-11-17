import logging

from fastapi import APIRouter, FastAPI, status

from billboards.router import router as billboards_router
from crm.router import router as crm_router
from geo.router import router as geo_router
from metrics.router import router as metrics_router
from mock.mock_router import router as mock_router
from ws.ws_route import router as ws_router


logger = logging.getLogger(__name__)

health_router = APIRouter()


@health_router.get("/health", status_code=status.HTTP_204_NO_CONTENT)
async def health() -> None:
    """
    Проверка готовности сервиса. Наружу отдаём только статус, без деталей.
    """
    # Сюда добавлять проверки зависимостей (БД, кэш, внешние сервисы).
    # При провале логировать причину и поднимать
    # HTTPException(status_code=503),
    # текст ошибки в ответ не передавать. Пример для БД:
    #     try:
    #         await session.execute(text("SELECT 1"))
    #     except Exception:
    #         logger.exception("Health: БД недоступна")
    #         raise HTTPException(status_code=503)


def get_routers() -> list[APIRouter]:
    """
    Возвращает список маршрутов для подключения к приложению.
    """
    return [
        health_router,
        billboards_router,
        ws_router,
        mock_router,
        geo_router,
        crm_router,
        metrics_router,
    ]


def setup_routers(app: FastAPI) -> None:
    """
    Подключает все маршруты к приложению и логирует их инициализацию.
    """
    for router in get_routers():
        app.include_router(router)
        logger.debug("Init router %s", getattr(router, "prefix", ""))
