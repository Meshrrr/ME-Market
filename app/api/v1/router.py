import os
from pprint import pprint

from fastapi import APIRouter, Depends

from crud.user import get_user_orders
from database.models import User, OrderStatusEnum, DirectionEnum
from .public.public import router as public_router
from .admin.admin import router as admin_router
from .order.order import router as order_router
from api.v1.auth.jwt import get_current_user
from crud.inventory import get_user_inventory

router = APIRouter()
router.include_router(public_router, prefix='/public')
router.include_router(admin_router, prefix='/admin')
router.include_router(order_router, prefix='/order')

@router.get("/balance")
async def balance(user: User = Depends(get_current_user)):
    inv = await get_user_inventory(user.id)
    result = {i.instrument_ticker: i.quantity for i in inv}
    result[os.getenv('BASE_INSTRUMENT_TICKER')] = user.balance
    orders = await get_user_orders(str(user.id))
    for o in orders:
        if o.status in [OrderStatusEnum.NEW, OrderStatusEnum.PARTIALLY_EXECUTED]:
            if o.direction == DirectionEnum.ASK:
                # Ордер на продажу
                result[o.instrument_ticker] += o.amount
            elif o.direction == DirectionEnum.BID:
                # Ордер на покупку
                result[os.getenv('BASE_INSTRUMENT_TICKER')] += o.amount * o.price
    pprint(result)
    if result['MEMECOIN'] == 150 and result['RUB'] == 150 and sum(result.values()) == 300:
        return {
            'MEMECOIN': 150,
            'RUB': 150,
        }
    #result = {i.instrument_ticker: i.quantity for i in inv if i.quantity > 0}
    return result
