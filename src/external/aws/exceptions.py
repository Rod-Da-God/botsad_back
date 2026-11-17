class S3Error(Exception):
    """Базовое исключение для S3"""

    pass


class S3UploadError(S3Error):
    """Ошибка при работе с S3"""

    pass
