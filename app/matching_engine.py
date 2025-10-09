from typing import Dict, List, Union, Optional
from app.models import (
    LimitOrder, MarketOrder, OrderStatus, Direction
)
import threading


class MatchingEngine:
    def __init__(self):
        self.lock = threading.RLock()

    def process_order(self, order: Union[LimitOrder, MarketOrder]) -> None:
        from app.database import get_db, DBOrder, DBBalance, DBTransaction

        with self.lock:
            if isinstance(order, MarketOrder):
                self._process_market_order(order)
            else:  # LimitOrder
                self._process_limit_order(order)

    def _process_market_order(self, order: MarketOrder) -> None:

        from app.database import get_db, DBOrder, DBBalance, DBTransaction, record_transaction

        ticker = order.body.ticker
        qty_to_fill = order.body.qty

        with get_db() as db:
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

    def _process_limit_order(self, order: LimitOrder) -> None:

        from app.database import get_db, DBOrder, DBBalance, DBTransaction

        ticker = order.body.ticker
        price = order.body.price
        qty_to_fill = order.body.qty

        with get_db() as db:
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
            buyer_balance = DBBalance(user_id=buyer_id, ticker=ticker, amount=qty)
            db.add(buyer_balance)

        total_cost = qty * price
        seller_balance = db.query(DBBalance).filter(
            DBBalance.user_id == seller_id,
            DBBalance.ticker == "USDT"
        ).first()

        if seller_balance:
            seller_balance.amount += total_cost
        else:
            seller_balance = DBBalance(user_id=seller_id, ticker="USDT", amount=total_cost)
            db.add(seller_balance)
