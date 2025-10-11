import uuid

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from database.database import Base
from datetime import datetime
from enum import Enum as PythonEnum
from sqlalchemy.dialects.postgresql import UUID

class RoleEnum(PythonEnum):
    USER = "user"
    ADMIN = "admin"

class DirectionEnum(PythonEnum):
    ASK = "ask"
    BID = "bid"

class OrderStatusEnum(PythonEnum):
    NEW = "NEW"
    EXECUTED = "EXECUTED"
    PARTIALLY_EXECUTED = "PARTIALLY_EXECUTED"
    CANCELLED = "CANCELLED"

class User(Base):
    __tablename__ = 'users'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=False, nullable=False)
    role = Column(Enum(RoleEnum), default=RoleEnum.USER)
    balance = Column(Float, default=0.0)
    api_key = Column(String, unique=False, nullable=True)
    # Создаем отношения
    orders = relationship("Order", back_populates="user", cascade="all, delete-orphan", passive_deletes=True)
    transactions_sent = relationship("Transaction", foreign_keys='Transaction.user_from_id', back_populates="user_from")
    transactions_received = relationship("Transaction", foreign_keys='Transaction.user_to_id', back_populates="user_to")
    inventory = relationship("UserInventory", back_populates="user", cascade="all, delete-orphan", passive_deletes=True)

class UserInventory(Base):
    __tablename__ = 'user_inventories'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    instrument_ticker = Column(String(10), ForeignKey('instruments.ticker', ondelete="CASCADE"), nullable=False)
    quantity = Column(Float, nullable=False, default=0.0)

    # Создаем отношения
    user = relationship("User", back_populates="inventory")
    instrument = relationship("Instrument")


class Order(Base):
    __tablename__ = 'orders'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    instrument_ticker = Column(String(10), ForeignKey('instruments.ticker', ondelete="CASCADE"), nullable=False)
    amount = Column(Integer, nullable=False)
    filled = Column(Integer, nullable=False, default=0)
    price = Column(Integer, nullable=True)
    direction = Column(Enum(DirectionEnum), nullable=False)
    status = Column(Enum(OrderStatusEnum), default=OrderStatusEnum.NEW)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Создаем отношения
    user = relationship("User", back_populates="orders")
    instrument = relationship("Instrument")


class Transaction(Base):
    __tablename__ = 'transactions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_from_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete="SET NULL"), nullable=True)
    user_to_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete="SET NULL"), nullable=True)
    instrument_ticker = Column(String(10), ForeignKey('instruments.ticker', ondelete="SET NULL"), nullable=True)
    amount = Column(Float, nullable=False)
    price = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Создаем отношения
    user_from = relationship("User", foreign_keys=[user_from_id], back_populates="transactions_sent")
    user_to = relationship("User", foreign_keys=[user_to_id], back_populates="transactions_received")
    instrument = relationship("Instrument")


class Instrument(Base):
    __tablename__ = 'instruments'

    ticker = Column(String(10), primary_key=True, unique=True, nullable=False)
    name = Column(String(100), nullable=False)

    # Обратные связи (если нужны)
    inventories = relationship("UserInventory", back_populates="instrument", cascade="all, delete-orphan", passive_deletes=True)
    orders = relationship("Order", back_populates="instrument", cascade="all, delete-orphan", passive_deletes=True)
    transactions = relationship("Transaction", back_populates="instrument")
