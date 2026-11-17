import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar


logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class ParallelExecutor:
    """
    Выполняет асинхронные задачи параллельно с ограничением.

    Attributes:
        max_concurrent: Максимальное число одновременных задач
    """

    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self._semaphore: asyncio.Semaphore | None = None

    @property
    def semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)
        return self._semaphore

    async def map(
        self,
        func: Callable[[T], Awaitable[R]],
        items: list[T],
        on_error: Callable[[Exception, T], R] | None = None,
    ) -> list[R]:
        """
        Применить async-функцию к каждому элементу параллельно.

        Args:
            func: Асинхронная функция для применения
            items: Список элементов
            on_error: Обработчик ошибок (Exception, item) -> fallback_value
                      Если None, ошибки пробрасываются

        Returns:
            Список результатов в том же порядке, что и items

        """

        async def wrapped(item: T) -> R:
            async with self.semaphore:
                if on_error is None:
                    return await func(item)

                try:
                    return await func(item)
                except Exception as error:
                    logger.exception(
                        "Параллельная задача завершилась ошибкой: %r", error
                    )
                    return on_error(error, item)

        tasks = [wrapped(item) for item in items]
        return await asyncio.gather(*tasks)

    async def map_with_index(
        self,
        func: Callable[[int, T], Awaitable[R]],
        items: list[T],
        on_error: Callable[[Exception, int, T], R] | None = None,
    ) -> list[R]:
        """
        То же что map, но func получает (index, item).

        Example:
            async def process(idx, item):
                logger.info(f"Processing {idx}/{total}")
                return await do_work(item)
        """

        async def wrapped(index: int, item: T) -> R:
            async with self.semaphore:
                if on_error is None:
                    return await func(index, item)

                try:
                    return await func(index, item)
                except Exception as error:
                    logger.exception(
                        "Параллельная задача завершилась ошибкой: %r", error
                    )
                    return on_error(error, index, item)

        tasks = [wrapped(i, item) for i, item in enumerate(items)]
        return await asyncio.gather(*tasks)


photo_executor = ParallelExecutor(max_concurrent=2)
address_executor = ParallelExecutor(max_concurrent=2)
