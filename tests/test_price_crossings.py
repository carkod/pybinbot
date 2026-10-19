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
            "high": 110.0,
            "low": 90.0,
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
def test_counts_close_side_changes_ignoring_wicks_and_exact_touches(closes, expected):
    assert (
        price_crossings_six_hours(
            candles(closes), 100.0, now_ms=NOW_MS, interval_ms=INTERVAL_MS
        )
        == expected
    )


@pytest.mark.parametrize(
    "case", ["missing", "gap", "stale", "duplicate", "nan", "nonpositive", "unclosed"]
)
def test_incomplete_or_invalid_history_has_no_crossing_count(case):
    frame = candles([99.0, 101.0] * 12)
    if case == "missing":
        frame = frame.drop(columns=["close_time"])
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
    else:
        frame.loc[10, "close_time"] = NOW_MS + INTERVAL_MS
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
