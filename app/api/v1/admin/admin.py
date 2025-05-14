import os
from pprint import pprint

from fastapi import APIRouter, Depends, HTTPException

from api.v1.admin.schemas import InstrumentCreateRequest, BalanceChangeScheme
from api.v1.auth.jwt import get_current_admin
from crud.instrument import create_instrument, get_instrument_by_ticker, delete_instrument
from crud.user import get_user, change_balance, delete_user
from database.models import User, Instrument
from depends import get_instrument_depend, get_user_depend

router = APIRouter()


@router.post('/instrument')
async def instrument(instrument: InstrumentCreateRequest, user: User = Depends(get_current_admin)):
    print('create instrument', instrument.ticker)
    instr = await get_instrument_by_ticker(instrument.ticker)
    if instr:
        raise HTTPException(422)
    await create_instrument(instrument.name, instrument.ticker)
    return {
        "success": True
    }


@router.post('/balance/deposit')
async def deposit(balance_change: BalanceChangeScheme, admin: User = Depends(get_current_admin)):
    user = await get_user(str(balance_change.user_id))
    pprint(balance_change)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if balance_change.ticker != os.getenv('BASE_INSTRUMENT_TICKER'):
        instrument = await get_instrument_by_ticker(balance_change.ticker)
        if not instrument:
            raise HTTPException(status_code=404, detail="Instrument not found")

    await change_balance(str(balance_change.user_id), balance_change.ticker, balance_change.amount)

    return {
        "success": True
    }


@router.post('/balance/withdraw')
async def deposit(balance_change: BalanceChangeScheme, admin: User = Depends(get_current_admin)):
    user = await get_user(str(balance_change.user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if balance_change.ticker != os.getenv('BASE_INSTRUMENT_TICKER'):
        instrument = await get_instrument_by_ticker(balance_change.ticker)
        if not instrument:
            raise HTTPException(status_code=404, detail="Instrument not found")

    await change_balance(str(balance_change.user_id), balance_change.ticker, -1 * balance_change.amount)

    return {
        "success": True
    }



@router.delete('/user/{user_id}')
async def delete_user_met(user_to_delete: User = Depends(get_user_depend), admin: User = Depends(get_current_admin)):
    deleted = await delete_user(str(user_to_delete.id))
    res = {
        "id": deleted.id,
        "name": deleted.name,
        "role": deleted.role.name,
        "api_key": deleted.api_key
    }
    return res


@router.delete('/instrument/{ticker}')
async def instrument(instrument: Instrument = Depends(get_instrument_depend), user: User = Depends(get_current_admin)):
    ticker = instrument.ticker
    deleted = await delete_instrument(ticker)
    return {
        "success": True
    }
