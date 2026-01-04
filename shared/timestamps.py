import os
from time import time
import math
from zoneinfo import ZoneInfo
from shared.maths import round_numbers_ceiling
from datetime import datetime

format = "%Y-%m-%d %H:%M:%S"

def timestamp() -> int:
    ts = time() * 1000
    rounded_ts = round_timestamp(ts)
    return rounded_ts


def round_timestamp(ts: int | float) -> int:
    """
    Round (or trim) millisecond timestamps to at most 13 digits.

    For realistic millisecond timestamps (13 digits) this is a no-op.
    For larger integers, extra lower-order digits are discarded so that
    the result has exactly 13 digits.
    """
    ts_int = int(ts)
    digits = int(math.log10(ts_int)) + 1 if ts_int > 0 else 1

    if digits > 13:
        # Drop extra lower-order digits to get back to 13 digits.
        decimals = digits - 13
        factor = 10**decimals
        return ts_int // factor
    else:
        return ts_int


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
    b_str_date = datetime.strftime(dt_obj, format)
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
    """Convert timestamp to human-readable date.

    Accepts either seconds (10 digits) or milliseconds (13 digits) and
    normalises to seconds for ``datetime.fromtimestamp``.
    """
    if len(str(abs(ts))) > 10:
        # if timestamp is in milliseconds
        ts = ts // 1000
    return datetime.fromtimestamp(ts).strftime(format)


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
    timestamp = int(round_numbers_ceiling(int(timestamp) / 1000, 0))
    dt = datetime.fromtimestamp(
        timestamp, tz=ZoneInfo(os.getenv("TZ", "Europe/London"))
    )
    return dt.strftime(format)
    