import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .broadcast import TOPICS, Broadcast


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])


@router.websocket("/updates")
async def websocket_subscribe(websocket: WebSocket):
    """
    WebSocket: /ws/updates
    Автоматически подписывает клиента на топик TOPICS.UPDATES.
    Пересылает все сообщения из Redis → клиенту.
    При отключении — подписка завершается.
    """
    await websocket.accept()
    logger.debug("Client connected to /ws/updates")

    try:
        async for message in Broadcast.subscribe(TOPICS.UPDATES):
            try:
                await websocket.send_json(message)
            except WebSocketDisconnect:
                logger.debug("Client disconnected during send")
                break
            except Exception:
                logger.exception("Error sending message")
                break

    except WebSocketDisconnect:
        logger.debug("Client disconnected")
    except asyncio.CancelledError:
        logger.debug("WebSocket task cancelled (client disconnected)")
    except Exception:
        logger.exception("Unexpected error in WebSocket")
        await websocket.close(code=1011)
    finally:
        logger.debug("WebSocket connection fully closed")
        # ← Всегда сработает
