import logging
import mimetypes
import uuid
from collections.abc import Callable
from functools import wraps

import aioboto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from .config import s3_settings  # ваш Pydantic settings
from .exceptions import S3UploadError


logger = logging.getLogger(__name__)


def s3_client(func: Callable) -> Callable:
    """
    Декоратор: создаёт s3_client и передаёт его как первый аргумент в функцию.
    Использует глобальную сессию из S3Cloud.
    """

    @wraps(func)
    async def wrapper(cls, *args, **kwargs):
        async with S3Cloud.get_session().client(
            "s3",
            endpoint_url=s3_settings.s3_endpoint,
            aws_access_key_id=s3_settings.aws_access_key,
            aws_secret_access_key=s3_settings.aws_secret_key,
            config=Config(signature_version="s3v4"),
            region_name=s3_settings.s3_region or None,
        ) as client:
            return await func(cls, client, *args, **kwargs)

    return wrapper


class S3Cloud:
    """Синглтон-подход к aioboto3.Session через классовый кэш."""

    _session: aioboto3.Session | None = None

    @classmethod
    def get_session(cls) -> aioboto3.Session:
        """Ленивая инициализация сессии."""
        if cls._session is None:
            logger.debug("Creating new aioboto3.Session for S3")
            cls._session = aioboto3.Session()
        return cls._session

    @classmethod
    @s3_client
    async def save_image(
        cls,
        client,
        byte_data: bytes,
        filename: str,  # ← Обязательный
        content_type: str | None = None,  # ← Опционально переопределяет MIME
    ) -> str:
        """
        Сохраняет изображение в S3 и возвращает публичную ссылку.

        **Args:**
            s3_client: aioboto3 S3 клиент (внедряется декоратором)
            byte_data (bytes): Двоичные данные изображения
            filename (str): Имя файла
                (обязательно, используется для расширения и MIME)
            content_type (str | None): MIME-тип
                (опционально, переопределяет угадывание)

        **Returns:**
            str: Публичная ссылка на загруженный файл[](https://...)

        **Raises:**
            S3UploadError: При любой ошибке S3 (таймаут, права, сеть и т.д.)
        """
        if not filename or not isinstance(filename, str):
            raise ValueError(
                "filename is required and must be a non-empty string"
            )

        ext = None
        if "." in filename:
            ext = filename.rsplit(".", 1)[-1].lower()
            if len(ext) > 10 or ext in {"php", "exe", "sh", "bat"}:  # защита
                ext = None

        mime_from_content = content_type
        mime_from_filename = mimetypes.guess_type(filename)[0]

        mime_type = (
            mime_from_content
            or mime_from_filename
            or "application/octet-stream"
        )

        unique_id = str(uuid.uuid4())
        if ext:
            unique_id += f".{ext}"

        try:
            await client.put_object(
                Bucket=s3_settings.s3_bucket,
                Key=unique_id,
                Body=byte_data,
                ACL="public-read",
                ContentType=mime_type,
            )
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.exception(
                "S3 ClientError: %s - %s",
                error_code,
                e.response["Error"]["Message"],
            )
            if error_code == "NoSuchBucket":
                raise S3UploadError("Bucket not found or inaccessible") from e
            elif error_code in {"InvalidAccessKeyId", "SignatureDoesNotMatch"}:
                raise S3UploadError("Invalid S3 credentials") from e
            else:
                raise S3UploadError(f"S3 upload failed: {error_code}") from e
        except BotoCoreError as e:
            logger.exception("S3 connection error: %s", e)
            raise S3UploadError("Failed to connect to S3") from e

        public_url = (
            f"{s3_settings.s3_endpoint}/{s3_settings.s3_bucket}/{unique_id}"
        )
        logger.info("Uploaded: %s (from %s)", public_url, filename)
        return public_url
