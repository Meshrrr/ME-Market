from uuid import UUID

from pydantic import BaseModel, constr, field_validator


class InstrumentCreateRequest(BaseModel):
    name: constr()
    ticker: constr(pattern="^[A-Z]{2,10}$")

class BalanceChangeScheme(BaseModel):
    user_id: UUID
    ticker: constr(min_length=2, max_length=10, pattern="^[A-Z]+$")
    amount: int

    @field_validator('amount')
    def amount_must_be_greater_then_zero(cls, value):
        if value <= 0:
            raise ValueError("Amount must be > 0")
        return value
