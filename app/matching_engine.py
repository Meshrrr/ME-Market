from typing import Dict, List, Union, Optional

from sqlalchemy.exc import IntegrityError

from app.database import DBInstrument
from app.models import (
    LimitOrder, MarketOrder, OrderStatus, Direction
)
import threading


class MatchingEngine:
    def __init__(self):
        self.lock = threading.RLock()

    def process_order(self, order: Union[LimitOrder, MarketOrder], db) -> None:
        from app.database import DBOrder, DBBalance, DBTransaction

        with self.lock:
            if isinstance(order, MarketOrder):
                self._process_market_order(order, db)
            else:
                self._process_limit_order(order, db)

    def _process_market_order(self, order: MarketOrder, db) -> None:

        from app.database import DBOrder, DBBalance, DBTransaction, record_transaction, DBInstrument

        ticker = order.body.ticker
        qty_to_fill = order.body.qty

        matching_orders = db.query(DBOrder).filter(
            DBOrder.ticker == ticker,
            DBOrder.price != None,
            DBOrder.direction != order.body.direction,
            DBOrder.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED])
        ).all()

        if order.body.direction == Direction.BUY:
            matching_orders.sort(key=lambda x: x.price)
        else:
            matching_orders.sort(key=lambda x: x.price, reverse=True)

        for matching_order in matching_orders:
            if qty_to_fill <= 0:
                break

            available_qty = matching_order.qty - matching_order.filled
            match_qty = min(qty_to_fill, available_qty)
            price = matching_order.price

            if order.body.direction == Direction.BUY:
                buyer_usd = db.query(DBBalance).filter(
                    DBBalance.user_id == order.user_id,
                    DBBalance.ticker == "USD"
                ).first()

                if not buyer_usd or buyer_usd.amount <= 0:
                    break

                max_affordable = buyer_usd.amount // price
                if max_affordable <= 0:
                    break
                if match_qty > max_affordable:
                    match_qty = max_affordable

                buyer_usd.amount -= match_qty * price

                matching_order.filled += match_qty
                qty_to_fill -= match_qty

                if matching_order.filled == matching_order.qty:
                    matching_order.status = OrderStatus.EXECUTED
                else:
                    matching_order.status = OrderStatus.PARTIALLY_EXECUTED

                self._update_balances_after_match(
                    db, order.user_id, matching_order.user_id,
                    ticker, match_qty, price,
                    order.body.direction
                )

                transaction = DBTransaction(
                    ticker=ticker,
                    amount=match_qty,
                    price=price
                )
                db.add(transaction)

            db_order = db.query(DBOrder).filter(DBOrder.id == order.id).first()
            if db_order:
                if qty_to_fill == 0:
                    db_order.status = OrderStatus.EXECUTED
                elif qty_to_fill == order.body.qty:
                    db_order.status = OrderStatus.CANCELLED
                else:
                    db_order.status = OrderStatus.PARTIALLY_EXECUTED
                    if db_order:
                        db_order.filled = order.body.qty - qty_to_fill


    def _process_limit_order(self, order: LimitOrder, db) -> None:
        from app.database import DBOrder, DBBalance, DBTransaction

        ticker = order.body.ticker
        price = order.body.price
        qty_to_fill = order.body.qty

        matching_orders = db.query(DBOrder).filter(
            DBOrder.ticker == ticker,
            DBOrder.price != None,  # лимитки только
            DBOrder.direction != order.body.direction,
            DBOrder.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_EXECUTED])
        ).all()

        if order.body.direction == Direction.BUY:
            matching_orders = [o for o in matching_orders if o.price <= price]
            matching_orders.sort(key=lambda x: x.price)
        else:
            matching_orders = [o for o in matching_orders if o.price >= price]
            matching_orders.sort(key=lambda x: x.price, reverse=True)

            for matching_order in matching_orders:
                if qty_to_fill <= 0:
                    break

                available_qty = matching_order.qty - matching_order.filled
                match_qty = min(qty_to_fill, available_qty)
                match_price = matching_order.price  # Цена исполнения - цена существующей заявки

                matching_order.filled += match_qty
                qty_to_fill -= match_qty

                if matching_order.filled == matching_order.qty:
                    matching_order.status = OrderStatus.EXECUTED
                else:
                    matching_order.status = OrderStatus.PARTIALLY_EXECUTED

                self._update_balances_after_match(
                    db, order.user_id, matching_order.user_id,
                    ticker, match_qty, match_price,
                    order.body.direction
                )

                # Записываем транзакцию
                transaction = DBTransaction(
                    ticker=ticker,
                    amount=match_qty,
                    price=match_price
                )
                db.add(transaction)

            db_order = db.query(DBOrder).filter(DBOrder.id == order.id).first()
            if db_order:
                db_order.filled = order.body.qty - qty_to_fill
                if qty_to_fill == 0:
                    db_order.status = OrderStatus.EXECUTED
                elif qty_to_fill < order.body.qty:
                    db_order.status = OrderStatus.PARTIALLY_EXECUTED

    def _update_balances_after_match(
            self, db, buyer_id, seller_id, ticker, qty, price, direction
    ):
        from app.database import DBBalance

        if direction == Direction.BUY:
            buyer_id, seller_id = buyer_id, seller_id
        else:
            buyer_id, seller_id = seller_id, buyer_id

        buyer_balance = db.query(DBBalance).filter(
            DBBalance.user_id == buyer_id,
            DBBalance.ticker == ticker
        ).first()

        if buyer_balance:
            buyer_balance.amount += qty
        else:
            instrument = db.query(DBInstrument).filter(DBInstrument.ticker == ticker).first()
            if not instrument:
                raise ValueError(f"Instrument {ticker} not found")

            buyer_balance = DBBalance(user_id=buyer_id, ticker=ticker, amount=qty)
            db.add(buyer_balance)
            db.flush()

        total_cost = qty * price
        seller_balance = db.query(DBBalance).filter(
            DBBalance.user_id == seller_id,
            DBBalance.ticker == "USD"
        ).first()

        if seller_balance:
            seller_balance.amount += total_cost
        else:
            usd_instrument = db.query(DBInstrument).filter(DBInstrument.ticker == "USD").first()
            if not usd_instrument:
                try:
                    usd_instrument = DBInstrument(ticker="USD", name="US Dollar")
                    db.add(usd_instrument)
                    db.flush()
                except IntegrityError:
                    db.rollback()
                    usd_instrument = db.query(DBInstrument).filter(DBInstrument.ticker == "USD").first()

            seller_balance = DBBalance(user_id=seller_id, ticker="USD", amount=total_cost)
            db.add(seller_balance)
            db.flush()

