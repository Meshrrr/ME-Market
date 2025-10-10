from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Optional, Union, Any
import uuid
from datetime import datetime
from app.models import (
    NewUser, User, UserRole, Instrument,
    LimitOrderBody, MarketOrderBody, LimitOrder, MarketOrder,
    OrderStatus, Direction, CreateOrderResponse, Ok,
    L2OrderBook, Level, Transaction, DepositRequest, WithdrawRequest
)
from app.database import (
    get_user_by_api_key, create_user, delete_user_by_id,
    get_instruments, add_instrument, delete_instrument,
    get_user_balances, deposit_balance, withdraw_balance,
    create_order, get_order_by_id, get_user_orders, cancel_order,
    get_orderbook, get_transactions, create_tables, create_admin_user
)
from app.auth import get_current_user, get_admin_user

create_tables()

app = FastAPI(title="ME-Exchange")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    admin = create_admin_user()
    print(f"Admin created with API key: {admin.api_key}")

@app.post("/api/v1/public/register", response_model=User, tags=["public"])
async def register(user_data: NewUser):
    return create_user(user_data)

@app.get("/api/v1/public/instrument", response_model=List[Instrument], tags=["public"])
async def list_instruments():
    return get_instruments()

@app.get("/api/v1/public/orderbook/{ticker}", response_model=L2OrderBook, tags=["public"])
async def get_orderbook_endpoint(ticker: str, limit: int = 10):
    if limit > 25:
        limit = 25
    return get_orderbook(ticker, limit)

@app.get("/api/v1/public/transactions/{ticker}", response_model=List[Transaction], tags=["public"])
async def get_transaction_history(ticker: str, limit: int = 10):
    if limit > 100:
        limit = 100
    return get_transactions(ticker, limit)

@app.get("/api/v1/balance", response_model=Dict[str, int], tags=["balance"])
async def get_balances(user: User = Depends(get_current_user)) -> Dict[str, int]:
    return get_user_balances(user.id)

@app.post("/api/v1/order", response_model=CreateOrderResponse, tags=["order"])
async def create_order_endpoint(
    order_data: Union[LimitOrderBody, MarketOrderBody],
    user: User = Depends(get_current_user)
):
    try:
        order_id = create_order(user.id, order_data)
        return CreateOrderResponse(order_id=order_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/v1/order", response_model=List[Union[LimitOrder, MarketOrder]], tags=["order"])
async def list_orders(user: User = Depends(get_current_user)) -> List[Union[LimitOrder, MarketOrder]]:
    return get_user_orders(user.id)

@app.get("/api/v1/order/{order_id}", response_model=Union[LimitOrder, MarketOrder], tags=["order"])
async def get_order(order_id: uuid.UUID, user: User = Depends(get_current_user)) -> Union[LimitOrder, MarketOrder]:
    order = get_order_by_id(order_id)
    if not order or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.delete("/api/v1/order/{order_id}", response_model=Ok, tags=["order"])
async def cancel_order_endpoint(order_id: uuid.UUID, user: User = Depends(get_current_user)):
    success = cancel_order(order_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Order not found or already executed")
    return Ok()

@app.delete("/api/v1/admin/user/{user_id}", response_model=User, tags=["admin", "user"])
async def delete_user_endpoint(user_id: uuid.UUID, admin: User = Depends(get_admin_user)):
    user = delete_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.post("/api/v1/admin/instrument", response_model=Ok, tags=["admin"])
async def add_instrument_endpoint(instrument: Instrument, admin: User = Depends(get_admin_user)):
    success = add_instrument(instrument)
    if not success:
        raise HTTPException(status_code=400, detail="Instrument already exists")
    return Ok()

@app.delete("/api/v1/admin/instrument/{ticker}", response_model=Ok, tags=["admin"])
async def delete_instrument_endpoint(ticker: str, admin: User = Depends(get_admin_user)):
    success = delete_instrument(ticker)
    if not success:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return Ok()

@app.post("/api/v1/admin/balance/deposit", response_model=Ok, tags=["admin", "balance"])
async def deposit(
    data: DepositRequest,
    admin: User = Depends(get_admin_user)
):
    success = deposit_balance(data.user_id, data.ticker, data.amount)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to deposit")
    return Ok()

@app.post("/api/v1/admin/balance/withdraw", response_model=Ok, tags=["admin", "balance"])
async def withdraw(
    data: WithdrawRequest,
    admin: User = Depends(get_admin_user)
):
    success = withdraw_balance(data.user_id, data.ticker, data.amount)
    if not success:
        raise HTTPException(status_code=400, detail="Insufficient funds or user not found")
    return Ok()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)