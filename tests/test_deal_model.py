from pybinbot.models.deal import DealBase


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
