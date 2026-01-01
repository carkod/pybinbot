from typing import List, Optional
from uuid import uuid4, UUID
from pydantic import BaseModel, Field, field_validator
from databases.utils import Amount, timestamp
from tools.enum_definitions import (
    QuoteAssets,
    BinanceKlineIntervals,
    CloseConditions,
    Status,
    Strategy,
    DealType,
    OrderStatus,
)
from tools.handle_error import IResponseBase
from tools.maths import ts_to_humandate
from databases.tables.bot_table import BotTable, PaperTradingTable
from databases.tables.deal_table import DealTable
from databases.tables.order_table import ExchangeOrderTable


class OrderModel(BaseModel):
    order_type: str = Field(
        description="Because every exchange has different naming, we should keep it as a str rather than OrderType enum"
    )
    time_in_force: str
    timestamp: int = Field(default=0)
    order_id: int | str = Field(
        description="Because every exchange has id type, we should keep it as looose as possible. Int is for backwards compatibility"
    )
    order_side: str = Field(
        description="Because every exchange has different naming, we should keep it as a str rather than OrderType enum"
    )
    pair: str
    qty: float
    status: OrderStatus
    price: float
    deal_type: DealType
    model_config = {
        "from_attributes": True,
        "use_enum_values": True,
        "json_schema_extra": {
            "description": "Most fields are optional. Deal field is generated internally, orders are filled up by Exchange",
            "examples": [
                {
                    "order_type": "LIMIT",
                    "time_in_force": "GTC",
                    "timestamp": 0,
                    "order_id": 0,
                    "order_side": "BUY",
                    "pair": "",
                    "qty": 0,
                    "status": "",
                    "price": 0,
                }
            ],
        },
    }

    @classmethod
    def dump_from_table(cls, bot):
        if isinstance(bot, BotTable) or isinstance(bot, PaperTradingTable):
            model = BotModel.model_construct(**bot.model_dump())
            deal_model = DealModel.model_construct(**bot.deal.model_dump())
            order_models = [
                OrderModel.model_construct(**order.model_dump()) for order in bot.orders
            ]
            model.deal = deal_model
            model.orders = order_models
            return model
        else:
            return bot


class DealModel(BaseModel):
    base_order_size: Amount = Field(default=0, gt=-1)
    current_price: Amount = Field(default=0)
    take_profit_price: Amount = Field(default=0)
    trailling_stop_loss_price: Amount = Field(
        default=0,
        description="take_profit but for trailling, to avoid confusion, trailling_profit_price always be > trailling_stop_loss_price",
    )
    trailling_profit_price: Amount = Field(default=0)
    stop_loss_price: Amount = Field(default=0)
    total_interests: float = Field(default=0, gt=-1)
    total_commissions: float = Field(default=0, gt=-1)
    margin_loan_id: int = Field(
        default=0,
        ge=0,
        description="Txid from Binance. This is used to check if there is a loan, 0 means no loan",
    )
    margin_repay_id: int = Field(
        default=0, ge=0, description="= 0, it has not been repaid"
    )
    opening_price: Amount = Field(
        default=0,
        description="replaces previous buy_price or short_sell_price/margin_short_sell_price",
    )
    opening_qty: Amount = Field(
        default=0,
        description="replaces previous buy_total_qty or short_sell_qty/margin_short_sell_qty",
    )
    opening_timestamp: int = Field(default=0)
    closing_price: Amount = Field(
        default=0,
        description="replaces previous sell_price or short_sell_price/margin_short_sell_price",
    )
    closing_qty: Amount = Field(
        default=0,
        description="replaces previous sell_qty or short_sell_qty/margin_short_sell_qty",
    )
    closing_timestamp: int = Field(
        default=0,
        description="replaces previous buy_timestamp or margin/short_sell timestamps",
    )

    @field_validator("margin_loan_id", mode="before")
    @classmethod
    def validate_margin_loan_id(cls, value):
        if isinstance(value, float):
            return int(value)
        else:
            return value

    @field_validator("margin_loan_id", mode="after")
    @classmethod
    def cast_float(cls, value):
        if isinstance(value, float):
            return int(value)
        else:
            return value
