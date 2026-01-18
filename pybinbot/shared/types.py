from typing import Annotated
from pydantic import BeforeValidator
from pybinbot.shared.maths import ensure_float
from pybinbot.apis.kucoin.base import KucoinApi
from pybinbot.apis.binance.base import BinanceApi

Amount = Annotated[
    float,
    BeforeValidator(ensure_float),
]

CombinedApis = BinanceApi | KucoinApi
