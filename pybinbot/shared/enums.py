from enum import Enum
from pydantic import BaseModel, field_validator


class DealType(str, Enum):
    base_order = "base_order"
    take_profit = "take_profit"
    stop_loss = "stop_loss"
    short_sell = "short_sell"
    short_buy = "short_buy"
    margin_short = "margin_short"
    panic_close = "panic_close"
    trailling_profit = "trailling_profit"
    conversion = "conversion"  # converts one crypto to another


class CloseConditions(str, Enum):
    dynamic_trailling = "dynamic_trailling"
    # No trailling, standard stop loss
    timestamp = "timestamp"
    # binbot-research param (self.market_trend_reversal)
    market_reversal = "market_reversal"


class KafkaTopics(str, Enum):
    klines_store_topic = "klines-store-topic"
    technical_indicators = "technical-indicators"
    signals = "signals"
    restart_streaming = "restart-streaming"
    restart_autotrade = "restart-autotrade"


class BinanceOrderModel(BaseModel):
    """
    Data model given by Binance,
    therefore it should be strings
    """

    order_type: str
    time_in_force: str
    timestamp: int
    order_id: int
    order_side: str
    pair: str
    qty: float
    status: str
    price: float
    deal_type: DealType

    @field_validator("timestamp", "order_id", "price", "qty", "order_id")
    @classmethod
    def validate_str_numbers(cls, v):
        if isinstance(v, float):
            return v
        elif isinstance(v, int):
            return v
        elif isinstance(v, str):
            return float(v)
        else:
            raise ValueError(f"{v} must be a number")


class Status(str, Enum):
    all = "all"
    inactive = "inactive"
    active = "active"
    completed = "completed"
    error = "error"


class Strategy(str, Enum):
    long = "long"
    margin_short = "margin_short"


class OrderType(str, Enum):
    limit = "LIMIT"
    market = "MARKET"
    stop_loss = "STOP_LOSS"
    stop_loss_limit = "STOP_LOSS_LIMIT"
    take_profit = "TAKE_PROFIT"
    take_profit_limit = "TAKE_PROFIT_LIMIT"
    limit_maker = "LIMIT_MAKER"


class TimeInForce(str, Enum):
    gtc = "GTC"
    ioc = "IOC"
    fok = "FOK"


class OrderSide(str, Enum):
    buy = "BUY"
    sell = "SELL"


class OrderStatus(str, Enum):
    """
    Must be all uppercase for SQL alchemy
    and Alembic to do migration properly
    """

    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

    @classmethod
    def map_from_kucoin_status(cls, kucoin_status: str) -> "OrderStatus":
        """
        Map Kucoin order status to internal OrderStatus enum.
        Kucoin statuses: active, done, canceled
        """
        mapping = {
            "open": cls.NEW,
            "match": cls.PARTIALLY_FILLED,
            "done": cls.FILLED,
        }
        return mapping.get(kucoin_status, cls.REJECTED)


class TrendEnum(str, Enum):
    up_trend = "uptrend"
    down_trend = "downtrend"
    neutral = None


class BinanceKlineIntervals(str, Enum):
    one_minute = "1m"
    three_minutes = "3m"
    five_minutes = "5m"
    fifteen_minutes = "15m"
    thirty_minutes = "30m"
    one_hour = "1h"
    two_hours = "2h"
    four_hours = "4h"
    six_hours = "6h"
    eight_hours = "8h"
    twelve_hours = "12h"
    one_day = "1d"
    three_days = "3d"
    one_week = "1w"
    one_month = "1M"

    def bin_size(self):
        return int(self.value[:-1])

    def unit(self):
        if self.value[-1:] == "m":
            return "minute"
        elif self.value[-1:] == "h":
            return "hour"
        elif self.value[-1:] == "d":
            return "day"
        elif self.value[-1:] == "w":
            return "week"
        elif self.value[-1:] == "M":
            return "month"

    def to_kucoin_interval(self) -> str:
        """
        Convert Binance interval format to Kucoin interval format.

        Binance: 1m, 5m, 15m, 1h, 4h, 1d, 1w
        Kucoin: 1min, 5min, 15min, 1hour, 4hour, 1day, 1week
        """
        interval_map = {
            "1m": "1min",
            "3m": "3min",
            "5m": "5min",
            "15m": "15min",
            "30m": "30min",
            "1h": "1hour",
            "2h": "2hour",
            "4h": "4hour",
            "6h": "6hour",
            "8h": "8hour",
            "12h": "12hour",
            "1d": "1day",
            "3d": "3day",
            "1w": "1week",
            "1M": "1month",
        }
        return interval_map.get(self.value, self.value)

    @staticmethod
    def get_interval_ms(interval_str: str) -> int:
        """Convert Binance interval string to milliseconds"""
        interval_map = {
            "1m": 60 * 1000,
            "3m": 3 * 60 * 1000,
            "5m": 5 * 60 * 1000,
            "15m": 15 * 60 * 1000,
            "30m": 30 * 1000,
            "1h": 60 * 60 * 1000,
            "2h": 2 * 60 * 60 * 1000,
            "4h": 4 * 60 * 60 * 1000,
            "6h": 6 * 60 * 60 * 1000,
            "8h": 8 * 60 * 60 * 1000,
            "12h": 12 * 60 * 60 * 1000,
            "1d": 24 * 60 * 60 * 1000,
            "3d": 3 * 24 * 60 * 60 * 1000,
            "1w": 7 * 24 * 60 * 60 * 1000,
            "1M": 30 * 24 * 60 * 60 * 1000,  # Approximate month as 30 days
        }
        return interval_map.get(interval_str, 60 * 1000)  # Default to 1 minute

    def get_ms(self) -> int:
        """
        Instance method to get interval duration in milliseconds
        """
        return self.get_interval_ms(self.value)


class KucoinKlineIntervals(str, Enum):
    ONE_MINUTE = "1min"
    THREE_MINUTES = "3min"
    FIVE_MINUTES = "5min"
    FIFTEEN_MINUTES = "15min"
    THIRTY_MINUTES = "30min"
    ONE_HOUR = "1hour"
    TWO_HOURS = "2hour"
    FOUR_HOURS = "4hour"
    SIX_HOURS = "6hour"
    EIGHT_HOURS = "8hour"
    TWELVE_HOURS = "12hour"
    ONE_DAY = "1day"
    ONE_WEEK = "1week"

    # Helper to calculate interval duration in milliseconds
    @staticmethod
    def get_interval_ms(interval_str: str | None = None) -> int:
        """Convert Kucoin interval string to milliseconds. Raises ValueError if not valid."""
        interval_map = {
            "1min": 60 * 1000,
            "3min": 3 * 60 * 1000,
            "5min": 5 * 60 * 1000,
            "15min": 15 * 60 * 1000,
            "30min": 30 * 60 * 1000,
            "1hour": 60 * 60 * 1000,
            "2hour": 2 * 60 * 60 * 1000,
            "4hour": 4 * 60 * 60 * 1000,
            "6hour": 6 * 60 * 60 * 1000,
            "8hour": 8 * 60 * 60 * 1000,
            "12hour": 12 * 60 * 60 * 1000,
            "1day": 24 * 60 * 60 * 1000,
            "1week": 7 * 24 * 60 * 60 * 1000,
        }
        valid_intervals = {e.value for e in KucoinKlineIntervals}
        if interval_str not in valid_intervals:
            raise ValueError(
                f"Invalid interval: {interval_str}. Must be one of: {sorted(valid_intervals)}"
            )
        return interval_map[interval_str]

    def get_ms(self) -> int:
        """
        Instance method to get interval duration in milliseconds
        """
        return self.get_interval_ms(self.value)


class AutotradeSettingsDocument(str, Enum):
    # Autotrade settings for test bots
    test_autotrade_settings = "test_autotrade_settings"
    # Autotrade settings for real bots
    settings = "autotrade_settings"


class UserRoles(str, Enum):
    # Full access to all resources
    user = "user"
    # Access to terminal and customer accounts
    admin = "admin"
    # Only access to funds and client website
    customer = "customer"


class QuoteAssets(str, Enum):
    """
    Quote assets supported by Binbot orders
    Includes both crypto assets and fiat currencies
    """

    # Crypto assets
    USDT = "USDT"
    USDC = "USDC"
    BTC = "BTC"
    ETH = "ETH"
    # Backwards compatibility
    TRY = "TRY"

    def is_fiat(self) -> bool:
        """Check if the asset is a fiat currency"""
        return self.value in ["TRY", "EUR", "USD"]

    @classmethod
    def get_fiat_currencies(cls) -> list["QuoteAssets"]:
        """
        Get all fiat currencies
        """
        return [asset for asset in cls if asset.is_fiat()]


class ExchangeId(str, Enum):
    KUCOIN = "kucoin"
    BINANCE = "binance"


class MarketDominance(str, Enum):
    NEUTRAL = "neutral"
    GAINERS = "gainers"
    LOSERS = "losers"


class MarketType(str, Enum):
    SPOT = "SPOT"
    MARGIN = "MARGIN"
    FUTURES = "FUTURES"

    @classmethod
    def from_name(cls, name: str) -> "MarketType":
        """
        Map internal name to uppercase API market type.
        Accepts 'spot', 'margin', 'futures' (case-insensitive).
        """
        mapping = {
            "spot": cls.SPOT,
            "margin": cls.MARGIN,
            "futures": cls.FUTURES,
        }
        key = name.lower()
        if key not in mapping:
            raise ValueError(f"Unknown market type: {name}")
        return mapping[key]

    @classmethod
    def to_account_type(cls, market_type: "MarketType") -> str:
        """
        Convert MarketType to Kucoin account type string.
        """
        account_type_map = {
            cls.SPOT: "SPOT",
            cls.MARGIN: "MARGIN",
            cls.FUTURES: "CONTRACT",
        }
        return account_type_map.get(market_type, "SPOT")
