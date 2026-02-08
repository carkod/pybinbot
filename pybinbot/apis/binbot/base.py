from aiohttp import ClientSession
from pybinbot import ExchangeId, Status
from requests import Session
from pybinbot import BinanceApi, handle_binance_errors, aio_response_handler


class BinbotApi:
    def __init__(self, base_url: str) -> None:
        """
        API endpoints on this project itself
        includes Binance Api
        """

        if not base_url:
            raise ValueError("Base URL must be provided for BinbotApi")

        bb_base_url = base_url

        self.bb_symbols_raw = f"{bb_base_url}/account/symbols"
        self.bb_bot_url = f"{bb_base_url}/bot"
        self.bb_activate_bot_url = f"{bb_base_url}/bot/activate"
        self.bb_gainers_losers = f"{bb_base_url}/account/gainers-losers"
        self.bb_market_domination = f"{bb_base_url}/charts/market-domination"
        self.bb_top_gainers = f"{bb_base_url}/charts/top-gainers"
        self.bb_top_losers = f"{bb_base_url}/charts/top-losers"
        self.bb_timeseries_url = f"{bb_base_url}/charts/timeseries"
        self.bb_adr_series_url = f"{bb_base_url}/charts/adr-series"

        # Trade operations
        self.bb_buy_order_url = f"{bb_base_url}/order/buy"
        self.bb_tp_buy_order_url = f"{bb_base_url}/order/buy/take-profit"
        self.bb_buy_market_order_url = f"{bb_base_url}/order/buy/market"
        self.bb_sell_order_url = f"{bb_base_url}/order/sell"
        self.bb_tp_sell_order_url = f"{bb_base_url}/order/sell/take-profit"
        self.bb_sell_market_order_url = f"{bb_base_url}/order/sell/market"
        self.bb_opened_orders_url = f"{bb_base_url}/order/open"
        self.bb_close_order_url = f"{bb_base_url}/order/close"
        self.bb_stop_buy_order_url = f"{bb_base_url}/order/buy/stop-limit"
        self.bb_stop_sell_order_url = f"{bb_base_url}/order/sell/stop-limit"
        self.bb_submit_errors = f"{bb_base_url}/bot/errors"
        self.bb_pt_submit_errors_url = f"{bb_base_url}/paper-trading/errors"
        self.bb_liquidation_url = f"{bb_base_url}/account/one-click-liquidation"

        # balances
        self.bb_balance_url = f"{bb_base_url}/account/balance"
        self.bb_balance_series_url = f"{bb_base_url}/account/balance/series"
        self.bb_kucoin_balance_url = f"{bb_base_url}/account/kucoin-balance"

        # research
        self.bb_autotrade_settings_url = f"{bb_base_url}/autotrade-settings/bots"
        self.bb_blacklist_url = f"{bb_base_url}/research/blacklist"
        self.bb_symbols = f"{bb_base_url}/symbols"
        self.bb_one_symbol_url = f"{bb_base_url}/symbol"

        # bots
        self.bb_active_pairs = f"{bb_base_url}/bot/active-pairs"

        # paper trading
        self.bb_test_bot_url = f"{bb_base_url}/paper-trading"
        self.bb_paper_trading_url = f"{bb_base_url}/paper-trading"
        self.bb_activate_test_bot_url = f"{bb_base_url}/paper-trading/activate"
        self.bb_paper_trading_activate_url = f"{bb_base_url}/paper-trading/activate"
        self.bb_paper_trading_deactivate_url = f"{bb_base_url}/paper-trading/deactivate"
        self.bb_test_bot_active_list = f"{bb_base_url}/paper-trading/active-list"
        self.bb_test_autotrade_url = f"{bb_base_url}/autotrade-settings/paper-trading"
        self.bb_test_active_pairs = f"{bb_base_url}/paper-trading/active-pairs"

    def request(self, url, method="GET", session: Session = Session(), **kwargs):
        res = session.request(url=url, method=method, **kwargs)
        data = handle_binance_errors(res)
        return data

    async def fetch(self, url, method="GET", **kwargs):
        """
        Async HTTP client/server for asyncio
        that replaces requests library
        """
        async with ClientSession() as session:
            async with session.request(method=method, url=url, **kwargs) as response:
                data = await aio_response_handler(response)
                return data

    def get_symbols(self) -> list[dict]:
        response = self.request(url=self.bb_symbols)
        return response["data"]

    def get_single_symbol(self, symbol: str) -> dict:
        response = self.request(url=f"{self.bb_one_symbol_url}/{symbol}")
        return response["data"]

    async def get_market_breadth(self, size=400):
        """
        Get market breadth data
        """
        response = await self.fetch(url=self.bb_adr_series_url, params={"size": size})
        if "data" in response:
            return response["data"]
        return None

    def get_latest_btc_price(self):
        binance_api = BinanceApi()
        # Get 24hr last BTCUSDC
        btc_ticker_24 = binance_api.get_ticker_price("BTCUSDC")
        self.btc_change_perc = float(btc_ticker_24["priceChangePercent"])
        return self.btc_change_perc

    def post_error(self, msg):
        data = self.request(
            method="PUT", url=self.bb_autotrade_settings_url, json={"system_logs": msg}
        )
        return data

    def get_test_autotrade_settings(self):
        data = self.request(url=self.bb_test_autotrade_url)
        return data["data"]

    def get_autotrade_settings(self) -> dict:
        data = self.request(url=self.bb_autotrade_settings_url)
        return data["data"]

    def get_bots_by_status(
        self,
        start_date,
        end_date,
        collection_name="bots",
        status=Status.active,
    ):
        url = self.bb_bot_url
        if collection_name == "paper_trading":
            url = self.bb_test_bot_url

        data = self.request(
            url=url,
            params={
                "status": status.value,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        return data["data"]

    def submit_bot_event_logs(self, bot_id, message):
        data = self.request(
            url=f"{self.bb_submit_errors}/{bot_id}",
            method="POST",
            json={"errors": message},
        )
        return data

    def submit_paper_trading_event_logs(self, bot_id, message):
        data = self.request(
            url=f"{self.bb_pt_submit_errors_url}/{bot_id}",
            method="POST",
            json={"errors": message},
        )
        return data

    def add_to_blacklist(self, symbol, reason=None):
        payload = {"symbol": symbol, "reason": reason}
        data = self.request(url=self.bb_blacklist_url, method="POST", json=payload)
        return data

    def clean_margin_short(self, pair):
        """
        Liquidate and disable margin_short trades
        """
        data = self.request(url=f"{self.bb_liquidation_url}/{pair}", method="DELETE")
        return data

    def delete_bot(self, bot_id: str | list[str]):
        bot_ids = []
        if isinstance(bot_id, str):
            bot_ids.append(bot_id)

        data = self.request(
            url=f"{self.bb_bot_url}", method="DELETE", params={"id": bot_ids}
        )
        return data

    def get_balances(self):
        data = self.request(url=self.bb_balance_url)
        return data

    def get_balances_by_type(self):
        data = self.request(url=self.bb_kucoin_balance_url)
        return data

    def get_available_fiat(
        self, exchange: str, fiat: str = "USDT", is_margin=False
    ) -> float:
        if exchange == ExchangeId.KUCOIN.value:
            all_balances = self.get_balances_by_type()
            available_fiat = 0.0

            for item in all_balances["data"]["balances"]:
                if is_margin:
                    if item == "margin":
                        for key in all_balances["data"]["balances"]["margin"]:
                            if key == fiat:
                                available_fiat += float(
                                    all_balances["data"]["balances"]["margin"][key]
                                )
                else:
                    if item == "trade":
                        for key in all_balances["data"]["balances"]["trade"]:
                            if key == fiat:
                                available_fiat += float(
                                    all_balances["data"]["balances"]["trade"][key]
                                )

                if item == "main":
                    for key in all_balances["data"]["balances"]["main"]:
                        if key == fiat:
                            available_fiat += float(
                                all_balances["data"]["balances"]["main"][key]
                            )

            return float(all_balances["data"]["fiat_available"])
        else:
            all_balances = self.get_balances()
            return float(all_balances["data"]["fiat_available"])

    def create_bot(self, data):
        data = self.request(url=self.bb_bot_url, method="POST", data=data)
        return data

    def activate_bot(self, bot_id):
        data = self.request(url=f"{self.bb_activate_bot_url}/{bot_id}")
        return data

    def create_paper_bot(self, data):
        data = self.request(url=self.bb_test_bot_url, method="POST", data=data)
        return data

    def activate_paper_bot(self, bot_id):
        data = self.request(url=f"{self.bb_activate_test_bot_url}/{bot_id}")
        return data

    def delete_paper_bot(self, bot_id):
        bot_ids = []
        if isinstance(bot_id, str):
            bot_ids.append(bot_id)

        data = self.request(
            url=f"{self.bb_test_bot_url}", method="DELETE", data={"id": bot_ids}
        )
        return data

    def get_active_pairs(self, collection_name="bots"):
        """
        Get distinct (non-repeating) bots by status active
        """
        url = self.bb_active_pairs
        if collection_name == "paper_trading":
            url = self.bb_test_active_pairs

        res = self.request(
            url=url,
        )

        if res["data"] is None:
            return []

        return res["data"]

    def filter_excluded_symbols(self) -> list[str]:
        """
        all symbols that are active, not blacklisted
        minus active bots
        minus all symbols that match base asset of these active bots
        i.e. BTC in BTCUSDC
        """
        active_pairs = self.get_active_pairs()
        all_symbols = self.get_symbols()
        exclusion_list = []
        exclusion_list.extend(active_pairs)

        for s in all_symbols:
            for ap in active_pairs:
                if (
                    ap.startswith(s["base_asset"]) and s["id"] not in exclusion_list
                ) or (not s["active"]):
                    exclusion_list.append(s["id"])

        return exclusion_list

    async def get_top_gainers(self):
        """
        Top crypto/token/coin gainers of the day
        """
        response = await self.fetch(url=self.bb_top_gainers)
        return response["data"]

    async def get_top_losers(self):
        """
        Top crypto/token/coin losers of the day
        """
        response = await self.fetch(url=self.bb_top_losers)
        return response["data"]

    def price_precision(self, symbol) -> int:
        """
        Get price decimals from API db
        """
        symbol_info = self.get_single_symbol(symbol)
        return symbol_info["price_precision"]

    def qty_precision(self, symbol) -> int:
        """
        Get qty decimals from API db
        """
        symbol_info = self.get_single_symbol(symbol)
        return symbol_info["qty_precision"]
