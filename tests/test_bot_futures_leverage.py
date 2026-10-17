import pytest
from pydantic import ValidationError

from pybinbot import BotBase, BotModel, SignalsConsumer


def test_bot_defaults_to_one_x_without_marking_leverage_as_submitted():
    bot = BotBase(pair="XBTUSDTM")
    assert bot.futures_leverage == 1
    assert "futures_leverage" not in bot.model_fields_set


@pytest.mark.parametrize("leverage", [1, 2, 3, 4, 5])
def test_futures_leverage_survives_signal_serialization_and_bot_model(leverage):
    signal = SignalsConsumer(
        bot_params=BotBase(pair="XBTUSDTM", futures_leverage=leverage)
    )
    restored = SignalsConsumer.model_validate_json(signal.model_dump_json())
    assert restored.bot_params is not None
    assert restored.bot_params.futures_leverage == leverage
    bot = BotModel.model_validate(restored.bot_params.model_dump())
    assert bot.futures_leverage == leverage


@pytest.mark.parametrize("leverage", [0, -1, 6, 100, 1.5, None])
def test_bot_rejects_futures_leverage_outside_whole_one_to_five_range(leverage):
    with pytest.raises(ValidationError):
        BotBase(pair="XBTUSDTM", futures_leverage=leverage)
