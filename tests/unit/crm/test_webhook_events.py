"""Тесты обработчиков входящих webhook-событий Bitrix24."""

from typing import Any, Dict, Optional

import pytest

from crm.utils.webhook.events import create as create_module
from crm.utils.webhook.events import delete as delete_module
from crm.utils.webhook.events import update as update_module
from crm.utils.webhook.events.create import CreateEventHandler
from crm.utils.webhook.events.delete import DeleteEventHandler
from crm.utils.webhook.events.update import UpdateEventHandler


SYNC_RESULT = {"billboard_id": 42, "location_id": 7}


class FakeCrmSyncService:
    """Заглушка сервиса синхронизации CRM."""

    def __init__(self, result: Optional[Dict[str, Any]]) -> None:
        self.result = result
        self.sync_calls: list[int] = []
        self.delete_calls: list[int] = []

    async def sync_one(self, item_id: int) -> Optional[Dict[str, Any]]:
        self.sync_calls.append(item_id)
        return self.result

    async def delete_by_bitrix_id(
        self, item_id: int
    ) -> Optional[Dict[str, Any]]:
        self.delete_calls.append(item_id)
        return self.result


class FakeBillboardService:
    """Сервис билбордов обработчикам не нужен: broadcast замокан."""

    async def get_billboard_details(self, location_id: int) -> None:
        return None


class NotifyRecorder:
    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.calls: list[tuple[str, Dict[str, Any]]] = []

    async def __call__(self, event_type: str, payload: Dict[str, Any]) -> bool:
        self.calls.append((event_type, payload))
        return self.result


def _make_handler(handler_cls, sync_result):
    sync_service = FakeCrmSyncService(sync_result)
    handler = handler_cls(sync_service, FakeBillboardService())
    broadcast_calls: list[tuple[int, str]] = []

    async def fake_broadcast(location_id: int, action: str) -> None:
        broadcast_calls.append((location_id, action))

    handler.broadcast_billboard = fake_broadcast  # type: ignore[method-assign]
    return handler, sync_service, broadcast_calls


@pytest.mark.parametrize(
    ("handler_cls", "module", "event_type", "action", "success_status"),
    [
        (
            CreateEventHandler,
            create_module,
            "billboard.created",
            "create",
            "created",
        ),
        (
            UpdateEventHandler,
            update_module,
            "billboard.updated",
            "update",
            "updated",
        ),
        (
            DeleteEventHandler,
            delete_module,
            "billboard.deleted",
            "delete",
            "deleted",
        ),
    ],
)
async def test_successful_processing_notifies_billboard_event(
    monkeypatch: pytest.MonkeyPatch,
    handler_cls,
    module,
    event_type: str,
    action: str,
    success_status: str,
) -> None:
    recorder = NotifyRecorder()
    monkeypatch.setattr(module, "notify_billboard_event", recorder)

    handler, sync_service, broadcast_calls = _make_handler(
        handler_cls, dict(SYNC_RESULT)
    )

    result = await handler.handle(1038)

    assert result["status"] == success_status
    assert result["item_id"] == 1038
    assert result["billboard_id"] == SYNC_RESULT["billboard_id"]
    assert result["location_id"] == SYNC_RESULT["location_id"]

    # Затронут ровно один путь синхронизации.
    assert len(sync_service.sync_calls) + len(sync_service.delete_calls) == 1

    assert recorder.calls == [
        (
            event_type,
            {
                "billboard_id": SYNC_RESULT["billboard_id"],
                "location_id": SYNC_RESULT["location_id"],
                "crm_item_id": 1038,
            },
        )
    ]
    assert broadcast_calls == [(SYNC_RESULT["location_id"], action)]


@pytest.mark.parametrize(
    ("handler_cls", "module", "failure_status"),
    [
        (CreateEventHandler, create_module, "error"),
        (UpdateEventHandler, update_module, "error"),
        (DeleteEventHandler, delete_module, "not_found"),
    ],
)
async def test_failed_sync_does_not_notify(
    monkeypatch: pytest.MonkeyPatch,
    handler_cls,
    module,
    failure_status: str,
) -> None:
    recorder = NotifyRecorder()
    monkeypatch.setattr(module, "notify_billboard_event", recorder)

    handler, sync_service, broadcast_calls = _make_handler(
        handler_cls, None
    )

    result = await handler.handle(1038)

    assert result["status"] == failure_status
    assert result["item_id"] == 1038
    assert recorder.calls == []
    assert broadcast_calls == []
    assert len(sync_service.sync_calls) + len(sync_service.delete_calls) == 1


@pytest.mark.parametrize(
    ("handler_cls", "module"),
    [
        (CreateEventHandler, create_module),
        (UpdateEventHandler, update_module),
        (DeleteEventHandler, delete_module),
    ],
)
async def test_notification_failure_does_not_break_processing(
    monkeypatch: pytest.MonkeyPatch, handler_cls, module
) -> None:
    """Исходящий вебхук — побочный эффект, его отказ не меняет результат."""
    recorder = NotifyRecorder(result=False)
    monkeypatch.setattr(module, "notify_billboard_event", recorder)

    handler, _, _ = _make_handler(handler_cls, dict(SYNC_RESULT))

    result = await handler.handle(1038)

    assert result["status"] in {"created", "updated", "deleted"}
    assert len(recorder.calls) == 1
