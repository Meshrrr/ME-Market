from typing import List

from sqlalchemy import select

from database.database import async_session_maker
from database.models import Transaction, Instrument


async def get_transactions_by_ticker(ticker: str, limit: int = 10) -> List[Transaction]:
    async with async_session_maker() as session:
        stmt = (
            select(Transaction)
            .join(Transaction.instrument)
            .filter(Instrument.ticker == ticker)
            .order_by(Transaction.timestamp.desc())
            .limit(limit)
        )

        result = await session.execute(stmt)
        transactions = result.scalars().all()

        return transactions


async def create_transaction(user_from_id: str, user_to_id: str, ticker: str, amount: int, price: float) -> Transaction:
    async with async_session_maker() as session:
        t = await __create_transaction(session, user_from_id, user_to_id, ticker, amount, price)
        await session.commit()
        await session.refresh(t)

        return t


async def __create_transaction(session, user_from_id: str, user_to_id: str, ticker: str, amount: int,
                               price: float) -> Transaction:
    transaction = Transaction(
        user_from_id=user_from_id,
        user_to_id=user_to_id,
        instrument_ticker=ticker,
        amount=amount,
        price=price
    )
    session.add(transaction)
    return transaction
