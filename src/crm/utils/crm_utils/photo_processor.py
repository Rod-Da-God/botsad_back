import logging

import httpx

from external.aws.s3 import S3Cloud


logger = logging.getLogger(__name__)


async def process_photo_from_bitrix(
    photo_array: list[dict],
) -> str:
    """
    Обработать фото из массива Bitrix: скачать и загрузить в S3.
    Args:
        photo_array: Массив фото из Bitrix [{'id': 146, 'url': '...', ...}]

    Returns:
        str: Публичная S3-ссылка или пустая строка
    """
    if not photo_array or not isinstance(photo_array, list):
        logger.debug("photo_array пуст или не список")
        return ""

    if len(photo_array) == 0:
        logger.debug("photo_array не содержит элементов")
        return ""

    first_photo = photo_array[0]

    bitrix_url = first_photo.get("urlMachine") or first_photo.get("url")

    if bitrix_url:
        logger.debug(f"Найден прямой URL фото: {bitrix_url[:80]}...")
        s3_url = await _download_from_url_and_upload(bitrix_url)
        return s3_url or ""

    logger.warning(f"Не удалось обработать фото: {first_photo}")
    return ""


async def _download_from_url_and_upload(url: str) -> str | None:
    """
    Скачать фото по прямой ссылке и загрузить в S3.

    Args:
        url: Прямая ссылка на фото

    Returns:
        Optional[str]: Публичная ссылка на S3 или None
    """
    if not url:
        return None

    logger.debug(f"Скачивание фото по URL: {url}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()

            photo_bytes = response.content
            content_type = response.headers.get("content-type", "image/jpeg")

            logger.debug(
                f"Фото скачано: {len(photo_bytes)} байт, "
                f"content-type={content_type}"
            )

        s3_url = await _upload_to_s3(photo_bytes, content_type)

        logger.info(f"Фото загружено в S3: {url[:50]}... → {s3_url}")
        return s3_url

    except httpx.HTTPError as e:
        logger.error(f"HTTP ошибка при скачивании {url}: {e}")
        return None


async def _upload_to_s3(photo_bytes: bytes, content_type: str) -> str:
    """
    Загрузить фото в S3.

    Args:
        photo_bytes: Бинарные данные фото
        content_type: MIME-тип (например, "image/jpeg")

    Returns:
        str: Публичная ссылка на S3

    Raises:
        S3UploadError: При ошибках загрузки в S3
    """
    ext_map = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "image/gif": "gif",
    }
    ext = ext_map.get(content_type, "jpg")
    filename = f"billboard_photo.{ext}"

    s3_url = await S3Cloud.save_image(
        byte_data=photo_bytes,
        filename=filename,
        content_type=content_type,
    )

    return s3_url
