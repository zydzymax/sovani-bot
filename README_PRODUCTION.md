# 🚀 SoVAni Bot - Production Documentation

## 📋 Обзор проекта

**SoVAni Bot** - это Telegram-бот для автоматизации работы продавца на маркетплейсах Wildberries и Ozon.

### 🎯 Основные функции
- 🤖 **Автоматическая обработка отзывов** с ChatGPT-4
- 📊 **Финансовая аналитика** (P&L, выручка, ROI)
- 💰 **Управление себестоимостью** через Excel
- 📋 **Складские остатки** и рекомендации
- 🔍 **API мониторинг** статуса интеграций

## 🏗️ Архитектура

### Технический стек
- **Framework**: aiogram 2.25.1 (асинхронный Telegram Bot)
- **Database**: SQLite (sovani_bot.db)
- **APIs**:
  - Wildberries API (6 токенов с JWT подписью)
  - Ozon API (Client-Id + API-Key)
  - OpenAI ChatGPT-4
- **Data Processing**: pandas, openpyxl
- **Scheduler**: APScheduler

### Ключевые модули

| Файл | Размер | Назначение |
|------|--------|------------|
| `bot.py` | 5.7k строк | Главный диспетчер команд |
| `api_clients_main.py` | 2.4k строк | API клиенты WB/Ozon |
| `real_data_reports.py` | 1.8k строк | Финансовые отчеты |
| `wb_reviews_manager.py` | 400 строк | Управление отзывами |
| `config.py` | 320 строк | Конфигурация токенов |

## 🔧 Установка и настройка

### 1. Зависимости
```bash
pip install -r requirements.txt
```

### 2. Переменные окружения
Создать файл `.env`:
```env
WB_FEEDBACKS_TOKEN=your_wb_feedbacks_token
WB_STATS_TOKEN=your_wb_stats_token
WB_ADS_TOKEN=your_wb_ads_token
WB_SUPPLY_TOKEN=your_wb_supply_token
WB_ANALYTICS_TOKEN=your_wb_analytics_token
WB_CONTENT_TOKEN=your_wb_content_token
OZON_CLIENT_ID=your_ozon_client_id
OZON_API_KEY_ADMIN=your_ozon_api_key
OPENAI_API_KEY=your_openai_api_key
```

### 3. WB приватный ключ
Поместить `wb_private_key.pem` в корень проекта для JWT подписи.

### 4. Запуск
```bash
python bot.py
```

## 📊 API Интеграции

### Wildberries API (6 токенов)
1. **Feedbacks API** - отзывы и вопросы
2. **Statistics API** - финансовая статистика
3. **Content API** - управление товарами
4. **Marketplace API** - заказы и продажи
5. **Analytics API** - углубленная аналитика
6. **Ads API** - рекламные кампании

### Ozon API (2 токена)
1. **Client-Id** - идентификатор клиента
2. **API-Key** - ключ для авторизации

### OpenAI ChatGPT
- **Модель**: gpt-4
- **Назначение**: генерация персонализированных ответов на отзывы

## 🐛 Критические исправления (Сентябрь 2025)

### Проблема: Парсинг отзывов
**Было**: Все покупатели назывались "Покупатель", 2-звездные отзывы обрабатывались как 5-звездные
**Стало**:
- ✅ Реальные имена покупателей из `userName`
- ✅ Корректные рейтинги из `productValuation`
- ✅ Названия товаров из `productDetails.productName`

### Местоположение исправлений
- `wb_reviews_manager.py:_parse_wb_review()` - строки 268-314
- Убран fallback на 5 звезд для рейтингов
- Добавлена fallback логика для отображения отвеченных отзывов

## 🔒 Безопасность

### Токены и ключи
- Все токены читаются из переменных окружения
- Приватный ключ WB хранится в защищенном файле
- Логирование без раскрытия токенов

### Rate Limiting
- Автоматические задержки между запросами
- Retry механизмы при временных ошибках
- Мониторинг статуса API

## 📈 Производительность

### Оптимизации
- Асинхронная обработка всех API запросов
- Параллельная обработка данных WB/Ozon
- Кэширование статуса API
- Chunked обработка больших периодов

### Мониторинг
- Логирование всех операций
- Статус API проверки
- Автоматические уведомления об ошибках

## 🧪 Тестирование

Проект содержит 69+ тестовых файлов для проверки:
- API connectivity
- Data parsing accuracy
- Financial calculations
- Review processing logic
- Excel integration

## 📞 Поддержка

### Структура файлов
```
sovani_bot/
├── bot.py                     # Главный файл
├── api_clients_main.py        # API клиенты
├── wb_reviews_manager.py      # Отзывы ChatGPT
├── real_data_reports.py       # Финансовые отчеты
├── config.py                  # Конфигурация
├── requirements.txt           # Зависимости
├── api_clients/               # API модули
├── handlers/                  # Обработчики команд
├── reports/                   # Генерируемые отчеты
└── test_*.py                  # Тестовые файлы
```

### Команды бота
- `/start` - главное меню
- `🟣 Отчеты WB` - финансовые отчеты Wildberries
- `🟠 Отчеты Ozon` - финансовые отчеты Ozon
- `⭐ Управление отзывами` - работа с отзывами
- `💰 Себестоимость` - загрузка COGS данных

---

**Разработчик**: SoVAni Team
**Версия**: 2.0 (Сентябрь 2025)
**Статус**: Production Ready ✅
