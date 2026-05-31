from decimal import Decimal
from pybinbot import KucoinRest, KucoinKlineIntervals, OrderType, OrderStatus, DealType
from requests import HTTPError, request
from uuid import uuid4
from time import sleep, time
from typing import Literal
from pybinbot.models.order import OrderBase
from kucoin_universal_sdk.generate.futures.order import (
    AddOrderReqBuilder,
    GetOrderByOrderIdReqBuilder,
    GetTradeHistoryReqBuilder,
    GetTradeHistoryResp,
    GetTradeHistoryReq,
)
from kucoin_universal_sdk.generate.futures.order.model_add_order_req import AddOrderReq
from kucoin_universal_sdk.generate.futures.order.model_get_order_by_order_id_resp import (
    GetOrderByOrderIdResp,
)
from kucoin_universal_sdk.generate.account.transfer.model_flex_transfer_req import (
    FlexTransferReq,
    FlexTransferReqBuilder,
)
from kucoin_universal_sdk.generate.futures.market import (
    GetKlinesReqBuilder,
    GetSymbolReqBuilder,
    GetPartOrderBookReqBuilder,
    GetSymbolResp,
)
from kucoin_universal_sdk.generate.account.transfer.model_flex_transfer_resp import (
    FlexTransferResp,
)
from kucoin_universal_sdk.generate.futures.positions.model_modify_margin_leverage_req import (
    ModifyMarginLeverageReqBuilder,
)
from kucoin_universal_sdk.generate.futures.positions.model_modify_margin_leverage_resp import (
    ModifyMarginLeverageResp,
)
from kucoin_universal_sdk.generate.futures.positions.model_get_position_details_req import (
    GetPositionDetailsReqBuilder,
)
from kucoin_universal_sdk.generate.futures.positions.model_get_position_details_resp import (
    GetPositionDetailsResp,
)
from kucoin_universal_sdk.generate.futures.positions import (
    SwitchMarginModeReq,
    SwitchMarginModeReqBuilder,
    SwitchMarginModeResp,
)
from kucoin_universal_sdk.generate.futures.order import (
    CancelAllOrdersV3ReqBuilder,
)
from kucoin_universal_sdk.model.common import RestError
from kucoin_universal_sdk.generate.account.account import (
    GetFuturesAccountReqBuilder,
    GetFuturesAccountResp,
)
from kucoin_universal_sdk.generate.futures.positions.model_get_isolated_margin_risk_limit_resp import (
    GetIsolatedMarginRiskLimitData,
)
from kucoin_universal_sdk.generate.futures.positions.model_get_isolated_margin_risk_limit_req import (
    GetIsolatedMarginRiskLimitReqBuilder,
)
from kucoin_universal_sdk.generate.futures.order.model_get_stop_order_list_resp import (
    GetStopOrderListItems,
)
from kucoin_universal_sdk.generate.futures.order import GetStopOrderListReqBuilder
from kucoin_universal_sdk.generate.futures.order.model_batch_cancel_orders_req import (
    BatchCancelOrdersReqBuilder,
)
from kucoin_universal_sdk.generate.futures.order.model_batch_cancel_orders_resp import (
    BatchCancelOrdersResp,
)
from kucoin_universal_sdk.generate.account.deposit import (
    GetDepositHistoryReq,
    GetDepositHistoryReqBuilder,
    GetDepositHistoryResp,
)

from pybinbot.shared.maths import round_numbers

Kline = list[int | float]
MarginModeName = Literal["ISOLATED", "CROSS"]


class KucoinFutures(KucoinRest):
    """
    Basic Kucoin Futures order endpoints using KucoinApi as base.

    To be replaced in the future with KucoinApi class inheriting from
    Futures API KucoinApi(KucoinFutures) in pybinbot


    ---------------------------------------------------------------------------
    Anti-wick exit execution constants
    Execution-side: band-capped, escalating close orders
    ---------------------------------------------------------------------------
    """

    # Max slippage off the reference price for the first IOC limit step (matches
    # the spot engine's existing 0.2% cap in orders.py:219-225).
    _EXIT_MAX_SLIPPAGE_PCT: float = 0.002
    # How much to widen the cap per escalation step (toward market).
    _EXIT_ESCALATION_STEP_PCT: float = 0.001
    # Absolute worst cap before falling back to a market order (0.2 + 3×0.1 = 0.5%).
    _EXIT_MAX_SLIPPAGE_HARD_PCT: float = 0.005
    # Seconds to wait for each IOC step to be processed before checking fill.
    _EXIT_ESCALATION_SLEEP_S: float = 2.0

    def __init__(self, key: str, secret: str, passphrase: str) -> None:
        self.DEFAULT_LEVERAGE = 3
        self.DEFAULT_MULTIPLIER = 1
        super().__init__(
            key=key,
            secret=secret,
            passphrase=passphrase,
        )
        self.setup_futures_api()

    def get_symbol_info(self, symbol: str) -> GetSymbolResp:
        req = GetSymbolReqBuilder().set_symbol(symbol).build()
        return self.futures_market_api.get_symbol(req)

    def _tick_size(self, symbol: str) -> float:
        """
        Cached in production
        """
        info = self.get_symbol_info(symbol)
        if info.tick_size is None:
            raise ValueError(f"tick_size not available for symbol {symbol}")
        return float(info.tick_size)

    def _calculate_price_precision(self, symbol: str) -> int:
        """
        Decimals needed for Binance price
        @deprecated - use calculate_price_precision
        """
        precision = -1 * (Decimal(str(self._tick_size(symbol))).as_tuple().exponent)
        price_precision = int(precision)
        return price_precision

    def matching_engine(
        self,
        symbol: str,
        size: float,
        side: AddOrderReq.SideEnum,
        reference_price: float | None = None,
    ) -> float | None:
        """Compute a limit price for an immediate reduce-only close.

        Without ``reference_price`` (the legacy path, used for entries):
        - Crosses the spread by exactly 1 tick (best_ask+tick for BUY,
          best_bid-tick for SELL) and returns that price unconditionally.

        With ``reference_price`` (the exit / anti-wick path):
        - Walks book levels to find the price that fills ``size`` contracts.
        - Clamps the crossing price to a ``_EXIT_MAX_SLIPPAGE_PCT`` band off
          ``reference_price`` so we never post into a hollow book / wick.
          SELL: price clamped *up* to ``reference * (1 - pct)``
          BUY:  price clamped *down* to ``reference * (1 + pct)``
        - Returns ``None`` when no level fills ``size`` within the band, so
          callers can escalate (widen the cap) rather than fill into garbage.
        """
        req = (
            GetPartOrderBookReqBuilder()
            .set_size(str(int(size)))
            .set_symbol(symbol)
            .build()
        )
        book = self.futures_market_api.get_full_order_book(req)

        tick = Decimal(str(self._tick_size(symbol)))
        precision = self._calculate_price_precision(symbol)

        if reference_price is None:
            # --- Legacy: 1-tick aggressive cross, no band, always returns a price ---
            if side == AddOrderReq.SideEnum.BUY:
                best_ask = Decimal(book.asks[0][0])
                price = best_ask + tick
            else:
                best_bid = Decimal(book.bids[0][0])
                price = best_bid - tick
            return float(round_numbers(float(price), precision))

        # --- Anti-wick path: walk levels, clamp to slippage band ---
        levels = book.bids if side == AddOrderReq.SideEnum.SELL else book.asks
        if not levels:
            return None

        # Best price is the first level in the book (bids: highest first,
        # asks: lowest first per KuCoin API ordering).
        best_price = float(levels[0][0])
        if best_price <= 0:
            return None

        # 1-tick crossing price from the best level
        if side == AddOrderReq.SideEnum.SELL:
            crossing = best_price - float(tick)
        else:
            crossing = best_price + float(tick)

        # Slippage cap relative to reference price
        slippage_pct = self._EXIT_MAX_SLIPPAGE_PCT
        if side == AddOrderReq.SideEnum.SELL:
            cap = reference_price * (1.0 - slippage_pct)
            # SELL: we receive cap or better (higher) — clamp crossing up to cap
            clamped = max(crossing, cap)
        else:
            cap = reference_price * (1.0 + slippage_pct)
            # BUY: we pay cap or better (lower) — clamp crossing down to cap
            clamped = min(crossing, cap)

        # Walk levels to verify ``size`` contracts can fill at or better than clamped
        remaining = float(size)
        for level_price_raw, level_qty_raw in levels:
            level_price = float(level_price_raw)
            level_qty = float(level_qty_raw)
            if level_qty <= 0:
                continue
            # Stop walking if this level is worse than our clamped price
            if side == AddOrderReq.SideEnum.SELL:
                if level_price < clamped:
                    break  # bids are descending; nothing better below
            else:
                if level_price > clamped:
                    break  # asks are ascending; nothing better above
            remaining -= min(remaining, level_qty)
            if remaining <= 0:
                break

        if remaining > 0:
            # Not enough liquidity within the band
            return None

        return float(round_numbers(clamped, precision))

    def _close_with_escalation(
        self,
        symbol: str,
        side: AddOrderReq.SideEnum,
        qty: float,
        leverage: int,
        reference_price: float,
        reduce_only: bool = True,
    ) -> OrderBase | None:
        """
        Place a bounded, escalating reduce-only close order.

        Posts an IOC limit at the slippage-capped price (``_EXIT_MAX_SLIPPAGE_PCT``
        off ``reference_price``).  If the IOC doesn't fill, widens the cap by
        ``_EXIT_ESCALATION_STEP_PCT`` per step up to ``_EXIT_ESCALATION_MAX_STEPS``
        times, then falls back to a plain market order so the exit is guaranteed.

        This prevents closing into a wick (prices clamped to a sane band) while
        ensuring the position is always eventually closed.
        """
        remaining_qty = float(qty)
        last_order: OrderBase | None = None
        current_pct = self._EXIT_MAX_SLIPPAGE_PCT

        while current_pct <= self._EXIT_MAX_SLIPPAGE_HARD_PCT:
            # Derive price from the slippage band; widen each iteration
            if side == AddOrderReq.SideEnum.SELL:
                limit_price = reference_price * (1.0 - current_pct)
            else:
                limit_price = reference_price * (1.0 + current_pct)

            precision = self._calculate_price_precision(symbol)
            limit_price = float(round_numbers(limit_price, precision))

            order_resp = self.place_futures_order(
                symbol=symbol,
                side=side,
                size=int(remaining_qty),
                price=limit_price,
                leverage=leverage,
                order_type=OrderType.limit,
                reduce_only=reduce_only,
                # IOC: fill what's available immediately, cancel the rest
                time_in_force=AddOrderReq.TimeInForceEnum.IMMEDIATE_OR_CANCEL,
            )

            if order_resp and order_resp.order_id:
                sleep(self._EXIT_ESCALATION_SLEEP_S)
                try:
                    details = self.retrieve_order(str(order_resp.order_id))
                    filled = float(details.filled_size or 0)
                    remaining_qty -= filled
                    if filled > 0:
                        last_order = order_resp
                except RestError:
                    pass

            if remaining_qty <= 0:
                break
            current_pct += self._EXIT_ESCALATION_STEP_PCT

        if remaining_qty > 0:
            # Final guaranteed fallback: plain market order for residual
            market_resp = self.place_futures_order(
                symbol=symbol,
                side=side,
                size=int(remaining_qty),
                leverage=leverage,
                order_type=OrderType.market,
                reduce_only=reduce_only,
            )
            if market_resp:
                last_order = market_resp

        return last_order

    def buy(
        self,
        symbol: str,
        qty: float,
        reduce_only: bool = False,
        reference_price: float | None = None,
    ) -> OrderBase:
        """Place a futures BUY order.

        When ``reference_price`` is provided the order is a reduce-only exit:
        a band-capped IOC limit is posted, escalating in steps toward market
        price to guarantee the position is always closed without chasing a wick.

        Without ``reference_price`` the legacy path is used: a single GTC limit
        priced by the 1-tick crossing engine (used for base-order entries).
        """
        if reference_price is not None:
            return self._close_with_escalation(
                symbol=symbol,
                side=AddOrderReq.SideEnum.BUY,
                qty=qty,
                leverage=int(self.DEFAULT_LEVERAGE),
                reference_price=reference_price,
                reduce_only=reduce_only,
            )

        # --- Legacy entry path ---
        price = self.matching_engine(symbol, size=qty, side=AddOrderReq.SideEnum.BUY)
        order_resp = self.place_futures_order(
            symbol=symbol,
            side=AddOrderReq.SideEnum.BUY,
            size=int(qty),
            price=price,
            leverage=int(self.DEFAULT_LEVERAGE),
            order_type=OrderType.limit,
            reduce_only=reduce_only,
        )
        return order_resp

    def sell(
        self,
        symbol: str,
        qty: float,
        leverage: int = 1,
        reduce_only: bool = False,
        reference_price: float | None = None,
    ) -> OrderBase:
        """Place a futures SELL order.

        When ``reference_price`` is provided the order is a reduce-only exit:
        a band-capped IOC limit is posted, escalating in steps toward market
        price to guarantee the position is always closed without chasing a wick.

        Without ``reference_price`` the legacy path is used (GTC limit + market
        fallback), unchanged from before.
        """
        if reference_price is not None:
            return self._close_with_escalation(
                symbol=symbol,
                side=AddOrderReq.SideEnum.SELL,
                qty=qty,
                leverage=leverage,
                reference_price=reference_price,
                reduce_only=reduce_only,
            )

        # --- Legacy path ---
        price = self.matching_engine(symbol, size=qty, side=AddOrderReq.SideEnum.SELL)
        if price is None:
            raise ValueError(
                f"matching_engine returned no price for {symbol} sell — order book may be empty"
            )
        order_resp = self.place_futures_order(
            symbol=symbol,
            side=AddOrderReq.SideEnum.SELL,
            size=qty,
            leverage=leverage,
            price=price,
            order_type=OrderType.limit,
            reduce_only=reduce_only,
        )

        if not order_resp or not order_resp.order_id:
            order_resp = self.place_futures_order(
                symbol=symbol,
                side=AddOrderReq.SideEnum.SELL,
                size=qty,
                leverage=leverage,
                price=price,
                order_type=OrderType.market,
                reduce_only=reduce_only,
            )

        try:
            order_details = self.retrieve_order(str(order_resp.order_id))
            status = OrderStatus.map_from_kucoin_status(order_details.status.value)
            filled_size = float(order_details.filled_size)
            price_used = float(order_details.avg_deal_price)
            timestamp = order_details.created_at
        except RestError as e:
            if float(e.response.code) == 100001:
                # filler response to wait for completion
                order_details = GetOrderByOrderIdResp(
                    order_id=order_resp.order_id,
                    symbol=symbol,
                    side=AddOrderReq.SideEnum.SELL.value,
                    type=AddOrderReq.TypeEnum.LIMIT.value,
                    price=str(price),
                    size=str(qty),
                    filled_size=str(qty),
                    time_in_force=AddOrderReq.TimeInForceEnum.GOOD_TILL_CANCELED.value,
                )
                status = OrderStatus.NEW
                filled_size = qty
                price_used = price
                timestamp = int(time() * 1000)
            else:
                raise e

        return OrderBase(
            order_id=order_resp.order_id,
            order_type=order_details.type.value,
            pair=symbol,
            timestamp=timestamp,
            order_side=order_details.side.value,
            qty=filled_size,
            price=price_used,
            status=status,
            time_in_force=order_details.time_in_force,
            deal_type=DealType.base_order,
        )

    def get_all_stop_loss_orders(self, symbol: str) -> list[GetStopOrderListItems]:
        """
        Get all open stop loss orders for a symbol.
        """
        req = GetStopOrderListReqBuilder().set_symbol(symbol).build()
        book = self.futures_order_api.get_stop_order_list(req)
        self.check_rate_limit(
            book.common_response.rate_limit.remaining, "get_stop_order_list"
        )
        return book.items

    def cancel_all_futures_orders(self, symbol: str) -> list[str]:
        """Cancel all open futures orders, optionally filtered by symbol.

        Uses the futures Cancel All Orders V3 endpoint, which supports
        an optional symbol filter. This cancels standard (non-stop)
        futures orders in bulk, rather than one order_id at a time.
        """
        request = CancelAllOrdersV3ReqBuilder().set_symbol(symbol).build()
        # We intentionally ignore the detailed response; any errors will
        # be raised via the transport layer.
        response = self.futures_order_api.cancel_all_orders_v3(request)
        return response.cancelled_order_ids

    def retrieve_order(self, order_id: str) -> GetOrderByOrderIdResp:
        """
        Get order status/details by order_id.
        """
        builder = GetOrderByOrderIdReqBuilder().set_order_id(order_id)
        request = builder.build()
        resp = self.futures_order_api.get_order_by_order_id(request)
        return resp

    def transfer_main_to_futures(
        self, currency: str, amount: float
    ) -> FlexTransferResp:
        """
        Transfer funds from main account to futures account.
        """
        client_oid = str(uuid4())
        req = (
            FlexTransferReqBuilder()
            .set_client_oid(client_oid)
            .set_currency(currency)
            .set_amount(str(amount))
            .set_type(FlexTransferReq.TypeEnum.INTERNAL)
            .set_from_account_type(FlexTransferReq.FromAccountTypeEnum.MAIN)
            .set_to_account_type(FlexTransferReq.ToAccountTypeEnum.CONTRACT)
            .build()
        )
        return self.transfer_api.flex_transfer(req)

    def transfer_trade_to_futures(
        self, currency: str, amount: float
    ) -> FlexTransferResp:
        """
        Transfer funds from trade (spot) account to futures account.
        """
        client_oid = str(uuid4())
        req = (
            FlexTransferReqBuilder()
            .set_client_oid(client_oid)
            .set_currency(currency)
            .set_amount(str(amount))
            .set_type(FlexTransferReq.TypeEnum.INTERNAL)
            .set_from_account_type(FlexTransferReq.FromAccountTypeEnum.TRADE)
            .set_to_account_type(FlexTransferReq.ToAccountTypeEnum.CONTRACT)
            .build()
        )
        return self.transfer_api.flex_transfer(req)

    def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[Kline]:
        """
        Get raw klines/candlestick data from KuCoin Futures.

        Returns Binance-compatible format:
        [open_time_ms, open, high, low, close, volume, close_time_ms]
        """

        # --- Interval ---
        interval_enum = KucoinKlineIntervals(interval)
        granularity = interval_enum.to_minutes()  # e.g., 15
        interval_ms = granularity * 60 * 1000

        builder = GetKlinesReqBuilder().set_symbol(symbol).set_granularity(granularity)

        if start_time:
            builder.set_from_(int(start_time))

        if end_time:
            builder.set_to(int(end_time))

        request = builder.build()
        response = self.futures_market_api.get_klines(request)

        # --- Parse response ---
        klines: list[Kline] = []
        for kline in response.data:
            open_time_ms = int(kline[0])
            open_price = float(kline[1])
            high_price = float(kline[2])
            low_price = float(kline[3])
            close_price = float(kline[4])
            volume = float(kline[5])

            close_time_ms = open_time_ms + interval_ms - 1

            klines.append(
                [
                    open_time_ms,
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    volume,
                    close_time_ms,
                ]
            )

        # Safety: ensure sorted
        klines.sort(key=lambda x: x[0])

        return klines[-limit:]

    def get_ui_klines(
        self,
        symbol: str,
        interval: str,
        limit: int | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[Kline]:
        interval_enum = KucoinKlineIntervals(interval)
        is_five_minute_interval = interval_enum == KucoinKlineIntervals.FIVE_MINUTES
        if limit is None:
            limit = 800 if is_five_minute_interval else 500
        if not is_five_minute_interval:
            return self.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit,
                start_time=start_time,
                end_time=end_time,
            )
        interval_minutes = interval_enum.to_minutes()
        interval_ms = interval_minutes * 60 * 1000

        if end_time is None:
            now_ms = int(time() * 1000)
            end_time = now_ms - (now_ms % interval_ms)

        if start_time is None:
            window_multiplier = (
                3
                if interval_minutes == KucoinKlineIntervals.FIVE_MINUTES.to_minutes()
                else 1
            )
            start_time = int(end_time) - (limit * window_multiplier * interval_ms)

        try:
            params: dict[str, str | int] = {
                "type": interval,
                "begin": int(start_time) // 1000,
                "end": int(end_time) // 1000,
                "symbol": symbol,
            }
            response = request(
                method="GET",
                url="https://www.kucoin.com/_api_kumex/kumex-kline/v3/kline/history",
                params=params,
                timeout=15,
            )
            if response.status_code >= 400:
                raise HTTPError(response=response)

            content = response.json()
            if content["code"] != "200":
                raise ValueError(
                    f"Unexpected KuCoin dashboard response code: {content.get('code')}"
                )

            klines: list[Kline] = []
            for kline in content["data"]:
                open_time_ms = int(kline[0]) * 1000
                close_time_ms = open_time_ms + interval_ms - 1
                klines.append(
                    [
                        open_time_ms,
                        float(kline[1]),
                        float(kline[2]),
                        float(kline[3]),
                        float(kline[4]),
                        float(kline[5]),
                        close_time_ms,
                    ]
                )

            klines.sort(key=lambda x: x[0])
            return klines
        except Exception:
            return self.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit,
                start_time=start_time,
                end_time=end_time,
            )

    def set_futures_leverage(
        self, symbol: str, leverage: int
    ) -> ModifyMarginLeverageResp:
        """Set cross-margin leverage for a futures symbol.

        This uses the Kucoin futures positions API `modify_margin_leverage` endpoint.
        """
        req = (
            ModifyMarginLeverageReqBuilder()
            .set_symbol(symbol)
            .set_leverage(str(leverage))
            .build()
        )
        return self.futures_positions_api.modify_margin_leverage(req)

    def set_futures_margin_mode(
        self, symbol: str, margin_mode: SwitchMarginModeReq.MarginModeEnum
    ) -> SwitchMarginModeResp:
        """Set margin mode (ISOLATED or CROSS) for a futures symbol.

        This uses the dedicated futures positions margin-mode endpoint.
        """
        req = (
            SwitchMarginModeReqBuilder()
            .set_symbol(symbol)
            .set_margin_mode(margin_mode)
            .build()
        )
        return self.futures_positions_api.switch_margin_mode(req)

    def get_futures_position(self, symbol: str) -> GetPositionDetailsResp:
        """
        Get current futures position details for a symbol.
        """
        req = GetPositionDetailsReqBuilder().set_symbol(symbol).build()
        resp = self.futures_positions_api.get_position_details(req)
        self.check_rate_limit(
            resp.common_response.rate_limit.remaining, "get_position_details"
        )
        return resp

    def place_futures_order(
        self,
        symbol: str,
        side: AddOrderReq.SideEnum,
        size: float,
        leverage: int = 2,
        order_type: OrderType = OrderType.limit,
        margin_mode: MarginModeName | None = "ISOLATED",
        reduce_only: bool = False,
        close_order: bool = False,
        price: float | None = None,
        stop: AddOrderReq.StopEnum | None = None,
        stop_price: float | None = None,
        stop_price_type: AddOrderReq.StopPriceTypeEnum | None = None,
        time_in_force: AddOrderReq.TimeInForceEnum | None = None,
    ) -> OrderBase:
        """Place a Kucoin futures order using the official SDK.

        Args:
            symbol: Futures contract symbol, e.g. "XBTUSDTM" or "BTC-USDT" depending on market.
            side: "buy" or "sell" (case-insensitive).
            size: Contract size (lot size) as float.
            price: Limit price as float; required for limit orders.
            leverage: Leverage multiplier.
            order_type: Internal OrderType (limit/market).
            margin_mode: Optional margin mode, "ISOLATED" or "CROSS".
            reduce_only: Optional reduce-only flag.
            close_order: Optional close-position flag.
            stop: Optional stop direction (DOWN/UP). If provided, stop_price and
                stop_price_type must also be set.
            stop_price: Optional stop trigger price. Required when stop is set.
            stop_price_type: Optional stop price type (TP/MP/IP). Required when
                stop is set.
            client_oid: Optional client order id; if omitted a UUID is generated.
        """

        client_oid = str(uuid4())

        # Ensure the symbol-level margin mode is set before placing the order.
        if margin_mode is not None:
            # Map the string ("ISOLATED"/"CROSS") to the futures margin-mode enum
            mm_enum = SwitchMarginModeReq.MarginModeEnum[margin_mode]
            self.set_futures_margin_mode(symbol, mm_enum)

        if order_type == OrderType.limit:
            type_enum = AddOrderReq.TypeEnum.LIMIT
        else:
            type_enum = AddOrderReq.TypeEnum.MARKET

        builder = (
            AddOrderReqBuilder()
            .set_client_oid(client_oid)
            .set_symbol(symbol)
            .set_side(side)
            .set_type(type_enum)
        )

        if leverage is not None:
            builder = builder.set_leverage(str(leverage))

        if price is not None:
            builder = builder.set_price(str(price))

        builder = builder.set_size(int(size))

        if reduce_only is not None:
            builder = builder.set_reduce_only(reduce_only)

        if close_order is not None:
            builder = builder.set_close_order(close_order)

        if time_in_force is not None:
            builder = builder.set_time_in_force(time_in_force)

        # Optional stop-loss / take-profit trigger parameters
        if stop is not None:
            if stop_price is None or stop_price_type is None:
                raise ValueError(
                    "stop_price and stop_price_type must be provided when stop is set"
                )
            builder = builder.set_stop(stop)
            builder = builder.set_stop_price(str(stop_price))
            builder = builder.set_stop_price_type(stop_price_type)

        req = builder.build()
        order_resp = self.futures_order_api.add_order(req)

        if not order_resp or not order_resp.order_id:
            order_resp = self.place_futures_order(
                symbol=symbol,
                side=AddOrderReq.SideEnum.BUY,
                size=int(size),
                price=price,
                leverage=int(self.DEFAULT_LEVERAGE),
                order_type=OrderType.market,
                reduce_only=reduce_only,
            )

        # Small delay to allow order to be processed and show up in order details endpoint;
        sleep(5)
        try:
            # Fetch order details as source of truth for status/fills
            order_details = self.retrieve_order(order_resp.order_id)
            # status it he only enum field to help with db consistency
            status = OrderStatus.map_from_kucoin_status(order_details.status.value)
            filled_size = float(order_details.filled_size)
            price_used = float(order_details.avg_deal_price)
            timestamp = order_details.created_at
            order_type_value = order_details.type.value
            time_in_force_value = order_details.time_in_force
            order_side_value = order_details.side.value

        except RestError as e:
            if float(e.response.code) == 100001:
                # Order not yet visible in details endpoint — fall back to
                # the request inputs we already have (do NOT touch order_details,
                # which is unbound here).
                fallback_price = price if price is not None else (stop_price or 0)
                status = OrderStatus.NEW
                filled_size = size
                price_used = fallback_price
                timestamp = int(time() * 1000)
                order_type_value = type_enum.value
                time_in_force_value = (
                    AddOrderReq.TimeInForceEnum.GOOD_TILL_CANCELED.value
                )
                order_side_value = side.value
            else:
                raise e

        return OrderBase(
            order_type=order_type_value,
            time_in_force=time_in_force_value,
            timestamp=timestamp,
            order_id=order_resp.order_id,
            order_side=order_side_value,
            pair=symbol,
            qty=filled_size,
            price=price_used,
            status=status,
            deal_type=DealType.base_order,
        )

    def get_futures_balance(self, fiat: str) -> GetFuturesAccountResp:
        """
        Get futures account balances.
        """
        req = GetFuturesAccountReqBuilder().set_currency(fiat).build()
        return self.futures_account_api.get_futures_account(req)

    def get_max_allowed_leverage(self, symbol: str, position_notional: float) -> int:
        """
        Returns the maximum leverage allowed for the given symbol
        based on intended position size.
        """

        # 1️⃣ Fetch risk limit tiers
        req = GetIsolatedMarginRiskLimitReqBuilder().set_symbol(symbol).build()
        tiers = self.futures_positions_api.get_isolated_margin_risk_limit(req)

        if not tiers.data:
            raise ValueError(f"No isolated margin risk tiers returned for {symbol}")

        # 2️⃣ Sort tiers by min risk limit ascending
        tiers_sorted: list[GetIsolatedMarginRiskLimitData] = sorted(
            tiers.data, key=lambda t: t.min_risk_limit or 0
        )

        # 3️⃣ Find the tier that matches the position size
        for tier in tiers_sorted:
            max_risk = Decimal(str(tier.max_risk_limit or 0))
            min_risk = Decimal(str(tier.min_risk_limit or 0))
            if min_risk <= position_notional <= max_risk:
                # Use initial_margin to compute max allowed leverage
                if tier.initial_margin:
                    max_leverage = int(Decimal("1") / Decimal(str(tier.initial_margin)))
                    return max_leverage
        # Fallback to last tier
        last_tier = tiers_sorted[-1]
        return int(Decimal("1") / Decimal(str(last_tier.initial_margin)))

    def batch_cancel_stop_loss_orders(self, so_ids: list[str]) -> BatchCancelOrdersResp:
        """
        Cancel multiple stop loss orders by their IDs.
        """
        req = BatchCancelOrdersReqBuilder().set_order_ids_list(so_ids).build()
        return self.futures_order_api.batch_cancel_orders(req)

    def get_fills(
        self,
        order_id: str | None = None,
        symbol: str | None = None,
        side: GetTradeHistoryReq.SideEnum | None = None,
        order_type: GetTradeHistoryReq.TypeEnum | None = None,
        trade_types: str | None = None,
        start_at: int | None = None,
        end_at: int | None = None,
        current_page: int | None = None,
        page_size: int | None = None,
    ) -> GetTradeHistoryResp:
        """Fetch trade fills via GET /api/v1/fills."""

        builder = GetTradeHistoryReqBuilder()

        if order_id is not None:
            builder = builder.set_order_id(order_id)
        if symbol is not None:
            builder = builder.set_symbol(symbol)
        if side is not None:
            builder = builder.set_side(side)
        if order_type is not None:
            builder = builder.set_type(order_type)
        if trade_types is not None:
            builder = builder.set_trade_types(trade_types)
        if start_at is not None:
            builder = builder.set_start_at(start_at)
        if end_at is not None:
            builder = builder.set_end_at(end_at)
        if current_page is not None:
            builder = builder.set_current_page(current_page)
        if page_size is not None:
            builder = builder.set_page_size(page_size)

        req = builder.build()
        return self.futures_order_api.get_trade_history(req)

    def get_open_interest(self, symbol: str) -> str:
        """
        Get the current open interest (in lots) for a futures symbol.

        KuCoin does not expose a dedicated /api/v1/contracts/openInterest
        endpoint.  Open interest is returned as part of the contract details
        from GET /api/v1/contracts/{symbol}, so this method wraps
        ``get_symbol_info`` and extracts the ``open_interest`` field.

        Args:
            symbol: Futures contract symbol, e.g. "XBTUSDTM".

        Returns:
            Open interest as a string representing lots.

        Raises:
            ValueError: If open interest data is not available for the symbol.
        """
        info = self.get_symbol_info(symbol)
        if info.open_interest is None:
            raise ValueError(f"open_interest not available for symbol {symbol}")
        return info.open_interest

    def get_deposit_history(
        self,
        currency: str | None = None,
        status: GetDepositHistoryReq.StatusEnum | None = None,
        start_at: int | None = None,
        end_at: int | None = None,
        current_page: int | None = None,
        page_size: int | None = None,
    ) -> GetDepositHistoryResp:
        """
        Get deposit history.

        Args:
            currency: Filter by currency (optional).
            status: Filter by status - PROCESSING, SUCCESS, or FAILURE (optional).
            start_at: Start time in milliseconds (optional).
            end_at: End time in milliseconds (optional).
            current_page: Current request page (optional).
            page_size: Number of results per request, min 10, max 500 (optional).

        Returns:
            GetDepositHistoryResp with paginated deposit history items.
        """
        builder = GetDepositHistoryReqBuilder()

        if currency is not None:
            builder = builder.set_currency(currency)
        if status is not None:
            builder = builder.set_status(status)
        if start_at is not None:
            builder = builder.set_start_at(start_at)
        if end_at is not None:
            builder = builder.set_end_at(end_at)
        if current_page is not None:
            builder = builder.set_current_page(current_page)
        if page_size is not None:
            builder = builder.set_page_size(page_size)

        req = builder.build()
        return self.deposit_api.get_deposit_history(req)
