import importlib
import logging
import pathlib

from .handler import WebhookEventHandler


logger = logging.getLogger(__name__)


HANDLERS_REGISTRY: dict[str, type[WebhookEventHandler]] = {}


def register_handler(event_name: str):
    """
    Декоратор для автоматической регистрации обработчиков.

    Использование:
        @register_handler("ONCRMDYNAMICITEMADD")
        class CreateEventHandler(WebhookEventHandler):
            ...

    Args:
        event_name: Название события Bitrix24 (например, "ONCRMDYNAMICITEMADD")
    """

    def decorator(
        handler_class: type[WebhookEventHandler],
    ) -> type[WebhookEventHandler]:
        if not issubclass(handler_class, WebhookEventHandler):
            raise TypeError(
                f"Класс {handler_class.__name__} должен наследоваться"
                " от WebhookEventHandler"
            )

        if event_name in HANDLERS_REGISTRY:
            logger.warning(
                f"Обработчик для {event_name} уже существует. Перезаписываем."
            )

        HANDLERS_REGISTRY[event_name] = handler_class
        logger.info(
            "Зарегистрирован обработчик: %s → %s",
            event_name,
            handler_class.__name__,
        )
        return handler_class

    return decorator


def get_handler_class(event_name: str) -> type[WebhookEventHandler] | None:
    """
    Получить класс обработчика по имени события.

    Args:
        event_name: Название события Bitrix24

    Returns:
        Класс обработчика или None, если обработчик не найден
    """
    return HANDLERS_REGISTRY.get(event_name)


def _load_all_handlers():
    """
    Автоматическая загрузка всех обработчиков из папки events/.

    Вызывается один раз при старте приложения.
    Проходит по всем .py файлам в папке events и импортирует их.
    При импорте срабатывает @register_handler → реестр заполняется.
    """
    events_dir = pathlib.Path(__file__).parent / "events"

    if not events_dir.exists():
        logger.warning(f"Папка с обработчиками не найдена: {events_dir}")
        return

    for file_path in events_dir.iterdir():
        if file_path.suffix == ".py" and file_path.name not in {"__init__.py"}:
            module_name = file_path.stem

            try:
                importlib.import_module(
                    f".events.{module_name}",
                    package="crm.utils.webhook",
                )
                logger.debug(f"Импортирован модуль обработчика: {module_name}")
            except Exception as e:
                logger.error(
                    f"Ошибка загрузки обработчика {module_name}: {e}",
                    exc_info=True,
                )


_load_all_handlers()

logger.info(f"Загружено обработчиков webhook: {len(HANDLERS_REGISTRY)}")
for event, cls in HANDLERS_REGISTRY.items():
    logger.info(f"  → {event} → {cls.__name__}")


__all__ = [
    "WebhookEventHandler",
    "register_handler",
    "get_handler_class",
    "HANDLERS_REGISTRY",
]
