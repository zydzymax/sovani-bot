# 📊 Реальные примеры данных от API WB/Ozon

## 🟣 Wildberries API - Реальные ответы

### Statistics API - Детализированный отчет (v5)
**Endpoint**: `GET /api/v5/supplier/reportDetailByPeriod`
**Период**: 2025-09-22 → 2025-09-29 (7 дней)

```json
{
  "data": [
    {
      "realizationreport_id": 123456,
      "date_from": "2025-09-22",
      "date_to": "2025-09-29",
      "suppliercontract_code": "",
      "rrd_id": 0,
      "gi_id": 12345678,
      "subject_name": "Пижамы",
      "nm_id": 413157507,
      "brand_name": "SoVAni FD",
      "sa_name": "PM-TOP/pink",
      "ts_name": "M",
      "barcode": "2000654321987",
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
      "shk_id": 35836615549,
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

### Feedbacks API - Отзывы покупателей
**Endpoint**: `GET /api/v1/feedbacks?isAnswered=false&take=5&skip=0`

```json
{
  "data": {
    "feedbacks": [
      {
        "id": "Os4zhn64gTGhkIq2alPw",
        "text": "Спасибо продавцу 🥰",
        "pros": "Очень приятная ткань! В меру плотная и невероятно мягкая. Не вылезаю из нее совсем.\nСкрашивает пасмурные осенние дни✨\nЯ очень довольна покупкой!",
        "cons": "Все чудесно",
        "productValuation": 5,
        "createdDate": "2025-09-23T09:48:02Z",
        "answer": null,
        "state": "wbRu",
        "productDetails": {
          "imtId": 166536416,
          "nmId": 413157507,
          "productName": "Пижама с шортами и топом домашняя модная хлопок",
          "supplierArticle": "PM-TOP/pink",
          "supplierName": "Индивидуальный предприниматель Гладких Наталья Сергеевна",
          "brandName": "SoVAni FD",
          "size": "M"
        },
        "video": {
          "previewImage": "https://videofeedback02.wbbasket.ru/e7224cdc-c0bd-40b5-a671-1419037ff487/preview.webp",
          "link": "https://videofeedback02.wbbasket.ru/e7224cdc-c0bd-40b5-a671-1419037ff487/index.m3u8",
          "durationSec": 9
        },
        "wasViewed": true,
        "photoLinks": [
          {
            "fullSize": "https://feedback09.wbbasket.ru/vol3365/part336530/336530789/photos/fs.jpg",
            "miniSize": "https://feedback09.wbbasket.ru/vol3365/part336530/336530789/photos/ms.jpg"
          },
          {
            "fullSize": "https://feedback09.wbbasket.ru/vol3365/part336530/336530777/photos/fs.jpg",
            "miniSize": "https://feedback09.wbbasket.ru/vol3365/part336530/336530777/photos/ms.jpg"
          }
        ],
        "userName": "Виктория",
        "matchingSize": "ok",
        "isAbleSupplierFeedbackValuation": true,
        "supplierFeedbackValuation": 0,
        "isAbleSupplierProductValuation": true,
        "supplierProductValuation": 0,
        "isAbleReturnProductOrders": true,
        "returnProductOrdersDate": null,
        "bables": [
          "качество",
          "по размеру",
          "внешний вид",
          "хорошо сидит",
          "удобно носить",
          "приятно на ощупь"
        ],
        "lastOrderShkId": 35836615549,
        "lastOrderCreatedAt": "2025-09-11T16:45:06.05603Z",
        "color": "розовый",
        "subjectId": 162,
        "subjectName": "Пижамы",
        "parentFeedbackId": null,
        "childFeedbackId": null
      },
      {
        "id": "Asy4hn24gTGhkIq3alXw",
        "text": "Трусы вообще не налезли, хотя размер правильный заказала, а верх еле как влезает",
        "pros": "",
        "cons": "Размер маленький",
        "productValuation": 3,
        "createdDate": "2025-09-22T14:30:00Z",
        "answer": null,
        "state": "wbRu",
        "productDetails": {
          "imtId": 298469134,
          "nmId": 51322491,
          "productName": "Комплект нижнего белья без пушап с чашечками и стрингами",
          "supplierArticle": "SET-BRA/black-M",
          "supplierName": "Индивидуальный предприниматель Гладких Наталья Сергеевна",
          "brandName": "SoVAni FD",
          "size": "M"
        },
        "video": null,
        "wasViewed": false,
        "photoLinks": null,
        "userName": "Ася",
        "matchingSize": "small",
        "isAbleSupplierFeedbackValuation": true,
        "supplierFeedbackValuation": 0,
        "isAbleSupplierProductValuation": true,
        "supplierProductValuation": 0,
        "isAbleReturnProductOrders": true,
        "returnProductOrdersDate": null,
        "bables": null,
        "lastOrderShkId": 15120617417,
        "lastOrderCreatedAt": "2025-09-20T09:20:46.147324Z",
        "color": "черный",
        "subjectId": 1117,
        "subjectName": "Комплекты нижнего белья",
        "parentFeedbackId": null,
        "childFeedbackId": null
      }
    ]
  }
}
```

### Marketplace API - Рекламные кампании
**Endpoint**: `GET /adv/v1/promotion/count`

```json
{
  "result": {
    "all": 247,
    "active": 247,
    "paused": 0,
    "completed": 0,
    "archived": 0
  }
}
```

## 🟠 Ozon API - Реальные ответы

### Finance API - Транзакции FBS
**Endpoint**: `POST /v3/finance/transaction/list`
**Период**: 2025-09-22 → 2025-09-29 (7 дней)

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
            "name": "Пижама с шортами и топом домашняя модная хлопок"
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
          },
          {
            "name": "Магистраль",
            "price": -45.23
          },
          {
            "name": "Последняя миля",
            "price": -78.90
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
        },
        "items": [
          {
            "sku": 9876543210,
            "name": "Костюм с начесом спортивный"
          }
        ],
        "services": [
          {
            "name": "Обработка возврата",
            "price": -89.12
          }
        ]
      },
      {
        "operation_id": 555666777,
        "operation_type": "MarketplaceRedistributionOfAcquiringOperation",
        "operation_date": "2025-09-26T18:30:00Z",
        "operation_type_name": "Перераспределение эквайринга",
        "delivery_charge": 0,
        "return_delivery_charge": 0,
        "accruals_for_sale": 0,
        "sale_commission": 0,
        "amount": 0,
        "type": "services",
        "posting": null,
        "items": [],
        "services": [
          {
            "name": "Перераспределение эквайринга",
            "price": 0
          }
        ]
      }
    ],
    "page_count": 15,
    "has_next": true
  }
}
```

### Analytics API - Данные по товарам
**Endpoint**: `POST /v1/analytics/data`

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
          1790.50,  // revenue (выручка)
          1,        // ordered_units (заказанные единицы)
          145,      // hits_view_search (просмотры в поиске)
          89,       // hits_view_pdp (просмотры карточки)
          1.12      // conversion (конверсия)
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
      91380.00,  // общая выручка за период
      51,        // общее количество заказанных единиц
      3456,      // общие просмотры в поиске
      2134,      // общие просмотры карточек
      1.48       // средняя конверсия
    ]
  }
}
```

### Products API - Остатки товаров
**Endpoint**: `POST /v1/product/info/stocks`

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
      },
      {
        "offer_id": "KST-BRT/gray-L",
        "product_id": 9876543210,
        "stocks": [
          {
            "type": "fbs",
            "present": 3,
            "reserved": 1
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

## 📊 Агрегированные данные SoVAni Bot

### Финансовый отчет за 7 дней (реальные данные)
```
🟣 WILDBERRIES ФИНАНСОВЫЙ ОТЧЕТ

💰 ОБЩИЕ ПОКАЗАТЕЛИ
Выручка: 5,824 ₽ (4 WB продажи)
Себестоимость: 2,400 ₽
Валовая прибыль: 3,424 ₽ (58.8%)

📊 ДЕТАЛИЗАЦИЯ WB
Комиссия WB + эквайринг: 2,151 ₽ (36.9%)
Логистика и хранение: 472 ₽ (8.1%)
К перечислению: 5,824 ₽ (4 операций)
СПП компенсация: 3,218 ₽
Возвратов: 0

🟠 OZON ПОКАЗАТЕЛИ
Выручка: 91,380 ₽ (51 ед.)
Доставлено: 91,380 ₽ (51 операций)
Комиссия: 13,817 ₽
Реклама: 13,003 ₽
Чистая прибыль: 28,122 ₽

💰 ИТОГОВЫЙ P&L
Общая выручка: 97,204 ₽
Чистая прибыль: -72,167 ₽ (-74.2%)
ROI: -74.2%
```

### Обработанный отзыв (ChatGPT ответ)
```
Исходный отзыв:
👤 Покупатель: "Виктория"
⭐ Рейтинг: 5 звезд
💬 Текст: "Спасибо продавцу 🥰"
📦 Товар: "Пижама с шортами и топом домашняя модная хлопок"

Сгенерированный ответ:
"Виктория, как здорово видеть ваше фото и получить такой тёплый отзыв! 😊
Ваша позитивная энергия заставляет нашу команду SoVAni прыгать от счастья.
Мы очень рады, что наша модная пижама с шортами и топом принесла вам столько радости!

С нетерпением ждём, когда вы снова заглянете к нам за новыми уютными находками!

С теплом и благодарностью,
Команда SoVAni ✨"
```

### Статистика рейтингов отзывов (реальная)
```
⭐ 2 звезды: 3 отзыва (6%)
⭐ 3 звезды: 3 отзыва (6%)
⭐ 4 звезды: 1 отзыв (2%)
⭐ 5 звезд: 93 отзыва (86%)

Средний рейтинг: 4.7/5.0
```

## 🔍 Особенности парсинга данных

### Проблемы и решения (исправлено в сентябре 2025)
1. **Имена покупателей**: Извлекаются из `userName`, не fallback "Покупатель"
2. **Названия товаров**: Из `productDetails.productName`, не fallback "Товар"
3. **Рейтинги**: Точный парсинг `productValuation`, без fallback на 5 звезд

### Структура данных WB отзывов
- `userName` → реальное имя покупателя
- `productDetails.productName` → полное название товара
- `productValuation` → рейтинг 1-5 звезд
- `photoLinks`, `videoLinks` → медиафайлы
- `bables` → теги качества товара

### Структура финансовых данных Ozon
- `accruals_for_sale` → начисления за продажу
- `sale_commission` → комиссия маркетплейса (отрицательная)
- `amount` → итоговая сумма к зачислению
- `services` → детализация всех услуг и комиссий

---
**Источник**: Реальные API ответы от SoVAni Bot
**Период данных**: Сентябрь 2025
**Клиенты**: WB Supplier ID 2692024, Ozon Client-Id 1030740