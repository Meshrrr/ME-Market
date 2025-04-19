import asyncio
import os
from uuid import UUID
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select, asc, desc, delete
from sqlalchemy.ext.asyncio import AsyncSession

from crud.user import __change_balance
from crud.locks import LOCKS, acquire_locks
from database.database import async_session_maker
from database.models import Order, DirectionEnum, User, OrderStatusEnum, Transaction, UserInventory


RUB = os.getenv('BASE_INSTRUMENT_TICKER')

async def delete_all_orders():
    async with async_session_maker() as session:
        await session.execute(delete(Order))
        await session.commit()


async def cancel_order(order_id: str, user_id: UUID) -> Optional[Order]:
    async with async_session_maker() as session:
        q = select(Order).where(Order.id == order_id, Order.user_id == user_id)
        result = await session.execute(q)
        order: Order = result.scalars().first()
        if not order:
            return None

        lock = LOCKS[order.instrument_ticker]
        async with acquire_locks(lock):
            if order.status in [OrderStatusEnum.PARTIALLY_EXECUTED, OrderStatusEnum.EXECUTED, OrderStatusEnum.CANCELLED]:
                raise HTTPException(400, 'Order executed/partially_executed/cancelled')
            if order.price is None:
                raise HTTPException(400, 'Order is market')

            if order.direction == DirectionEnum.ASK:
                await __change_balance(session, order.user_id, order.instrument_ticker, order.amount)
            elif order.direction == DirectionEnum.BID:
                await __change_balance(session, order.user_id, RUB, order.amount * order.price)
            order.status = OrderStatusEnum.CANCELLED
            session.add(order)
            await session.flush()
            await session.refresh(order)
            await session.commit()
            return order


async def get_order(order_id: str) -> Optional[Order]:
    async with async_session_maker() as session:
        q = select(Order).where(Order.id == order_id)
        result = await session.execute(q)
        return result.scalars().first()


async def get_orders(ticker: str, direction: DirectionEnum, limit: int = 10) -> List[Order]:
    async with async_session_maker() as session:
        return await __get_orders(session, ticker, direction, limit)


async def __get_orders(session, ticker: str, direction: DirectionEnum, limit: int = 10) -> List[Order]:
    q = (
        select(Order)
        .filter(
            Order.instrument_ticker == ticker,
            Order.direction == direction.name,
            Order.status.in_([OrderStatusEnum.NEW, OrderStatusEnum.PARTIALLY_EXECUTED])
        )
        .order_by(
            desc(Order.price) if direction == DirectionEnum.BID else asc(Order.price),
            Order.created_at
        )
        .limit(limit)
    )
    result = await session.execute(q)
    return result.scalars().all()


async def create_limit_buy_order(ticker, qty, price, user: User):
    if ticker not in LOCKS:
        LOCKS[ticker] = asyncio.Lock()
    order_lock = LOCKS[ticker]
    async with acquire_locks(order_lock):
        async with async_session_maker() as session:
            orderbook = await __get_orders(session, ticker, DirectionEnum.ASK, qty)
            new_order = Order(
                user_id=user.id,
                instrument_ticker=ticker,
                amount=qty,
                filled=0,
                price=price,
                direction=DirectionEnum.BID,
                status=OrderStatusEnum.NEW
            )
            try:
                # Скупаем все что можно
                for order in orderbook:
                    if new_order.amount == 0 or (price is not None and order.price > price):
                        break
                    count_to_buy = min(order.amount, new_order.amount)
                    await buy(session, order.user_id, user.id, ticker, order.price, count_to_buy)
                    await partially_execute_order(session, order, count_to_buy)
                    await partially_execute_order(session, new_order, count_to_buy)

                # Замораживаем баланс для остатка ордера
                if new_order.status != OrderStatusEnum.EXECUTED:
                    if price is not None:
                        await freeze_balance(session, user.id, RUB, new_order.amount * new_order.price)
                    else:
                        raise Exception('Not enough orders')

                session.add(new_order)
                await session.commit()
                return new_order

            except Exception as e:
                # Не хватило денег
                print(e)
                await session.rollback()
                new_order.filled = 0
                new_order.amount = qty
                new_order.status = OrderStatusEnum.CANCELLED
                session.add(new_order)
                await session.commit()
                return new_order


async def create_limit_sell_order(ticker, qty, price, user: User):
    if ticker not in LOCKS:
        LOCKS[ticker] = asyncio.Lock()
    order_lock = LOCKS[ticker]
    async with acquire_locks(order_lock):
        async with async_session_maker() as session:
            orderbook = await __get_orders(session, ticker, DirectionEnum.BID, qty)
            new_order = Order(
                user_id=user.id,
                instrument_ticker=ticker,
                amount=qty,
                filled=0,
                price=price,
                direction=DirectionEnum.ASK,
                status=OrderStatusEnum.NEW
            )
            try:
                # Продаем все что можно
                for order in orderbook:
                    if new_order.amount == 0 or (price is not None and order.price < price):
                        break
                    count_to_sell = min(order.amount, new_order.amount)
                    await sell(session, user.id, order.user_id, ticker, order.price, count_to_sell)
                    await partially_execute_order(session, order, count_to_sell)
                    await partially_execute_order(session, new_order, count_to_sell)

                # Замораживаем инструменты
                if new_order.status != OrderStatusEnum.EXECUTED:
                    if price is not None:
                        await freeze_balance(session, user.id, ticker, new_order.amount)
                    else:
                        raise Exception('Not enough orders')

                session.add(new_order)
                await session.commit()
                return new_order

            except Exception as e:
                # Не хватило инструментов
                print(e)
                await session.rollback()
                new_order.filled = 0
                new_order.amount = qty
                new_order.status = OrderStatusEnum.CANCELLED
                session.add(new_order)
                await session.commit()
                return new_order


async def create_market_buy_order(ticker, qty, user: User):
    return await create_limit_buy_order(ticker, qty, None, user)


async def create_market_sell_order(ticker, qty, user: User):
    return await create_limit_sell_order(ticker, qty, None, user)


async def buy(session: AsyncSession, seller_id: UUID, buyer_id: UUID, ticker: str, price: int, amount: int):
    buyer = await session.get(User, buyer_id)
    seller = await session.get(User, seller_id)

    buyer_q = select(UserInventory).where(UserInventory.user_id == buyer_id,
                                          UserInventory.instrument_ticker == ticker)
    buyer_inv = (await session.execute(buyer_q)).scalars().first()

    if buyer.balance < amount * price:
        raise Exception('Not enough balance')

    transaction = Transaction(
        user_from_id=seller_id,
        user_to_id=buyer_id,
        instrument_ticker=ticker,
        amount=amount,
        price=price
    )
    session.add(transaction)
    seller.balance += amount * price
    buyer.balance -= amount * price
    buyer_inv.quantity += amount

    await session.flush()
    return transaction


async def sell(session: AsyncSession, seller_id: UUID, buyer_id: UUID, ticker: str, price: int, amount: int):
    seller = await session.get(User, seller_id)

    seller_q = select(UserInventory).where(UserInventory.user_id == seller_id,
                                           UserInventory.instrument_ticker == ticker)
    seller_inv = (await session.execute(seller_q)).scalars().first()

    buyer_q = select(UserInventory).where(UserInventory.user_id == buyer_id,
                                          UserInventory.instrument_ticker == ticker)
    buyer_inv = (await session.execute(buyer_q)).scalars().first()

    if seller_inv.quantity < amount:
        raise Exception('Not enough instruments')

    transaction = Transaction(
        user_from_id=seller_id,
        user_to_id=buyer_id,
        instrument_ticker=ticker,
        amount=amount,
        price=price
    )
    session.add(transaction)
    seller.balance += amount * price
    seller_inv.quantity -= amount
    buyer_inv.quantity += amount

    await session.flush()
    return transaction


async def partially_execute_order(session: AsyncSession, order: Order, amount: int):
    if order.amount < amount:
        raise Exception('Order not enough amount')
    order.amount -= amount
    order.filled += amount
    order.status = OrderStatusEnum.EXECUTED if order.amount == 0 else OrderStatusEnum.PARTIALLY_EXECUTED
    await session.flush()


async def freeze_balance(session, user_id: UUID, ticker: str, amount: int):
    inventory: Optional[UserInventory] = None
    user = await session.get(User, user_id)
    if ticker != RUB:
        q = select(UserInventory).where(UserInventory.user_id == user.id,
                                        UserInventory.instrument_ticker == ticker)
        inventory = (await session.execute(q)).scalars().first()

    balance = user.balance if ticker == RUB else inventory.quantity
    if balance < amount:
        raise Exception('User not enough balance/instruments')
    if ticker != RUB:
        inventory.quantity -= amount
    else:
        user.balance -= amount
    await session.flush()


async def unfreeze_balance(session, user_id: UUID, ticker: str, amount: int):
    if ticker != RUB:
        q = select(UserInventory).where(UserInventory.user_id == user_id,
                                        UserInventory.instrument_ticker == ticker)
        inventory = (await session.execute(q)).scalars().first()
        inventory.quantity += amount
    else:
        user = await session.get(User, user_id)
        user.balance += amount
    await session.flush()
