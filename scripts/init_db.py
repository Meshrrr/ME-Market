import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:kirill18032005@localhost:5432/postgres")


def create_database():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM pg_database WHERE datname = 'stock_exchange'")
        exists = cursor.fetchone()

        if not exists:
            cursor.execute("CREATE DATABASE stock_exchange")
            print("База данных 'stock_exchange' успешно создана")
        else:
            print("База данных 'stock_exchange' уже существует")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"Ошибка при создании базы данных: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    create_database()