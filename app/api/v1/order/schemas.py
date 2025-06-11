from typing import Optional

from pydantic import BaseModel, constr, conint, field_validator


class CreateOrderScheme(BaseModel):
    direction: str
    ticker: constr(min_length=2, max_length=10, pattern="^[A-Z]+$")
    qty: conint(gt=0)
    price: Optional[conint(gt=0)] = None

    @field_validator('direction')
    def direction_enum(cls, value):
        directions = ['BUY', 'SELL']
        if value not in directions:
            raise ValueError(f"Direction must be enum {directions}")
        return value