import json
import logging
from aiokafka import AIOKafkaProducer

logger = logging.getLogger(__name__)


class AsyncProducer:
    """Async Kafka producer wrapper using AIOKafkaProducer.

    Provides explicit async lifecycle methods and a simple send API that
    serializes values to JSON.
    """

    def __init__(
        self,
        host: str,
        port: int = 29092,
        partitioner: str = "murmur2",
        linger_ms: int = 5,
        aks: str | int = 1,
        max_in_flight_requests_per_connection: int = 5,
        retry_backoff_ms: int = 100,
        compression_type: str | None = None,
        max_batch_size: int = 8192,
        request_timeout_ms: int = 15000,
        enable_idempotence: bool = False,
    ) -> None:
        super().__init__()
        self._started = False
        self.host = host
        self.port = str(port)
        # this is set to anything random to force it to start clean
        self.partitioner = partitioner
        self.producer = AIOKafkaProducer(
            bootstrap_servers=f"{self.host}:{self.port}",
            linger_ms=linger_ms,
            acks=aks,
            enable_idempotence=enable_idempotence,
            request_timeout_ms=request_timeout_ms,
            value_serializer=self.serialize_value,
            max_batch_size=max_batch_size,
            compression_type=compression_type,
            partitioner=self.partitioner,
            retry_backoff_ms=retry_backoff_ms,
        )

    def serialize_value(self, v):
        """Serialize value to bytes. If already a JSON string, just encode. Otherwise JSON-encode first."""
        if isinstance(v, str):
            return v.encode("utf-8")
        return json.dumps(v).encode("utf-8")

    async def start(self) -> AIOKafkaProducer:
        if self._started:
            assert self.producer is not None
            return self.producer

        await self.producer.start()
        self._started = True
        logger.debug("AIOKafkaProducer started")
        return self.producer

    async def send(
        self, topic: str, value: dict | str, key: str, timestamp: int | None = None
    ) -> None:
        """
        Send a message to Kafka. Value will be JSON serialized.
        """
        if not self._started or not self.producer:
            raise RuntimeError("Producer not started. Call await start() first.")

        logger.debug(
            f"Sending to topic={topic}, key={key}, value_type={type(value).__name__}"
        )

        await self.producer.send_and_wait(
            topic=topic,
            value=value,
            key=str(key).encode("utf-8"),
            timestamp_ms=timestamp,
        )

        logger.debug(f"Successfully sent message to {topic}")

    async def stop(self) -> None:
        if self.producer and self._started:
            await self.producer.stop()
            logger.info("AIOKafkaProducer stopped")
        self.producer = None
        self._started = False
