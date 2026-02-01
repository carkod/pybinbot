from kucoin_universal_sdk.generate.spot.market import (
    GetPartOrderBookReqBuilder,
    GetAllSymbolsReqBuilder,
    GetSymbolReqBuilder,
)
from kucoin_universal_sdk.generate.spot.market.model_get_all_symbols_resp import (
    GetAllSymbolsResp,
)
from kucoin_universal_sdk.generate.spot.market.model_get_symbol_resp import (
    GetSymbolResp,
)
from kucoin_universal_sdk.generate.spot.market.model_get_part_order_book_resp import (
    GetPartOrderBookResp,
)
from kucoin_universal_sdk.generate.account.account import (
    GetSpotAccountListReqBuilder,
    GetIsolatedMarginAccountReqBuilder,
)
from kucoin_universal_sdk.generate.account.account.model_get_spot_account_list_resp import (
    GetSpotAccountListResp,
)
from kucoin_universal_sdk.generate.account.account.model_get_isolated_margin_account_resp import (
    GetIsolatedMarginAccountResp,
)
from kucoin_universal_sdk.generate.account.transfer.model_flex_transfer_req import (
    FlexTransferReq,
    FlexTransferReqBuilder,
)
from kucoin_universal_sdk.generate.account.transfer.model_flex_transfer_resp import (
    FlexTransferResp,
)
from uuid import uuid4
from pybinbot.apis.kucoin.orders import KucoinOrders


class KucoinApi(KucoinOrders):
    def __init__(self, key: str, secret: str, passphrase: str):
        super().__init__(key=key, secret=secret, passphrase=passphrase)
        self.account_api = (
            self.client.rest_service().get_account_service().get_account_api()
        )

    def get_all_symbols(self) -> GetAllSymbolsResp:
        request = GetAllSymbolsReqBuilder().build()
        response = self.spot_api.get_all_symbols(request)
        return response

    def get_symbol(self, symbol: str) -> GetSymbolResp:
        """
        Get single symbol data
        """
        request = GetSymbolReqBuilder().set_symbol(symbol).build()
        response = self.spot_api.get_symbol(request)
        return response

    def get_ticker_price(self, symbol: str) -> float:
        request = GetPartOrderBookReqBuilder().set_symbol(symbol).set_size("1").build()
        response = self.spot_api.get_ticker(request)
        return float(response.price)

    def get_account_balance(self) -> dict[str, dict[str, float]]:
        """
        Aggregate all balances from all account types (spot, main, trade, margin, futures).

        The right data shape for Kucion should be provided by
        get_account_balance_by_type method.

        However, this method provides a normalized version for backwards compatibility (Binance) and consistency with current balances table.

        Returns a dict:
            {
                asset:
                    {
                        total: float,
                        breakdown:
                            {
                                    account_type: float, ...
                            }
                    }
            }
        """
        spot_request = GetSpotAccountListReqBuilder().build()
        all_accounts = self.account_api.get_spot_account_list(spot_request)
        balance_items = dict()
        for item in all_accounts.data:
            if float(item.balance) > 0:
                balance_items[item.currency] = {
                    "balance": float(item.balance),
                    "free": float(item.available),
                    "locked": float(item.holds),
                }

        margin_request = GetIsolatedMarginAccountReqBuilder().build()
        margin_accounts = self.account_api.get_isolated_margin_account(margin_request)
        if float(margin_accounts.total_asset_of_quote_currency) > 0:
            balance_items["USDT"]["balance"] += float(
                margin_accounts.total_asset_of_quote_currency
            )

        return balance_items

    def get_account_balance_by_type(self) -> dict[str, dict[str, dict[str, float]]]:
        """
        Get balances grouped by account type.
        Returns:
            {
                'MAIN': {'USDT': {...}, 'BTC': {...}, ...},
                'TRADE': {'USDT': {...}, ...},
                'MARGIN': {...},
                ...
            }
        Each currency has: balance (total), available, holds
        """
        spot_request = GetSpotAccountListReqBuilder().build()
        all_accounts = self.account_api.get_spot_account_list(spot_request)

        balance_by_type: dict[str, dict[str, dict[str, float]]] = {}
        for item in all_accounts.data:
            if float(item.balance) > 0:
                account_type = item.type  # MAIN, TRADE, MARGIN, etc.
                if account_type not in balance_by_type:
                    balance_by_type[account_type] = {}
                balance_by_type[account_type][item.currency] = {
                    "balance": float(item.balance),
                    "available": float(item.available),
                    "holds": float(item.holds),
                }

        return balance_by_type

    def get_single_spot_balance(self, asset: str) -> float:
        spot_request = GetSpotAccountListReqBuilder().build()
        all_accounts = self.account_api.get_spot_account_list(spot_request)
        total_balance = 0.0
        for item in all_accounts.data:
            if item.currency == asset:
                return float(item.balance)

        return total_balance

    def get_isolated_balance(self, symbol: str) -> GetIsolatedMarginAccountResp:
        request = GetIsolatedMarginAccountReqBuilder().set_symbol(symbol).build()
        response = self.account_api.get_isolated_margin_account(request)
        return response

    def transfer_isolated_margin_to_spot(
        self, asset: str, symbol: str, amount: float
    ) -> FlexTransferResp:
        """
        Transfer funds from isolated margin to spot (main) account.
        `symbol` is the isolated pair like "BTC-USDT".
        """
        client_oid = str(uuid4())
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
        client_oid = str(uuid4())
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
        client_oid = str(uuid4())
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
        client_oid = str(uuid4())
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
