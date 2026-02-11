from typing import Annotated, TYPE_CHECKING, Union

from pydantic import BeforeValidator

from pybinbot.shared.maths import ensure_float

if TYPE_CHECKING:  # Only imported for type checkers to avoid runtime cycles
    from pybinbot.apis.kucoin.base import KucoinApi
    from pybinbot.apis.binance.base import BinanceApi

Amount = Annotated[
    float,
    BeforeValidator(ensure_float),
]

CombinedApis = Union["BinanceApi", "KucoinApi"]
