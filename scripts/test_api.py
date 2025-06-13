import requests
import json
import os
import sys
import time
import random
from datetime import datetime

BASE_URL = os.getenv("API_URL", "http://localhost:8000")

def test_api():
    try:
        print("Регистрация пользователей...")
        user1 = register_user("Trader 1")
        user2 = register_user("Trader 2")

        if not user1 or not user2:
            print("Ошибка при регистрации пользователей")
            return

        print(f"Пользователь 1: {user1['name']} (ID: {user1['id']}, API Key: {user1['api_key']})")
        print(f"Пользователь 2: {user2['name']} (ID: {user2['id']}, API Key: {user2['api_key']})")

        print("\nПолучение списка инструментов...")
        instruments = get_instruments()

        if not instruments:
            print("Ошибка при получении списка инструментов или список пуст")
            print("Добавление базовых инструментов...")
            add_instruments(user1['api_key'])
            instruments = get_instruments()

        print(f"Доступные инструменты: {', '.join([i['ticker'] for i in instruments])}")

        print("\nПополнение балансов пользователей...")
        deposit_balance(user1['api_key'], user1['id'], "USD", 10000)
        deposit_balance(user1['api_key'], user2['id'], "USD", 10000)
        deposit_balance(user1['api_key'], user1['id'], "AAPL", 100)
        deposit_balance(user1['api_key'], user2['id'], "MSFT", 100)

        print("\nПроверка балансов...")
        balance1 = get_balance(user1['api_key'])
        balance2 = get_balance(user2['api_key'])

        print(f"Баланс пользователя 1: {balance1}")
        print(f"Баланс пользователя 2: {balance2}")

        print("\nСоздание заявок...")
        order1 = create_limit_order(user1['api_key'], "BUY", "AAPL", 10, 150)
        print(f"Заявка 1 (покупка AAPL): {order1}")

        order2 = create_limit_order(user2['api_key'], "SELL", "AAPL", 5, 155)
        print(f"Заявка 2 (продажа AAPL): {order2}")

        print("\nПроверка стакана заявок для AAPL...")
        orderbook = get_orderbook("AAPL")
        print(f"Стакан заявок: {orderbook}")

        print("\nСоздание рыночной заявки для сопоставления...")
        order3 = create_market_order(user2['api_key'], "SELL", "AAPL", 3)
        print(f"Заявка 3 (рыночная продажа AAPL): {order3}")

        time.sleep(1)

        print("\nПроверка статуса заявок...")
        order1_status = get_order(user1['api_key'], order1['order_id'])
        print(f"Статус заявки 1: {order1_status}")

        print("\nПроверка истории сделок для AAPL...")
        transactions = get_transactions("AAPL")
        print(f"История сделок: {transactions}")

        print("\nОтмена оставшихся заявок...")
        cancel_order(user1['api_key'], order1['order_id'])
        cancel_order(user2['api_key'], order2['order_id'])

        print("\nПроверка обновленных балансов...")
        balance1 = get_balance(user1['api_key'])
        balance2 = get_balance(user2['api_key'])

        print(f"Обновленный баланс пользователя 1: {balance1}")
        print(f"Обновленный баланс пользователя 2: {balance2}")

        print("\nТестирование API завершено успешно!")

    except Exception as e:
        print(f"Произошла ошибка при тестировании API: {str(e)}")


def register_user(name):
    response = requests.post(
        f"{BASE_URL}/api/v1/public/register",
        json={"name": name}
    )

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Ошибка при регистрации пользователя: {response.text}")
        return None


def get_instruments():
    response = requests.get(f"{BASE_URL}/api/v1/public/instrument")

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Ошибка при получении списка инструментов: {response.text}")
        return None


def add_instruments(api_key):
    instruments = [
        {"name": "US Dollar", "ticker": "USD"},
        {"name": "Apple Inc.", "ticker": "AAPL"},
        {"name": "Microsoft Corporation", "ticker": "MSFT"},
        {"name": "Amazon.com Inc.", "ticker": "AMZN"},
        {"name": "Tesla Inc.", "ticker": "TSLA"},
        {"name": "Meme Coin", "ticker": "MEMCOIN"}
    ]

    headers = {"Authorization": f"TOKEN {api_key}"}

    for instrument in instruments:
        response = requests.post(
            f"{BASE_URL}/api/v1/admin/instrument",
            headers=headers,
            json=instrument
        )

        if response.status_code == 200:
            print(f"Добавлен инструмент: {instrument['ticker']}")
        else:
            print(f"Ошибка при добавлении инструмента {instrument['ticker']}: {response.text}")


def deposit_balance(api_key, user_id, ticker, amount):
    headers = {"Authorization": f"TOKEN {api_key}"}

    response = requests.post(
        f"{BASE_URL}/api/v1/admin/balance/deposit",
        headers=headers,
        json={
            "user_id": user_id,
            "ticker": ticker,
            "amount": amount
        }
    )

    if response.status_code == 200:
        print(f"Баланс пользователя {user_id} пополнен: {ticker} +{amount}")
        return True
    else:
        print(f"Ошибка при пополнении баланса: {response.text}")
        return False


def get_balance(api_key):
    headers = {"Authorization": f"TOKEN {api_key}"}

    response = requests.get(
        f"{BASE_URL}/api/v1/balance",
        headers=headers
    )

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Ошибка при получении баланса: {response.text}")
        return None


def create_limit_order(api_key, direction, ticker, qty, price):
    headers = {"Authorization": f"TOKEN {api_key}"}

    response = requests.post(
        f"{BASE_URL}/api/v1/order",
        headers=headers,
        json={
            "direction": direction,
            "ticker": ticker,
            "qty": qty,
            "price": price
        }
    )

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Ошибка при создании лимитной заявки: {response.text}")
        return None


def create_market_order(api_key, direction, ticker, qty):
    headers = {"Authorization": f"TOKEN {api_key}"}

    response = requests.post(
        f"{BASE_URL}/api/v1/order",
        headers=headers,
        json={
            "direction": direction,
            "ticker": ticker,
            "qty": qty
        }
    )

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Ошибка при создании рыночной заявки: {response.text}")
        return None


def get_order(api_key, order_id):
    headers = {"Authorization": f"TOKEN {api_key}"}

    response = requests.get(
        f"{BASE_URL}/api/v1/order/{order_id}",
        headers=headers
    )

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Ошибка при получении информации о заявке: {response.text}")
        return None


def cancel_order(api_key, order_id):
    headers = {"Authorization": f"TOKEN {api_key}"}

    response = requests.delete(
        f"{BASE_URL}/api/v1/order/{order_id}",
        headers=headers
    )

    if response.status_code == 200:
        print(f"Заявка {order_id} отменена")
        return True
    else:
        print(f"Ошибка при отмене заявки: {response.text}")
        return False


def get_orderbook(ticker):
    response = requests.get(f"{BASE_URL}/api/v1/public/orderbook/{ticker}")

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Ошибка при получении стакана заявок: {response.text}")
        return None


def get_transactions(ticker):
    response = requests.get(f"{BASE_URL}/api/v1/public/transactions/{ticker}")

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Ошибка при получении истории сделок: {response.text}")
        return None


if __name__ == "__main__":
    test_api()