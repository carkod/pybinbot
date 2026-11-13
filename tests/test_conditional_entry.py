import pytest
from pydantic import ValidationError

from pybinbot import BotBase, EntryMode, MarketType


@pytest.mark.parametrize(
    "overrides",
    [{}, {"entry_mode": None, "entry_expires_at": None, "entry_price": None}],
)
def test_omitted_or_null_entry_fields_default_to_immediate_and_six_hours(overrides):
    bot = BotBase(pair="XBTUSDTM", created_at=1000, **overrides)
    assert bot.entry_mode == EntryMode.immediate
    assert bot.entry_expires_at == 21_601_000
    assert bot.entry_price is None
    assert bot.model_dump(mode="json")["entry_price"] is None


def test_conditional_entry_serializes_strings_and_preserves_deadline():
    bot = BotBase(
        pair="XBTUSDTM",
        market_type=MarketType.FUTURES,
        entry_mode="conditional_limit",
        entry_price=100,
        entry_expires_at=9000,
    )
    assert bot.model_dump(mode="json")["entry_mode"] == "conditional_limit"
    assert bot.entry_expires_at == 9000


@pytest.mark.parametrize(
    "values",
    [
        {"entry_mode": "unknown"},
        {"entry_mode": "conditional_limit"},
        {"entry_mode": "conditional_limit", "entry_price": None},
        {"entry_mode": "conditional_limit", "entry_price": 0},
        {"entry_mode": "conditional_limit", "entry_price": -1},
        {"entry_mode": "conditional_limit", "entry_price": float("inf")},
        {"entry_expires_at": float("nan")},
    ],
)
def test_invalid_entry_configuration_is_rejected(values):
    with pytest.raises(ValidationError):
        BotBase(pair="XBTUSDTM", market_type=MarketType.FUTURES, **values)
