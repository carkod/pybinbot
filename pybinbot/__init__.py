"""Public API for the ``pybinbot`` distribution.

This package exposes a flat, convenient API for common types, enums and
models, while still allowing access to the structured subpackages via
``pybinbot.shared`` and ``pybinbot.models``.
"""

from pybinbot.shared.maths import (
    format_ts,
    interval_to_millisecs,
    round_numbers,
    round_numbers_ceiling,
    round_numbers_floor,
    supress_notation,
    supress_trailling,
    zero_remainder,
)
from pybinbot.shared.timestamps import (
    ms_to_sec,
    round_timestamp,
    sec_to_ms,
    timestamp,
    timestamp_to_datetime,
    ts_to_day,
    ts_to_humandate,
)
from pybinbot.shared.enums import (
    AutotradeSettingsDocument,
    BinanceKlineIntervals,
    BinanceOrderModel,
    CloseConditions,
    DealType,
    ExchangeId,
    KafkaTopics,
    KucoinKlineIntervals,
    MarketDominance,
    OrderSide,
    OrderStatus,
    OrderType,
    QuoteAssets,
    Status,
    Strategy,
    TimeInForce,
    TrendEnum,
    UserRoles,
)
from pybinbot.shared.indicators import Indicators
from pybinbot.shared.heikin_ashi import HeikinAshi
from pybinbot.shared.logging_config import configure_logging
from pybinbot.shared.types import Amount
from pybinbot.models.bot_base import BotBase
from pybinbot.models.deal import DealBase
from pybinbot.models.order import OrderBase
from pybinbot.models.signals import HABollinguerSpread, SignalsConsumer

from . import models, shared

__all__ = [
    # subpackages
    "shared",
    "models",
    # models
    "BotBase",
    "OrderBase",
    "DealBase",
    # misc
    "Amount",
    "configure_logging",
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
    "timestamp_to_datetime",
    # dataframes
    "Indicators",
    "HeikinAshi",
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
    "MarketDominance",
]
