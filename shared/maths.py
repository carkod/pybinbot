import math
import re
import os
from decimal import Decimal
from datetime import datetime
from typing import cast
from zoneinfo import ZoneInfo


def ensure_float(value: str | int | float) -> float:
    if isinstance(value, str) or isinstance(value, int):
        return float(value)

    return value


def supress_trailling(value: str | float | int) -> float:
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


def timestamp_to_datetime(timestamp: str | int) -> str:
    """
    Convert a timestamp in milliseconds to seconds
    to match expectation of datetime
    Then convert to a human readable format.

    Parameters
    ----------
    timestamp : str | int
        The timestamp in milliseconds. Always in London timezone
        to avoid inconsistencies across environments (Github, prod, local)
    """
    format = "%Y-%m-%d %H:%M:%S"
    timestamp = int(round_numbers_ceiling(int(timestamp) / 1000, 0))
    dt = datetime.fromtimestamp(
        timestamp, tz=ZoneInfo(os.getenv("TZ", "Europe/London"))
    )
    return dt.strftime(format)
