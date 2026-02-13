from pybinbot.models.bot_base import BotBase
from pybinbot.shared.utils import convert_to_kucoin_symbol, convert_from_kucoin_symbol
from pybinbot.shared.enums import QuoteAssets, MarketType


class TestConvertToKucoinSymbol:
    def test_converts_usdc_pair_with_quote_asset_enum(self) -> None:
        # BotBase stores enum values as strings internally due to model_config,
        # so we explicitly assign the QuoteAssets enum instance here to match
        # convert_to_kucoin_symbol's expectation of an enum with .value.
        bot = BotBase(pair="BTCUSDC", fiat="USDC")
        bot.quote_asset = QuoteAssets.USDC
        bot.market_type = MarketType.SPOT

        symbol = convert_to_kucoin_symbol(bot)

        assert symbol == "BTC-USDC"

    def test_converts_usdt_pair_with_quote_asset_enum(self) -> None:
        bot = BotBase(pair="ETHUSDT", fiat="USDT")
        bot.quote_asset = QuoteAssets.USDT
        bot.market_type = MarketType.SPOT

        symbol = convert_to_kucoin_symbol(bot)

        assert symbol == "ETH-USDT"

    def test_futures_symbol_returns_pair_unchanged(self) -> None:
        """For futures market type, symbol should not be reformatted."""

        bot = BotBase(pair="BTCUSDTM", fiat="USDT")
        bot.quote_asset = QuoteAssets.USDT
        bot.market_type = MarketType.FUTURES

        symbol = convert_to_kucoin_symbol(bot)

        assert symbol == "BTCUSDTM"


class TestConvertFromKucoinSymbol:
    def test_converts_standard_symbol(self) -> None:
        assert convert_from_kucoin_symbol("BTC-USDC") == "BTCUSDC"

    def test_converts_multiple_dashes(self) -> None:
        # Defensive: any '-' will be stripped
        assert convert_from_kucoin_symbol("BTC-US-DC") == "BTCUSDC"

    def test_converts_lowercase_symbol(self) -> None:
        assert convert_from_kucoin_symbol("eth-usdt") == "ethusdt"
