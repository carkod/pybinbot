from pydantic import BaseModel, Field


class StandardResponse(BaseModel):
    message: str
    error: int = Field(default=0)
