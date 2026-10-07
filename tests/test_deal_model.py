import pytest
from pydantic import ValidationError

from pybinbot.models.bot import BotModel
from pybinbot.models.deal import DealBase, PositionSizeOrder
from pybinbot.models.order import DealModel


def test_legacy_sizing_intent_defaults_to_uncertain_submission():
    pending = PositionSizeOrder(
        client_oid="legacy",
        reducing=True,
        quantity_before=100,
        entry_price_before=100,
        requested_qty=25,
        signal_price=95,
    )
    assert pending.submission_phase == "submitting"
    assert pending.not_found_count == 0
    assert pending.not_found_since_ms == 0
    pending.not_found_count = 2
    pending.not_found_since_ms = 100_000
    deal = DealBase(position_size_order=pending)
    assert DealBase.model_validate(deal.model_dump()).position_size_order == pending


@pytest.mark.parametrize("deal_model", [DealBase, DealModel])
def test_position_size_percentage_has_validated_default(deal_model):
    assert deal_model().position_size_pct == 25
    for invalid in (0, -1, 101):
        with pytest.raises(ValidationError):
            deal_model(position_size_pct=invalid)


def test_dynamic_sizing_requires_futures_thresholds_and_trailing_fallback():
    assert BotModel(pair="BTCUSDT").dynamic_position_sizing is False
    parameters = dict(
        pair="XBTUSDTM",
        market_type="FUTURES",
        dynamic_position_sizing=True,
        stop_loss=5,
        take_profit=10,
        trailing_profit=5,
        trailing_deviation=2,
    )
    assert BotModel(**parameters).dynamic_position_sizing is True
    for field, invalid in (
        ("market_type", "SPOT"),
        ("stop_loss", 0),
        ("take_profit", 0),
        ("trailing_deviation", 0),
    ):
        with pytest.raises(ValidationError):
            BotModel(**(parameters | {field: invalid}))


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
