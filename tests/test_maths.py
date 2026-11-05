import pytest

from pybinbot.shared import maths
from pybinbot.shared.enums import Position
from pybinbot.shared.maths import (
    ceil_price_to_tick,
    floor_price_to_tick,
    resolve_tick_size,
    stop_limit_price,
)


def test_coerce_number():
    assert maths.coerce_number("3.14") == 3.14
    assert maths.coerce_number(2) == 2.0
    assert maths.coerce_number(None) is None
    assert maths.coerce_number("not-a-number") is None
    assert maths.coerce_number(float("nan")) is None
    assert maths.coerce_number(float("inf")) is None


def test_coerce_number_is_exported_from_top_level_package():
    from pybinbot import coerce_number

    assert coerce_number("3.14") == 3.14


def test_ema():
    assert maths.ema([1.0], 3) == [1.0]
    values = maths.ema([1.0, 2.0, 3.0, 4.0], 3)
    assert values[0] == 1.0
    assert values[-1] == pytest.approx(3.125)


def test_ema_is_exported_from_top_level_package():
    from pybinbot import ema

    assert ema([1.0, 2.0], 3) == pytest.approx([1.0, 1.5])


def test_ensure_float():
    assert maths.ensure_float("3.14") == 3.14
    assert maths.ensure_float(2) == 2.0
    assert maths.ensure_float(2.5) == 2.5


def test_supress_trailing():
    assert maths.supress_trailing("3.14000") == 3.14
    assert maths.supress_trailing(2.05e-5) == 0.0000205
    assert maths.supress_trailing(3.140000004) == 3.140000004


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


def test_floor_price_to_tick_uses_exact_increment_not_decimal_precision():
    assert floor_price_to_tick(1.063, 0.005) == 1.06


def test_ceil_price_to_tick_uses_exact_increment_not_decimal_precision():
    assert ceil_price_to_tick(1.061, 0.005) == 1.065


@pytest.mark.parametrize("tick_size", [0, -0.01, float("nan")])
def test_floor_price_to_tick_rejects_invalid_tick_size(tick_size):
    with pytest.raises(ValueError, match="Tick size must be positive"):
        floor_price_to_tick(1.0, tick_size)


def test_resolve_tick_size_prefers_exchange_tick_over_precision():
    assert resolve_tick_size("0.005", 2) == 0.005
    assert resolve_tick_size(None, 4) == 0.0001


@pytest.mark.parametrize(
    "position,expected_limit", [(Position.long, 97.51), (Position.short, 102.51)]
)
def test_stop_limit_price_sits_offset_past_stop_on_tick(position, expected_limit):
    stop_price = 102.0 if position == Position.short else 98.0

    assert stop_limit_price(stop_price, position, tick_size=0.01) == expected_limit


def test_stop_limit_price_rounds_away_from_stop_on_coarse_ticks():
    """FHEUSDTM: SL 0.02249 on a 0.00001 tick rests the sell at 0.02237."""
    assert stop_limit_price(0.02249, Position.long, tick_size=0.00001) == 0.02237
    # 1.005 * 1.063 = 1.068315 rounds up to the next 0.005 tick, never down.
    assert stop_limit_price(1.063, Position.short, tick_size=0.005) == 1.07
