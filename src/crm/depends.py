import logging

from billboards.dependens import get_billboard_service
from external.crm.bitrix import BitrixCrmClient
from external.districts.client import DistrictsClient
from external.geocoder.service import GeocoderService
from external.geocoder.yandex import YandexGeocoderClient

from .config import crm_settings
from .services.booking_service import BookingService
from .services.crm_service import CrmSyncService
from .services.webhook_service import WebhookService


logger = logging.getLogger(__name__)


_bitrix_client: BitrixCrmClient | None = None
_geocoder_client: YandexGeocoderClient | None = None
_crm_sync_service: CrmSyncService | None = None
_booking_service: BookingService | None = None
_webhook_service: WebhookService | None = None
_geocoder_service: GeocoderService | None = None
_districts_client: DistrictsClient | None = None


def get_districts_client() -> DistrictsClient:
    """
    Получить синглтон-инстанс Districts клиента.
    """
    global _districts_client

    if _districts_client is None:
        logger.debug("Создание DistrictsClient")
        _districts_client = DistrictsClient(
            base_url=crm_settings.districts_service_url, timeout=10.0
        )
        logger.info("DistrictsClient инициализирован")

    return _districts_client


def get_bitrix_client() -> BitrixCrmClient:
    """
    Получить синглтон-инстанс Bitrix CRM клиента.

    Returns:
        BitrixCrmClient: Клиент для работы с Bitrix24 API
    """
    global _bitrix_client

    if _bitrix_client is None:
        logger.debug("Создание BitrixCrmClient")
        _bitrix_client = BitrixCrmClient(
            webhook_url=crm_settings.bitrix_webhook_url,
            entity_type_id=crm_settings.bitrix_entity_type_id,
        )
        logger.info("BitrixCrmClient инициализирован")

    return _bitrix_client


def get_geocoder_client() -> YandexGeocoderClient:
    """
    Получить синглтон-инстанс Yandex Geocoder клиента.

    Returns:
        YandexGeocoderClient: Клиент для работы с Yandex Geocoder API
    """
    global _geocoder_client

    if _geocoder_client is None:
        logger.debug("Создание YandexGeocoderClient")
        _geocoder_client = YandexGeocoderClient(
            api_key=crm_settings.geocoder_api_key
        )
        logger.info("YandexGeocoderClient инициализирован")

    return _geocoder_client


def get_geocoder_service() -> GeocoderService:
    """
    Получить синглтон-инстанс Geocoder Service.

    Returns:
        GeocoderService: Сервис геокодирования с бизнес-логикой
    """
    global _geocoder_service

    if _geocoder_service is None:
        logger.debug("Создание GeocoderService")

        geocoder_client = get_geocoder_client()
        districts_client = get_districts_client()

        _geocoder_service = GeocoderService(
            geocoder_client=geocoder_client,
            default_city="Хабаровск",
            districts_client=districts_client,
        )

        logger.info("GeocoderService инициализирован")

    return _geocoder_service


def get_crm_sync_service() -> CrmSyncService:
    global _crm_sync_service

    if _crm_sync_service is None:
        logger.debug("Создание CrmSyncService")

        bitrix = get_bitrix_client()
        geocoder = get_geocoder_service()

        _crm_sync_service = CrmSyncService(
            crm_client=bitrix, geocoder_service=geocoder
        )

        logger.info("CrmSyncService инициализирован")

    return _crm_sync_service


def get_booking_service() -> BookingService:
    """
    Получить синглтон-инстанс BookingService.

    Returns:
        BookingService: Сервис бронирования
    """
    global _booking_service
    if _booking_service is None:
        logger.debug("Создание BookingService")

        bitrix_client = get_bitrix_client()

        _booking_service = BookingService(bitrix_client=bitrix_client)

        logger.info("BookingService инициализирован")

    return _booking_service


def get_webhook_service() -> WebhookService:
    """
    Получить синглтон-инстанс WebhookService.

    Returns:
        WebhookService: Сервис обработки вебхуков
    """
    global _webhook_service

    if _webhook_service is None:
        logger.debug("Создание WebhookService")

        crm_sync = get_crm_sync_service()
        billboard = get_billboard_service()

        _webhook_service = WebhookService(
            crm_sync_service=crm_sync, billboard_service=billboard
        )

        logger.info("WebhookService инициализирован")

    return _webhook_service


async def cleanup_crm_clients():
    """
    Закрыть все HTTP клиенты при завершении приложения.
    """
    global \
        _bitrix_client, \
        _geocoder_client, \
        _crm_sync_service, \
        _districts_client

    if _bitrix_client:
        await _bitrix_client.close()
        logger.info("BitrixCrmClient закрыт")
        _bitrix_client = None

    if _geocoder_client:
        await _geocoder_client.close()
        logger.info("YandexGeocoderClient закрыт")
        _geocoder_client = None

    if _districts_client:
        await _districts_client.close()
        logger.info("DistrictsClient закрыт")
        _districts_client = None

    _crm_sync_service = None
    logger.info("CRM клиенты очищены")
