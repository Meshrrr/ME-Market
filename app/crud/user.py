import asyncio
import os
import uuid
from typing import Optional, List

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from crud.locks import acquire_locks, LOCKS
from database.models import User, RoleEnum, Instrument, UserInventory, Order
from database.database import async_session_maker


async def create_user(name: str, role: RoleEnum=RoleEnum.USER) -> User:
    async with async_session_maker() as session:
        new_user = User(name=name, role=role)
        session.add(new_user)

        result = await session.execute(select(Instrument))
        instruments = result.scalars().all()
        for instrument in instruments:
            inv = UserInventory(user=new_user, instrument=instrument, quantity=0.0)
            session.add(inv)

        await session.commit()
        await session.refresh(new_user)
        return new_user


async def get_user(uuid_str: str) -> Optional[User]:
    async with async_session_maker() as session:
        user_uuid = uuid.UUID(uuid_str)
        result = await session.execute(select(User).where(User.id == user_uuid))
        user = result.scalars().first()
        return user

async def apply_api_key(uuid_str: str, key:str):
    async with async_session_maker() as session:
        user = await get_user(uuid_str)
        user.api_key = key
        session.add(user)
        await session.commit()
        return user

async def delete_user(uuid_str: str) -> Optional[User]:
    async with acquire_locks(*LOCKS.values()):
        async with async_session_maker() as session:
            user = await get_user(uuid_str)
            if not user:
                raise HTTPException(status_code=404, detail='Пользователь с таким id не найден')
            await session.delete(user)
            await session.commit()
            #await asyncio.sleep(1)
            return user

async def change_balance(id: [uuid.UUID, str], ticker: str, amount: int) -> Optional[User]:
    async with async_session_maker() as session:
        b = await __change_balance(session, id, ticker, amount)
        await session.commit()
        await session.refresh(b)
        return b


async def __change_balance(session, id: [uuid.UUID, str], ticker: str, amount: int) -> Optional[User]:
    id = str(id)
    if ticker == os.getenv('BASE_INSTRUMENT_TICKER'):
        user = await session.get(User, uuid.UUID(id))
        if user is None:
            user = await get_user(id)
        new_balance = user.balance + amount
        if new_balance < 0:
            raise HTTPException(status_code=400, detail='Balance must be >= 0')
        user.balance = new_balance
        session.add(user)
    else:
        result = await session.execute(
            select(User).where(User.id == uuid.UUID(id)).options(selectinload(User.inventory))
        )
        user = result.scalar_one_or_none()
        for inv in user.inventory:
            if inv.instrument_ticker == ticker:
                new_balance = inv.quantity + amount
                if new_balance < 0:
                    raise HTTPException(status_code=400, detail='Balance must be >= 0')
                inv.quantity = new_balance
                session.add(inv)
                break

    #await session.commit()
    return user




async def get_user_orders(uuid_str: str) -> List[Order]:
    async with async_session_maker() as session:
        result = await session.execute(
            select(Order).where(Order.user_id == uuid.UUID(uuid_str))
        )
        orders = result.scalars().all()
        return orders
