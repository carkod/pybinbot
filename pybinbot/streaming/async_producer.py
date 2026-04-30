import asyncio
import logging

logger = logging.getLogger(__name__)


class AsyncProducer:
    """
    In-process async queue producer.

    Drop-in replacement for the previous Kafka-backed producer: callers still
    use `start()` / `send()` / `stop()`, but messages are pushed onto an
    `asyncio.Queue` consumed elsewhere in the same Python process. Removes the
    Kafka broker dependency entirely.
    """

    def __init__(
        self,
        queue: asyncio.Queue | None = None,
        # Legacy kwargs kept so existing call-sites that pass host/port don't
        # break during the migration; values are ignored.
        host: str | None = None,
        port: int | str | None = None,
        **_: object,
    ) -> None:
        self.queue: asyncio.Queue = queue if queue is not None else asyncio.Queue()
        self._started = False

    async def start(self) -> "AsyncProducer":
        self._started = True
        logger.debug("AsyncProducer started (in-process queue)")
        return self

    async def send(
        self,
        value: dict | str,
        topic: str | None = None,
        key: str | None = None,
        timestamp: int | None = None,
    ) -> None:
        """Push a message onto the in-process queue. Returns once enqueued."""
        if not self._started:
            raise RuntimeError("Producer not started. Call await start() first.")
        await self.queue.put(value)

    async def stop(self) -> None:
        self._started = False
        logger.debug("AsyncProducer stopped")
