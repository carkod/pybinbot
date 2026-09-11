import pytest
from pydantic import ValidationError

from pybinbot.models.bot import BotModel
from pybinbot.models.deal import DealBase
from pybinbot.models.order import DealModel


def test_current_position_quantity_is_distinct_from_opening_quantity() -> None:
    deal = DealBase(opening_qty=4522, current_position_qty=922)

    assert deal.opening_qty == 4522
    assert deal.current_position_qty == 922
    opening_description = DealBase.model_fields["opening_qty"].description
    current_description = DealBase.model_fields["current_position_qty"].description
    assert opening_description is not None
    assert current_description is not None
    assert "current_position_qty" in opening_description
    assert "opening_qty" in current_description


@pytest.mark.parametrize("deal_model", [DealBase, DealModel])
def test_current_position_quantity_rejects_negative_fractional_values(
    deal_model,
) -> None:
    with pytest.raises(ValidationError):
        deal_model(current_position_qty=-0.5)


@pytest.mark.parametrize("status", ["active", "pending"])
def test_legacy_open_bot_uses_opening_quantity_as_current_quantity(
    status: str,
) -> None:
    bot = BotModel.model_validate(
        {
            "pair": "SAGAUSDTM",
            "status": status,
            "deal": {"opening_qty": 4522},
        }
    )

    assert bot.deal.current_position_qty == 4522


@pytest.mark.parametrize("status", ["active", "pending"])
def test_dump_from_legacy_open_table_uses_opening_quantity(status: str) -> None:
    bot = BotModel.dump_from_table(
        {
            "pair": "SAGAUSDTM",
            "status": status,
            "deal": {"opening_qty": 4522},
        }
    )

    assert bot.deal.current_position_qty == 4522


def test_legacy_completed_bot_defaults_current_quantity_to_flat() -> None:
    bot = BotModel.model_validate(
        {
            "pair": "SAGAUSDTM",
            "status": "completed",
            "deal": {"opening_qty": 4522},
        }
    )

    assert bot.deal.current_position_qty == 0


def test_explicit_flat_quantity_is_not_overwritten_for_active_bot() -> None:
    bot = BotModel.model_validate(
        {
            "pair": "SAGAUSDTM",
            "status": "active",
            "deal": {
                "opening_qty": 4522,
                "current_position_qty": 0,
            },
        }
    )

    assert bot.deal.current_position_qty == 0
