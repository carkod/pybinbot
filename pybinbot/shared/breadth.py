from typing import TYPE_CHECKING

from pybinbot.models.routes import MarketBreadthSeries
from pybinbot.shared.maths import coerce_number, ema
from pybinbot.shared.timestamps import timestamp_sort_key

if TYPE_CHECKING:
    from pandas import DataFrame

DEFAULT_MIN_BREADTH_HISTORY = 12
DEFAULT_BREADTH_FAST_EMA_SPAN = 3
DEFAULT_BREADTH_EXTENSION_THRESHOLD = 0.15

DEFAULT_MIN_TREND_HISTORY = 20
DEFAULT_TREND_EMA_SPAN = 20


def breadth_momentum_reversal(
    breadth: MarketBreadthSeries | None,
    *,
    direction: int,
    min_history: int = DEFAULT_MIN_BREADTH_HISTORY,
    fast_ema_span: int = DEFAULT_BREADTH_FAST_EMA_SPAN,
    extension_threshold: float = DEFAULT_BREADTH_EXTENSION_THRESHOLD,
) -> tuple[dict[str, float] | None, str]:
    """
    Detect a fast/slow EMA oscillator cross on market_breadth while it is
    still extended the opposite way. direction=1 looks for the bullish
    setup (extended bearish breadth turning up); direction=-1 looks for its
    exact mirror, the bearish setup (extended bullish breadth turning down).

    The slow EMA is market_breadth.market_breadth_ma (already computed
    upstream); the fast EMA is computed here from market_breadth.

    Backtested against 52 days of market-breadth, BTC price, and BTC
    funding-rate history for the top_gainer_breadth strategy (binquant) and
    its live-tick mirror (binbot/streaming): shared here so both surfaces
    agree on the same signal rather than maintaining two copies that could
    drift out of calibration.
    """
    label = "bullish" if direction > 0 else "bearish"

    if breadth is None:
        return None, "market_breadth_unavailable"

    points: list[tuple[float, float, float]] = []
    for timestamp, value, trend in zip(
        breadth.timestamp,
        breadth.market_breadth,
        breadth.market_breadth_ma,
        strict=False,
    ):
        timestamp_key = timestamp_sort_key(timestamp)
        breadth_value = coerce_number(value)
        trend_value = coerce_number(trend)
        if (
            timestamp_key is not None
            and breadth_value is not None
            and trend_value is not None
        ):
            points.append((timestamp_key, breadth_value, trend_value))

    if len(points) < min_history:
        return None, "market_breadth_history_too_short"

    points.sort(key=lambda point: point[0])
    breadth_values = [point[1] for point in points]
    slow_ema_values = [point[2] for point in points]
    fast_ema_values = ema(breadth_values, fast_ema_span)

    previous_oscillator = fast_ema_values[-2] - slow_ema_values[-2]
    latest_oscillator = fast_ema_values[-1] - slow_ema_values[-1]
    latest_breadth = breadth_values[-1]

    if not (previous_oscillator * direction <= 0 < latest_oscillator * direction):
        return None, f"breadth_momentum_did_not_cross_{label}"
    opposite_label = "bearish" if direction > 0 else "bullish"
    if latest_breadth * direction > -extension_threshold:
        return None, f"breadth_not_extended_{opposite_label}"

    return {
        "breadth_timestamp": points[-1][0],
        "market_breadth": latest_breadth,
        "market_breadth_fast_ema": fast_ema_values[-1],
        "market_breadth_slow_ema": slow_ema_values[-1],
        "previous_breadth_oscillator": previous_oscillator,
        "breadth_oscillator": latest_oscillator,
    }, f"breadth_momentum_{label}_reversal"


def btc_trend_confirms(
    btc_df: "DataFrame | None",
    *,
    direction: int,
    min_history: int = DEFAULT_MIN_TREND_HISTORY,
    trend_ema_span: int = DEFAULT_TREND_EMA_SPAN,
) -> tuple[float, float] | None:
    """
    direction=1 requires BTC's close above its own trend EMA (uptrend);
    direction=-1 requires it below (downtrend). Returns (close, trend_ema)
    on confirmation, else None.
    """
    if btc_df is None or "close" not in btc_df.columns:
        return None

    closes = btc_df["close"].dropna()
    if len(closes) < min_history:
        return None

    trend_ema = closes.ewm(span=trend_ema_span, adjust=False).mean()
    latest_close = float(closes.iloc[-1])
    latest_trend_ema = float(trend_ema.iloc[-1])
    if (latest_close - latest_trend_ema) * direction <= 0:
        return None

    return latest_close, latest_trend_ema
