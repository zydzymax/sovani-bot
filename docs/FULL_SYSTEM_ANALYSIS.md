# ПОЛНЫЙ АНАЛИЗ СИСТЕМЫ SOVANI BOT - БЕЗ ИСПРАВЛЕНИЙ

**Дата анализа**: 2025-10-05
**Режим**: Только анализ, БЕЗ исправлений

---

## 1. СТРУКТУРА ПРОЕКТА

### 1.1 Директории
```
/root/sovani_bot/          ← ОСНОВНОЙ проект (SQLite, 315 Python файлов)
/root/sovani_api/          ← СТАРЫЙ проект (PostgreSQL, deprecated)
/root/sovani_crosspost/    ← Отдельный проект (кросспостинг)
```

### 1.2 Активные сервисы
```
✅ sovani-bot.service             - Telegram бот (minimal_bot.py)
✅ sovani-web.service             - TMA API backend (FastAPI на порту 8000)
❌ sovani-replies-worker.service  - Auto-restart loop (постоянно перезапускается)
✅ sovani-ai-seller.service       - Docker Compose (exited, но active)
```

---

## 2. БАЗА ДАННЫХ - КРИТИЧЕСКАЯ ПРОБЛЕМА

### 2.1 Путь к БД
`/root/sovani_bot/sovani_bot.db` (SQLite)

### 2.2 Таблицы и данные
```
reviews:              55 rows  ✅ ЕСТЬ ДАННЫЕ (но нет marketplace поля!)
daily_sales:          0 rows   ❌ ПУСТО
daily_stock:          0 rows   ❌ ПУСТО
sku:                  0 rows   ❌ ПУСТО
organizations:        1 row    ✅
users:                1 row    ✅
org_members:          1 row    ✅
```

### 2.3 Структура таблицы reviews
```sql
id                 TEXT PRIMARY KEY
sku                TEXT (nullable)
text               TEXT
rating             INTEGER (nullable)
has_media          BOOLEAN
answer             TEXT
date               TIMESTAMP
answered           BOOLEAN
reply_text         VARCHAR (nullable)
first_reply_at_utc DATETIME (nullable)
reply_kind         VARCHAR(10) (nullable)
created_at_utc     DATETIME (nullable)
org_id             INTEGER

⚠️ ОТСУТСТВУЕТ: marketplace (поле не существует в БД!)
```

### 2.4 Пример данных reviews
```
ID: 92wHoIk4rD1rJNd... | SKU: 215819984 | Rating: 5 | Text: (пусто) | Answered: 0
ID: 4XACGgrMNwjWa6k... | SKU: 168894684 | Rating: 5 | Text: (пусто) | Answered: 0
ID: 3FhvGLmZjpn3CpI... | SKU: 182906670 | Rating: 5 | Text: Выбор в пользу друго пижаму с кимоно | Answered: 0
```

**ПРОБЛЕМЫ**:
- Большинство отзывов имеют **пустой текст**
- Ни один отзыв не имеет ответа (answered=0)
- Нет информации о маркетплейсе (WB/Ozon)
- Непонятно откуда взяты эти отзывы

---

## 3. КОНФИГУРАЦИЯ (.env)

### 3.1 API Tokens
```bash
BOT_TOKEN=8320329020:AAF-JeUX08V2eQHsnT8pX51_lB1-zFQENO8  ✅ Реальный токен
TELEGRAM_TOKEN=${BOT_TOKEN}                                ✅
TZ=DEV_MODE                                                 ✅ DEV режим включен

# WB API - ВСЕ PLACEHOLDER!
WB_FEEDBACKS_TOKEN=placeholder_wb_1      ❌ НЕ НАСТРОЕНО
WB_ADS_TOKEN=placeholder_wb_2            ❌ НЕ НАСТРОЕНО
WB_STATS_TOKEN=placeholder_wb_3          ❌ НЕ НАСТРОЕНО
WB_SUPPLY_TOKEN=placeholder_wb_4         ❌ НЕ НАСТРОЕНО
WB_ANALYTICS_TOKEN=placeholder_wb_5      ❌ НЕ НАСТРОЕНО
WB_CONTENT_TOKEN=placeholder_wb_6        ❌ НЕ НАСТРОЕНО

# Ozon API - ТОЖЕ PLACEHOLDER!
OZON_CLIENT_ID=placeholder_ozon_client   ❌ НЕ НАСТРОЕНО
OZON_API_KEY_ADMIN=placeholder_ozon_key  ❌ НЕ НАСТРОЕНО
```

**КРИТИЧЕСКАЯ ПРОБЛЕМА**: Все API токены для WB и Ozon - это плейсхолдеры!
Система не может получать реальные данные с маркетплейсов.

---

## 4. СКРИПТ СБОРА ДАННЫХ

### 4.1 Файл: `/root/sovani_bot/collect_recent_data.py`
```python
async def main():
    # Собирает данные за последние 30 дней
    wb_sales_count = await collect_wb_sales_range(db, d_from, d_to)
    wb_stocks_count = await collect_wb_stocks_now(db)
    ozon_txn_count = await collect_ozon_transactions_range(db, d_from, d_to)
    ozon_stocks_count = await collect_ozon_stocks_now(db)
```

**ПРОБЛЕМА**: Скрипт есть, но:
- Не запущен (нет данных в daily_sales/daily_stock)
- Будет падать с ошибкой из-за placeholder токенов
- Нет systemd service или cron job для автоматического запуска

---

## 5. API ENDPOINTS - ФУНКЦИОНАЛЬНОСТЬ

### 5.1 Работающие endpoints
```
✅ GET  /api/v1/reviews              - Список отзывов (55 штук)
✅ GET  /api/v1/dashboard/summary    - Дашборд (возвращает 0 везде)
✅ GET  /api/v1/inventory/stocks     - Остатки (пустой массив)
✅ GET  /health                      - Health check
```

### 5.2 Сломанные endpoints
```
❌ POST /api/v1/reviews/{id}/draft   - Генерация черновика ответа
   Ошибка: "build_reply_for_review() takes 1 positional argument but 2 were given"

❌ POST /api/v1/reviews/{id}/reply   - Отправка ответа
   Ошибка: Зависит от /draft, тоже не работает
```

### 5.3 Ошибки в логах
```
sqlite3.OperationalError: no such column: reviews.review_id
```

**Причина**:
- Код использует `Review.review_id`
- БД имеет поле `id`, а не `review_id`
- Несоответствие между моделью SQLAlchemy и реальной схемой БД

---

## 6. ПРОБЛЕМЫ В КОДЕ

### 6.1 Файл: `app/services/reviews_service.py`

**Строка 65**:
```python
stmt = select(Review).where(Review.review_id == review_id, Review.org_id == org_id)
```
❌ Использует `Review.review_id`, которого нет в БД (должно быть `Review.id`)

**Строка 156**:
```python
db.execute(
    update(Review)
    .where(Review.review_id == review_id)  # ❌ review_id не существует
    ...
)
```

### 6.2 Файл: `app/web/routers/reviews.py`

**Строка 105**:
```python
draft_text = await build_reply_for_review(review_id, db)
```
❌ Неправильная сигнатура вызова

Функция `build_reply_for_review` определена как:
```python
async def build_reply_for_review(db: Session, *, org_id: int, review_id: str) -> str:
```

Но вызывается как:
```python
await build_reply_for_review(review_id, db)  # ❌ Неправильный порядок аргументов!
```

**Правильно должно быть**:
```python
await build_reply_for_review(db, org_id=org_id, review_id=review_id)
```

### 6.3 Файл: `app/db/models.py`

**Строки 193-197**:
```python
class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sku: Mapped[str | None] = mapped_column(String, nullable=True)
```

✅ Модель правильно использует `id` и `sku`

❌ НО код в reviews_service.py все еще использует старые имена:
- `Review.review_id` вместо `Review.id`
- `Review.sku_id` вместо `Review.sku`

### 6.4 Файл: `app/web/routers/reviews.py` - Вывод данных

**Строки 63-77**:
```python
return [
    ReviewDTO(
        review_id=r.id,                    # ✅ Правильно
        marketplace="WB",                  # ❌ ХАРДКОД! Всегда "WB"
        sku_key=r.sku,                     # ✅ Правильно
        rating=r.rating,
        text=r.text,
        ...
    )
]
```

**ПРОБЛЕМА**: `marketplace` всегда возвращает "WB", даже если отзыв с Ozon!
Потому что в БД нет этого поля.

---

## 7. TMA FRONTEND (static/index.html)

### 7.1 Функции
```javascript
✅ openReviews()    - Показывает отзывы (работает)
❌ openInventory()  - Показывает остатки (пусто, нет данных)
❌ openFinance()    - Показывает финансы (все 0)
```

### 7.2 Нет функционала ответа на отзывы
```javascript
// Код показывает только СПИСОК отзывов:
data.forEach(review => {
    html += `<div class="data-row">`;
    html += `<span class="data-label">⭐ ${review.rating}/5</span>`;
    html += `<span class="data-value">${review.text.substring(0, 30)}...</span>`;
    html += `</div>`;
});
```

❌ **НЕТ**:
- Кнопок для ответа на отзыв
- Модального окна для написания ответа
- Вызова API `/reviews/{id}/draft`
- Вызова API `/reviews/{id}/reply`
- Функции автоответа на все отзывы

**Frontend только ЧИТАЕТ отзывы, не может на них отвечать!**

---

## 8. СИСТЕМНЫЕ ФАЙЛЫ

### 8.1 `/etc/systemd/system/sovani-bot.service`
```ini
ExecStart=/usr/bin/flock -n /var/run/sovani_bot.lock /usr/bin/python3 /root/sovani_bot/minimal_bot.py
Environment="BOT_TOKEN=8320329020:AAF-JeUX08V2eQHsnT8pX51_lB1-zFQENO8"
```
✅ Работает корректно

### 8.2 `/etc/systemd/system/sovani-web.service`
```ini
ExecStart=/usr/bin/python3 -m uvicorn app.web.main:app --host 0.0.0.0 --port 8000
EnvironmentFile=-/root/sovani_bot/.env
```
✅ Работает корректно

### 8.3 `/etc/systemd/system/sovani-replies-worker.service`
```
Active: activating (auto-restart)
```
❌ Постоянно перезапускается (краш-луп)

---

## 9. АРХИТЕКТУРА ПРОБЛЕМ

### 9.1 Два проекта вместо одного
```
sovani_bot/     ← Основной (SQLite, 55 отзывов, 0 продаж)
sovani_api/     ← Старый (PostgreSQL, deprecated но работает replies_worker)
```

**ПРОБЛЕМА**: Replies worker запускается из `/root/sovani_api/`, который использует другую БД!

### 9.2 Несоответствие схем БД и кода
```
БД имеет:        Код использует:
id               review_id      ❌ Несоответствие
sku              sku_id         ❌ Несоответствие
(нет поля)       marketplace    ❌ Хардкод "WB"
```

### 9.3 Placeholder токены
```
WB API:   placeholder_wb_1..6   ❌ Не настроено
Ozon API: placeholder_ozon_*    ❌ Не настроено
```

---

## 10. ОТСУТСТВУЮЩИЙ ФУНКЦИОНАЛ

### 10.1 ❌ Ответы на отзывы через TMA
- Нет UI для ответа
- Нет кнопки "Ответить"
- Нет модального окна для написания текста
- Нет вызова `/draft` API
- Нет вызова `/reply` API

### 10.2 ❌ Автоответ на все отзывы
- Нет функции массовой обработки
- Нет кнопки "Ответить на все"
- Нет batch processing в backend

### 10.3 ❌ Сбор данных с маркетплейсов
- Скрипт `collect_recent_data.py` не запущен
- Нет cron job / systemd timer
- Placeholder токены не позволят собрать данные

### 10.4 ❌ Генерация ответов (AI)
- Endpoint `/draft` сломан (неправильные аргументы функции)
- OpenAI API key: `sk-placeholder_openai` ❌

---

## 11. ПРИЧИНА НУЛЕВЫХ ДАННЫХ

### 11.1 Dashboard возвращает 0
```json
{"revenue_net":0.0,"profit":0.0,"margin":0.0,"units":0,"refunds_qty":0}
```

**ПРИЧИНА**:
```sql
SELECT * FROM daily_sales;  -- 0 rows
SELECT * FROM daily_stock;  -- 0 rows
SELECT * FROM sku;          -- 0 rows
```

Таблицы пустые → нет данных для подсчета.

### 11.2 Почему таблицы пустые?

1. **Не запущен `collect_recent_data.py`**
2. **Placeholder токены WB/Ozon** → API вызовы не работают
3. **Нет автоматизации** (cron/systemd timer)

---

## 12. ОТКУДА ВЗЯЛИСЬ 55 ОТЗЫВОВ?

**Вопрос**: В таблице `reviews` есть 55 записей, но:
- `daily_sales` пустая
- `sku` пустая
- Токены placeholder

**Возможные варианты**:
1. Старые данные из миграции БД
2. Ручная вставка (testing)
3. Импорт из CSV/JSON
4. Остатки от предыдущей версии системы

**Проверка**:
```sql
SELECT created_at_utc FROM reviews ORDER BY created_at_utc DESC LIMIT 5;
```
Даты: 2025-09-23, 2025-09-21, 2025-08-02, 2025-07-16, 2025-07-14

Это **РЕАЛЬНЫЕ даты** (июль-сентябрь 2025), значит:
- Либо данные были собраны когда токены были настоящими
- Либо система импортировала их из другого источника
- Либо это тестовые данные с реалистичными датами

---

## 13. СТРУКТУРНЫЕ ОШИБКИ КОДА

### 13.1 Несоответствие имен полей (3+ места)

**Файлы с ошибками**:
```
app/services/reviews_service.py:65     Review.review_id  ❌
app/services/reviews_service.py:156    Review.review_id  ❌
app/web/routers/export.py:198          r.id (правильно)  ✅
app/web/routers/reviews.py:63          r.id (правильно)  ✅
app/web/routers/reviews.py:108         Review.id         ✅
```

**Вывод**: Код частично исправлен, но `reviews_service.py` использует старые имена.

### 13.2 Неправильный вызов функции

**reviews.py:105**:
```python
draft_text = await build_reply_for_review(review_id, db)
```

**Правильная сигнатура**:
```python
async def build_reply_for_review(db: Session, *, org_id: int, review_id: str) -> str:
```

**Ошибка**: Передает аргументы не в том порядке и без keyword arguments.

### 13.3 Отсутствие поля marketplace

**БД**: Нет колонки `marketplace`
**Код**: Хардкодит `"WB"` везде
**Проблема**: Невозможно отличить отзывы WB от Ozon

---

## 14. НЕДОСТАЮЩИЕ КОМПОНЕНТЫ

### 14.1 UI для ответов на отзывы
```
❌ Нет в static/index.html:
   - Кнопка "Ответить" на каждом отзыве
   - Модальное окно для написания ответа
   - Показ сгенерированного AI черновика
   - Кнопка "Отправить ответ"
   - Кнопка "Автоответ на все"
```

### 14.2 Batch processing API
```
❌ Нет endpoint:
   POST /api/v1/reviews/reply-all
   {
     "filter": {"rating": [1,2], "answered": false},
     "template": "auto"
   }
```

### 14.3 Scheduled tasks
```
❌ Нет systemd timer для:
   - collect_recent_data.py (ежедневный сбор)
   - auto_reviews_processor.py (автоответы)
```

### 14.4 Мониторинг
```
❌ Нет алертов на:
   - Пустые таблицы (daily_sales, daily_stock, sku)
   - Placeholder токены в .env
   - Краш-луп sovani-replies-worker
```

---

## 15. РАБОТАЮЩИЕ ЧАСТИ СИСТЕМЫ

### 15.1 ✅ Telegram Bot
- Запущен
- Отвечает на /start
- Показывает кнопку TMA
- URL: https://app.justbusiness.lol/

### 15.2 ✅ TMA Frontend
- Загружается
- Показывает интерфейс
- Делает API запросы
- Показывает отзывы (55 штук)

### 15.3 ✅ FastAPI Backend
- Запущен на порту 8000
- DEV_MODE работает (обход авторизации)
- Endpoint /reviews работает
- Endpoint /dashboard/summary работает (но возвращает 0)

### 15.4 ✅ База данных
- SQLite работает
- Схема создана (27 таблиц)
- Есть 55 отзывов
- Есть 1 организация, 1 пользователь

---

## 16. НЕ РАБОТАЮЩИЕ ЧАСТИ СИСТЕМЫ

### 16.1 ❌ Генерация ответов на отзывы
- Endpoint `/draft` падает с ошибкой
- Неправильный вызов функции
- OpenAI токен placeholder

### 16.2 ❌ Отправка ответов на отзывы
- Endpoint `/reply` работает технически
- Но UI для вызова отсутствует
- Нет функции постинга в WB/Ozon (API не поддерживает)

### 16.3 ❌ Сбор данных с маркетплейсов
- Скрипт не запущен
- Placeholder токены
- Таблицы пустые (sales, stock, sku)

### 16.4 ❌ Финансовая аналитика
- Все метрики = 0
- Нет данных для расчета
- Формулы правильные, но нечего считать

### 16.5 ❌ Складская аналитика
- Таблица stock пустая
- Endpoint возвращает []
- UI показывает "Данных нет"

---

## 17. СПИСОК БАГОВ (приоритет)

### 17.1 🔴 КРИТИЧЕСКИЕ (блокируют функционал)

1. **Placeholder API токены WB/Ozon**
   - Файл: `.env`
   - Проблема: Невозможно собрать данные с маркетплейсов
   - Где нужны настоящие: WB_FEEDBACKS_TOKEN, WB_STATS_TOKEN, WB_SUPPLY_TOKEN, OZON_CLIENT_ID, OZON_API_KEY_ADMIN

2. **Неправильный вызов build_reply_for_review()**
   - Файл: `app/web/routers/reviews.py:105`
   - Проблема: `await build_reply_for_review(review_id, db)` - неправильный порядок
   - Должно быть: `await build_reply_for_review(db, org_id=org_id, review_id=review_id)`

3. **Review.review_id не существует в БД**
   - Файл: `app/services/reviews_service.py:65, 156`
   - Проблема: Использует `Review.review_id`, но в БД поле называется `id`
   - Должно быть: `Review.id`

4. **Отсутствует UI для ответов**
   - Файл: `static/index.html`
   - Проблема: Нет кнопок, модального окна, вызовов API
   - Нужно добавить: Кнопка "Ответить", модальное окно, интеграцию с `/draft` и `/reply`

### 17.2 🟠 ВАЖНЫЕ (данные отсутствуют)

5. **Пустые таблицы daily_sales, daily_stock, sku**
   - Причина: `collect_recent_data.py` не запущен
   - Решение: Настроить токены + запустить скрипт + добавить в cron/systemd timer

6. **Placeholder OpenAI токен**
   - Файл: `.env`
   - Проблема: `OPENAI_API_KEY=sk-placeholder_openai`
   - Результат: AI генерация ответов не работает

7. **sovani-replies-worker в краш-лупе**
   - Сервис: `sovani-replies-worker.service`
   - Проблема: Постоянно перезапускается
   - Запускает: `/root/sovani_api/replies_worker.py` (старый проект!)

### 17.3 🟡 СРЕДНИЕ (улучшения)

8. **Нет поля marketplace в БД**
   - Таблица: `reviews`
   - Проблема: Невозможно отличить WB от Ozon
   - Код хардкодит: `marketplace="WB"` везде

9. **Нет автоматизации сбора данных**
   - Нет systemd timer для `collect_recent_data.py`
   - Данные не обновляются автоматически

10. **Нет функции массового автоответа**
    - Нет endpoint `/reviews/reply-all`
    - Нет UI кнопки "Ответить на все"

---

## 18. ЧТО РАБОТАЕТ СЕЙЧАС (ФАКТЫ)

### 18.1 Telegram Bot
- ✅ Запущен через systemd
- ✅ Отвечает на команды
- ✅ Показывает кнопку TMA с URL
- ✅ Токен настоящий (8320329020:...)

### 18.2 TMA Web App
- ✅ Загружается по https://app.justbusiness.lol/
- ✅ Показывает интерфейс
- ✅ Делает API запросы
- ✅ Показывает список 55 отзывов
- ❌ Не может ответить на отзывы (нет UI)
- ❌ Показывает 0 по финансам (нет данных)
- ❌ Показывает пусто по остаткам (нет данных)

### 18.3 API Backend
- ✅ FastAPI работает на порту 8000
- ✅ DEV_MODE активен (TZ=DEV_MODE)
- ✅ Авторизация обходится
- ✅ GET /reviews работает (55 записей)
- ✅ GET /dashboard/summary работает (но 0 везде)
- ✅ GET /inventory/stocks работает (но пустой [])
- ❌ POST /reviews/{id}/draft падает с ошибкой
- ❌ POST /reviews/{id}/reply технически работает, но нет UI

### 18.4 База данных
- ✅ SQLite подключена
- ✅ 27 таблиц созданы
- ✅ 55 отзывов есть
- ✅ 1 организация, 1 пользователь
- ❌ 0 продаж
- ❌ 0 остатков
- ❌ 0 SKU
- ⚠️ Непонятно откуда взялись 55 отзывов (вероятно старые данные или импорт)

---

## 19. ЧТО НЕ РАБОТАЕТ (ФАКТЫ)

### 19.1 Ответы на отзывы
- ❌ Нет кнопки "Ответить" в UI
- ❌ Endpoint `/draft` падает (TypeError: неправильные аргументы)
- ❌ Нет AI генерации (OpenAI токен placeholder)
- ❌ Нет автоответа на все отзывы

### 19.2 Данные с маркетплейсов
- ❌ Все WB токены = placeholder
- ❌ Все Ozon токены = placeholder
- ❌ `collect_recent_data.py` не запущен
- ❌ Таблицы sales/stock/sku пустые

### 19.3 Аналитика
- ❌ Финансы: все 0 (нет данных для расчета)
- ❌ Остатки: пусто (таблица daily_stock пустая)
- ❌ SKU: нет в БД (таблица sku пустая)

### 19.4 Маркетплейс отзывов
- ❌ Нет информации WB или Ozon (нет поля marketplace в БД)
- ❌ Код хардкодит "WB" для всех отзывов

### 19.5 Автоматизация
- ❌ Нет cron job для сбора данных
- ❌ Нет systemd timer
- ❌ replies-worker в краш-лупе
- ❌ Нет мониторинга пустых таблиц

---

## 20. КОРНЕВЫЕ ПРИЧИНЫ ПРОБЛЕМ

### 20.1 Причина №1: Нет настоящих API токенов
```
Последствия:
- Невозможно собрать продажи
- Невозможно собрать остатки
- Невозможно собрать SKU
- Невозможно получить актуальные отзывы
- Невозможно ответить на отзывы (API WB/Ozon не поддерживает)
```

### 20.2 Причина №2: Несоответствие схемы БД и кода
```
БД:           Код:
id            review_id    ← Код устарел
sku           sku_id       ← Код устарел
(нет поля)    marketplace  ← Код хардкодит "WB"
```

### 20.3 Причина №3: Отсутствие UI для ответов
```
static/index.html содержит только:
- Показ списка отзывов
- НЕ содержит:
  - Кнопки ответа
  - Модального окна
  - Вызовов /draft и /reply API
```

### 20.4 Причина №4: Скрипт сбора не запущен
```
collect_recent_data.py существует, но:
- Не запущен вручную
- Не добавлен в cron
- Не добавлен в systemd timer
- Упадет с ошибкой из-за placeholder токенов
```

### 20.5 Причина №5: Два проекта вместо одного
```
/root/sovani_bot/   ← Основной (SQLite, TMA, API)
/root/sovani_api/   ← Старый (PostgreSQL, deprecated)
                      Но replies-worker запускается отсюда!
```

---

## 21. ДЕТАЛЬНЫЙ ПЛАН ИСПРАВЛЕНИЯ (для ChatGPT)

### ЭТАП 1: Настройка API токенов
```bash
# Файл: .env
# Заменить placeholder на настоящие токены:
WB_FEEDBACKS_TOKEN=<настоящий токен WB для отзывов>
WB_STATS_TOKEN=<настоящий токен WB для статистики>
WB_SUPPLY_TOKEN=<настоящий токен WB для поставок>
WB_ANALYTICS_TOKEN=<настоящий токен WB для аналитики>
WB_CONTENT_TOKEN=<настоящий токен WB для контента>
OZON_CLIENT_ID=<настоящий Client ID Ozon>
OZON_API_KEY_ADMIN=<настоящий API Key Ozon>
OPENAI_API_KEY=<настоящий OpenAI API key>
```

### ЭТАП 2: Исправление БД несоответствий

**2.1. Добавить поле marketplace в reviews**
```sql
ALTER TABLE reviews ADD COLUMN marketplace VARCHAR(10);
UPDATE reviews SET marketplace = 'WB';  -- временно, пока не знаем реальный источник
```

**2.2. Обновить модель Review**
```python
# app/db/models.py
class Review(Base):
    marketplace: Mapped[str | None] = mapped_column(String(10), nullable=True)
```

**2.3. Исправить reviews_service.py**
```python
# Строка 65: Review.review_id → Review.id
stmt = select(Review).where(Review.id == review_id, Review.org_id == org_id)

# Строка 156: Review.review_id → Review.id
db.execute(
    update(Review)
    .where(Review.id == review_id)
    ...
)
```

**2.4. Убрать хардкод marketplace**
```python
# app/web/routers/reviews.py:65
# Было:
marketplace="WB",
# Стало:
marketplace=r.marketplace or "WB",  # fallback если null
```

### ЭТАП 3: Исправление вызова build_reply_for_review

**Файл**: `app/web/routers/reviews.py:105`

**Было**:
```python
draft_text = await build_reply_for_review(review_id, db)
```

**Стало**:
```python
draft_text = await build_reply_for_review(db, org_id=org_id, review_id=review_id)
```

### ЭТАП 4: Добавление UI для ответов

**Файл**: `static/index.html`

**4.1. Добавить кнопку "Ответить" в список отзывов**
```javascript
// В функции openReviews(), после строки 321:
html += `<button onclick="replyToReview('${review.review_id}')">Ответить</button>`;
```

**4.2. Добавить функцию генерации черновика**
```javascript
async function replyToReview(reviewId) {
    showModal('💬 Ответ на отзыв', '<div class="loading">Генерация ответа...</div>');

    try {
        const headers = initData ? {'X-Telegram-Init-Data': initData} : {};
        const response = await fetch(`/api/v1/reviews/${reviewId}/draft`, {
            method: 'POST',
            headers
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        // Показать черновик + кнопку отправки
        document.getElementById('modalBody').innerHTML = `
            <textarea id="replyText" style="width:100%;height:100px;">${data.draft_text}</textarea>
            <button onclick="sendReply('${reviewId}')">Отправить ответ</button>
        `;
    } catch (error) {
        document.getElementById('modalBody').innerHTML =
            `<p style="color: #f44336;">❌ Ошибка: ${error.message}</p>`;
    }
}
```

**4.3. Добавить функцию отправки ответа**
```javascript
async function sendReply(reviewId) {
    const replyText = document.getElementById('replyText').value;
    const headers = initData ? {'X-Telegram-Init-Data': initData} : {};

    const response = await fetch(`/api/v1/reviews/${reviewId}/reply`, {
        method: 'POST',
        headers: {...headers, 'Content-Type': 'application/json'},
        body: JSON.stringify({text: replyText})
    });

    if (response.ok) {
        alert('✅ Ответ отправлен!');
        closeModal();
    } else {
        alert('❌ Ошибка отправки');
    }
}
```

**4.4. Добавить кнопку "Автоответ на все"**
```javascript
// В функции openReviews(), после списка отзывов:
html += `<button onclick="replyToAll()">🤖 Автоответ на все</button>`;

async function replyToAll() {
    if (!confirm('Ответить на все неотвеченные отзывы?')) return;

    const headers = initData ? {'X-Telegram-Init-Data': initData} : {};
    const response = await fetch('/api/v1/reviews?limit=100', {headers});
    const reviews = await response.json();

    for (const review of reviews.filter(r => !r.reply_status)) {
        await replyToReview(review.review_id);
        await new Promise(r => setTimeout(r, 1000)); // задержка 1 сек
    }

    alert('✅ Все ответы отправлены!');
}
```

### ЭТАП 5: Запуск сбора данных

**5.1. Запустить вручную**
```bash
cd /root/sovani_bot
python3 collect_recent_data.py
```

**5.2. Проверить результат**
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('sovani_bot.db')
c = conn.cursor()
c.execute('SELECT COUNT(*) FROM daily_sales')
print(f'Sales: {c.fetchone()[0]}')
c.execute('SELECT COUNT(*) FROM daily_stock')
print(f'Stock: {c.fetchone()[0]}')
c.execute('SELECT COUNT(*) FROM sku')
print(f'SKU: {c.fetchone()[0]}')
conn.close()
"
```

**5.3. Добавить в systemd timer**
```ini
# /etc/systemd/system/sovani-collect-data.service
[Unit]
Description=SoVAni Data Collection

[Service]
Type=oneshot
User=root
WorkingDirectory=/root/sovani_bot
EnvironmentFile=/root/sovani_bot/.env
ExecStart=/usr/bin/python3 /root/sovani_bot/collect_recent_data.py

# /etc/systemd/system/sovani-collect-data.timer
[Unit]
Description=Run SoVAni data collection daily

[Timer]
OnCalendar=daily
OnBootSec=5min
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
systemctl daemon-reload
systemctl enable --now sovani-collect-data.timer
```

### ЭТАП 6: Исправление sovani-replies-worker

**6.1. Проверить что запускает**
```bash
cat /etc/systemd/system/sovani-replies-worker.service
```

**6.2. Исправить путь**
Если запускает `/root/sovani_api/replies_worker.py`, изменить на:
```ini
ExecStart=/usr/bin/python3 /root/sovani_bot/auto_reviews_processor.py
```

Или отключить, если функционал дублируется:
```bash
systemctl disable --now sovani-replies-worker
```

### ЭТАП 7: Перезапуск сервисов

```bash
systemctl daemon-reload
systemctl restart sovani-web
systemctl restart sovani-bot
systemctl status sovani-web
systemctl status sovani-bot
```

### ЭТАП 8: Тестирование

**8.1. Проверка генерации ответов**
```bash
curl -s -X POST 'http://localhost:8000/api/v1/reviews/1ZixpD57BDPhkLacaiIR/draft' | jq
```

**8.2. Проверка данных**
```bash
curl -s 'http://localhost:8000/api/v1/dashboard/summary?date_from=2025-07-01&date_to=2025-12-31' | jq
```

**8.3. Проверка TMA**
- Открыть @SoVAni_helper_bot
- Нажать кнопку TMA
- Открыть раздел Отзывы
- Нажать кнопку "Ответить" на отзыве
- Проверить черновик
- Отправить ответ

---

## 22. ФАЙЛЫ ТРЕБУЮЩИЕ ИЗМЕНЕНИЙ

### Изменения в коде:
```
✏️ app/db/models.py                     - Добавить поле marketplace
✏️ app/services/reviews_service.py      - Заменить review_id на id
✏️ app/web/routers/reviews.py           - Исправить вызов build_reply_for_review
✏️ app/web/routers/reviews.py           - Убрать хардкод marketplace
✏️ static/index.html                    - Добавить UI для ответов
```

### Изменения в конфигурации:
```
✏️ .env                                 - Настоящие API токены
✏️ /etc/systemd/system/sovani-collect-data.service   - Новый
✏️ /etc/systemd/system/sovani-collect-data.timer     - Новый
✏️ /etc/systemd/system/sovani-replies-worker.service - Исправить или отключить
```

### SQL миграции:
```sql
-- Добавить поле marketplace
ALTER TABLE reviews ADD COLUMN marketplace VARCHAR(10);
UPDATE reviews SET marketplace = 'WB' WHERE marketplace IS NULL;
```

---

## 23. ИТОГОВАЯ ОЦЕНКА СОСТОЯНИЯ

### ✅ Работает (30%):
- Telegram Bot
- TMA загружается
- API возвращает отзывы
- База данных подключена

### ⚠️ Работает частично (20%):
- API endpoints (часть работает, часть падает)
- Данные (есть 55 отзывов, нет sales/stock)

### ❌ Не работает (50%):
- Ответы на отзывы (нет UI + код с багами)
- Сбор данных (placeholder токены)
- Аналитика (нет данных для расчета)
- Автоматизация (нет scheduled tasks)

### Приоритет исправлений:
1. 🔴 **СРОЧНО**: Настройка API токенов
2. 🔴 **СРОЧНО**: Исправление reviews_service.py (Review.id)
3. 🔴 **СРОЧНО**: Исправление вызова build_reply_for_review()
4. 🟠 **ВАЖНО**: Добавление UI для ответов
5. 🟠 **ВАЖНО**: Запуск collect_recent_data.py
6. 🟡 **ЖЕЛАТЕЛЬНО**: Добавление поля marketplace в БД
7. 🟡 **ЖЕЛАТЕЛЬНО**: Systemd timer для автосбора

---

## 24. ЗАВИСИМОСТИ МЕЖДУ ПРОБЛЕМАМИ

```
Нет API токенов
    ↓
Невозможно собрать данные
    ↓
Таблицы sales/stock/sku пустые
    ↓
Dashboard показывает 0
    ↓
TMA не может показать финансы/остатки

---

Review.review_id в коде
    ↓
БД имеет поле id
    ↓
SQL запросы падают с ошибкой
    ↓
Endpoint /draft не работает
    ↓
Невозможно генерировать ответы

---

Нет UI для ответов
    ↓
Пользователь не может нажать "Ответить"
    ↓
Функционал ответов недоступен
    (даже если API работает)
```

---

## 25. ЗАКЛЮЧЕНИЕ

### Система находится в состоянии:
**"Частично работающий прототип с критическими багами"**

### Работает:
- Инфраструктура (systemd, nginx, БД)
- Отображение данных (те что есть в БД)
- Авторизация (DEV_MODE bypass)

### Не работает:
- Ответы на отзывы (баги в коде + нет UI)
- Сбор данных (нет токенов)
- Аналитика (нет данных)

### Для полной работоспособности нужно:
1. Настроить API токены WB/Ozon/OpenAI
2. Исправить 3 критических бага в коде
3. Добавить UI для ответов
4. Запустить сбор данных
5. Настроить автоматизацию

### Время на исправление (оценка):
- Настройка токенов: 30 минут
- Исправление багов: 1 час
- Добавление UI: 2 часа
- Запуск и проверка: 1 час
- **Итого**: ~4-5 часов работы

---

**Конец анализа**
