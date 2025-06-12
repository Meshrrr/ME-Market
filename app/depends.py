import uuid

from fastapi import HTTPException

from crud.instrument import get_instrument_by_ticker
from crud.user import get_user
from database.models import Instrument, User


async def get_instrument_depend(ticker: str) -> Instrument:
    instrument = await get_instrument_by_ticker(ticker)
    if not instrument:
        raise HTTPException(404)
    return instrument

async def get_user_depend(user_id: uuid.UUID) -> User:
    user_id = str(user_id)
    user = await get_user(user_id)
    if not user:
        raise HTTPException(404)
    return user