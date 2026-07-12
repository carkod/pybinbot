from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from pybinbot.models.bot_base import BotBase, RecoveryParams
from pybinbot.models.deal import DealBase as DealModel
from pybinbot.models.order import OrderBase


class RecoveryBotModel(RecoveryParams):
    id: UUID
    created_at: float
    updated_at: float

    model_config = {"from_attributes": True}


class OrderModel(OrderBase):
    @field_validator("order_type", "order_side")
    @classmethod
    def validate_order_params(cls, v):
        if not isinstance(v, str):
            return str(v)
        return v

    @classmethod
    def dump_from_table(cls, bot):
        """
        Same as model_dump() but from a bot table-like object.
        """
        if hasattr(bot, "model_dump") and hasattr(bot, "deal"):
            model = BotModel.model_construct(**bot.model_dump())
            deal_model = DealModel.model_construct(**bot.deal.model_dump())
            order_models = [
                OrderModel.model_construct(**order.model_dump()) for order in bot.orders
            ]
            model.deal = deal_model
            model.orders = order_models
            return model
        return bot


class BotModel(BotBase):
    """
    Runtime/API bot model with nested deal, order and recovery details.
    """

    id: UUID = Field(default_factory=uuid4)
    deal: DealModel = Field(default_factory=DealModel)
    orders: list[OrderModel] = Field(default_factory=list)
    recovery_mode_id: UUID | None = None
    recovery_params: RecoveryBotModel | None = None

    @model_validator(mode="before")
    @classmethod
    def handle_trailing_rename(cls, values):
        """Backward compat: map old field names from pybinbot to renamed fields."""
        if isinstance(values, dict):
            renames = {
                "trailling": "trailing",
                "trailling_deviation": "trailing_deviation",
                "trailling_profit": "trailing_profit",
                "dynamic_trailling": "dynamic_trailing",
            }
            for old, new in renames.items():
                if old in values and new not in values:
                    values[new] = values.pop(old)
            if "strategy" in values and "position" not in values:
                values["position"] = values.pop("strategy")
            if values.get("position") == "margin_short":
                values["position"] = "short"
        return values

    model_config = {
        "from_attributes": True,
        "use_enum_values": True,
        "json_schema_extra": {
            "description": "BotModel with id, deal, and orders. Deal and orders fields are generated internally and filled by Exchange",
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "pair": "BNBUSDT",
                    "fiat": "USDC",
                    "quote_asset": "USDC",
                    "fiat_order_size": 15,
                    "candlestick_interval": "15m",
                    "close_condition": "dynamic_trailing",
                    "cooldown": 0,
                    "created_at": 1702999999.0,
                    "updated_at": 1702999999.0,
                    "dynamic_trailing": False,
                    "logs": [],
                    "mode": "manual",
                    "name": "Default bot",
                    "status": "inactive",
                    "stop_loss": 0,
                    "take_profit": 2.3,
                    "trailing": True,
                    "trailing_deviation": 0.63,
                    "trailing_profit": 2.3,
                    "margin_short_reversal": False,
                    "position": "long",
                    "deal": {},
                    "orders": [],
                }
            ],
        },
    }

    @staticmethod
    def _dump_value(value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if hasattr(value, "model_dump"):
            return value.model_dump()
        return dict(value)

    @classmethod
    def dump_from_table(cls, bot: Any) -> "BotModel":
        """
        Same as model_dump() but from a table-like object with deal/orders
        relationships already loaded.
        """
        bot_payload = cls._dump_value(bot)
        model = cls.model_construct(**bot_payload)
        deal_source = (
            bot_payload.get("deal")
            if isinstance(bot, dict)
            else getattr(bot, "deal", None)
        )
        deal_payload = cls._dump_value(deal_source)
        if not deal_payload.get("base_order_size"):
            deal_payload["base_order_size"] = 0
        model.deal = DealModel.model_validate(deal_payload)
        order_source = (
            bot_payload.get("orders", [])
            if isinstance(bot, dict)
            else getattr(bot, "orders", None) or []
        )
        model.orders = [
            OrderModel.model_construct(**cls._dump_value(order))
            for order in order_source
        ]
        model.recovery_mode_id = (
            bot_payload.get("recovery_mode_id")
            if isinstance(bot, dict)
            else getattr(bot, "recovery_mode_id", None)
        )
        recovery_params = (
            bot_payload.get("recovery_params")
            if isinstance(bot, dict)
            else getattr(bot, "recovery_params", None)
        )
        model.recovery_params = (
            RecoveryBotModel.model_validate(recovery_params)
            if recovery_params is not None
            else None
        )
        return model


class BotDataErrorResponse(BotBase):
    error: str


class BotResponse(BaseModel):
    message: str
    error: int = Field(default=0)
    data: BotModel | dict[str, Any] | str | None = Field(
        default=None,
        union_mode="left_to_right",
    )


class BotPairsList(BaseModel):
    message: str
    error: int = Field(default=0)
    data: list[str] = Field(default_factory=list)


class BotListResponse(BaseModel):
    """
    Response model used to serialize lists of bots.
    """

    message: str
    error: int = Field(default=0)
    data: list[BotModel] = Field(default_factory=list)


class ErrorsRequestBody(BaseModel):
    errors: str | list[str]

    @field_validator("errors")
    @classmethod
    def check_names_not_empty(cls, v):
        if isinstance(v, list):
            assert len(v) != 0, "List of errors is empty."
        if isinstance(v, str):
            assert v != "", "Empty pair field."
        return v


class BulkDeleteRequest(BaseModel):
    ids: list[str] = Field(..., min_length=1)

    @field_validator("ids")
    @classmethod
    def ensure_ids_not_empty(cls, v):
        if not v:
            raise ValueError("List of ids is empty.")
        return v


class AlgoRankingItem(BaseModel):
    name: str
    count: int
    bot_profit: float


class GetBotParams(BaseModel):
    status: str | None = None
    start_date: float | None = None
    end_date: float | None = None
    no_cooldown: bool = True
    limit: int = 100
    offset: int = 0
