"""Тесты контракта модуля исходящих вебхуков."""

from types import SimpleNamespace

import pytest

from external import webhooks
from external.seo.client import WebhookEvent
from external.webhooks import notifier


PAYLOAD = {
    "billboard_id": 42,
    "location_id": 7,
    "crm_item_id": 1038,
}


def test_event_type_constants() -> None:
    assert notifier.BILLBOARD_CREATED == "billboard.created"
    assert notifier.BILLBOARD_UPDATED == "billboard.updated"
    assert notifier.BILLBOARD_DELETED == "billboard.deleted"

    assert notifier.BILLBOARD_EVENTS == {
        "billboard.created",
        "billboard.updated",
        "billboard.deleted",
    }
    # Публичный реэкспорт из пакета должен указывать на те же значения.
    assert webhooks.BILLBOARD_CREATED == notifier.BILLBOARD_CREATED


async def test_unknown_event_type_is_ignored(
    monkeypatch: pytest.MonkeyPatch, fake_webhook_client
) -> None:
    registry = SimpleNamespace(webhook=fake_webhook_client)
    monkeypatch.setattr(notifier, "api_registry", registry)

    result = await notifier.notify_billboard_event(
        "billboard.unknown", dict(PAYLOAD)
    )

    assert result is False
    assert fake_webhook_client.calls == []


async def test_missing_webhook_client_is_not_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        notifier, "api_registry", SimpleNamespace(webhook=None)
    )

    result = await notifier.notify_billboard_event(
        notifier.BILLBOARD_CREATED, dict(PAYLOAD)
    )

    assert result is False


async def test_successful_send_passes_webhook_event(
    monkeypatch: pytest.MonkeyPatch, fake_webhook_client
) -> None:
    monkeypatch.setattr(
        notifier, "api_registry", SimpleNamespace(webhook=fake_webhook_client)
    )

    result = await notifier.notify_billboard_event(
        notifier.BILLBOARD_UPDATED, dict(PAYLOAD)
    )

    assert result is True
    assert len(fake_webhook_client.calls) == 1

    event = fake_webhook_client.calls[0]["event"]
    assert isinstance(event, WebhookEvent)
    assert event.type == "billboard.updated"
    assert event.payload == PAYLOAD


async def test_client_error_is_swallowed(
    monkeypatch: pytest.MonkeyPatch, fake_webhook_client
) -> None:
    fake_webhook_client.error = RuntimeError("webhook endpoint is down")
    monkeypatch.setattr(
        notifier, "api_registry", SimpleNamespace(webhook=fake_webhook_client)
    )

    result = await notifier.notify_billboard_event(
        notifier.BILLBOARD_DELETED, dict(PAYLOAD)
    )

    assert result is False
    assert len(fake_webhook_client.calls) == 1


async def test_payload_is_not_mutated(
    monkeypatch: pytest.MonkeyPatch, fake_webhook_client
) -> None:
    original = {
        "billboard_id": 42,
        "location_id": 7,
        "crm_item_id": 1038,
        "nested": {"status": "свободно", "months": ["2026-01", "2026-02"]},
    }
    snapshot = {
        "billboard_id": 42,
        "location_id": 7,
        "crm_item_id": 1038,
        "nested": {"status": "свободно", "months": ["2026-01", "2026-02"]},
    }
    monkeypatch.setattr(
        notifier, "api_registry", SimpleNamespace(webhook=fake_webhook_client)
    )

    result = await notifier.notify_billboard_event(
        notifier.BILLBOARD_CREATED, original
    )

    assert result is True
    assert original == snapshot
    assert fake_webhook_client.calls[0]["event"].payload == snapshot
