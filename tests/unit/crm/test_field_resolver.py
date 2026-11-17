"""Тесты резолвера полей Bitrix24 и экстракторов на его основе."""

import pytest

from crm.config import crm_settings
from crm.utils.crm_utils import extractors
from crm.utils.crm_utils.field_resolver import (
    BitrixFieldMap,
    FieldResolutionError,
    bitrix_fields,
    normalize_label,
)


ENTITY_TYPE_ID = 1042


class FakeBitrixClient:
    """Минимальная заглушка клиента Bitrix24 для резолвера."""

    def __init__(self, fields, types=None, error=None):
        self._fields = fields
        self._types = (
            types
            if types is not None
            else [
                {
                    "id": 8,
                    "title": "Конструкции",
                    "entityTypeId": ENTITY_TYPE_ID,
                }
            ]
        )
        self._error = error
        self.entity_type_id = None
        self.requested_titles = []

    async def get_spa_types(self, title=None):
        self.requested_titles.append(title)
        if self._error is not None:
            raise self._error
        if title is None:
            return self._types
        return [spa for spa in self._types if spa.get("title") == title]

    async def get_item_fields(self, entity_type_id):
        assert entity_type_id == ENTITY_TYPE_ID
        return self._fields

    def use_entity_type(self, entity_type_id):
        self.entity_type_id = int(entity_type_id)


def enum_items(labels, start=60):
    return [
        {"ID": str(start + index), "VALUE": label}
        for index, label in enumerate(labels)
    ]


def build_fields():
    """Описание полей, повторяющее структуру ответа crm.item.fields."""
    fields = {
        # Название с другим регистром проверяет нормализацию.
        "ufCrm8_100": {"type": "address", "title": "адрес конструкции"},
        "ufCrm8_101": {
            "type": "enumeration",
            "title": "Тип конструкции",
            "items": enum_items(["6x3", "4x3"]),
        },
        "ufCrm8_102": {
            "type": "enumeration",
            "title": "Сторона",
            "items": enum_items(["А", "Б"]),
        },
        # Ключи в нижнем регистре проверяют разбор camelCase-ответа.
        "ufCrm8_103": {
            "type": "enumeration",
            "title": "Подсветка",
            "items": [
                {"id": "64", "value": "Да"},
                {"id": "66", "value": "Нет"},
            ],
        },
        "ufCrm8_104": {"type": "file", "title": "Фото"},
        "ufCrm8_105": {"type": "string", "title": "Материал"},
        "ufCrm8_110": {"type": "money", "title": "Цена аренды"},
        "ufCrm8_111": {"type": "money", "title": "Монтаж/демонтаж"},
        "ufCrm8_112": {"type": "money", "title": "Производство"},
    }

    for month in range(1, 7):
        fields[f"ufCrm8_12{month}"] = {
            "type": "enumeration",
            "title": f"Статус, месяц {month}",
            "items": enum_items(
                ["Свободно", "Занято", "Резерв"],
                start=68 + (month - 1) * 6,
            ),
        }

    return fields


@pytest.fixture
async def resolved_fields():
    """Загрузить описание полей в общий резолвер и очистить его после."""
    bitrix_fields.reset()
    client = FakeBitrixClient(build_fields())
    await bitrix_fields.ensure_loaded(client, force=True)

    yield client

    bitrix_fields.reset()


def test_normalize_label() -> None:
    assert normalize_label("  Тип   Конструкции  ") == "тип конструкции"
    assert normalize_label("Адрес Ёлки") == "адрес елки"
    assert normalize_label(None) == ""
    assert normalize_label(0) == ""


async def test_resolves_codes_by_title():
    resolver = BitrixFieldMap()
    client = FakeBitrixClient(build_fields())

    await resolver.ensure_loaded(client, force=True)

    assert resolver.ready
    assert resolver.entity_type_id == ENTITY_TYPE_ID
    assert client.entity_type_id == ENTITY_TYPE_ID
    assert client.requested_titles == [crm_settings.bitrix_spa_title]
    assert resolver.code("address") == "ufCrm8_100"
    assert resolver.code("construction_type") == "ufCrm8_101"
    assert resolver.code_optional("material") == "ufCrm8_105"
    assert resolver.code_optional("неизвестное_поле") is None
    assert resolver.field_type("address") == "address"
    assert set(resolver.codes()) == {
        "ufCrm8_100",
        "ufCrm8_101",
        "ufCrm8_102",
        "ufCrm8_103",
        "ufCrm8_104",
        "ufCrm8_105",
        "ufCrm8_110",
        "ufCrm8_111",
        "ufCrm8_112",
        *(f"ufCrm8_12{month}" for month in range(1, 7)),
    }


async def test_unknown_semantic_code_raises():
    resolver = BitrixFieldMap()
    await resolver.ensure_loaded(FakeBitrixClient(build_fields()), force=True)

    with pytest.raises(FieldResolutionError):
        resolver.code("does_not_exist")


async def test_ensure_loaded_is_cached():
    resolver = BitrixFieldMap()
    client = FakeBitrixClient(build_fields())

    await resolver.ensure_loaded(client, force=True)
    await resolver.ensure_loaded(client)

    # Повторная загрузка без force не должна ходить в Bitrix24.
    assert len(client.requested_titles) == 1


async def test_reload_forces_refetch():
    resolver = BitrixFieldMap()
    client = FakeBitrixClient(build_fields())

    await resolver.ensure_loaded(client, force=True)
    await resolver.reload(client)

    assert len(client.requested_titles) == 2


async def test_reset_clears_state():
    resolver = BitrixFieldMap()
    await resolver.ensure_loaded(FakeBitrixClient(build_fields()), force=True)

    resolver.reset()

    assert resolver.ready is False
    assert resolver.entity_type_id is None
    assert resolver.spa_id is None
    assert resolver.codes() == []
    assert resolver.code_optional("address") is None


async def test_resolves_enum_labels_and_ids():
    resolver = BitrixFieldMap()
    await resolver.ensure_loaded(FakeBitrixClient(build_fields()), force=True)

    assert resolver.enum_label("side", "60") == "А"
    assert resolver.enum_label("side", "61") == "Б"
    assert resolver.enum_label("lighting", "64") == "Да"
    assert resolver.enum_label("status1", "69") == "Занято"
    assert resolver.enum_label("side", None) is None
    assert resolver.enum_label("side", "") is None
    assert resolver.enum_label("side", []) is None
    assert resolver.enum_label("side", "999") is None

    assert resolver.enum_id("status1", "Занято") == "69"
    assert resolver.enum_id("side", "б") == "61"
    assert resolver.enum_id("side", "В") is None
    assert resolver.enum_values("lighting") == {"64": "Да", "66": "Нет"}


async def test_enum_label_handles_container_values():
    resolver = BitrixFieldMap()
    await resolver.ensure_loaded(FakeBitrixClient(build_fields()), force=True)

    assert resolver.enum_label("side", ["60"]) == "А"
    assert resolver.enum_label("side", {"VALUE": "61"}) == "Б"
    assert resolver.enum_label("side", {"title": "А"}) is None
    # У поля без вариантов значение возвращается как есть.
    assert resolver.enum_label("material", "Акрил") == "Акрил"


async def test_matches_spa_by_normalized_title():
    resolver = BitrixFieldMap()
    types = [
        {"id": 3, "title": "Другое", "entityTypeId": 1111},
        # Без entityTypeId запись должна быть пропущена.
        {"id": 9, "title": "Конструкции"},
        {"id": 8, "title": "конструкции", "entityTypeId": ENTITY_TYPE_ID},
    ]
    client = FakeBitrixClient(build_fields(), types=types)

    await resolver.ensure_loaded(client, force=True)

    assert resolver.spa_id == 8
    assert resolver.entity_type_id == ENTITY_TYPE_ID
    # Серверный фильтр не нашёл точное название - был запрос полного списка.
    assert client.requested_titles == [crm_settings.bitrix_spa_title, None]


async def test_matches_spa_by_partial_title():
    resolver = BitrixFieldMap()
    types = [
        {
            "id": 5,
            "title": f"{crm_settings.bitrix_spa_title} Битрикс",
            "entityTypeId": 1055,
        },
    ]

    class PartialSpaClient(FakeBitrixClient):
        async def get_item_fields(self, entity_type_id):
            self.requested_entity_type_id = entity_type_id
            return build_fields()

    client = PartialSpaClient(build_fields(), types=types)

    await resolver.ensure_loaded(client, force=True)

    assert resolver.spa_id == 5
    assert resolver.entity_type_id == 1055
    assert client.requested_entity_type_id == 1055


async def test_raises_when_required_field_missing():
    fields = build_fields()
    del fields["ufCrm8_101"]

    with pytest.raises(FieldResolutionError):
        await BitrixFieldMap().ensure_loaded(
            FakeBitrixClient(fields), force=True
        )


async def test_missing_optional_field_is_allowed():
    fields = build_fields()
    del fields["ufCrm8_105"]  # материал необязателен

    resolver = BitrixFieldMap()
    await resolver.ensure_loaded(FakeBitrixClient(fields), force=True)

    assert resolver.ready
    assert resolver.code_optional("material") is None


async def test_falls_back_to_env_entity_type_id(monkeypatch):
    monkeypatch.setattr(crm_settings, "bitrix_entity_type_id", ENTITY_TYPE_ID)
    resolver = BitrixFieldMap()
    client = FakeBitrixClient(
        build_fields(), error=RuntimeError("ACCESS_DENIED")
    )

    await resolver.ensure_loaded(client, force=True)

    assert resolver.entity_type_id == ENTITY_TYPE_ID
    assert client.entity_type_id == ENTITY_TYPE_ID


async def test_raises_when_spa_missing_and_no_fallback(monkeypatch):
    monkeypatch.setattr(crm_settings, "bitrix_entity_type_id", None)
    client = FakeBitrixClient(build_fields(), types=[])

    with pytest.raises(FieldResolutionError):
        await BitrixFieldMap().ensure_loaded(client, force=True)


async def test_extractors_use_resolved_fields(resolved_fields):
    item = {
        "ufCrm8_100": "Комсомольская 1|48.48;135.07|12",
        "ufCrm8_101": "60",  # 6x3
        "ufCrm8_102": "61",  # Б
        "ufCrm8_103": "64",  # Да
        "ufCrm8_104": [{"id": 1, "url": "photo.jpg"}],
        "ufCrm8_105": "Акрил",
        "ufCrm8_110": {"AMOUNT": 10000, "CURRENCY_ID": "RUB"},
        "ufCrm8_111": "15000|RUB",
        "ufCrm8_112": 20000,
        "ufCrm8_121": "69",  # Занято в первом месяце
    }

    assert extractors.extract_address(item) == "Комсомольская 1"
    assert extractors.extract_coordinates(item) == (135.07, 48.48)
    assert extractors.extract_size(item) == "6x3"
    assert extractors.extract_side(item) == "Б"
    assert extractors.extract_lighting(item) is True
    assert extractors.extract_material(item) == "Акрил"
    assert extractors.extract_rental_price(item) == "10000|RUB"
    assert extractors.extract_mounting_price(item) == "15000|RUB"
    assert extractors.extract_production_price(item) == "20000|RUB"
    assert extractors.extract_photo(item) == [{"id": 1, "url": "photo.jpg"}]

    statuses = extractors.extract_month_statuses(item)
    assert statuses["status_month1"] == "занято"
    assert statuses["status_month2"] == "свободно"


async def test_extractors_fall_back_to_defaults(resolved_fields):
    assert extractors.extract_size({}) == "6x3"
    assert extractors.extract_side({}) == "А"
    assert extractors.extract_lighting({}) is False
    assert extractors.extract_material({}) == ""
    assert extractors.extract_rental_price({}) == "0|RUB"
    assert extractors.extract_month_statuses({})["status_month1"] == "свободно"
