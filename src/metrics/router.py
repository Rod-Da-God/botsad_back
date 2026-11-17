from fastapi import APIRouter

from .schemas import EventsBatch
from .service import metrics_service


router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/events")
async def post_events(batch: EventsBatch):
    accepted = await metrics_service.ingest_batch(batch.events)

    return {"accepted": accepted}
