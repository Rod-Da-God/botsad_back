import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from crm.depends import cleanup_crm_clients, get_crm_sync_service
from database.core.connection import init_db
from exc_handler import setup_exception_handlers
from external.api.api_registry import api_registry
from external.cache.cache import Cache
from metrics.db import analytics_db
from middleware import setup_middlewares
from routers import setup_routers
from ws.broadcast import Broadcast


logger = logging.getLogger(__name__)


async def startup() -> None:
    logger.info("START Application")

    await init_db(use_create_all=True)

    await Broadcast.setup_broadcast()
    await Cache.init()
    await analytics_db.init()
    await api_registry.startup()

    # Полная синхронизация с Bitrix24 не должна блокировать старт API:
    # при недоступном портале сервис поднимается и продолжает работать,
    # а данные догружаются по входящим вебхукам.
    crm_service = get_crm_sync_service()
    try:
        await crm_service.load_all_constructions()
    except Exception:
        logger.exception(
            "Не удалось загрузить конструкции при старте, "
            "продолжаем работу без полной синхронизации"
        )

    logger.info("START Completed")


async def shutdown() -> None:
    await Cache.close()
    await analytics_db.close()
    await api_registry.shutdown()
    await cleanup_crm_clients()
    logger.info("FINISH Application")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.registry = api_registry
    await startup()
    yield
    await shutdown()


def create_app() -> FastAPI:
    """
    Фабрика приложения. Модуль импортируется uvicorn-ом после setup_tracing(),
    поэтому FastAPI и SQLAlchemy здесь уже инструментированы.
    """
    app = FastAPI(lifespan=lifespan, redirect_slashes=False)
    setup_routers(app=app)
    setup_exception_handlers(app=app)
    setup_middlewares(app=app)
    return app
