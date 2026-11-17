"""Тесты форматирования адреса билборда."""

import pytest

from billboards.utils.parsers.address import format_billboard_address


def test_landmark_has_priority_over_street() -> None:
    location = {
        "landmark": "ул. Ленина 5, у остановки",
        "street_name": "Ленина",
        "building_number": "5",
    }

    assert format_billboard_address(location) == "ул. Ленина 5, у остановки"


def test_street_and_building_number() -> None:
    location = {"street_name": "Ленина", "building_number": "5"}

    assert format_billboard_address(location) == "Ленина 5"


def test_street_without_building_number() -> None:
    location = {"street_name": "Ленина", "building_number": None}

    assert format_billboard_address(location) == "Ленина"


def test_blank_landmark_falls_back_to_street() -> None:
    location = {
        "landmark": "   ",
        "street_name": "Ленина",
        "building_number": "5",
    }

    assert format_billboard_address(location) == "Ленина 5"


def test_blank_building_number_is_ignored() -> None:
    location = {
        "landmark": None,
        "street_name": "Ленина",
        "building_number": "  ",
    }

    assert format_billboard_address(location) == "Ленина"


def test_values_are_stripped() -> None:
    location = {
        "landmark": "  ул. Ленина 5  ",
        "street_name": "  ",
        "building_number": "  ",
    }

    assert format_billboard_address(location) == "ул. Ленина 5"

    location = {
        "landmark": " ",
        "street_name": "  Ленина  ",
        "building_number": "  5  ",
    }
    assert format_billboard_address(location) == "Ленина 5"


@pytest.mark.parametrize(
    "location",
    [
        {},
        {"landmark": None, "street_name": None, "building_number": None},
        {"landmark": "", "street_name": "", "building_number": ""},
        {"building_number": "5"},
    ],
)
def test_missing_address_returns_placeholder(location: dict) -> None:
    result = format_billboard_address(location)

    assert isinstance(result, str)
    assert result.strip()
    assert "5" not in result
