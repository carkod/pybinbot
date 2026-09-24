import pandas as pd
import pytest

from pybinbot.models.routes import MarketBreadthSeries
from pybinbot.shared import breadth

# 9 bars of extended bearish breadth (-0.30), then a 3-bar recovery ending at
# -0.16 (still <= -0.15, i.e. still extended) on the exact bar the fast/slow
# EMA oscillator turns bullish.
ENTRY_BREADTH = [-0.30] * 9 + [-0.24, -0.20, -0.16]
ENTRY_BREADTH_MA = [-0.24] * 9 + [-0.235, -0.225, -0.21]

# Exact sign-mirror: extended bullish breadth fading back down.
EXIT_BREADTH = [0.30] * 9 + [0.24, 0.20, 0.16]
EXIT_BREADTH_MA = [0.24] * 9 + [0.235, 0.225, 0.21]

TIMESTAMPS = [
    "2026-09-23T07:30:00+00:00",
    "2026-09-23T07:45:00+00:00",
    "2026-09-23T08:00:00+00:00",
    "2026-09-23T08:15:00+00:00",
    "2026-09-23T08:30:00+00:00",
    "2026-09-23T08:45:00+00:00",
    "2026-09-23T09:00:00+00:00",
    "2026-09-23T09:15:00+00:00",
    "2026-09-23T09:30:00+00:00",
    "2026-09-23T09:45:00+00:00",
    "2026-09-23T10:00:00+00:00",
    "2026-09-23T10:15:00+00:00",
]


def make_market_breadth(
    breadth_values: list[float], breadth_ma_values: list[float]
) -> MarketBreadthSeries:
    length = len(breadth_values)
    return MarketBreadthSeries(
        timestamp=TIMESTAMPS[-length:],
        advancers=[500] * length,
        decliners=[500] * length,
        market_breadth=breadth_values,
        market_breadth_ma=breadth_ma_values,
        avg_gain=[0.03] * length,
        avg_loss=[-0.01] * length,
        total_volume=[1_000.0] * length,
        strength_index=[0.1] * length,
    )


def test_breadth_momentum_reversal_detects_bullish_cross_while_extended():
    values, reason = breadth.breadth_momentum_reversal(
        make_market_breadth(ENTRY_BREADTH, ENTRY_BREADTH_MA), direction=1
    )

    assert reason == "breadth_momentum_bullish_reversal"
    assert values is not None
    assert values["market_breadth"] == -0.16
    assert values["previous_breadth_oscillator"] <= 0
    assert values["breadth_oscillator"] > 0


def test_breadth_momentum_reversal_detects_bearish_cross_while_extended():
    values, reason = breadth.breadth_momentum_reversal(
        make_market_breadth(EXIT_BREADTH, EXIT_BREADTH_MA), direction=-1
    )

    assert reason == "breadth_momentum_bearish_reversal"
    assert values is not None
    assert values["market_breadth"] == 0.16
    assert values["previous_breadth_oscillator"] >= 0
    assert values["breadth_oscillator"] < 0


@pytest.mark.parametrize(
    ("breadth_values", "breadth_ma_values", "expected_reason"),
    [
        pytest.param(
            [-0.30] * 12,
            [-0.24] * 12,
            "breadth_momentum_did_not_cross_bullish",
            id="momentum-still-bearish-no-cross",
        ),
        pytest.param(
            [-0.30] * 9 + [-0.24, -0.20, -0.05],
            ENTRY_BREADTH_MA,
            "breadth_not_extended_bearish",
            id="cross-happened-but-no-longer-extended",
        ),
        pytest.param(
            [-0.30] * 5,
            [-0.24] * 5,
            "market_breadth_history_too_short",
            id="history-shorter-than-minimum",
        ),
    ],
)
def test_breadth_momentum_reversal_rejects_invalid_bullish_setups(
    breadth_values: list[float],
    breadth_ma_values: list[float],
    expected_reason: str,
):
    values, reason = breadth.breadth_momentum_reversal(
        make_market_breadth(breadth_values, breadth_ma_values), direction=1
    )

    assert values is None
    assert reason == expected_reason


def test_breadth_momentum_reversal_rejects_missing_series():
    values, reason = breadth.breadth_momentum_reversal(None, direction=1)

    assert values is None
    assert reason == "market_breadth_unavailable"


def make_btc_df(*, uptrend: bool = True, rows: int = 20) -> pd.DataFrame:
    closes = (
        [100.0 + i for i in range(rows)]
        if uptrend
        else [100.0 - i for i in range(rows)]
    )
    return pd.DataFrame({"close": closes})


def test_btc_trend_confirms_uptrend_for_positive_direction():
    result = breadth.btc_trend_confirms(make_btc_df(uptrend=True), direction=1)

    assert result is not None
    close, trend_ema = result
    assert close > trend_ema


def test_btc_trend_confirms_downtrend_for_negative_direction():
    result = breadth.btc_trend_confirms(make_btc_df(uptrend=False), direction=-1)

    assert result is not None
    close, trend_ema = result
    assert close < trend_ema


def test_btc_trend_confirms_rejects_wrong_direction_short_history_and_missing_data():
    assert breadth.btc_trend_confirms(make_btc_df(uptrend=False), direction=1) is None
    assert breadth.btc_trend_confirms(make_btc_df(rows=5), direction=1) is None
    assert breadth.btc_trend_confirms(None, direction=1) is None


def test_breadth_functions_exported_from_top_level_package():
    from pybinbot import breadth_momentum_reversal, btc_trend_confirms

    assert breadth_momentum_reversal is breadth.breadth_momentum_reversal
    assert btc_trend_confirms is breadth.btc_trend_confirms
