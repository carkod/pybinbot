from typing import Annotated, Any, ClassVar

from pybinbot.shared.enums import ExchangeId
from pydantic import ConfigDict, Field, BaseModel, create_model
from time import time


class AssetIndexModel(BaseModel):
    id: str = Field(description="Unique ID")
    name: str = Field(default="", description="Name of the index")


class SymbolModel(BaseModel):
    """
    Pydantic model for SymbolTable.
    This model has to be kept identical with databases.tables.SymbolTable

    It's harder to manage SymbolTable,
    closing session will remove the nested children objects
    missing Pydantic methods
    """

    id: str = Field(description="Symbol/Pair")
    created_at: int = Field(default_factory=lambda: int(time() * 1000))
    updated_at: int = Field(default_factory=lambda: int(time() * 1000))
    active: bool = Field(default=True, description="Blacklisted items = False")
    blacklist_reason: str = Field(default="")
    description: str = Field(default="", description="Description of the symbol")
    quote_asset: str = Field(
        default="", description="in BTCUSDC, BTC would be quote asset"
    )
    base_asset: str = Field(
        default="", description="in BTCUSDC, USDC would be base asset"
    )
    cooldown: int = Field(default=0, description="Time in seconds between trades")
    cooldown_start_ts: int = Field(
        default=0,
        description="Timestamp when cooldown started in milliseconds",
    )
    futures_leverage: int = Field(
        default=1,
        ge=1,
        le=3,
        description="Default leverage to use for this symbol when trading futures",
    )
    asset_indices: list[AssetIndexModel] = Field(
        default=[], description="list of asset indices e.g. memecoin"
    )
    exchange_id: ExchangeId = Field(
        description="Exchange name where the exchange-specific values belong to (below)"
    )
    is_margin_trading_allowed: bool = Field(default=False)
    price_precision: int = Field(
        default=0,
        description="Usually there are 2 price precisions, one for base and another for quote, here we usually indicate quote, since we always use the same base: USDC",
    )
    qty_precision: int = Field(default=0)
    min_notional: float = Field(default=0, description="Minimum price x qty value")

    _update_model: ClassVar[type[BaseModel] | None] = None

    @classmethod
    def update_model(cls) -> type[BaseModel]:
        if cls._update_model is None:
            update_fields: dict[str, Any] = {}
            for field_name, model_field in cls.model_fields.items():
                annotation: Any = model_field.annotation
                if model_field.metadata:
                    annotation = Annotated[annotation, *model_field.metadata]
                nullable_annotation: Any = annotation | None
                update_fields[field_name] = (
                    nullable_annotation,
                    Field(default=None, description=model_field.description),
                )
            cls._update_model = create_model(
                f"{cls.__name__}Update",
                __config__=ConfigDict(extra="forbid"),
                **update_fields,
            )
        return cls._update_model

    @classmethod
    def to_update_payload(cls, **fields: Any) -> dict[str, Any]:
        """
        Validate a partial update without applying SymbolModel defaults.

        The full SymbolModel requires fields such as id/exchange_id and would
        populate defaults for omitted fields, which would overwrite current
        backend values. The generated update model keeps the same field
        validation while allowing sparse payloads.
        """
        return (
            cls.update_model()
            .model_validate(fields)
            .model_dump(
                mode="json",
                exclude_unset=True,
                exclude_none=True,
            )
        )
