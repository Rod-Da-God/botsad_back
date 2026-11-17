"""Тесты нормализации и форматирования размеров конструкций."""

from decimal import Decimal

import pytest

from billboards.utils.normalizers.size import (
    format_size_for_display,
    format_size_from_dict,
)


@pytest.mark.parametrize(
    ("width", "height", "expected"),
    [
        (Decimal("6.0"), Decimal("3.0"), "6x3"),
        (Decimal("6.5"), Decimal("3.0"), "6,5x3"),
        (Decimal("4.25"), Decimal("1.50"), "4,25x1,5"),
        (Decimal("0.5"), Decimal("0.5"), "0,5x0,5"),
        (Decimal("6"), Decimal("3"), "6x3"),
        (Decimal("100"), Decimal("20.0"), "100x20"),
        (Decimal("10.50"), Decimal("5"), "10,5x5"),
    ],
)
def test_format_size_for_display(
    width: Decimal, height: Decimal, expected: str
) -> None:
    assert format_size_for_display(width, height) == expected


def test_format_size_uses_comma_as_decimal_separator() -> None:
    result = format_size_for_display(Decimal("6.50"), Decimal("3.25"))

    assert "." not in result
    assert result == "6,5x3,25"


def test_two_digit_integer_width_not_truncated() -> None:
    result = format_size_for_display(Decimal("10"), Decimal("5"))

    assert result == "10x5"


def test_two_digit_integer_dict_size_not_truncated() -> None:
    result = format_size_from_dict({"width": 10, "height": 5})

    assert result == "10x5"


def test_format_size_from_dict_none_and_empty() -> None:
    assert format_size_from_dict(None) == "Не указан"
    assert format_size_from_dict({}) == "Не указан"


@pytest.mark.parametrize(
    "size_data",
    [
        {"width": Decimal("6.0")},
        {"height": Decimal("3.0")},
        {"width": None, "height": Decimal("3.0")},
        {"width": Decimal("6.0"), "height": None},
    ],
)
def test_format_size_from_dict_requires_both_dimensions(
    size_data: dict,
) -> None:
    assert format_size_from_dict(size_data) == "Не указан"


@pytest.mark.parametrize(
    ("size_data", "expected"),
    [
        ({"width": Decimal("6.0"), "height": Decimal("3.0")}, "6x3"),
        ({"width": Decimal("6.5"), "height": Decimal("3.0")}, "6,5x3"),
        ({"width": 6, "height": 3}, "6x3"),
        ({"width": 100, "height": 25}, "100x25"),
    ],
)
def test_format_size_from_dict_valid(size_data: dict, expected: str) -> None:
    assert format_size_from_dict(size_data) == expected
