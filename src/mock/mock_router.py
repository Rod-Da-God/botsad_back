import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ws.broadcast import TOPICS, Broadcast


ACTIONS = ["create", "update", "delete"]


logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/mock_ws")
async def mock_ws(location_id: int):
    """
    Отправляет случайное действие (create, update, delete)
    в WebSocket через Broadcast.publish.
    """
    import random

    def random_khabarovsk_coordinates():
        """Генерирует случайные координаты в пределах Хабаровска."""
        lon = round(random.uniform(134.90, 135.20), 6)
        lat = round(random.uniform(48.40, 48.55), 6)
        return [lon, lat]

    try:
        # Выбираем случайное действие
        action = random.choice(ACTIONS)

        # Если действие delete — шлём только id
        if action == "delete":
            await Broadcast.publish(
                topic=TOPICS.UPDATES,
                message={"id": location_id},
                action=action,
            )
            logger.info(
                "Broadcast отправлен: action=delete, location_id=%s",
                location_id,
            )
            return JSONResponse({"status": "ok", "action": action})

        coordinates = random_khabarovsk_coordinates()
        billboard_dict = {
            "id": location_id,
            "coordinates": coordinates,
            "address": "ул. Тихоокеанская, 73",
            "district": "Центральный",
            "constructionType": "6x3",
            "sides": {
                "A": {
                    "id": f"{location_id}-A",
                    "price": random.choice([15000, 16000, 17000]),
                    "images": [
                        "https://static.tildacdn.com/tild6261-6264-4536-b239-633339356230/_.jpg"
                    ],
                    "statuses": {
                        "2025-10": random.choice(
                            ["Свободно", "Занято", "Резерв"]
                        ),
                        "2025-11": random.choice(
                            ["Свободно", "Занято", "Резерв"]
                        ),
                        "2025-12": random.choice(
                            ["Свободно", "Занято", "Резерв"]
                        ),
                        "2026-01": random.choice(
                            ["Свободно", "Занято", "Резерв"]
                        ),
                        "2026-02": random.choice(
                            ["Свободно", "Занято", "Резерв"]
                        ),
                    },
                },
                "B": {
                    "id": f"{location_id}-B",
                    "price": random.choice([18000, 19000, 20000]),
                    "images": [
                        "https://static.tildacdn.com/tild6366-3435-4566-a464-623837663235/sample.jpg"
                    ],
                    "statuses": {
                        "2025-10": random.choice(
                            ["Свободно", "Занято", "Резерв"]
                        ),
                        "2025-11": random.choice(
                            ["Свободно", "Занято", "Резерв"]
                        ),
                        "2025-12": random.choice(
                            ["Свободно", "Занято", "Резерв"]
                        ),
                        "2026-01": random.choice(
                            ["Свободно", "Занято", "Резерв"]
                        ),
                        "2026-02": random.choice(
                            ["Свободно", "Занято", "Резерв"]
                        ),
                    },
                },
            },
        }

        await Broadcast.publish(
            topic=TOPICS.UPDATES, message=billboard_dict, action=action
        )
        logger.info(
            f"Broadcast отправлен: action={action}, location_id={location_id}"
        )

        return JSONResponse(
            {
                "status": "ok",
                "action": action,
                "billboard_id": location_id,
                "data": billboard_dict,
            }
        )

    except Exception as e:
        logger.error(
            "Ошибка при отправке broadcast для location_id=%s: %s",
            location_id,
            e,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e)) from e
