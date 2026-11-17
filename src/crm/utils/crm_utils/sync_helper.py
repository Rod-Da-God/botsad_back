import logging

from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from billboards.utils.translit_slug import translit_city
from database.repository import (
    BillboardRepository,
    DistrictRepository,
    LocationRepository,
    MaterialRepository,
    SizeRepository,
)
from database.schemas.billboard_schemas import BillboardUpdate, SizeCreate
from external.geocoder.service import GeocoderService

from ..parsers.crm_item import (
    parse_crm_item_to_billboard_data,
    parse_crm_item_to_billboard_update,
)
from .extractors import (
    extract_address,
    extract_coordinates,
    extract_material,
    extract_photo,
    extract_side,
    extract_size,
)
from .photo_processor import process_photo_from_bitrix


logger = logging.getLogger(__name__)


class CrmSyncHelper:
    """
    Хелпер для операций синхронизации CRM -> БД.

    Инкапсулирует логику создания и обновления сущностей:
    - Билборды (создание, обновление)
    - Локации (с геокодированием)
    - Справочники (размеры, материалы)
    """

    def __init__(self, geocoder_service: GeocoderService):
        self.geocoder_service = geocoder_service

    async def sync_location_with_sides(
        self, address: str, sides_data: list[dict]
    ) -> int:
        """
        Синхронизировать локацию со всеми сторонами.
        Оптимизировано: геокодирование только если локация не существует.
        """
        logger.debug(f"Обработка '{address}': {len(sides_data)} сторон")

        first_item = sides_data[0]
        coords_from_crm = extract_coordinates(first_item)

        location_id = None
        if coords_from_crm:
            existing_location = await LocationRepository.find_by_coordinates(
                longitude=coords_from_crm[0], latitude=coords_from_crm[1]
            )
            if existing_location:
                location_id = existing_location["id"]
                logger.debug(
                    f"Локация найдена по координатам: ID={location_id}, "
                    f"геокодирование не требуется"
                )

        if location_id is None:

            class LocationFilter(BaseModel):
                landmark: str

            existing_by_address = await LocationRepository.get_one(
                filters=LocationFilter(landmark=address)
            )
            if existing_by_address:
                location_id = existing_by_address["id"]
                logger.debug(
                    f"Локация найдена по адресу: ID={location_id}, "
                    f"геокодирование не требуется"
                )

        if location_id is None:
            logger.debug(
                f"Локация не найдена, выполняется геокодирование: {address}"
            )
            location_id = await self.get_or_create_location(
                address, first_item
            )

        for item in sides_data:
            await self._create_or_update_billboard(item, location_id)

        return len(sides_data)

    async def _create_or_update_billboard(
        self, crm_item: dict, location_id: int
    ) -> int:
        """
        Создать или обновить билборд с умной загрузкой фото.

        Фото загружается только если:
        - Билборд новый
        - У существующего билборда нет фото
        - Фото изменилось в CRM (другой ID)
        """
        bitrix_id = crm_item.get("id")
        side = extract_side(crm_item)

        class BitrixIdFilter(BaseModel):
            bitrix_id: int

        existing_by_bitrix = None
        if bitrix_id:
            existing_by_bitrix = await BillboardRepository.get_one(
                filters=BitrixIdFilter(bitrix_id=int(bitrix_id))
            )

        class BillboardFilter(BaseModel):
            location_id: int
            side: str

        existing_by_location = await BillboardRepository.get_one(
            filters=BillboardFilter(location_id=location_id, side=side)
        )

        existing = existing_by_bitrix or existing_by_location

        if existing:
            existing_photo_url = existing.get("photo_url")

            photo_url = existing_photo_url

            if not existing_photo_url:
                logger.info(
                    f"У билборда ID={existing['id']} нет фото, загружаем..."
                )
                photo_array = extract_photo(crm_item)
                photo_url = await process_photo_from_bitrix(photo_array)
            else:
                photo_array = extract_photo(crm_item)
                if photo_array and len(photo_array) > 0:
                    logger.debug(
                        "У билборда ID=%s уже есть фото, пропускаем загрузку",
                        existing["id"],
                    )

            logger.debug(
                f"Билборд уже существует: ID={existing['id']}, "
                f"bitrix_id={existing.get('bitrix_id')}, "
                f"location_id={existing['location_id']}, "
                f"side={existing['side']}"
            )

            size_id = await self.get_or_create_size(crm_item)
            material_id = await self.get_or_create_material(crm_item)

            update_data = parse_crm_item_to_billboard_update(
                crm_item=crm_item,
                size_id=size_id,
                material_id=material_id,
                photo_url=photo_url,
            )

            if existing_by_bitrix and (
                existing["location_id"] != location_id
                or existing["side"] != side
            ):
                logger.warning(
                    f"Билборд bitrix_id={bitrix_id} переносится: "
                    f"location {existing['location_id']}->{location_id}, "
                    f"side {existing['side']}->{side}"
                )
                update_dict = update_data.model_dump(exclude_unset=True)
                update_dict["location_id"] = location_id
                update_dict["side"] = side
                update_data = BillboardUpdate(**update_dict)

            await BillboardRepository.update(
                id=existing["id"], values=update_data
            )

            logger.info(
                f"Билборд обновлён: ID={existing['id']}, "
                f"location_id={location_id}, сторона={side}"
            )

            return existing["id"]
        else:
            logger.info(
                "Создаём новый билборд: location_id=%s, сторона=%s",
                location_id,
                side,
            )

            photo_array = extract_photo(crm_item)
            photo_url = await process_photo_from_bitrix(photo_array)

            size_id = await self.get_or_create_size(crm_item)
            material_id = await self.get_or_create_material(crm_item)

            billboard_data = parse_crm_item_to_billboard_data(
                crm_item=crm_item,
                location_id=location_id,
                size_id=size_id,
                material_id=material_id,
                photo_url=photo_url,
            )

            try:
                billboard_id = await BillboardRepository.create_and_return_id(
                    values=billboard_data
                )

                logger.info(
                    f"Билборд создан: ID={billboard_id}, "
                    f"location_id={location_id}, сторона={side}"
                )

                return billboard_id
            except IntegrityError as e:
                if "unique_location_side" in str(e):
                    logger.warning(
                        "Race condition: билборд location_id=%s, "
                        "side=%s уже создан другим потоком."
                        " Получаем существующий.",
                        location_id,
                        side,
                    )

                    existing = await BillboardRepository.get_one(
                        filters=BillboardFilter(
                            location_id=location_id, side=side
                        )
                    )

                    if existing:
                        logger.info(
                            f"Получен существующий билборд:"
                            f" ID={existing['id']}, "
                            f"location_id={location_id}, сторона={side}"
                        )
                        return existing["id"]
                    else:
                        logger.error(
                            "Не удалось получить билборд"
                            " после race condition: "
                            f"location_id={location_id}, side={side}"
                        )
                        raise
                else:
                    raise

    async def create_billboard_from_item(self, crm_item: dict) -> int:
        """
        Создать билборд из CRM item (без известной локации).

        Args:
            crm_item: Элемент конструкции из CRM

        Returns:
            int: ID созданного билборда
        """
        address = extract_address(crm_item)
        location_id = await self.get_or_create_and_update_location(
            address, crm_item
        )

        return await self.create_billboard_with_location(crm_item, location_id)

    async def create_billboard_with_location(
        self, crm_item: dict, location_id: int
    ) -> int:
        """
        Создать билборд для известной локации.

        Args:
            crm_item: Элемент конструкции из CRM
            location_id: ID существующей локации

        Returns:
            int: ID созданного билборда
        """
        size_id = await self.get_or_create_size(crm_item)
        material_id = await self.get_or_create_material(crm_item)

        photo_array = extract_photo(crm_item)
        photo_url = await process_photo_from_bitrix(photo_array)

        billboard_data = parse_crm_item_to_billboard_data(
            crm_item=crm_item,
            location_id=location_id,
            size_id=size_id,
            material_id=material_id,
            photo_url=photo_url,
        )

        try:
            billboard_id = await BillboardRepository.create_and_return_id(
                values=billboard_data
            )

            logger.info(
                f"Билборд создан: ID={billboard_id}, "
                f"location_id={location_id}, сторона={billboard_data.side}"
            )

            return billboard_id
        except IntegrityError as e:
            if "unique_location_side" in str(e):
                logger.warning(
                    f"Race condition при создании билборда: "
                    f"location_id={location_id}, side={billboard_data.side}"
                )

                class BillboardFilter(BaseModel):
                    location_id: int
                    side: str

                existing = await BillboardRepository.get_one(
                    filters=BillboardFilter(
                        location_id=location_id, side=billboard_data.side
                    )
                )

                if existing:
                    logger.info(
                        f"Получен существующий билборд: ID={existing['id']}"
                    )
                    return existing["id"]
                else:
                    raise
            else:
                raise

    async def prepare_billboard_update(self, crm_item: dict):
        """
        Подготовить данные для обновления билборда.

        Args:
            crm_item: Элемент конструкции из CRM

        Returns:
            BillboardUpdate: Схема для обновления
        """
        size_id = await self.get_or_create_size(crm_item)
        material_id = await self.get_or_create_material(crm_item)

        photo_array = extract_photo(crm_item)
        photo_url = await process_photo_from_bitrix(photo_array)

        return parse_crm_item_to_billboard_update(
            crm_item=crm_item,
            size_id=size_id,
            material_id=material_id,
            photo_url=photo_url,
        )

    async def get_or_create_location(
        self, address: str, crm_item: dict
    ) -> int:
        coords_from_crm = extract_coordinates(crm_item)

        if coords_from_crm:
            existing = await LocationRepository.find_by_coordinates(
                longitude=coords_from_crm[0], latitude=coords_from_crm[1]
            )

            if existing:
                logger.debug(
                    f"Локация найдена по координатам: ID={existing['id']}"
                )
                return existing["id"]

        logger.debug(f"Геокодирование: {address}")

        geocode_result = await self.geocoder_service.geocode_with_fallback(
            address=address,
            coords_from_crm=coords_from_crm,
        )

        location_id = await LocationRepository.get_or_create_by_address(
            address=geocode_result["formatted_address"],
            coords=geocode_result["coordinates"],
            city=geocode_result["city"],
            street_name=geocode_result.get("street_name"),
            building_number=geocode_result.get("building_number"),
            district_name=geocode_result.get("district"),
            district_repo=DistrictRepository,
        )

        logger.info(f"Локация создана: ID={location_id}")
        return location_id

    async def get_or_create_size(self, crm_item: dict) -> int:
        """
        Получить или создать размер.

        Args:
            crm_item: Элемент конструкции из CRM

        Returns:
            int: ID размера
        """
        size_str = extract_size(crm_item)
        size = SizeCreate.from_size_string(size_str)

        return await SizeRepository.get_or_create_by_dimensions(
            width=size.width,
            height=size.height,
        )

    async def get_or_create_material(self, crm_item: dict) -> int | None:
        """
        Получить или создать материал.

        Args:
            crm_item: Элемент конструкции из CRM

        Returns:
            int | None: ID материала или None
        """
        material_str = extract_material(crm_item)

        if not material_str:
            return None

        return await MaterialRepository.get_or_create_by_name(
            name=material_str
        )

    async def get_or_create_and_update_location(
        self, address: str, crm_item: dict
    ) -> int:
        """
        Получить или создать локацию С ОБНОВЛЕНИЕМ данных.

        Используется в sync_one (webhook) где нужно обновить
        slug_city и district.

        Args:
            address: Адрес
            crm_item: Элемент из CRM

        Returns:
            ID локации
        """
        coords_from_crm = extract_coordinates(crm_item)

        existing_location = None
        if coords_from_crm:
            existing_location = await LocationRepository.find_by_coordinates(
                longitude=coords_from_crm[0], latitude=coords_from_crm[1]
            )

        logger.debug(f"Геокодирование: {address}")
        geocode_result = await self.geocoder_service.geocode_with_fallback(
            address=address,
            coords_from_crm=coords_from_crm,
        )

        if existing_location:
            location_id = existing_location["id"]

            needs_update = False
            update_data = {}

            if geocode_result.get("city"):
                new_slug_city = translit_city(geocode_result["city"])
                if existing_location.get("slug_city") != new_slug_city:
                    update_data["slug_city"] = new_slug_city
                    needs_update = True

            if geocode_result.get("district"):
                district_id = await DistrictRepository.get_or_create_by_name(
                    name=geocode_result["district"]
                )
                if existing_location.get("district_id") != district_id:
                    update_data["district_id"] = district_id
                    needs_update = True

            if (
                geocode_result.get("city")
                and existing_location.get("city") != geocode_result["city"]
            ):
                update_data["city"] = geocode_result["city"]
                needs_update = True

            if needs_update:
                await LocationRepository.update(
                    id=location_id, values=update_data
                )
                logger.info(
                    f"Локация обновлена: ID={location_id}, "
                    f"обновлено полей: {list(update_data.keys())}"
                )
            else:
                logger.debug(f"Локация ID={location_id} не требует обновления")

            return location_id

        location_id = await LocationRepository.get_or_create_by_address(
            address=geocode_result["formatted_address"],
            coords=geocode_result["coordinates"],
            city=geocode_result["city"],
            street_name=geocode_result.get("street_name"),
            building_number=geocode_result.get("building_number"),
            district_name=geocode_result.get("district"),
            district_repo=DistrictRepository,
        )

        logger.info(f"Локация создана: ID={location_id}")
        return location_id
