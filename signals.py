"""
Shared Pydantic models for Binquant and Binbot.
This file is auto-generated and should be reviewed for deduplication and refactoring.
"""

# Example imports (update as needed)
from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict
from typing import Optional, List, Sequence, Union
from uuid import UUID, uuid4
from datetime import datetime

# ...existing code...

# Example shared model (copy actual model code from source files)
class HABollinguerSpread(BaseModel):
    """
    Pydantic model for the Bollinguer spread.
    (optional)
    """
    bb_high: float
    bb_mid: float
    bb_low: float

class SignalsConsumer(BaseModel):
    """
    Pydantic model for the signals consumer.
    """
    type: str = Field(default="signal")
    date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    spread: Optional[float] = Field(default=0)
    current_price: Optional[float] = Field(default=0)
    msg: str
    symbol: str
    algo: str
    bot_strategy: str = Field(default="long")
    bb_spreads: Optional[HABollinguerSpread]
    autotrade: bool = Field(default=True, description="If it is in testing mode, False")

    model_config = ConfigDict(
        extra="allow",
        use_enum_values=True,
    )

    @field_validator("spread", "current_price")
    @classmethod
    def name_must_contain_space(cls, v):
        if v is None:
            return 0
        elif isinstance(v, str):
            return float(v)
        elif isinstance(v, float):
            return v
        else:
            raise ValueError("must be a float or 0")

# Add more shared models here by copying from the relevant source files
