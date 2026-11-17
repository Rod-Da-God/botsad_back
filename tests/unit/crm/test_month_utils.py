"""Тесты утилит для месяцев бронирования."""

from datetime import datetime

import pytest

from crm.utils.crm_utils.month_utils import (
    get_booking_months,
    validate_booking_months,
)


def test_booking_months_fields_and_count() -> None:
    months = get_booking_months(datetime(2025, 11, 15))

    assert [field for field, _ in months] == [
        "status_month1",
        "status_month2",
        "status_month3",
        "status_month4",
        "status_month5",
        "status_month6",
    ]
    assert len(months) == 6


def test_booking_months_sequence() -> None:
    months = get_booking_months(datetime(2025, 11, 15))

    assert [value for _, value in months] == [
        "2025-11",
        "2025-12",
        "2026-01",
        "2026-02",
        "2026-03",
        "2026-04",
    ]


def test_booking_months_year_rollover_from_december() -> None:
    months = get_booking_months(datetime(2025, 12, 1))

    assert [value for _, value in months] == [
        "2025-12",
        "2026-01",
        "2026-02",
        "2026-03",
        "2026-04",
        "2026-05",
    ]


def test_booking_months_keeps_day_out_of_output() -> None:
    months = get_booking_months(datetime(2026, 1, 31, 23, 59, 59))

    assert all(len(value) == 7 for _, value in months)
    assert months[0][1] == "2026-01"


def test_validate_accepts_available_months() -> None:
    available = [value for _, value in get_booking_months()]

    assert validate_booking_months(available) == available


def test_validate_accepts_empty_list() -> None:
    assert validate_booking_months([]) == []


def test_validate_preserves_order_and_duplicates() -> None:
    available = [value for _, value in get_booking_months()]
    requested = [available[1], available[0], available[1]]

    assert validate_booking_months(requested) == requested


def test_validate_rejects_unavailable_month() -> None:
    with pytest.raises(ValueError):
        validate_booking_months(["1999-01"])


def test_validate_rejects_past_and_far_future_months() -> None:
    with pytest.raises(ValueError):
        validate_booking_months(["2020-01", "2999-12"])


def test_validate_rejects_partially_valid_list() -> None:
    available = [value for _, value in get_booking_months()]

    with pytest.raises(ValueError):
        validate_booking_months([available[0], "2999-12"])
