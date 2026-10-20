from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from kucoin_universal_sdk.generate.futures.order import AddOrderReq
from pybinbot import KucoinFutures, OrderType


def test_conditional_missing_acknowledgement_never_retries_as_unconditional_market():
    api = object.__new__(KucoinFutures)
    api.futures_order_api = SimpleNamespace(
        add_order=Mock(return_value=SimpleNamespace(order_id=None))
    )
    with pytest.raises(RuntimeError, match="market fallback is disabled"):
        api.place_futures_order(
            symbol="TESTUSDTM",
            side=AddOrderReq.SideEnum.SELL,
            size=101,
            margin_mode=None,
            order_type=OrderType.market,
            stop=AddOrderReq.StopEnum.DOWN,
            stop_price=98,
            stop_price_type=AddOrderReq.StopPriceTypeEnum.MARK_PRICE,
            reduce_only=True,
            allow_market_fallback=True,
            client_oid="persisted-before-call",
        )
    api.futures_order_api.add_order.assert_called_once()
    req = api.futures_order_api.add_order.call_args.args[0]
    assert req.client_oid == "persisted-before-call"
    assert req.stop_price == "98"
    assert req.reduce_only is True


def test_fill_history_is_paginated_deduplicated_and_weighted_when_order_price_is_missing():
    api = object.__new__(KucoinFutures)
    api.retrieve_order = Mock(
        return_value=SimpleNamespace(
            filled_size=3, avg_deal_price=None, end_at=0, updated_at=0
        )
    )

    def fill(identifier, size, price, time):
        return SimpleNamespace(
            order_id="order-1",
            trade_id=identifier,
            size=size,
            price=price,
            trade_time=time * 1000000,
            created_at=time,
        )

    a = fill("a", 1, 100, 10)
    b = fill("b", 2, 103, 20)
    api.get_fills = Mock(
        side_effect=[
            SimpleNamespace(items=[a], total_page=2),
            SimpleNamespace(items=[a, b], total_page=2),
        ]
    )
    assert api.get_order_execution("order-1") == (3, 102, 20)
    assert api.get_fills.call_count == 2


def test_sdk_raw_fill_payload_is_decoded_when_typed_items_are_missing():
    from kucoin_universal_sdk.generate.futures.order import GetTradeHistoryResp
    from kucoin_universal_sdk.model.common import RestResponse

    api = object.__new__(KucoinFutures)
    response = GetTradeHistoryResp(
        common_response=RestResponse(
            code="200000",
            data={
                "currentPage": 1,
                "totalPage": 1,
                "items": [{"tradeId": "t1", "orderId": "o1", "size": 2, "price": "98"}],
            },
        )
    )
    api.futures_order_api = SimpleNamespace(get_trade_history=lambda req: response)
    decoded = api.get_fills(order_id="o1")
    assert decoded.items[0].order_id == "o1"
    assert decoded.items[0].price == "98"


def test_incomplete_fill_history_does_not_supply_a_partial_price_for_full_quantity():
    api = object.__new__(KucoinFutures)
    api.retrieve_order = Mock(
        return_value=SimpleNamespace(
            filled_size=3, avg_deal_price=None, end_at=0, updated_at=0
        )
    )
    api.get_fills = Mock(
        return_value=SimpleNamespace(
            items=[
                SimpleNamespace(
                    order_id="order-1",
                    trade_id="a",
                    size=1,
                    price=100,
                    trade_time=10_000_000,
                    created_at=10,
                )
            ],
            total_page=1,
        )
    )
    assert api.get_order_execution("order-1") == (3, 0, 0)


def test_top_gainer_short_rejects_recovery_configuration():
    from pybinbot import BotBase, RecoveryParams

    with pytest.raises(ValueError, match="position sizing without recovery"):
        BotBase(
            pair="TESTUSDTM", name="top_gainer_short", recovery_params=RecoveryParams()
        )
