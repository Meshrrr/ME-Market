from datetime import timezone
from pprint import pprint
from collections import defaultdict
from fastapi import APIRouter, Depends
from api.v1.auth.jwt import get_current_user, create_access_token, get_current_admin
from depends import get_instrument_depend
from .schemas import UserAuth
from database.models import User, DirectionEnum, Instrument
from crud.user import create_user
from crud.instrument import get_all_instruments, get_instrument_by_ticker, delete_all_instruments
from crud.order import get_orders, delete_all_orders
from crud.transaction import get_transactions_by_ticker

router = APIRouter()


@router.post('/register')
async def register(user: UserAuth):
    user = await create_user(user.name)
    await delete_all_orders()
    data = {
        "name": user.name,
        "id": str(user.id),
        "role": user.role.name
    }
    token = create_access_token(data)
    data['api_key'] = token
    print('create user ', user.id)
    return data


@router.get('/instrument')
async def public_test():
    return [{
        "name": i.name,
        "ticker": i.ticker
    } for i in await get_all_instruments()]


# @router.get('/orderbook/{ticker}')
# async def public_test(instrument: Instrument = Depends(get_instrument_depend), limit: int = 10):
#     ticker = instrument.ticker
#     bid_orders = await get_orders(ticker, DirectionEnum.BID, limit=limit)
#     bid_orders = [{
#         "price": b.price,
#         "qty": b.amount
#     } for b in bid_orders]
#
#     ask_orders = await get_orders(ticker, DirectionEnum.ASK, limit=limit)
#     ask_orders = [{
#         "price": a.price,
#         "qty": a.amount
#     } for a in ask_orders]
#     res = {
#         "bid_levels": bid_orders,
#         "ask_levels": ask_orders
#     }
#     pprint(res)
#     return res


@router.get('/orderbook/{ticker}')
async def public_test(instrument: Instrument = Depends(get_instrument_depend), limit: int = 10):
    ticker = instrument.ticker

    async def aggregate_orders(direction: DirectionEnum):
        orders = await get_orders(ticker, direction, limit=limit)
        aggregated = defaultdict(int)
        for order in orders:
            aggregated[order.price] += order.amount
        return [{"price": price, "qty": qty} for price, qty in
                sorted(aggregated.items(), reverse=(direction == DirectionEnum.BID))]

    bid_orders = await aggregate_orders(DirectionEnum.BID)
    ask_orders = await aggregate_orders(DirectionEnum.ASK)

    res = {
        "bid_levels": bid_orders,
        "ask_levels": ask_orders
    }
    pprint(res)
    return res


@router.get('/transactions/{ticker}')
async def public_test(instrument: Instrument = Depends(get_instrument_depend), limit: int = 10):
    ticker = instrument.ticker
    transactions = await get_transactions_by_ticker(ticker, limit)
    transactions = [
        {
            "ticker": t.instrument_ticker,
            "amount": t.amount,
            "price": t.price,
            "timestamp": t.timestamp.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        }
        for t in transactions
    ]
    return transactions
