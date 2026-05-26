import time

import requests
from pandas import DataFrame, to_datetime


class CoinGecko:
    """
    CoinGecko API client for fetching cryptocurrency data.

    _btc_ohlc_cache holds (fetched_at_unix, DataFrame). CoinGecko only refreshes
    the /ohlc endpoint every 30 minutes, so there is no benefit to calling it more
    often than that.
    """

    _btc_ohlc_cache: tuple[float, DataFrame] | None = None
    _BTC_OHLC_TTL = 1800

    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"

    def get_all_categories(self) -> list:
        url = f"{self.base_url}/coins/categories"
        r = requests.get(url)
        r.raise_for_status()
        return [cat["id"] for cat in r.json()]

    def get_coins_in_category(self, category_id: str) -> list:
        url = f"{self.base_url}/coins/markets"
        params = {
            "vs_currency": "usd",
            "category": category_id,
            "order": "market_cap_desc",
            "per_page": str(250),
            "page": str(1),
        }
        r = requests.get(url, params=params)
        r.raise_for_status()
        page = 1
        all_coins = []
        while True:
            url = f"{self.base_url}/coins/markets"
            params = {
                "vs_currency": "usd",
                "category": category_id,
                "order": "market_cap_desc",
                "per_page": str(250),
                "page": str(page),
            }
            r = requests.get(url, params=params)
            r.raise_for_status()
            data = r.json()
            if not data:
                break
            all_coins.extend(data)
            page += 1
        return all_coins

    def get_btc_ohlc(self, days: int = 2) -> DataFrame:
        """Return a time-indexed OHLC DataFrame for Bitcoin via CoinGecko.

        Args:
            days: How many days of history to request. CoinGecko returns
                  different bar granularity depending on this value:
                  1–2 days → 30-min bars, 3–30 days → 4-hour bars,
                  31+ days → 4-day bars. Default 2 gives ~96 30-min
                  candles, enough for a window-20 Bollinger calculation.

        Returns:
            DataFrame with columns [open_time, open, high, low, close],
            indexed by a UTC DatetimIndex derived from open_time.
        """
        now = time.time()
        if CoinGecko._btc_ohlc_cache is not None:
            fetched_at, cached_df = CoinGecko._btc_ohlc_cache
            if now - fetched_at < CoinGecko._BTC_OHLC_TTL:
                return cached_df

        url = f"{self.base_url}/coins/bitcoin/ohlc"
        r = requests.get(url, params={"vs_currency": "usd", "days": str(days)})
        r.raise_for_status()
        # Response: [[timestamp_ms, open, high, low, close], ...]
        df = DataFrame(r.json(), columns=["open_time", "open", "high", "low", "close"])
        df["timestamp"] = to_datetime(df["open_time"], unit="ms", utc=True)
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)

        CoinGecko._btc_ohlc_cache = (now, df)
        return df
