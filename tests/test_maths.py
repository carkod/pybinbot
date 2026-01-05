from pybinbot.shared import maths


def test_ensure_float():
    assert maths.ensure_float("3.14") == 3.14
    assert maths.ensure_float(2) == 2.0
    assert maths.ensure_float(2.5) == 2.5


def test_supress_trailling():
    assert maths.supress_trailling("3.14000") == 3.14
    assert maths.supress_trailling(2.05e-5) == 0.0000205
    assert maths.supress_trailling(3.140000004) == 3.140000004


def test_round_numbers():
    assert maths.round_numbers(3.14159, 2) == 3.14
    assert maths.round_numbers(3.999, 0) == 3
    assert maths.round_numbers(2, 3) == 2.0


def test_round_numbers_ceiling():
    assert maths.round_numbers_ceiling(3.14159, 2) == 3.15
    assert maths.round_numbers_ceiling(3.0001, 0) == 4.0


def test_round_numbers_floor():
    assert maths.round_numbers_floor(3.14159, 2) == 3.14
    assert maths.round_numbers_floor(3.999, 0) == 3.0


def test_supress_notation():
    assert maths.supress_notation(8e-5, 5) == "0.00008"
    assert maths.supress_notation(123.456, 2) == "123.46"


def test_interval_to_millisecs():
    assert maths.interval_to_millisecs("5m") == 300000
    assert maths.interval_to_millisecs("2h") == 7200000
    assert maths.interval_to_millisecs("1d") == 86400000
    assert maths.interval_to_millisecs("1w") == 432000000
    assert maths.interval_to_millisecs("1M") == 2592000000
    assert maths.interval_to_millisecs("10x") == 0


def test_format_ts():
    from datetime import datetime

    dt = datetime(2024, 1, 2, 3, 4, 5, 6789)
    assert maths.format_ts(dt).startswith("2024-01-02 03:04:05.")


def test_zero_remainder():
    assert maths.zero_remainder(5) == 5
    assert maths.zero_remainder(7) == 7
