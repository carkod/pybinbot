from typing import Annotated

from pydantic import BeforeValidator

from .maths import ensure_float


Amount = Annotated[
    float,
    BeforeValidator(ensure_float),
]
