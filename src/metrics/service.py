from __future__ import annotations

from .db import analytics_db
from .schemas import AnalyticsEvent


MAX_BATCH = 200


class MetricsService:
    async def ingest_batch(self, events: list[AnalyticsEvent]) -> int:
        if not events:
            return 0

        if len(events) > MAX_BATCH:
            events = events[:MAX_BATCH]  # мягкая обрезка

        rows = []
        for e in events:
            rows.append(
                {
                    "event_id": e.event_id,
                    "event_name": e.event_name,
                    "event_ts": e.event_ts,
                    "session_id": e.session_id,
                    "client_id": e.client_id,
                    "viewer_id": e.client_id,  # по ТЗ
                    "entity_type": e.entity_type,
                    "entity_id": e.entity_id,
                    "context": e.context or {},
                    "properties": e.properties or {},
                }
            )

        # пока ждём вставку (на этапе 2 сделаем fire-and-forget через очередь)
        await analytics_db.insert_events_raw(rows)  # type: ignore[arg-type]
        return len(rows)


metrics_service = MetricsService()
