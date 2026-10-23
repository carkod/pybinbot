import pytest
from pandas import DataFrame

from pybinbot.shared.price_crossings import price_crossings_six_hours

INTERVAL_MS = 15 * 60 * 1000
NOW_MS = 1_800_000_000_000 // INTERVAL_MS * INTERVAL_MS + 30_000


def candles(closes: list[float]) -> DataFrame:
    end = NOW_MS // INTERVAL_MS * INTERVAL_MS
    start = end - 24 * INTERVAL_MS
    return DataFrame(
        {
            "open_time": [start + i * INTERVAL_MS for i in range(len(closes))],
            "close_time": [
                start + (i + 1) * INTERVAL_MS - 1 for i in range(len(closes))
            ],
            "close": closes,
            "high": closes,
            "low": closes,
        }
    )


@pytest.mark.parametrize(
    "closes,expected",
    [
        ([99.0] * 24, 0),
        ([99.0] * 12 + [101.0] * 12, 1),
        ([99.0] * 8 + [101.0] * 8 + [99.0] * 8, 2),
        ([99.0] * 6 + [101.0] * 6 + [99.0] * 6 + [101.0] * 6, 3),
        ([99.0, 101.0] * 12, 23),
        ([99.0, 100.0, 99.0, 100.0, 101.0, 100.0] * 4, 7),
        ([100.0] * 24, 0),
    ],
)
def test_counts_gap_side_changes_and_ignores_exact_touches(closes, expected):
    assert (
        price_crossings_six_hours(
            candles(closes), 100.0, now_ms=NOW_MS, interval_ms=INTERVAL_MS
        )
        == expected
    )


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "missing_high",
        "missing_low",
        "gap",
        "stale",
        "duplicate",
        "nan",
        "nonpositive",
        "unclosed",
        "nan_high",
        "infinite_low",
        "zero_low",
        "inverted_range",
        "close_above_high",
        "close_below_low",
    ],
)
def test_incomplete_or_invalid_history_has_no_crossing_count(case):
    frame = candles([99.0, 101.0] * 12)
    if case == "missing":
        frame = frame.drop(columns=["close_time"])
    elif case == "missing_high":
        frame = frame.drop(columns=["high"])
    elif case == "missing_low":
        frame = frame.drop(columns=["low"])
    elif case == "gap":
        frame = frame.drop(index=10)
    elif case == "stale":
        frame = frame.iloc[:-1]
    elif case == "duplicate":
        frame.loc[10, "open_time"] = frame.loc[9, "open_time"]
    elif case == "nan":
        frame.loc[10, "close"] = float("nan")
    elif case == "nonpositive":
        frame.loc[10, "close"] = 0
    elif case == "unclosed":
        frame.loc[10, "close_time"] = NOW_MS + INTERVAL_MS
    else:
        field, value = {
            "nan_high": ("high", float("nan")),
            "infinite_low": ("low", float("inf")),
            "zero_low": ("low", 0),
            "inverted_range": ("low", 102),
            "close_above_high": ("high", 98),
            "close_below_low": ("low", 100),
        }[case]
        frame.loc[10, field] = value
    assert (
        price_crossings_six_hours(frame, 100.0, now_ms=NOW_MS, interval_ms=INTERVAL_MS)
        is None
    )


def test_forming_candle_and_older_crossings_do_not_count():
    frame = candles([99.0] * 24 + [101.0])
    end = NOW_MS // INTERVAL_MS * INTERVAL_MS
    frame.loc[-1] = [
        end - 25 * INTERVAL_MS,
        end - 24 * INTERVAL_MS - 1,
        101.0,
        110.0,
        90.0,
    ]
    frame = frame.sort_values("open_time")
    assert (
        price_crossings_six_hours(frame, 100.0, now_ms=NOW_MS, interval_ms=INTERVAL_MS)
        == 0
    )


@pytest.mark.parametrize("interval_ms", [300_000, INTERVAL_MS])
@pytest.mark.parametrize("side", [-1, 1])
def test_wicks_crossing_price_count_once_per_candle(interval_ms, side):
    count = 6 * 60 * 60 * 1000 // interval_ms
    end = NOW_MS // interval_ms * interval_ms
    frame = DataFrame(
        {
            "open_time": [end - (count - i) * interval_ms for i in range(count)],
            "close_time": [
                end - (count - i - 1) * interval_ms - 1 for i in range(count)
            ],
            "close": 100.0 + side,
            "high": 100.0 + side,
            "low": 100.0 + side,
        }
    )
    # Closes never change sides. Three wick excursions must still count.
    for index in [1, 10, count - 1]:
        frame.loc[index, ["high", "low"]] = [102.0, 98.0]
    assert (
        price_crossings_six_hours(frame, 100.0, now_ms=NOW_MS, interval_ms=interval_ms)
        == 3
    )


def test_range_crossing_is_not_double_counted_when_close_changes_side():
    frame = candles([99.0] * 12 + [101.0] * 12)
    frame.loc[12, ["high", "low"]] = [102.0, 98.0]
    assert (
        price_crossings_six_hours(frame, 100.0, now_ms=NOW_MS, interval_ms=INTERVAL_MS)
        == 1
    )


@pytest.mark.parametrize(
    "close,high,low",
    [(99.0, 100.0, 98.0), (101.0, 102.0, 100.0), (100.0, 100.0, 100.0)],
)
def test_exact_high_or_low_touch_does_not_count(close, high, low):
    frame = candles([close] * 24)
    frame["high"] = high
    frame["low"] = low
    assert (
        price_crossings_six_hours(frame, 100.0, now_ms=NOW_MS, interval_ms=INTERVAL_MS)
        == 0
    )


def test_repeated_straddling_candles_count_even_when_the_close_equals_price():
    frame = candles([100.0] * 24)
    frame["high"] = 101.0
    frame["low"] = 99.0
    assert (
        price_crossings_six_hours(frame, 100.0, now_ms=NOW_MS, interval_ms=INTERVAL_MS)
        == 24
    )
