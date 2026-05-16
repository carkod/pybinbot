import pytest

from pybinbot.models.symbol import SymbolModel


def test_symbol_update_payload_contains_only_passed_fields() -> None:
    payload = SymbolModel.to_update_payload(id="BTCUSDTM", futures_leverage=2)

    assert payload == {"id": "BTCUSDTM", "futures_leverage": 2}


def test_symbol_update_payload_omits_none_values() -> None:
    payload = SymbolModel.to_update_payload(id="BTCUSDTM", active=None)

    assert payload == {"id": "BTCUSDTM"}


def test_symbol_update_payload_validates_model_constraints() -> None:
    with pytest.raises(ValueError, match="less than or equal to 3"):
        SymbolModel.to_update_payload(id="BTCUSDTM", futures_leverage=4)


def test_symbol_update_payload_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        SymbolModel.to_update_payload(symbol="BTCUSDTM")
