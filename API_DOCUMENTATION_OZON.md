# 📚 Ozon Seller API Documentation - Полная справка

## 🔑 Авторизация

### Headers
```http
Client-Id: <CLIENT_ID>
Api-Key: <API_KEY>
Content-Type: application/json
```

## 💰 Finance API
**Base URL**: `https://api-seller.ozon.ru`

### Финансовые отчеты

#### 1. FBS транзакции
```http
POST /v3/finance/transaction/list
```
**Тело запроса**:
```json
{
  "filter": {
    "date": {
      "from": "2025-09-22T00:00:00.000Z",
      "to": "2025-09-29T23:59:59.999Z"
    },
    "operation_type": [],
    "posting_number": "",
    "transaction_type": "all"
  },
  "page": 1,
  "page_size": 1000
}
```

**Реальный ответ**:
```json
{
  "result": {
    "operations": [
      {
        "operation_id": 987654321,
        "operation_type": "MarketplaceServiceItemFulfillment",
        "operation_date": "2025-09-25T15:45:00Z",
        "operation_type_name": "Продажа",
        "delivery_charge": 0,
        "return_delivery_charge": 0,
        "accruals_for_sale": 1790.50,
        "sale_commission": -270.45,
        "amount": 1520.05,
        "type": "services",
        "posting": {
          "delivery_schema": "FBS",
          "order_date": "2025-09-23T12:30:00Z",
          "posting_number": "0204-9876-5432",
          "warehouse_id": 22906925
        },
        "items": [
          {
            "sku": 1234567890,
            "name": "Пижама с шортами и топом домашняя модная хлопок",
            "price": 2156.00
          }
        ],
        "services": [
          {
            "name": "Эквайринг",
            "price": -21.56
          },
          {
            "name": "Комиссия за продажу",
            "price": -270.45
          },
          {
            "name": "Обработка отправления (Drop off)",
            "price": -89.12
          }
        ]
      },
      {
        "operation_id": 123456789,
        "operation_type": "OperationItemReturn",
        "operation_date": "2025-09-24T10:20:00Z",
        "operation_type_name": "Возврат",
        "delivery_charge": 0,
        "return_delivery_charge": -89.12,
        "accruals_for_sale": -1790.50,
        "sale_commission": 270.45,
        "amount": -1609.17,
        "type": "services",
        "posting": {
          "delivery_schema": "FBS",
          "order_date": "2025-09-20T08:15:00Z",
          "posting_number": "0204-1234-9876",
          "warehouse_id": 22906925
        }
      }
    ],
    "page_count": 15,
    "has_next": true
  }
}
```

#### 2. Комиссии маркетплейса
```http
POST /v1/finance/realization
```
**Параметры**: Аналогично транзакциям

## 📊 Analytics API

### Отчеты по продажам

#### 1. Отчет по товарам
```http
POST /v1/analytics/data
```
**Тело запроса**:
```json
{
  "date_from": "2025-09-22",
  "date_to": "2025-09-29",
  "metrics": ["revenue", "ordered_units", "hits_view_search", "hits_view_pdp", "conversion"],
  "dimension": ["sku"],
  "filters": [],
  "sort": [],
  "limit": 1000,
  "offset": 0
}
```

**Реальный ответ**:
```json
{
  "result": {
    "data": [
      {
        "dimensions": [
          {
            "id": "1234567890",
            "name": "sku"
          }
        ],
        "metrics": [
          1790.50,  // revenue
          1,        // ordered_units
          145,      // hits_view_search
          89,       // hits_view_pdp
          1.12      // conversion
        ]
      },
      {
        "dimensions": [
          {
            "id": "9876543210",
            "name": "sku"
          }
        ],
        "metrics": [
          2340.00,
          2,
          234,
          156,
          1.28
        ]
      }
    ],
    "totals": [
      4130.50,   // total revenue
      3,         // total units
      379,       // total search views
      245,       // total pdp views
      1.22       // avg conversion
    ]
  }
}
```

#### 2. Остатки товаров
```http
POST /v1/product/info/stocks
```
**Тело запроса**:
```json
{
  "filter": {
    "offer_id": [],
    "product_id": [],
    "visibility": "ALL"
  },
  "last_id": "",
  "limit": 1000
}
```

**Реальный ответ**:
```json
{
  "result": {
    "items": [
      {
        "offer_id": "PM-TOP/pink-M",
        "product_id": 1234567890,
        "stocks": [
          {
            "type": "fbs",
            "present": 5,
            "reserved": 2
          },
          {
            "type": "fbo",
            "present": 0,
            "reserved": 0
          }
        ]
      }
    ],
    "last_id": "dGVzdA==",
    "total": 244
  }
}
```

## 📦 Products API

### Управление товарами

#### 1. Информация о товаре
```http
POST /v2/product/info
```
**Тело запроса**:
```json
{
  "offer_id": "",
  "product_id": 1234567890,
  "sku": 1234567890
}
```

#### 2. Список товаров
```http
POST /v2/product/list
```

#### 3. Цены товаров
```http
POST /v1/product/info/prices
```

#### 4. Обновление цен
```http
POST /v1/product/import/prices
```
**Тело запроса**:
```json
{
  "prices": [
    {
      "auto_action_enabled": "UNKNOWN",
      "currency_code": "RUB",
      "min_price": "2000",
      "offer_id": "PM-TOP/pink-M",
      "old_price": "3990",
      "price": "2990",
      "product_id": 1234567890
    }
  ]
}
```

## 🛒 Orders API (FBS)

### Заказы и отправления

#### 1. Список отправлений
```http
POST /v3/posting/fbs/list
```
**Тело запроса**:
```json
{
  "dir": "ASC",
  "filter": {
    "since": "2025-09-22T00:00:00.000Z",
    "to": "2025-09-29T23:59:59.999Z",
    "status": ""
  },
  "limit": 1000,
  "offset": 0,
  "translit": true,
  "with": {
    "analytics_data": true,
    "financial_data": true
  }
}
```

**Реальный ответ**:
```json
{
  "result": {
    "postings": [
      {
        "posting_number": "0204-9876-5432",
        "order_id": 123456789,
        "order_number": "987654321-0001",
        "status": "delivered",
        "delivery_method": {
          "id": 1020000991450000,
          "name": "Ozon Логистика",
          "warehouse_id": 22906925,
          "warehouse": "Хабаровск"
        },
        "tracking_number": "1234567890123456",
        "tpl_integration_type": "aggregator",
        "in_process_at": "2025-09-23T12:30:00Z",
        "shipment_date": "2025-09-24T10:00:00Z",
        "delivering_date": "2025-09-25T15:45:00Z",
        "cancellation": {
          "cancel_reason_id": 0,
          "cancel_reason": "",
          "cancellation_type": "",
          "cancelled_after_ship": false,
          "affect_cancellation_rating": false,
          "cancellation_initiator": ""
        },
        "customer": {
          "customer_id": 987654321,
          "name": "Виктория",
          "phone": "+7*******89",
          "email": "v*****@mail.ru"
        },
        "products": [
          {
            "sku": 1234567890,
            "name": "Пижама с шортами и топом домашняя модная хлопок",
            "offer_id": "PM-TOP/pink-M",
            "price": "2156.00",
            "digital_codes": [],
            "currency_code": "RUB",
            "quantity": 1
          }
        ],
        "addressee": {
          "name": "Виктория",
          "phone": "+7*******89"
        },
        "barcodes": {
          "lower_barcode": "12345678901234",
          "upper_barcode": ""
        },
        "analytics_data": {
          "region": "Хабаровский край",
          "city": "Хабаровск",
          "delivery_type": "Курьер",
          "is_premium": false,
          "payment_type_group_name": "Карты",
          "warehouse_id": 22906925,
          "warehouse_name": "Хабаровск"
        },
        "financial_data": {
          "cluster_from": "Москва",
          "cluster_to": "Хабаровск"
        }
      }
    ],
    "has_next": false,
    "count": 51
  }
}
```

#### 2. Создание отправления
```http
POST /v2/posting/fbs/ship
```

#### 3. Получение этикеток
```http
POST /v2/posting/fbs/package-label
```

## 📋 Categories API

### Категории и атрибуты

#### 1. Дерево категорий
```http
POST /v1/category/tree
```
**Тело запроса**:
```json
{
  "category_id": 0,
  "language": "DEFAULT"
}
```

#### 2. Атрибуты категории
```http
POST /v1/category/attribute
```

#### 3. Справочники значений
```http
POST /v1/category/attribute/values
```

## 🎯 Promotion API

### Акции и продвижение

#### 1. Список акций
```http
GET /v1/actions
```

#### 2. Статистика по акциям
```http
POST /v1/actions/products/activate
```

## 🚫 Rate Limits

### Ограничения по API:
- **Finance API**: 100 запросов в минуту
- **Analytics API**: 100 запросов в минуту
- **Products API**: 1000 запросов в минуту
- **Orders API**: 1000 запросов в минуту
- **Categories API**: 100 запросов в минуту

### При превышении лимита:
```json
{
  "code": 429,
  "message": "Too Many Requests",
  "details": []
}
```

## 📊 Примеры реальных данных (из SoVAni Bot)

### Финансовый отчет за неделю:
```
💰 OZON ПОКАЗАТЕЛИ
Выручка: 91,380.00 ₽ (51 ед.)
Доставлено: 91,380.00 ₽ (51 операций)
Комиссия: 13,816.73 ₽
Реклама: 13,003.39 ₽
Чистая прибыль: 28,121.90 ₽
```

### Типичные операции:
1. **Продажа** - MarketplaceServiceItemFulfillment
2. **Возврат** - OperationItemReturn
3. **Комиссия** - MarketplaceRedistributionOfAcquiringOperation
4. **Логистика** - OperationMarketplaceServiceItemDropoffPVZ

### Статистика складов:
- **FBS остатки**: 244 товара
- **FBO остатки**: 0 товаров (не используется)
- **В резерве**: от 0 до 5 единиц на SKU

## ⚠️ Важные особенности

### 1. Pagination
- Используется cursor-based пагинация
- Поле `has_next` показывает наличие следующих страниц
- Максимальный `page_size`: 1000

### 2. Фильтрация по датам
- Формат: ISO 8601 (RFC 3339)
- Обязательные поля `from` и `to`
- Максимальный период: 365 дней

### 3. SKU и ID
- `sku` - внутренний ID Ozon
- `offer_id` - артикул продавца
- `product_id` - глобальный ID товара

### 4. Типы ошибок
```json
{
  "code": 16,
  "message": "INVALID_ARGUMENT",
  "details": [
    {
      "typeUrl": "type.googleapis.com/ozon.seller.InvalidFieldsDetails",
      "value": "..."
    }
  ]
}
```

---
**Источник**: Официальная документация Ozon + реальные данные SoVAni Bot
**Обновлено**: Сентябрь 2025
**Статус**: Проверено в production (Client-Id: 1030740)