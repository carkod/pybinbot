import asyncio
import logging
import os

from kucoin_universal_sdk.api import DefaultClient
from kucoin_universal_sdk.generate.spot.spot_public.model_klines_event import (
    KlinesEvent as SpotKlinesEvent,
)
from kucoin_universal_sdk.generate.futures.futures_public.model_klines_event import (
    KlinesEvent as FuturesKlinesEvent,
)
from kucoin_universal_sdk.model.client_option import ClientOptionBuilder
from kucoin_universal_sdk.model.constants import GLOBAL_API_ENDPOINT
from kucoin_universal_sdk.model.websocket_option import WebSocketClientOptionBuilder

from pybinbot.shared.enums import KafkaTopics, KucoinKlineIntervals, MarketType
from pybinbot.models.signals import KlineProduceModel
from pybinbot.streaming.async_producer import AsyncProducer

logger = logging.getLogger(__name__)


class AsyncKucoinWebsocketClient:
    """
    Async KuCoin WebSocket client supporting SPOT and FUTURES via MarketType enum.
    """

    def __init__(
        self, producer: AsyncProducer, market_type: MarketType = MarketType.SPOT
    ):
        self.producer = producer
        self.market_type = market_type
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self._queue_processor_task: asyncio.Task | None = None

        self.interval = KucoinKlineIntervals.FIFTEEN_MINUTES
        self._last_emission: dict[str, int] = {}
        self._emission_cooldown_ms = self.interval.get_ms()

        client_option = (
            ClientOptionBuilder()
            .set_key(os.getenv("KUCOIN_API_KEY", ""))
            .set_secret(os.getenv("KUCOIN_API_SECRET", ""))
            .set_passphrase(os.getenv("KUCOIN_API_PASSPHRASE", ""))
            .set_spot_endpoint(GLOBAL_API_ENDPOINT)
            .set_websocket_client_option(WebSocketClientOptionBuilder().build())
            .build()
        )

        self.client = DefaultClient(client_option)
        ws_service = self.client.ws_service()

        # -------------------------------
        # Market Type Routing
        # -------------------------------
        if self.market_type == MarketType.FUTURES:
            self.ws = ws_service.new_futures_public_ws()
            logger.info("Initialized KuCoin FUTURES websocket")
        else:
            self.ws = ws_service.new_spot_public_ws()
            logger.info("Initialized KuCoin SPOT websocket")

        logger.info("Starting KuCoin websocket connection…")
        self.ws.start()
        logger.info("KuCoin websocket started")

    # -------------------------------------------------------
    # Subscription
    # -------------------------------------------------------

    async def subscribe_klines(self, symbol: str, interval: str):
        await asyncio.sleep(0.1)

        if self.market_type == MarketType.FUTURES:
            self.ws.klines(
                symbol=symbol,
                type=interval,
                callback=self.on_futures_kline,
            )
        else:
            self.ws.klines(
                symbol=symbol,
                type=interval,
                callback=self.on_spot_kline,
            )

        logger.info(f"Subscribed to {symbol} ({self.market_type.name})")

    # -------------------------------------------------------
    # Callbacks
    # -------------------------------------------------------

    def on_spot_kline(self, topic, subject, event: SpotKlinesEvent):
        try:
            if topic.startswith("/market/candles:"):
                self.process_kline_stream(
                    symbol=event.symbol,
                    candles=event.candles,
                )
        except Exception as e:
            logger.error(f"Spot kline error: {e}", exc_info=True)

    def on_futures_kline(self, topic, subject, event: FuturesKlinesEvent):
        try:
            if topic.startswith("/contractMarket/candles:"):
                self.process_kline_stream(
                    symbol=event.symbol,
                    candles=event.candles,
                )
        except Exception as e:
            logger.error(f"Futures kline error: {e}", exc_info=True)

    # -------------------------------------------------------
    # Shared Kline Processing
    # -------------------------------------------------------
    def process_kline_stream(self, symbol: str, candles: list[str]) -> None:
        if not candles or len(candles) < 6 or float(candles[5]) == 0:
            return

        ts = int(candles[0])
        ts_ms = ts * 1000

        last_emit = self._last_emission.get(symbol, 0)
        if ts_ms - last_emit < self._emission_cooldown_ms:
            return

        self._last_emission[symbol] = ts_ms

        kline = KlineProduceModel(
            symbol=symbol,
            open_time=str(ts_ms),
            close_time=str((ts + 60) * 1000),
            open_price=str(candles[1]),
            close_price=str(candles[2]),
            high_price=str(candles[3]),
            low_price=str(candles[4]),
            volume=str(candles[5]),
        )

        try:
            self.message_queue.put_nowait(
                {
                    "symbol": symbol,
                    "json": kline.model_dump_json(),
                    "timestamp": ts_ms,
                }
            )
        except asyncio.QueueFull:
            logger.error(f"Queue full, dropping {symbol}")
        except Exception as e:
            logger.error(f"Queue error: {e}", exc_info=True)

    # -------------------------------------------------------
    # Kafka Async Loop
    # -------------------------------------------------------

    async def _process_message_queue(self) -> None:
        while True:
            kline_data = await self.message_queue.get()
            try:
                await self.producer.send(
                    topic=KafkaTopics.klines_store_topic.value,
                    value=kline_data["json"],
                    key=kline_data["symbol"],
                    timestamp=kline_data["timestamp"],
                )
            finally:
                self.message_queue.task_done()

    async def run_forever(self) -> None:
        self._queue_processor_task = asyncio.create_task(self._process_message_queue())

        while True:
            await asyncio.sleep(1)
