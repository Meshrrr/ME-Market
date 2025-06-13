import requests
import json
import os
import sys

BASE_URL = os.getenv("API_URL", "http://localhost:8000")


def create_admin_user():
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/public/register",
            json={"name": "Admin User"}
        )

        if response.status_code != 200:
            print(f"Ошибка при создании пользователя: {response.text}")
            return

        user_data = response.json()
        user_id = user_data["id"]
        api_key = user_data["api_key"]

        print(f"Создан пользователь:")
        print(f"ID: {user_id}")
        print(f"API Key: {api_key}")
        print("\nСохраните этот API ключ, он понадобится для административных операций!")

        add_instruments(api_key)

    except Exception as e:
        print(f"Произошла ошибка: {str(e)}")


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


if __name__ == "__main__":
    create_admin_user()