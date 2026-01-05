from pydantic import BaseModel, Field

from pybinbot.shared.enums import DealType, OrderStatus
from pybinbot.shared.types import Amount


class OrderBase(BaseModel):
    order_type: str = Field(
        description=(
            "Because every exchange has different naming, we should keep it as a "
            "str rather than OrderType enum"
        )
    )
    time_in_force: str
    timestamp: int = Field(default=0)
    order_id: int | str = Field(
        description=(
            "Because every exchange has id type, we should keep it as loose as "
            "possible. Int is for backwards compatibility"
        )
    )
    order_side: str = Field(
        description=(
            "Because every exchange has different naming, we should keep it as a "
            "str rather than OrderType enum"
        )
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
            "description": (
                "Most fields are optional. Deal field is generated internally, "
                "orders are filled up by Exchange"
            ),
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


class DealModel(BaseModel):
    base_order_size: Amount = Field(default=0, gt=-1)
    current_price: Amount = Field(default=0)
    take_profit_price: Amount = Field(default=0)
    trailling_stop_loss_price: Amount = Field(
        default=0,
        description=(
            "take_profit but for trailling, to avoid confusion, "
            "trailling_profit_price always be > trailling_stop_loss_price"
        ),
    )
    trailling_profit_price: Amount = Field(default=0)
    stop_loss_price: Amount = Field(default=0)
    total_interests: float = Field(default=0, gt=-1)
    total_commissions: float = Field(default=0, gt=-1)
    margin_loan_id: int = Field(
        default=0,
        ge=0,
        description=(
            "Txid from Binance. This is used to check if there is a loan, "
            "0 means no loan"
        ),
    )
    margin_repay_id: int = Field(
        default=0, ge=0, description="= 0, it has not been repaid"
    )
    opening_price: Amount = Field(
        default=0,
        description=(
            "replaces previous buy_price or short_sell_price/margin_short_sell_price"
        ),
    )
    opening_qty: Amount = Field(
        default=0,
        description=(
            "replaces previous buy_total_qty or short_sell_qty/margin_short_sell_qty"
        ),
    )
    opening_timestamp: int = Field(default=0)
    closing_price: Amount = Field(
        default=0,
        description=(
            "replaces previous sell_price or short_sell_price/margin_short_sell_price"
        ),
    )
    closing_qty: Amount = Field(
        default=0,
        description=(
            "replaces previous sell_qty or short_sell_qty/margin_short_sell_qty"
        ),
    )
    closing_timestamp: int = Field(
        default=0,
        description=("replaces previous buy_timestamp or margin/short_sell timestamps"),
    )
