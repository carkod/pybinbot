import random
import uuid
import logging
from time import sleep, time
from pybinbot.apis.kucoin.market import KucoinMarket
from kucoin_universal_sdk.generate.spot.order.model_add_order_sync_resp import (
    AddOrderSyncResp,
)
from kucoin_universal_sdk.generate.spot.order.model_add_order_sync_req import (
    AddOrderSyncReq,
    AddOrderSyncReqBuilder,
)
from kucoin_universal_sdk.generate.spot.order.model_batch_add_orders_sync_req import (
    BatchAddOrdersSyncReqBuilder,
)
from kucoin_universal_sdk.generate.spot.order.model_batch_add_orders_sync_order_list import (
    BatchAddOrdersSyncOrderList,
)
from kucoin_universal_sdk.generate.spot.order.model_cancel_order_by_order_id_sync_req import (
    CancelOrderByOrderIdSyncReqBuilder,
)
from kucoin_universal_sdk.generate.spot.order.model_get_order_by_order_id_req import (
    GetOrderByOrderIdReqBuilder,
)
from kucoin_universal_sdk.generate.spot.order.model_get_open_orders_req import (
    GetOpenOrdersReqBuilder,
)
from kucoin_universal_sdk.generate.margin.order.model_add_order_req import (
    AddOrderReq,
    AddOrderReqBuilder,
)
from kucoin_universal_sdk.generate.margin.order.model_cancel_order_by_order_id_req import (
    CancelOrderByOrderIdReqBuilder,
)
from kucoin_universal_sdk.generate.margin.order.model_get_order_by_order_id_resp import (
    GetOrderByOrderIdResp,
)
from kucoin_universal_sdk.generate.margin.debit.model_repay_req import (
    RepayReqBuilder,
)
from kucoin_universal_sdk.generate.margin.debit.model_repay_resp import (
    RepayResp,
)
from kucoin_universal_sdk.generate.margin.debit.model_borrow_req import (
    BorrowReqBuilder,
)
from kucoin_universal_sdk.generate.margin.debit.model_borrow_resp import (
    BorrowResp,
)
from kucoin_universal_sdk.generate.account.transfer.model_flex_transfer_req import (
    FlexTransferReqBuilder,
    FlexTransferReq,
)
from kucoin_universal_sdk.generate.account.transfer.model_flex_transfer_resp import (
    FlexTransferResp,
)
from kucoin_universal_sdk.generate.spot.market import (
    GetPartOrderBookReqBuilder,
    GetFullOrderBookReqBuilder,
)
from pybinbot import MarketType


class KucoinOrders(KucoinMarket):
    """
    Convienience wrapper for Kucoin order operations.

    - Kucoin transactions don't immediately return all order details so we need cooldown slee
    """

    TRANSACTION_COOLDOWN_SECONDS = 1

    def __init__(self, key: str, secret: str, passphrase: str):
        super().__init__(key=key, secret=secret, passphrase=passphrase)
        self.client = self.setup_client()
        self.spot_api = self.client.rest_service().get_spot_service().get_market_api()
        self.order_api = self.client.rest_service().get_spot_service().get_order_api()
        self.margin_order_api = (
            self.client.rest_service().get_margin_service().get_order_api()
        )
        self.debit_api = self.client.rest_service().get_margin_service().get_debit_api()
        self.transfer_api = (
            self.client.rest_service().get_account_service().get_transfer_api()
        )

    def get_order_with_retry(
        self,
        symbol: str,
        order_id: str,
        market_type: MarketType = MarketType.SPOT,
        max_retries: int = 5,
    ) -> GetOrderByOrderIdResp | None:
        """
        Get order by ID with exponential backoff retry.
        KuCoin's order data is not immediately available after placement.

        We only consider the order "ready" when:
        - it is no longer active (order.active is False), and
        - id, price and size are all populated.

        """
        get_order_by_order_id = self.get_order_by_order_id
        if market_type == MarketType.MARGIN:
            get_order_by_order_id = self.get_margin_order_by_order_id

        order = get_order_by_order_id(symbol=symbol, order_id=order_id)
        if order and float(order.deal_size) > 0:
            return order

        for attempt in range(max_retries):
            logging.info(f"Attempt {attempt + 1} to get order {order_id}")
            sleep(3 + attempt)
            order = get_order_by_order_id(symbol=symbol, order_id=order_id)

            if order and float(order.deal_size) > 0:
                return order

        return None

    def get_part_order_book(self, symbol: str, size: int):
        request = (
            GetPartOrderBookReqBuilder().set_symbol(symbol).set_size(str(size)).build()
        )
        response = self.spot_api.get_part_order_book(request)
        return response

    def get_full_order_book(self, symbol: str, size: int):
        request = GetFullOrderBookReqBuilder().set_symbol(symbol).build()
        response = self.spot_api.get_full_order_book(request)
        return response

    def simulate_order(
        self,
        symbol: str,
        side: AddOrderSyncReq.SideEnum,
        order_type: AddOrderSyncReq.TypeEnum = AddOrderSyncReq.TypeEnum.LIMIT,
        qty: float = 1,
    ) -> GetOrderByOrderIdResp:
        """
        Fake synchronous order response shaped similarly to add_order_sync.
        Returns a dict echoing inputs and a computed price when missing.
        """
        book_price = self.simple_matching_engine(
            symbol, order_side=(side == AddOrderSyncReq.SideEnum.SELL)
        )
        # fake data
        ts = int(time() * 1000)
        order_id = str(random.randint(1000000000, 9999999999))

        order = GetOrderByOrderIdResp.model_validate(
            {
                "id": order_id,
                "symbol": symbol,
                "op_type": "DEAL",
                "type": order_type.value,
                "side": side.value.lower(),
                "price": str(book_price),
                "size": str(qty),
                "funds": str(float(book_price) * qty),
                "deal_funds": str(float(book_price) * qty),
                "deal_size": str(qty),
                "fee": "0",
                "fee_currency": symbol.split("-")[1],
                "stp": "CN",
                "stop": "",
                "stop_price": "0",
                "time_in_force": AddOrderSyncReq.TimeInForceEnum.GTC.value,
                "post_only": False,
                "hidden": False,
                "iceberg": False,
                "visible_size": "0",
                "cancel_after": 0,
                "channel": "API",
                "client_oid": "",
                "remark": "",
                "tags": "",
                "is_active": False,
                "cancel_exist": False,
                "created_at": ts,
            }
        )
        return order

    def simple_matching_engine(self, symbol: str, order_side: bool) -> float:
        """
        Get top of book price for immediate buy/sell
        this is good for paper trading
        or initial price estimates

        @param: order_side -
            Buy order = get bid prices = False
            Sell order = get ask prices = True
        """
        # Part order book only returns top 1 level at time of writing
        data = self.get_part_order_book(symbol, size=1)
        price = data.bids[0][0] if order_side else data.asks[0][0]
        return price

    def matching_engine(
        self, symbol: str, order_side: bool, base_qty: float = 0
    ) -> float | None:
        """
        Match quantity with available 100% fill order price,
        so that order can immediately buy/sell

        Only use this if we need to find optimal price for given qty

        @param: order_side -
            Buy order = get bid prices = False
            Sell order = get ask prices = True
        """

        book = self.get_full_order_book(symbol, size=10)
        levels = book.asks if order_side else book.bids

        if not levels:
            return None

        remaining = base_qty
        worst_price = None
        best_price = float(levels[0][0])

        if remaining <= 0:
            return best_price

        for price, qty in levels:
            price = float(price)
            qty = float(qty)

            if qty <= 0:
                continue

            fill_qty = min(remaining, qty)
            if fill_qty <= 0:
                continue

            remaining -= fill_qty
            worst_price = price

            if remaining <= 0:
                break

        # Not enough liquidity
        if remaining > 0 or worst_price is None or best_price is None:
            return None

        # Safety check before arithmetic
        if best_price <= 0 or worst_price <= 0:
            return None

        # Hard slippage cap given no market orders
        if order_side is False:
            if (worst_price - best_price) / best_price > 0.002:
                return None
        else:
            if (best_price - worst_price) / best_price > 0.002:
                return None

        return worst_price

    def buy_order(
        self,
        symbol: str,
        qty: float,
        order_type: AddOrderSyncReq.TypeEnum = AddOrderSyncReq.TypeEnum.LIMIT,
    ) -> GetOrderByOrderIdResp:
        """
        Wrapper for Kucoin add order for convenience and consistency with other exchanges.

        Price is not provided so LIMIT orders can be filled immediately using matching engine.

        Because add_order_sync doesn't return enough info for our orders,
        we need to retrieve the order by order id after placing it.
        And because retrieving it is not immediate, we need to sleep delay
        """
        book_price = self.matching_engine(symbol, order_side=False, base_qty=qty)
        builder = (
            AddOrderSyncReqBuilder()
            .set_symbol(symbol)
            .set_side(AddOrderSyncReq.SideEnum.BUY)
            .set_type(order_type)
        )
        # is not None to screen when prices are 0 (rare event)
        if book_price is not None:
            builder = (
                builder.set_price(str(book_price))
                .set_type(AddOrderSyncReq.TypeEnum.LIMIT)
                .set_size(str(qty))
            )
        else:
            book = self.get_full_order_book(symbol, size=1)
            best_ask = float(book.asks[0][0])
            funds = qty * best_ask
            builder = builder.set_type(AddOrderSyncReq.TypeEnum.MARKET).set_funds(
                str(funds)
            )

        req = builder.build()
        order_response = self.order_api.add_order_sync(req)
        # order_response returns incomplete info, retry with backoff
        order = self.get_order_with_retry(
            symbol=symbol, order_id=order_response.order_id
        )
        if order is None:
            raise RuntimeError("Order placement failed after retries")
        return order

    def sell_order(
        self,
        symbol: str,
        qty: float,
        order_type: AddOrderSyncReq.TypeEnum = AddOrderSyncReq.TypeEnum.LIMIT,
    ) -> GetOrderByOrderIdResp:
        """
        Wrapper for KuCoin add order for convenience and consistent interface with other exchanges.

        Price is not provided so LIMIT orders can be filled immediately using matching engine.

        Because add_order_sync doesn't return enough info for our orders,
        we need to retrieve the order by order id after placing it.
        And because retrieving it is not immediate, we need to sleep delay
        """
        # Get optimal fill price for given quantity
        book_price = self.matching_engine(symbol, order_side=True, base_qty=qty)

        builder = (
            AddOrderSyncReqBuilder()
            .set_symbol(symbol)
            .set_side(AddOrderSyncReq.SideEnum.SELL)
            .set_type(order_type)
        )

        # If a valid top-of-book price is available, use LIMIT
        if book_price is not None:
            builder = (
                builder.set_price(str(book_price))
                .set_type(AddOrderSyncReq.TypeEnum.LIMIT)
                .set_size(str(qty))
            )
        else:
            # fallback to MARKET if no price returned (rare)
            book = self.get_full_order_book(symbol, size=1)
            best_bid = float(book.bids[0][0])
            builder = builder.set_type(AddOrderSyncReq.TypeEnum.MARKET).set_funds(
                str(qty * best_bid)
            )

        req = builder.build()
        order_response = self.order_api.add_order_sync(req)

        # Ensure we have the complete order details
        order = self.get_order_with_retry(
            symbol=symbol, order_id=order_response.order_id
        )
        if order is None:
            raise RuntimeError("Sell order placement failed after retries")

        return order

    def batch_add_orders_sync(self, orders: list[dict]) -> AddOrderSyncResp:
        """
        Batch place up to 5 limit orders for the same symbol.
        Each dict in `orders` should contain: symbol, side, type, size, price (for limit), optional fields as per SDK.

        Not usable at the time of writing due to inconsistency with other exchange's interfaces (other exchanges might not support batch orders).
        """
        order_list: list[BatchAddOrdersSyncOrderList] = []
        for o in orders:
            item = BatchAddOrdersSyncOrderList(
                client_oid=o.get("clientOid"),
                symbol=o["symbol"],
                side=(
                    BatchAddOrdersSyncOrderList.SideEnum.BUY
                    if str(o["side"]).lower() == "buy"
                    else BatchAddOrdersSyncOrderList.SideEnum.SELL
                ),
                type=BatchAddOrdersSyncOrderList.TypeEnum.LIMIT,
                size=str(o["size"]),
                price=str(o["price"]) if "price" in o else None,
                time_in_force=BatchAddOrdersSyncOrderList.TimeInForceEnum.GTC,
            )
            order_list.append(item)

        req = BatchAddOrdersSyncReqBuilder().set_order_list(order_list).build()
        return self.order_api.batch_add_orders_sync(req)

    def cancel_order_by_order_id_sync(self, symbol: str, order_id: str):
        req = (
            CancelOrderByOrderIdSyncReqBuilder()
            .set_symbol(symbol)
            .set_order_id(order_id)
            .build()
        )
        return self.order_api.cancel_order_by_order_id_sync(req)

    def get_order_by_order_id(
        self, symbol: str, order_id: str
    ) -> GetOrderByOrderIdResp:
        req = (
            GetOrderByOrderIdReqBuilder()
            .set_symbol(symbol)
            .set_order_id(order_id)
            .build()
        )
        return self.order_api.get_order_by_order_id(req)

    def get_open_orders(self, symbol: str):
        req = GetOpenOrdersReqBuilder().set_symbol(symbol).build()
        return self.order_api.get_open_orders(req)

    # --- Margin (Isolated) operations ---
    def buy_margin_order(
        self,
        symbol: str,
        qty: float,
        order_type: AddOrderReq.TypeEnum = AddOrderReq.TypeEnum.LIMIT,
        price: float = 0,
        time_in_force: AddOrderReq.TimeInForceEnum = AddOrderReq.TimeInForceEnum.GTC,
        client_oid: str | None = None,
        auto_borrow: bool = False,
        auto_repay: bool = False,
    ) -> GetOrderByOrderIdResp:
        builder = (
            AddOrderReqBuilder()
            .set_symbol(symbol)
            .set_side(AddOrderReq.SideEnum.BUY)
            .set_type(order_type)
            .set_size(str(qty))
            .set_time_in_force(time_in_force)
            .set_is_isolated(True)
        )
        if client_oid:
            builder = builder.set_client_oid(client_oid)
        if order_type == AddOrderReq.TypeEnum.LIMIT and price > 0:
            builder = builder.set_price(str(price))
        if auto_borrow:
            builder = builder.set_auto_borrow(True)
        if auto_repay:
            builder = builder.set_auto_repay(True)

        req = builder.build()
        order_response = self.margin_order_api.add_order(req)
        # order_response returns incomplete info, retry with backoff
        order = self.get_order_with_retry(
            symbol=symbol,
            order_id=order_response.order_id,
            market_type=MarketType.MARGIN,
        )
        return order

    def sell_margin_order(
        self,
        symbol: str,
        qty: float,
        order_type: AddOrderReq.TypeEnum = AddOrderReq.TypeEnum.LIMIT,
        price: float = 0,
        time_in_force: AddOrderReq.TimeInForceEnum = AddOrderReq.TimeInForceEnum.GTC,
        client_oid: str | None = None,
        auto_borrow: bool = False,
        auto_repay: bool = False,
    ) -> GetOrderByOrderIdResp:
        builder = (
            AddOrderReqBuilder()
            .set_symbol(symbol)
            .set_side(AddOrderReq.SideEnum.SELL)
            .set_type(order_type)
            .set_size(str(qty))
            .set_time_in_force(time_in_force)
            .set_is_isolated(True)
        )
        if client_oid:
            builder = builder.set_client_oid(client_oid)
        if order_type == AddOrderReq.TypeEnum.LIMIT and price > 0:
            builder = builder.set_price(str(price))
        if auto_borrow:
            builder = builder.set_auto_borrow(True)
        if auto_repay:
            builder = builder.set_auto_repay(True)

        req = builder.build()
        order_response = self.margin_order_api.add_order(req)
        # order_response returns incomplete info, retry with backoff
        order = self.get_order_with_retry(
            symbol=symbol,
            order_id=order_response.order_id,
            market_type=MarketType.MARGIN,
        )
        return order

    def cancel_margin_order_by_order_id(self, symbol: str, order_id: str):
        # Margin API uses cancel by order id req builder from margin.order
        req_cancel = (
            CancelOrderByOrderIdReqBuilder()
            .set_symbol(symbol)
            .set_order_id(order_id)
            .build()
        )
        return self.margin_order_api.cancel_order_by_order_id(req_cancel)

    def get_margin_order_by_order_id(
        self, symbol: str, order_id: str
    ) -> GetOrderByOrderIdResp:
        req = (
            GetOrderByOrderIdReqBuilder()
            .set_symbol(symbol)
            .set_order_id(order_id)
            .build()
        )
        return self.margin_order_api.get_order_by_order_id(req)

    def get_margin_open_orders(self, symbol: str):
        req = GetOpenOrdersReqBuilder().set_symbol(symbol).build()
        return self.margin_order_api.get_open_orders(req)

    def simulate_margin_order(
        self,
        symbol: str,
        side: AddOrderReq.SideEnum,
        order_type: AddOrderReq.TypeEnum = AddOrderReq.TypeEnum.LIMIT,
        qty: float = 1,
    ) -> GetOrderByOrderIdResp:
        """
        Fake isolated margin order response echoing inputs.
        """
        book_price = self.simple_matching_engine(
            symbol, order_side=(side == AddOrderReq.SideEnum.SELL)
        )
        ts = int(time() * 1000)
        order_id = str(random.randint(1000000000, 9999999999))
        order = GetOrderByOrderIdResp.model_validate(
            {
                "id": order_id,
                "symbol": symbol,
                "op_type": "DEAL",
                "type": order_type.value,
                "side": side.value.lower(),
                "price": str(book_price),
                "size": str(qty),
                "funds": str(float(book_price) * qty),
                "deal_funds": str(float(book_price) * qty),
                "deal_size": str(qty),
                "fee": "0",
                "fee_currency": symbol.split("-")[1],
                "stp": "CN",
                "stop": "",
                "stop_price": "0",
                "time_in_force": AddOrderSyncReq.TimeInForceEnum.GTC.value,
                "post_only": False,
                "hidden": False,
                "iceberg": False,
                "visible_size": "0",
                "cancel_after": 0,
                "channel": "API",
                "client_oid": "",
                "remark": "",
                "tags": "",
                "is_active": False,
                "cancel_exist": False,
                "created_at": ts,
            }
        )
        return order

    def repay_margin_loan(
        self,
        asset: str,
        symbol: str,
        amount: float,
    ) -> RepayResp:
        req = (
            RepayReqBuilder()
            .set_currency(asset)
            .set_symbol(symbol)
            .set_size(str(amount))
            .set_is_isolated(True)
            .build()
        )
        return self.debit_api.repay(req)

    def transfer_isolated_margin_to_spot(
        self, asset: str, symbol: str, amount: float
    ) -> FlexTransferResp:
        """
        Transfer funds from isolated margin to spot (main) account.
        `symbol` is the isolated pair like "BTC-USDT".
        """
        client_oid = str(uuid.uuid4())
        req = (
            FlexTransferReqBuilder()
            .set_client_oid(client_oid)
            .set_currency(asset)
            .set_amount(str(amount))
            .set_type(FlexTransferReq.TypeEnum.INTERNAL)
            .set_from_account_type(FlexTransferReq.FromAccountTypeEnum.ISOLATED)
            .set_from_account_tag(symbol)
            .set_to_account_type(FlexTransferReq.ToAccountTypeEnum.MAIN)
            .build()
        )
        return self.transfer_api.flex_transfer(req)

    def transfer_spot_to_isolated_margin(
        self, asset: str, symbol: str, amount: float
    ) -> FlexTransferResp:
        """
        Transfer funds from spot (main) account to isolated margin account.
        `symbol` must be the isolated pair like "BTC-USDT".
        """
        client_oid = str(uuid.uuid4())
        req = (
            FlexTransferReqBuilder()
            .set_client_oid(client_oid)
            .set_currency(asset)
            .set_amount(str(amount))
            .set_type(FlexTransferReq.TypeEnum.INTERNAL)
            .set_from_account_type(FlexTransferReq.FromAccountTypeEnum.MAIN)
            .set_to_account_type(FlexTransferReq.ToAccountTypeEnum.ISOLATED)
            .set_to_account_tag(symbol)
            .build()
        )
        return self.transfer_api.flex_transfer(req)

    def transfer_main_to_trade(self, asset: str, amount: float) -> FlexTransferResp:
        """
        Transfer funds from main to trade (spot) account.
        """
        client_oid = str(uuid.uuid4())
        req = (
            FlexTransferReqBuilder()
            .set_client_oid(client_oid)
            .set_currency(asset)
            .set_amount(str(amount))
            .set_type(FlexTransferReq.TypeEnum.INTERNAL)
            .set_from_account_type(FlexTransferReq.FromAccountTypeEnum.MAIN)
            .set_to_account_type(FlexTransferReq.ToAccountTypeEnum.TRADE)
            .build()
        )
        return self.transfer_api.flex_transfer(req)

    def transfer_trade_to_main(self, asset: str, amount: float) -> FlexTransferResp:
        """
        Transfer funds from trade (spot) account to main.
        """
        client_oid = str(uuid.uuid4())
        req = (
            FlexTransferReqBuilder()
            .set_client_oid(client_oid)
            .set_currency(asset)
            .set_amount(str(amount))
            .set_type(FlexTransferReq.TypeEnum.INTERNAL)
            .set_from_account_type(FlexTransferReq.FromAccountTypeEnum.TRADE)
            .set_to_account_type(FlexTransferReq.ToAccountTypeEnum.MAIN)
            .build()
        )
        return self.transfer_api.flex_transfer(req)

    def create_margin_loan(
        self,
        asset: str,
        symbol: str,
        amount: float,
        is_isolated: bool = True,
    ) -> BorrowResp:
        """
        Create a margin loan (borrow) on KuCoin.
        For isolated margin, pass the trading pair in `symbol` (e.g., "BTC-USDT") and set `is_isolated=True`.
        """
        req = (
            BorrowReqBuilder()
            .set_currency(asset)
            .set_symbol(symbol)
            .set_size(str(amount))
            .set_is_isolated(is_isolated)
            .build()
        )
        return self.debit_api.borrow(req)
