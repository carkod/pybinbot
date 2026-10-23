from math import isfinite

from pandas import DataFrame, to_numeric

CHOP_LOOKBACK_HOURS = 6
CHOP_CROSSING_THRESHOLD = 3
CHOP_CROSSING_SCORE_PENALTY = 0.1


def price_crossings_six_hours(
    df: DataFrame | None, current_price: float, *, now_ms: float, interval_ms: int
) -> int | None:
    """Count candle-range and gap crossings of the fixed current price.

    Require consecutive completed candles covering six hours before the
    current bar. Count each candle with low < current_price < high once,
    including wicks. Otherwise count close-to-close changes of side to catch
    gaps across the price. Never count a candle twice or infer the order of
    its high and low. Exact touches preserve the previous closing side.
    Return None for incomplete, stale, or invalid history.
    """
    if (
        not isfinite(current_price)
        or current_price <= 0
        or df is None
        or not {"open_time", "close_time", "high", "low", "close"}.issubset(df.columns)
    ):
        return None

    lookback_ms = CHOP_LOOKBACK_HOURS * 60 * 60 * 1000
    if interval_ms <= 0 or lookback_ms % interval_ms:
        return None

    window_end = int(now_ms // interval_ms) * interval_ms
    window_start = window_end - lookback_ms
    open_times = to_numeric(df["open_time"], errors="coerce")
    close_times = to_numeric(df["close_time"], errors="coerce")
    in_window = (open_times >= window_start) & (open_times < window_end)
    window = df.loc[in_window]
    if open_times.loc[in_window].tolist() != list(
        range(window_start, window_end, interval_ms)
    ):
        return None
    window_close_times = close_times.loc[in_window]
    if not (
        (window_close_times < now_ms)
        & (window_close_times >= open_times.loc[in_window])
        & (window_close_times <= open_times.loc[in_window] + interval_ms)
    ).all():
        return None
    closes = to_numeric(window["close"], errors="coerce")
    highs = to_numeric(window["high"], errors="coerce")
    lows = to_numeric(window["low"], errors="coerce")
    if (
        not closes.map(isfinite).all()
        or not highs.map(isfinite).all()
        or not lows.map(isfinite).all()
        or (lows <= 0).any()
        or (lows > closes).any()
        or (closes > highs).any()
    ):
        return None

    previous_side = 0
    crossings = 0
    for high, low, close in zip(highs, lows, closes, strict=True):
        side = 1 if close > current_price else -1 if close < current_price else 0
        if low < current_price < high:
            crossings += 1
        elif previous_side and side and side != previous_side:
            crossings += 1
        if side:
            previous_side = side
    return crossings
