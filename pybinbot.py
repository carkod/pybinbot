"""Public API module for the ``pybinbot`` distribution.

This module re-exports the internal ``shared`` and ``models`` packages and
the most commonly used helpers and enums so consumers can simply::

        from pybinbot import round_numbers, ExchangeId

The implementation deliberately avoids importing heavy third-party
libraries at module import time.
"""

from shared.maths import (
    supress_trailling,
    round_numbers,
    round_numbers_ceiling,
    round_numbers_floor,
    supress_notation,
    interval_to_millisecs,
    format_ts,
    zero_remainder,
)
from shared.timestamps import (
    timestamp,
    round_timestamp,
    ts_to_day,
    ms_to_sec,
    sec_to_ms,
    ts_to_humandate,
)
from shared.enums import (
    CloseConditions,
    KafkaTopics,
    DealType,
    BinanceOrderModel,
    Status,
    Strategy,
    OrderType,
    TimeInForce,
    OrderSide,
    OrderStatus,
    TrendEnum,
    BinanceKlineIntervals,
    KucoinKlineIntervals,
    AutotradeSettingsDocument,
    UserRoles,
    QuoteAssets,
    ExchangeId,
)
from shared.types import Amount
from models.bot_base import BotBase
from models.order import OrderBase
from models.deal import DealBase
from models.signals import HABollinguerSpread, SignalsConsumer

__all__ = [
    # models
    "BotBase",
    "OrderBase",
    "DealBase",
    # custom types
    "Amount",
    # maths helpers
    "supress_trailling",
    "round_numbers",
    "round_numbers_ceiling",
    "round_numbers_floor",
    "supress_notation",
    "interval_to_millisecs",
    "format_ts",
    "zero_remainder",
    # timestamp helpers
    "timestamp",
    "round_timestamp",
    "ts_to_day",
    "ms_to_sec",
    "sec_to_ms",
    "ts_to_humandate",
    # enums
    "CloseConditions",
    "KafkaTopics",
    "DealType",
    "BinanceOrderModel",
    "Status",
    "Strategy",
    "OrderType",
    "TimeInForce",
    "OrderSide",
    "OrderStatus",
    "TrendEnum",
    "BinanceKlineIntervals",
    "KucoinKlineIntervals",
    "AutotradeSettingsDocument",
    "UserRoles",
    "QuoteAssets",
    "ExchangeId",
    "HABollinguerSpread",
    "SignalsConsumer",
]
