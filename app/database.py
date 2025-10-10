from typing import Dict, List, Optional, Union, Any
import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, ForeignKey, DateTime, Enum, Boolean, Text, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.sql import func
import os
import json
from contextlib import contextmanager
from sqlalchemy.exc import IntegrityError


from app.models import (
    NewUser, User, UserRole, Instrument as PydanticInstrument,
    LimitOrderBody, MarketOrderBody, LimitOrder as PydanticLimitOrder,
    MarketOrder as PydanticMarketOrder, OrderStatus, Direction,
    Level, L2OrderBook, Transaction as PydanticTransaction
)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:mysecretpassword@localhost:5432/memarket")

engine = create_engine(DATABASE_URL)

Base = declarative_base()


class DBUser(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.USER)
    api_key = Column(String, unique=True, nullable=False)

    balances = relationship("DBBalance", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("DBOrder", back_populates="user", cascade="all, delete-orphan")

    def to_pydantic(self) -> User:
        return User(
            id=self.id,
            name=self.name,
            role=self.role,
            api_key=self.api_key
        )


class DBInstrument(Base):
    __tablename__ = "instruments"

    ticker = Column(String, primary_key=True)
    name = Column(String, nullable=False)

    balances = relationship("DBBalance", back_populates="instrument", cascade="all, delete-orphan")
    orders = relationship("DBOrder", back_populates="instrument", cascade="all, delete-orphan")
    transactions = relationship("DBTransaction", back_populates="instrument", cascade="all, delete-orphan")

    def to_pydantic(self) -> PydanticInstrument:
        return PydanticInstrument(
            ticker=self.ticker,
            name=self.name
        )


class DBBalance(Base):
    __tablename__ = "balances"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    ticker = Column(String, ForeignKey("instruments.ticker"), primary_key=True)
    amount = Column(Integer, nullable=False, default=0)

    user = relationship("DBUser", back_populates="balances")
    instrument = relationship("DBInstrument", back_populates="balances")


class DBOrder(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    ticker = Column(String, ForeignKey("instruments.ticker"), nullable=False)
    direction = Column(Enum(Direction), nullable=False)
    qty = Column(Integer, nullable=False)
    price = Column(Integer, nullable=True)  # Null для рыночных заявок
    status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.NEW)
    filled = Column(Integer, nullable=False, default=0)
    timestamp = Column(DateTime, nullable=False, default=func.now())

    user = relationship("DBUser", back_populates="orders")
    instrument = relationship("DBInstrument", back_populates="orders")

    def to_pydantic(self):
        if self.price is not None:  # Лимитная заявка
            body = LimitOrderBody(
                direction=self.direction,
                ticker=self.ticker,
                qty=self.qty,
                price=self.price
            )
            return PydanticLimitOrder(
                id=self.id,
                status=self.status,
                user_id=self.user_id,
                timestamp=self.timestamp,
                body=body,
                filled=self.filled
            )
        else:  # Рыночная заявка
            body = MarketOrderBody(
                direction=self.direction,
                ticker=self.ticker,
                qty=self.qty
            )
            return PydanticMarketOrder(
                id=self.id,
                status=self.status,
                user_id=self.user_id,
                timestamp=self.timestamp,
                body=body
            )


class DBTransaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker = Column(String, ForeignKey("instruments.ticker"), nullable=False)
    amount = Column(Integer, nullable=False)
    price = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=func.now())

    instrument = relationship("DBInstrument", back_populates="transactions")

    def to_pydantic(self) -> PydanticTransaction:
        return PydanticTransaction(
            ticker=self.ticker,
            amount=self.amount,
            price=self.price,
            timestamp=self.timestamp
        )


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_user(user_data: NewUser) -> User:
    with get_db() as db:
        user_id = uuid.uuid4()
        api_key = f"key-{uuid.uuid4()}"
        db_user = DBUser(
            id=user_id,
            name=user_data.name,
            role=UserRole.USER,
            api_key=api_key
        )
        db.add(db_user)
        return db_user.to_pydantic()


def get_user_by_api_key(api_key: str) -> Optional[User]:
    with get_db() as db:
        db_user = db.query(DBUser).filter(DBUser.api_key == api_key).first()
        if db_user:
            return db_user.to_pydantic()
        return None


def delete_user_by_id(user_id: uuid.UUID) -> Optional[User]:
    with get_db() as db:
        db_user = db.query(DBUser).filter(DBUser.id == user_id).first()
        if db_user:
            active_orders = db.query(DBOrder).filter(
                DBOrder.user_id == user_id,
                DBOrder.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED])
            ).all()

            for order in active_orders:
                order.status = OrderStatus.CANCELLED

            user = db_user.to_pydantic()

            db.delete(db_user)

            return user
        return None


def get_instruments() -> List[PydanticInstrument]:
    with get_db() as db:
        db_instruments = db.query(DBInstrument).all()
        return [instrument.to_pydantic() for instrument in db_instruments]


def add_instrument(instrument: PydanticInstrument) -> bool:
    with get_db() as db:
        existing = db.query(DBInstrument).filter(DBInstrument.ticker == instrument.ticker).first()
        if existing:
            return False

        db_instrument = DBInstrument(
            ticker=instrument.ticker,
            name=instrument.name
        )
        db.add(db_instrument)
        return True


def delete_instrument(ticker: str) -> bool:
    with get_db() as db:
        db_instrument = db.query(DBInstrument).filter(DBInstrument.ticker == ticker).first()
        if not db_instrument:
            return False

        active_orders = db.query(DBOrder).filter(
            DBOrder.ticker == ticker,
            DBOrder.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED])
        ).all()

        for order in active_orders:
            order.status = OrderStatus.CANCELLED

        db.delete(db_instrument)
        return True


def get_user_balances(user_id: uuid.UUID) -> Dict[str, int]:
    with get_db() as db:
        balances = db.query(DBBalance).filter(DBBalance.user_id == user_id).all()
        return {balance.ticker: balance.amount for balance in balances}


def deposit_balance(user_id: uuid.UUID, ticker: str, amount: int) -> bool:
    with get_db() as db:
        user = db.query(DBUser).filter(DBUser.id == user_id).first()
        if not user:
            return False

        instrument = db.query(DBInstrument).filter(DBInstrument.ticker == ticker).first()
        if not instrument:
            if ticker in ["USD", "EUR", "RUB"]:
                instrument = db.query(DBInstrument).filter(DBInstrument.ticker == ticker).first()
                if not instrument:
                    try:
                        instrument = DBInstrument(ticker=ticker, name=f"{ticker} Currency")
                        db.add(instrument)
                        db.flush()
                    except IntegrityError:
                        db.rollback()
                        instrument = db.query(DBInstrument).filter(DBInstrument.ticker == ticker).first()
            else:
                return False

        balance = db.query(DBBalance).filter(
            DBBalance.user_id == user_id,
            DBBalance.ticker == ticker
        ).first()

        if balance:
            balance.amount += amount
            return True
        else:
            try:
                balance = DBBalance(user_id=user_id, ticker=ticker, amount=amount)
                db.add(balance)
                db.flush()
                return True
            except IntegrityError:
                db.rollback()
                balance = db.query(DBBalance).filter(
                    DBBalance.user_id == user_id,
                    DBBalance.ticker == ticker
                ).first()
                if balance:
                    balance.amount += amount
                    return True
                return False


def withdraw_balance(user_id: uuid.UUID, ticker: str, amount: int) -> bool:
    with get_db() as db:
        balance = db.query(DBBalance).filter(
            DBBalance.user_id == user_id,
            DBBalance.ticker == ticker
        ).first()

        if not balance or balance.amount < amount:
            return False

        balance.amount -= amount
        return True


def create_order(user_id: uuid.UUID, order_data: Union[LimitOrderBody, MarketOrderBody]) -> uuid.UUID:
    with get_db() as db:
        ticker = order_data.ticker
        instrument = db.query(DBInstrument).filter(DBInstrument.ticker == ticker).first()
        if not instrument:
            raise ValueError(f"Instrument {ticker} not found")

        usd_instrument = db.query(DBInstrument).filter(DBInstrument.ticker == "USD").first()
        if not usd_instrument:
            try:
                usd_instrument = DBInstrument(ticker="USD", name="US Dollar")
                db.add(usd_instrument)
                db.flush()
            except IntegrityError:
                db.rollback()
                usd_instrument = db.query(DBInstrument).filter(DBInstrument.ticker == "USD").first()

        if isinstance(order_data, LimitOrderBody):
            if order_data.direction == Direction.BUY:
                required_balance = order_data.price * order_data.qty
                balance = db.query(DBBalance).filter(
                    DBBalance.user_id == user_id,
                    DBBalance.ticker == "USD"
                ).first()

                if not balance or balance.amount < required_balance:
                    raise ValueError("Insufficient balance")

                balance.amount -= required_balance

            else:
                balance = db.query(DBBalance).filter(
                    DBBalance.user_id == user_id,
                    DBBalance.ticker == ticker
                ).first()

                if not balance or balance.amount < order_data.qty:
                    raise ValueError(f"Insufficient {ticker} balance")

                balance.amount -= order_data.qty

            db_order = DBOrder(
                user_id=user_id,
                ticker=ticker,
                direction=order_data.direction,
                qty=order_data.qty,
                price=order_data.price,
                status=OrderStatus.NEW,
                filled=0
            )
        else:
            if order_data.direction == Direction.SELL:
                balance = db.query(DBBalance).filter(
                    DBBalance.user_id == user_id,
                    DBBalance.ticker == ticker
                ).first()

                if not balance or balance.amount < order_data.qty:
                    raise ValueError(f"Insufficient {ticker} balance")

                balance.amount -= order_data.qty

            db_order = DBOrder(
                user_id=user_id,
                ticker=ticker,
                direction=order_data.direction,
                qty=order_data.qty,
                price=None,
                status=OrderStatus.NEW,
                filled=0
            )

        db.add(db_order)
        db.flush()

        from app.matching_engine import MatchingEngine
        matching_engine = MatchingEngine()
        matching_engine.process_order(db_order.to_pydantic(), db)

        return db_order.id


def get_order_by_id(order_id: uuid.UUID) -> Optional[Union[PydanticLimitOrder, PydanticMarketOrder]]:
    with get_db() as db:
        db_order = db.query(DBOrder).filter(DBOrder.id == order_id).first()
        if db_order:
            return db_order.to_pydantic()
        return None


def get_user_orders(user_id: uuid.UUID) -> List[Union[PydanticLimitOrder, PydanticMarketOrder]]:
    with get_db() as db:
        db_orders = db.query(DBOrder).filter(DBOrder.user_id == user_id).all()
        return [order.to_pydantic() for order in db_orders]


def cancel_order(order_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    with get_db() as db:
        db_order = db.query(DBOrder).filter(
            DBOrder.id == order_id,
            DBOrder.user_id == user_id,
            DBOrder.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED])
        ).first()

        if not db_order:
            return False

        if db_order.price is not None:
            if db_order.direction == Direction.BUY:
                remaining_qty = db_order.qty - db_order.filled
                refund = remaining_qty * db_order.price

                balance = db.query(DBBalance).filter(
                    DBBalance.user_id == user_id,
                    DBBalance.ticker == "USD"
                ).first()

                if not balance:
                    balance = DBBalance(user_id=user_id, ticker="USD", amount=refund)
                    db.add(balance)
                else:
                    balance.amount += refund
            else:
                remaining_qty = db_order.qty - db_order.filled

                balance = db.query(DBBalance).filter(
                    DBBalance.user_id == user_id,
                    DBBalance.ticker == db_order.ticker
                ).first()

                if not balance:
                    balance = DBBalance(user_id=user_id, ticker=db_order.ticker, amount=remaining_qty)
                    db.add(balance)
                else:
                    balance.amount += remaining_qty

        db_order.status = OrderStatus.CANCELLED
        return True


def get_orderbook(ticker: str, limit: int) -> L2OrderBook:
    with get_db() as db:
        active_orders = db.query(DBOrder).filter(
            DBOrder.ticker == ticker,
            DBOrder.price != None,
            DBOrder.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED])
        ).all()

        bids = {}
        asks = {}

        for order in active_orders:
            price = order.price
            remaining_qty = order.qty - order.filled

            if order.direction == Direction.BUY:
                if price not in bids:
                    bids[price] = 0
                bids[price] += remaining_qty
            else:
                if price not in asks:
                    asks[price] = 0
                asks[price] += remaining_qty

        bid_levels = [Level(price=price, qty=qty) for price, qty in bids.items()]
        ask_levels = [Level(price=price, qty=qty) for price, qty in asks.items()]

        bid_levels.sort(key=lambda x: x.price, reverse=True)
        ask_levels.sort(key=lambda x: x.price)

        bid_levels = bid_levels[:limit]
        ask_levels = ask_levels[:limit]

        return L2OrderBook(bid_levels=bid_levels, ask_levels=ask_levels)


def get_transactions(ticker: str, limit: int) -> List[PydanticTransaction]:
    with get_db() as db:
        db_transactions = db.query(DBTransaction).filter(
            DBTransaction.ticker == ticker
        ).order_by(DBTransaction.timestamp.desc()).limit(limit).all()

        return [transaction.to_pydantic() for transaction in db_transactions]


def record_transaction(ticker: str, amount: int, price: int):
    with get_db() as db:
        transaction = DBTransaction(
            ticker=ticker,
            amount=amount,
            price=price
        )
        db.add(transaction)


def create_tables():
    Base.metadata.create_all(bind=engine)


def create_admin_user() -> User:
    with get_db() as db:
        admin = db.query(DBUser).filter(DBUser.role == UserRole.ADMIN).first()
        if admin:
            return admin.to_pydantic()

        admin_id = uuid.uuid4()
        api_key = os.getenv("ADMIN_API_KEY", f"admin-key-{uuid.uuid4()}")

        admin = DBUser(
            id=admin_id,
            name="Admin",
            role=UserRole.ADMIN,
            api_key=api_key
        )

        db.add(admin)
        db.flush()

        return admin.to_pydantic()
