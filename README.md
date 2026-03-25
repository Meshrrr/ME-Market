# Trading Platform API

Веб-приложение для торговой платформы (биржи) на FastAPI. Поддерживает лимитные и рыночные ордера, управление балансом и инвентарём инструментов.
Проект от Точка Банк.

##  Возможности

- **Аутентификация** — JWT-токены с префиксом `TOKEN`
- **Ордера** — лимитные и рыночные ордера на покупку/продажу
- **Orderbook** — агрегированный стакан заявок (bid/ask levels)
- **Транзакции** — история сделок по инструментам
- **Баланс** — управление балансом и инвентарём пользователей
- **Админ-панель** — управление пользователями, инструментами и балансами
- **Docker** — полная контейнеризация с PostgreSQL и Nginx


## 📦 Установка и запуск

### Требования

- Docker
- Docker Compose

### Быстрый старт

```bash
# Клонирование репозитория
git clone <repository-url>
cd <repository-name>

# Запуск всех сервисов
docker-compose up --build
```

После запуска доступны:

| Сервис | URL |
|--------|-----|
| API | http://localhost/api/v1 |
| Nginx | http://localhost:80 |
| PostgreSQL | localhost:5433 |

## 📚 API Endpoints

### Публичные

| Метод | Путь | Описание |
|-------|------|----------|
| `POST` | `/api/v1/public/register` | Регистрация пользователя |
| `GET` | `/api/v1/public/instrument` | Список инструментов |
| `GET` | `/api/v1/public/orderbook/{ticker}` | Стакан заявок |
| `GET` | `/api/v1/public/transactions/{ticker}` | История транзакций |

### Ордера (требует авторизации)

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/v1/order` | Список ордеров пользователя |
| `POST` | `/api/v1/order` | Создание ордера |
| `GET` | `/api/v1/order/{order_id}` | Получить ордер |
| `DELETE` | `/api/v1/order/{order_id}` | Отмена ордера |

### Баланс (требует авторизации)

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/v1/balance` | Баланс пользователя |

### Админ (требует роль ADMIN)

| Метод | Путь | Описание |
|-------|------|----------|
| `POST` | `/api/v1/admin/instrument` | Создание инструмента |
| `DELETE` | `/api/v1/admin/instrument/{ticker}` | Удаление инструмента |
| `POST` | `/api/v1/admin/balance/deposit` | Пополнение баланса |
| `POST` | `/api/v1/admin/balance/withdraw` | Снятие баланса |
| `DELETE` | `/api/v1/admin/user/{user_id}` | Удаление пользователя |

## 🔐 Аутентификация

API использует JWT-токены с префиксом `TOKEN`.

**Заголовок:**
```
Authorization: TOKEN <jwt_token>
```

При регистрации возвращается `api_key` — ваш токен для дальнейших запросов.

## 📋 Примеры запросов

### Регистрация пользователя

```bash
curl -X POST http://localhost/api/v1/public/register \
  -H "Content-Type: application/json" \
  -d '{"name": "username"}'
```

Ответ:
```json
{
  "name": "username",
  "id": "uuid-...",
  "role": "user",
  "api_key": "eyJ..."
}
```

### Создание ордера

```bash
curl -X POST http://localhost/api/v1/order \
  -H "Authorization: TOKEN <api_key>" \
  -H "Content-Type: application/json" \
  -d '{"direction": "BUY", "ticker": "MEMECOIN", "qty": 10, "price": 100}'
```

### Просмотр стакана

```bash
curl http://localhost/api/v1/public/orderbook/MEMECOIN
```

Ответ:
```json
{
  "bid_levels": [{"price": 100, "qty": 5}],
  "ask_levels": [{"price": 110, "qty": 3}]
}
```
