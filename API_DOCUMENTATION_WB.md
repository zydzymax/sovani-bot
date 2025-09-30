# 📚 Wildberries API Documentation - Полная справка

## 🔑 Авторизация

### JWT подпись (рекомендуемый метод)
```http
Authorization: Bearer <JWT_TOKEN>
```

### API токены (legacy)
```http
Authorization: <API_TOKEN>
```

## 📊 Statistics API
**Base URL**: `https://statistics-api.wildberries.ru`

### Финансовая отчетность

#### 1. Детализированный отчет
```http
GET /api/v5/supplier/reportDetailByPeriod
```
**Параметры**:
- `dateFrom` (string, required): Начальная дата (YYYY-MM-DD)
- `dateTo` (string, required): Конечная дата (YYYY-MM-DD)
- `limit` (int, optional): Лимит записей (по умолчанию 100000)
- `rrdid` (int, optional): ID родительской записи

**Ответ**:
```json
{
  "data": [
    {
      "realizationreport_id": 123456,
      "date_from": "2025-09-01",
      "date_to": "2025-09-30",
      "suppliercontract_code": "",
      "rrd_id": 0,
      "gi_id": 12345678,
      "subject_name": "Пижамы",
      "nm_id": 51322482,
      "brand_name": "SoVAni FD",
      "sa_name": "PM-TOP/pink",
      "ts_name": "M",
      "barcode": "2000123456789",
      "doc_type_name": "Продажа",
      "quantity": 1,
      "retail_price": 2156.00,
      "retail_amount": 2156.00,
      "sale_percent": 3,
      "commission_percent": 13.50,
      "office_name": "Хабаровск",
      "supplier_oper_name": "Продажа",
      "order_dt": "2025-09-23T12:30:00",
      "sale_dt": "2025-09-25T15:45:00",
      "rr_dt": "2025-09-25T15:45:00",
      "shk_id": 1682977270,
      "retail_price_withdisc_rub": 2156.00,
      "delivery_amount": 0,
      "return_amount": 0,
      "delivery_rub": 0,
      "gi_box_type_name": "Монопаллета",
      "product_discount_for_report": 3,
      "supplier_promo": 0,
      "rid": 987654321,
      "ppvz_spp_prc": 25.30,
      "ppvz_kvw_prc_base": 13.50,
      "ppvz_kvw_prc": 13.50,
      "sup_rating_prc_up": 0,
      "is_kgvp_v2": 0,
      "ppvz_sales_commission": 291.06,
      "ppvz_for_pay": 1486.56,
      "ppvz_reward": 0,
      "acquiring_fee": 21.56,
      "acquiring_bank": "ТинькоффБанк",
      "ppvz_vw": 378.38,
      "ppvz_vw_nds": 63.06,
      "ppvz_office_id": 507,
      "ppvz_office_name": "Хабаровск",
      "ppvz_supplier_id": 2692024,
      "ppvz_supplier_name": "ИП Гладких Наталья Сергеевна",
      "ppvz_inn": "271234567890",
      "declaration_number": "",
      "bonus_type_name": "",
      "sticker_id": "",
      "site_country": "RU",
      "penalty": 0,
      "additional_payment": 0,
      "rebill_logistic_cost": 0,
      "rebill_logistic_org": "",
      "kiz": "",
      "storage_fee": 0,
      "deduction": 0,
      "acceptance": 0,
      "srid": "S18974701156"
    }
  ]
}
```

#### 2. Отчет по заказам
```http
GET /api/v1/supplier/orders
```
**Параметры**:
- `dateFrom` (string, required): Начальная дата (RFC3339)
- `flag` (int, required): Флаг (0 - по дате заказа, 1 - по дате изменения)

#### 3. Отчет по продажам
```http
GET /api/v1/supplier/sales
```
**Параметры**:
- `dateFrom` (string, required): Начальная дата (RFC3339)
- `flag` (int, required): Флаг

### Аналитика

#### 4. Еженедельный отчет
```http
GET /api/v1/supplier/reportDetailByPeriod
```

#### 5. Остатки на складах
```http
GET /api/v1/supplier/stocks
```
**Параметры**:
- `dateFrom` (string, required): Дата (RFC3339)

## 🛒 Marketplace API
**Base URL**: `https://marketplace-api.wildberries.ru`

### Заказы

#### 1. Список заказов
```http
GET /api/v3/orders
```
**Параметры**:
- `next` (int, optional): Курсор пагинации
- `limit` (int, optional): Количество (макс 1000)

#### 2. Детали заказа
```http
GET /api/v3/orders/{id}
```

#### 3. Создание поставки
```http
POST /api/v3/supplies
```
**Тело запроса**:
```json
{
  "name": "Поставка от 2025-09-30"
}
```

### Сборочные задания

#### 4. Список сборочных заданий
```http
GET /api/v3/orders/new
```

#### 5. Добавить заказы в поставку
```http
PATCH /api/v3/supplies/{supplyId}
```

#### 6. Получить QR поставки
```http
GET /api/v3/supplies/{supplyId}/barcode
```

## 📝 Content API
**Base URL**: `https://content-api.wildberries.ru`

### Управление товарами

#### 1. Список товаров
```http
POST /content/v2/get/cards/list
```
**Тело запроса**:
```json
{
  "settings": {
    "cursor": {
      "limit": 100
    },
    "filter": {
      "withPhoto": -1
    }
  }
}
```

#### 2. Создание товара
```http
POST /content/v2/cards/upload
```

#### 3. Обновление товара
```http
POST /content/v2/cards/update
```

#### 4. Цены
```http
POST /public/api/v1/info
```
**Тело запроса**:
```json
{
  "nmId": 51322482
}
```

#### 5. Обновление цен
```http
POST /public/api/v1/prices
```
**Тело запроса**:
```json
[
  {
    "nmId": 51322482,
    "price": 2990
  }
]
```

## 💬 Feedbacks API
**Base URL**: `https://feedbacks-api.wildberries.ru`

### Отзывы

#### 1. Получение отзывов
```http
GET /api/v1/feedbacks
```
**Параметры**:
- `isAnswered` (boolean, required): true/false
- `take` (int, required): Количество (макс 5000)
- `skip` (int, required): Пропустить

**Ответ**:
```json
{
  "data": {
    "feedbacks": [
      {
        "id": "DA2jJJH05e8kEYFL46yI",
        "text": "Спасибо продавцу 🥰",
        "productValuation": 5,
        "createdDate": "2025-09-26T02:21:24Z",
        "userName": "Виктория",
        "productDetails": {
          "imtId": 298469125,
          "nmId": 51322482,
          "productName": "Костюм с начесом спортивный",
          "supplierArticle": "KST-BRT/KSST-FNГрафит",
          "brandName": "SoVAni FD",
          "size": "M"
        },
        "photoLinks": [
          {
            "fullSize": "https://feedback09.wbbasket.ru/vol3365/part336530/336530789/photos/fs.jpg",
            "miniSize": "https://feedback09.wbbasket.ru/vol3365/part336530/336530789/photos/ms.jpg"
          }
        ],
        "isAnswered": false,
        "answer": null
      }
    ]
  }
}
```

#### 2. Отправка ответа на отзыв
```http
POST /api/v1/feedbacks/answer
```
**Тело запроса**:
```json
{
  "id": "DA2jJJH05e8kEYFL46yI",
  "text": "Спасибо за отзыв, Виктория! Команда SoVAni рада что товар вам понравился!"
}
```

### Вопросы

#### 3. Получение вопросов
```http
GET /api/v1/questions
```
**Параметры**: аналогично отзывам

#### 4. Ответ на вопрос
```http
POST /api/v1/questions/answer
```

## 📈 Analytics API
**Base URL**: `https://seller-analytics-api.wildberries.ru`

### Аналитика продаж

#### 1. Воронка продаж
```http
GET /api/v2/nm-report/detail
```
**Параметры**:
- `nmIDs` (array): Массив артикулов WB
- `period` (object): Период
- `timezone` (string): Часовой пояс
- `aggregationLevel` (string): Уровень агрегации

#### 2. Остатки и склады
```http
GET /api/v1/supplier/stocks
```

#### 3. ABC анализ
```http
GET /api/v1/analytics/nm-report/grouped
```

## 🎯 Ads API (Promotion)
**Base URL**: `https://advert-api.wildberries.ru`

### Рекламные кампании

#### 1. Список кампаний
```http
GET /adv/v1/promotion/count
```

#### 2. Статистика кампаний
```http
GET /adv/v1/stat/words
```
**Параметры**:
- `dateFrom` (string): Начальная дата
- `dateTo` (string): Конечная дата

#### 3. Создание кампании
```http
POST /adv/v1/promotion/save
```

## 🚫 Rate Limits

### Ограничения по API:
- **Statistics**: 60 запросов в минуту
- **Marketplace**: 300 запросов в минуту
- **Content**: 100 запросов в минуту
- **Feedbacks**: 1000 запросов в день
- **Analytics**: 300 запросов в минуту
- **Ads**: 100 запросов в минуту

### Алгоритм "Token Bucket":
- При превышении лимита - HTTP 429
- Заголовок `Retry-After` указывает время ожидания

## ⚠️ Важные особенности

### 1. Версионирование API
- Старые версии поддерживаются ограниченное время
- Рекомендуется использовать последние версии
- **Statistics API v5** - текущая версия

### 2. Форматы дат
- **RFC3339**: `2025-09-30T15:30:00Z`
- **Simple**: `2025-09-30`

### 3. Пагинация
- Cursor-based для больших датасетов
- Limit-based для простых запросов

### 4. Ошибки
```json
{
  "error": true,
  "errorText": "Описание ошибки",
  "additionalErrors": ["Дополнительные детали"],
  "requestId": "b712e3e3-8fcb-4c2a-bcf4-cb39518ca252"
}
```

---
**Источник**: Официальная документация WB + практический опыт SoVAni Bot
**Обновлено**: Сентябрь 2025
**Статус**: Проверено в production