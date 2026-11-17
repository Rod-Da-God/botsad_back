import logging

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.path import ENV_FILE


logger = logging.getLogger(__name__)


# Название смарт-процесса в Bitrix24. По нему через crm.type.list
# определяется entityTypeId, поэтому в коде не нужен числовой ID.
DEFAULT_SPA_TITLE = "Конструкции"

# Смысл поля -> возможные названия в карточке Bitrix24.
# Резолвер сопоставляет их с ответом crm.item.fields, после чего
# в коде используются полученные коды полей (ufCrm...).
BITRIX_FIELD_TITLES: dict[str, tuple[str, ...]] = {
    "address": ("Адрес", "Адрес размещения", "Адрес конструкции"),
    "construction_type": (
        "Тип конструкции",
        "Размер конструкции",
        "Размер",
    ),
    "side": ("Сторона", "Сторона конструкции"),
    "lighting": ("Подсветка", "Освещение", "Наличие подсветки"),
    "photo": ("Фото", "Фотография", "Фото конструкции"),
    "material": ("Материал",),
    "rental_price": ("Цена аренды", "Аренда", "Стоимость аренды"),
    "mounting_price": ("Монтаж/демонтаж", "Монтаж", "Цена монтажа"),
    "production_price": ("Производство", "Печать", "Цена производства"),
    "status1": ("Статус, месяц 1", "Статус месяц 1", "Месяц 1"),
    "status2": ("Статус, месяц 2", "Статус месяц 2", "Месяц 2"),
    "status3": ("Статус, месяц 3", "Статус месяц 3", "Месяц 3"),
    "status4": ("Статус, месяц 4", "Статус месяц 4", "Месяц 4"),
    "status5": ("Статус, месяц 5", "Статус месяц 5", "Месяц 5"),
    "status6": ("Статус, месяц 6", "Статус месяц 6", "Месяц 6"),
}

# Без этих полей синхронизация невозможна - резолвер упадёт с ошибкой.
BITRIX_REQUIRED_FIELDS = frozenset(
    {
        "address",
        "construction_type",
        "side",
        "lighting",
        "photo",
        "rental_price",
        "mounting_price",
        "production_price",
        "status1",
        "status2",
        "status3",
        "status4",
        "status5",
        "status6",
    }
)

# Названия вариантов списков в Bitrix24. Значения - то, что нужно БД.
BITRIX_STATUS_LABELS = {
    "свободно": ("Свободно",),
    "занято": ("Занято",),
    "резерв": ("Резерв",),
}
BITRIX_SIDE_LABELS = {
    "А": ("А",),
    "Б": ("Б",),
    "В": ("В",),
    "Г": ("Г",),
}
BITRIX_LIGHTING_LABELS = {
    True: ("Да", "Есть", "С подсветкой"),
    False: ("Нет", "Без подсветки"),
}

BITRIX_DEFAULT_SIZE = "6x3"
BITRIX_DEFAULT_SIDE = "А"
BITRIX_DEFAULT_STATUS = "свободно"
BITRIX_DEFAULT_PRICE = "0|RUB"


class CrmSettings(BaseSettings):
    """
    Настройки для работы с CRM и геокодером.
    """

    bitrix_webhook_url: str = Field(
        ..., description="URL вебхука Bitrix24 для REST API"
    )

    bitrix_spa_title: str = Field(
        DEFAULT_SPA_TITLE,
        description="Название смарт-процесса с конструкциями",
    )

    bitrix_entity_type_id: int | None = Field(
        None,
        description=(
            "Фолбэк entityTypeId смарт-процесса, если crm.type.list "
            "недоступен. Основной способ - поиск по названию"
        ),
    )

    yandex_geocoder_api_key: SecretStr = Field(
        ..., description="API ключ для Yandex Geocoder"
    )

    districts_service_url: str = Field(
        ..., description="URL микросервиса районов"
    )

    @field_validator("bitrix_entity_type_id", mode="before")
    @classmethod
    def empty_entity_type_id_to_none(cls, value: object) -> object:
        """Пустое значение в .env означает «фолбэк не задан»."""
        if isinstance(value, str) and not value.strip():
            return None

        return value

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def geocoder_api_key(self) -> str:
        """Получить расшифрованный API ключ геокодера"""
        return self.yandex_geocoder_api_key.get_secret_value()


crm_settings = CrmSettings()
