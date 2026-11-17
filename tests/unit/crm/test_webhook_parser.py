"""Тесты парсера входящих webhook-событий Bitrix24."""

import pytest
from starlette.datastructures import FormData

from crm.utils.parsers.webhook_parser import (
    WebhookParseError,
    extract_item_id_from_dict,
    parse_webhook_data,
)


EVENT = "ONCRMDYNAMICITEMADD"


def test_parse_form_with_fields_id() -> None:
    form = FormData(
        {
            "event": EVENT,
            "data[FIELDS][ID]": "1038",
        }
    )

    assert parse_webhook_data(form) == (EVENT, 1038)


def test_parse_form_with_plain_id() -> None:
    form = FormData({"event": EVENT, "data[ID]": "42"})

    assert parse_webhook_data(form) == (EVENT, 42)


def test_fields_id_has_priority_over_plain_id() -> None:
    form = FormData(
        {
            "event": EVENT,
            "data[FIELDS][ID]": "1",
            "data[ID]": "2",
        }
    )

    assert parse_webhook_data(form) == (EVENT, 1)


def test_missing_event_raises() -> None:
    form = FormData({"data[FIELDS][ID]": "1038"})

    with pytest.raises(WebhookParseError) as error:
        parse_webhook_data(form)

    assert error.value.event_type is None


def test_missing_item_id_raises_with_event_type() -> None:
    form = FormData({"event": EVENT})

    with pytest.raises(WebhookParseError) as error:
        parse_webhook_data(form)

    assert error.value.event_type == EVENT


def test_empty_item_id_raises() -> None:
    form = FormData({"event": EVENT, "data[FIELDS][ID]": ""})

    with pytest.raises(WebhookParseError):
        parse_webhook_data(form)


def test_invalid_item_id_raises() -> None:
    form = FormData({"event": EVENT, "data[FIELDS][ID]": "not-a-number"})

    with pytest.raises(WebhookParseError) as error:
        parse_webhook_data(form)

    assert error.value.event_type == EVENT


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({"ID": 42}, 42),
        ({"ID": "42"}, 42),
        ({"FIELDS": {"ID": "7"}}, 7),
        ({"ID": None, "FIELDS": {"ID": 9}}, 9),
    ],
)
def test_extract_item_id_from_dict(data: dict, expected: int) -> None:
    assert extract_item_id_from_dict(data) == expected


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"ID": None},
        {"FIELDS": {}},
        {"FIELDS": {"ID": None}},
        {"ID": 0},
    ],
)
def test_extract_item_id_from_dict_missing(data: dict) -> None:
    assert extract_item_id_from_dict(data) is None
