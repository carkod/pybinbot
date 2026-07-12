from pybinbot import Candles


def test_partition_closed_candles_uses_explicit_close_timestamps():
    closed = [
        1_780_236_900_000,
        1.0,
        1.1,
        0.9,
        1.05,
        100,
        1_780_237_799_999,
    ]
    current = [
        1_780_237_800_000,
        1.05,
        1.1,
        1.0,
        1.02,
        50,
        1_780_238_699_999,
    ]

    completed, active = Candles.partition_closed_candles(
        [current, ["invalid"], closed],
        now_ms=1_780_238_100_000,
    )

    assert completed == [closed]
    assert active == current


def test_partition_closed_candles_derives_mapping_close_from_interval():
    interval_ms = 15 * 60 * 1000
    now_ms = 1_700_000_000_000
    closed = {
        "open_time": now_ms - 2 * interval_ms,
        "close_time": now_ms - 2 * interval_ms,
        "close": 100.0,
    }
    current = {
        "open_time": now_ms - 5 * 60 * 1000,
        "close_time": now_ms - 5 * 60 * 1000,
        "close": 101.0,
    }

    completed, active = Candles.partition_closed_candles(
        [current, closed],
        now_ms=now_ms,
        interval_ms=interval_ms,
    )

    assert completed == [closed]
    assert active == current


def test_partition_closed_candles_normalizes_seconds():
    closed = [1_700_000_000, 1.0, 1.1, 0.9, 1.05, 100, 1_700_000_899]

    completed, active = Candles.partition_closed_candles(
        [closed],
        now_ms=1_700_000_900_000,
    )

    assert completed == [closed]
    assert active is None
