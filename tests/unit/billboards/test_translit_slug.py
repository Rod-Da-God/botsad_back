"""Тесты транслитерации города и адреса в URL-slug."""

import re

import pytest

from billboards.utils.translit_slug import translit_address, translit_city


@pytest.mark.parametrize(
    ("city", "name", "expected"),
    [
        (
            "Хабаровск",
            "ул. Краснореченская 92",
            "khabarovsk/ul-krasnorechenskaia-92",
        ),
        ("Москва", "пр-т Ленина 5", "moskva/pr-t-lenina-5"),
        (
            "Санкт-Петербург",
            "шоссе Революции 14",
            "sankt-peterburg/shosse-revoliutsii-14",
        ),
        (
            "Нижний Новгород",
            "мкр. Северный 12",
            "nizhnii-novgorod/mkr-severnyi-12",
        ),
        ("Ростов-на-Дону", "Мира 25", "rostov-na-donu/mira-25"),
    ],
)
def test_translit_address_examples(city: str, name: str, expected: str) -> None:
    assert translit_address(city, name) == expected


def test_translit_address_format() -> None:
    slug = translit_address("Хабаровск", "ул. Краснореченская 92")

    assert slug.count("/") == 1
    city_slug, place_slug = slug.split("/")

    assert city_slug
    assert place_slug

    allowed = re.compile(r"^[a-z0-9-]+$")
    assert allowed.match(city_slug)
    assert allowed.match(place_slug)


def test_translit_address_strips_whitespace() -> None:
    assert (
        translit_address("  Хабаровск  ", "  ул. Ленина 1  ")
        == "khabarovsk/ul-lenina-1"
    )


@pytest.mark.parametrize(
    ("city", "name"),
    [
        ("", "ул. Пушкина 1"),
        ("Москва", ""),
        ("", ""),
        (None, "ул. Пушкина 1"),
        ("Москва", None),
    ],
)
def test_translit_address_empty_inputs(city, name) -> None:
    assert translit_address(city, name) == ""


def test_translit_city_basic() -> None:
    assert translit_city("Хабаровск") == "khabarovsk"
    assert translit_city("Санкт-Петербург") == "sankt-peterburg"
    assert translit_city("Нижний Новгород") == "nizhnii-novgorod"


def test_translit_city_strips_spaces() -> None:
    assert translit_city("  Москва  ") == "moskva"


def test_translit_city_handles_mixed_separators() -> None:
    assert translit_city("Ростов-на Дону") == "rostov-na-donu"
    assert translit_city("Ростов на-Дону") == "rostov-na-donu"
