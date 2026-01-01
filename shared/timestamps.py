from time import time
import math
from shared.maths import round_numbers
from datetime import datetime


def timestamp() -> int:
    ts = time() * 1000
    rounded_ts = round_timestamp(ts)
    return rounded_ts


def round_timestamp(ts: int | float) -> int:
    """
    Round millisecond timestamps to always 13 digits
    this is the universal format that JS and Python accept
    """
    digits = int(math.log10(ts)) + 1
    if digits > 13:
        decimals = digits - 13
        multiplier = 10**decimals
        return int(round_numbers(ts * multiplier, decimals))
    else:
        return int(ts)


def ts_to_day(ts: float | int) -> str:
    """
    Convert timestamp to date (day) format YYYY-MM-DD
    """
    digits = int(math.log10(ts)) + 1
    if digits >= 10:
        ts = ts // pow(10, digits - 10)
    else:
        ts = ts * pow(10, 10 - digits)

    dt_obj = datetime.fromtimestamp(ts)
    b_str_date = datetime.strftime(dt_obj, "%Y-%m-%d")
    return b_str_date


def ms_to_sec(ms: int) -> int:
    """
    JavaScript needs 13 digits (milliseconds)
    for new Date() to parse timestamps
    correctly
    """
    return ms // 1000


def sec_to_ms(sec: int) -> int:
    """
    Python datetime needs 10 digits (seconds)
    to parse dates correctly from timestamps
    """
    return sec * 1000


def ts_to_humandate(ts: int) -> str:
    """
    Convert timestamp to human-readable date
    """
    if len(str(abs(1747852851106))) > 10:
        # if timestamp is in milliseconds
        ts = ts // 1000
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
