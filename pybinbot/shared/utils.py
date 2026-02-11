from pybinbot.models.bot_base import BotBase, MarketType


def convert_to_kucoin_symbol(bot: BotBase) -> str:
    """
    Convert symbol to KuCoin format if exchange is KuCoin
    e.g. BTCUSDC -> BTC-USDC
    """
    quote = bot.quote_asset.value
    base = bot.pair.replace(quote, "")
    if bot.market_type == MarketType.FUTURES:
        kucoin_symbol = f"{base}-{quote}M"
    else:
        kucoin_symbol = f"{base}-{quote}"

    return kucoin_symbol


def convert_from_kucoin_symbol(kucoin_symbol: str) -> str:
    """
    Convert symbol from KuCoin format to standard format
    e.g. BTC-USDC -> BTCUSDC
    """
    return kucoin_symbol.replace("-", "")
