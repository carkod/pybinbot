"""Public API module for the ``pybinbot`` distribution.

This module re-exports the internal ``shared`` and ``models`` packages and
the most commonly used helpers and enums so consumers can simply::

	from pybinbot import round_numbers, ExchangeId

The implementation deliberately avoids importing heavy third-party
libraries at module import time.
"""

import shared  # type: ignore[import]
import models  # type: ignore[import]

from shared import maths, timestamps, enums  # type: ignore[import]
from shared.maths import (  # type: ignore[import]
	supress_trailling,
	round_numbers,
	round_numbers_ceiling,
	round_numbers_floor,
	supress_notation,
	interval_to_millisecs,
	format_ts,
	zero_remainder,
)
from shared.timestamps import (  # type: ignore[import]
	timestamp,
	round_timestamp,
	ts_to_day,
	ms_to_sec,
	sec_to_ms,
	ts_to_humandate,
)
from shared.enums import (  # type: ignore[import]
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

__all__ = [
	"shared",
	"models",
	"maths",
	"timestamps",
	"enums",
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
	# enums and models
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
]
