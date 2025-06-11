from pydantic import BaseModel, Field, validator
from typing import List, Optional, Union, Dict
from enum import Enum
import uuid
from datetime import datetime


class UserRole(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class Direction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    NEW = "NEW"
    EXECUTED = "EXECUTED"
    PARTIALLY_EXECUTED = "PARTIALLY_EXECUTED"
    CANCELLED = "CANCELLED"


class NewUser(BaseModel):
    name: str = Field(..., min_length=3)


class User(BaseModel):
    id: uuid.UUID
    name: str
    role: UserRole
    api_key: str


class Instrument(BaseModel):
    name: str
    ticker: str

    @validator('ticker')
    def validate_ticker(cls, v):
        import re
        if not re.match(r'^[A-Z]{2,10}$', v):
            raise ValueError('Ticker must be 2-10 uppercase letters')
        return v


class Level(BaseModel):
    price: int
    qty: int


class L2OrderBook(BaseModel):
    bid_levels: List[Level]
    ask_levels: List[Level]


class Transaction(BaseModel):
    ticker: str
    amount: int
    price: int
    timestamp: datetime


class LimitOrderBody(BaseModel):
    direction: Direction
    ticker: str
    qty: int = Field(..., gt=0)
    price: int = Field(..., gt=0)


class MarketOrderBody(BaseModel):
    direction: Direction
    ticker: str
    qty: int = Field(..., gt=0)


class LimitOrder(BaseModel):
    id: uuid.UUID
    status: OrderStatus
    user_id: uuid.UUID
    timestamp: datetime
    body: LimitOrderBody
    filled: int = 0


class MarketOrder(BaseModel):
    id: uuid.UUID
    status: OrderStatus
    user_id: uuid.UUID
    timestamp: datetime
    body: MarketOrderBody


class CreateOrderResponse(BaseModel):
    success: bool = True
    order_id: uuid.UUID


class Ok(BaseModel):
    success: bool = True


class DepositRequest(BaseModel):
    user_id: uuid.UUID = Field(..., examples=["35b0884d-9a1d-47b0-91c7-eecf0ca56bc8"])
    ticker: str = Field(..., examples=["MEMCOIN"])
    amount: int = Field(..., gt=0)


class WithdrawRequest(BaseModel):
    user_id: uuid.UUID = Field(..., examples=["35b0884d-9a1d-47b0-91c7-eecf0ca56bc8"])
    ticker: str = Field(..., examples=["MEMCOIN"])
    amount: int = Field(..., gt=0)
