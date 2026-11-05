import math
import re
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from datetime import datetime
from typing import Any, cast

from pybinbot.shared.enums import Position

# Native stop-limit: after the trigger, the exchange rests a reduce-only limit
# this far past the stop price, so a fill never goes deeper into a wick.
STOP_LIMIT_OFFSET_RATIO = 0.005  # 0.5% of the stop price


def coerce_number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def ema(values: list[float], span: int) -> list[float]:
    """Exponential moving average, seeded with the series' first value."""
    alpha = 2 / (span + 1)
    ema_values = [values[0]]
    for value in values[1:]:
        ema_values.append(alpha * value + (1 - alpha) * ema_values[-1])
    return ema_values


def ensure_float(value: str | int | float) -> float:
    if isinstance(value, str) or isinstance(value, int):
        return float(value)

    return value


def supress_trailing(value: str | float | int) -> float:
    """
    Supress trailing 0s without changing the numeric value.

    Also attempts to normalise away scientific notation for small
    numbers while preserving the original value.
    """
    # Use Decimal(str(value)) to avoid binary float rounding issues
    dec = Decimal(str(value))
    # Normalise to remove redundant trailing zeros while preserving value
    dec = dec.normalize()
    return float(dec)


def round_numbers(value: float | int, decimals=6) -> float | int:
    decimal_points = 10 ** int(decimals)
    number = float(value)
    result = math.floor(number * decimal_points) / decimal_points
    if decimals == 0:
        result = int(result)
    return result


def round_numbers_ceiling(value, decimals=6):
    decimal_points = 10 ** int(decimals)
    number = float(value)
    result = math.ceil(number * decimal_points) / decimal_points
    if decimals == 0:
        result = int(result)
    return float(result)


def round_numbers_floor(value, decimals=6):
    decimal_points = 10 ** int(decimals)
    number = float(value)
    result = math.floor(number * decimal_points) / decimal_points
    if decimals == 0:
        result = int(result)
    return float(result)


def resolve_tick_size(tick_size: float | str | None, price_precision: int) -> float:
    """Exchange tick size, or one unit of ``price_precision`` when omitted."""
    if tick_size is None:
        return 10**-price_precision
    return float(tick_size)


def floor_price_to_tick(price: float, tick_size: float) -> float:
    """Floor a positive price to an exact exchange tick boundary."""
    if not math.isfinite(price) or price <= 0:
        raise ValueError("Price must be positive")
    if not math.isfinite(tick_size) or tick_size <= 0:
        raise ValueError("Tick size must be positive")

    price_decimal = Decimal(str(price))
    tick_decimal = Decimal(str(tick_size))
    ticks = (price_decimal / tick_decimal).to_integral_value(rounding=ROUND_FLOOR)
    quantized_price = ticks * tick_decimal
    if quantized_price <= 0:
        raise ValueError("Price is below one exchange tick")
    return float(quantized_price)


def ceil_price_to_tick(price: float, tick_size: float) -> float:
    """Ceil a positive price to an exact exchange tick boundary."""
    if not math.isfinite(price) or price <= 0:
        raise ValueError("Price must be positive")
    if not math.isfinite(tick_size) or tick_size <= 0:
        raise ValueError("Tick size must be positive")

    price_decimal = Decimal(str(price))
    tick_decimal = Decimal(str(tick_size))
    ticks = (price_decimal / tick_decimal).to_integral_value(rounding=ROUND_CEILING)
    return float(ticks * tick_decimal)


def stop_limit_price(
    stop_price: float,
    position: Position,
    tick_size: float,
    offset_ratio: float = STOP_LIMIT_OFFSET_RATIO,
) -> float:
    """Worst fill price for a native stop-limit close at ``stop_price``.

    Longs close with a sell below the stop, shorts with a buy above it.
    Rounded away from the stop so the limit is never tighter than
    ``offset_ratio``.
    """
    if position == Position.short:
        return ceil_price_to_tick(stop_price * (1 + offset_ratio), tick_size)
    return floor_price_to_tick(stop_price * (1 - offset_ratio), tick_size)


def supress_notation(num: float, precision: int = 0) -> str:
    """
    Supress scientific notation and return a fixed-point string.

    Examples
    -------
    8e-5  -> "0.00008" (precision=5)
    123.456, precision=2 -> "123.46"
    """
    dec = Decimal(str(num))

    if precision >= 0:
        # Quantize to the requested number of decimal places using
        # Decimal's standard rounding (half even by default).
        quant = Decimal(1).scaleb(-precision)  # 10**-precision
        dec = dec.quantize(quant)
        decimal_points = precision
    else:
        # Let Decimal decide the scale, then format with all significant
        # decimal places.
        dec = dec.normalize()
        exp = cast(int, dec.as_tuple().exponent)
        decimal_points = -exp

    return f"{dec:.{decimal_points}f}"


def interval_to_millisecs(interval: str) -> int:
    time, notation = re.findall(r"[A-Za-z]+|\d+", interval)
    if notation == "m":
        # minutes
        return int(time) * 60 * 1000

    if notation == "h":
        # hours
        return int(time) * 60 * 60 * 1000

    if notation == "d":
        # day
        return int(time) * 24 * 60 * 60 * 1000

    if notation == "w":
        # weeks
        return int(time) * 5 * 24 * 60 * 60 * 1000

    if notation == "M":
        # month
        return int(time) * 30 * 24 * 60 * 60 * 1000

    return 0


def format_ts(time: datetime) -> str:
    """
    Central place to format datetime
    to human-readable date
    """
    return time.strftime("%Y-%m-%d %H:%M:%S.%f")


def zero_remainder(x):
    number = x

    while True:
        if number % x == 0:
            return number
        else:
            number += x
