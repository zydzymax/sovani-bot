# Rate Limiter Documentation

## Обзор

Централизованная система управления лимитами API запросов для предотвращения ошибок 429 (Too Many Requests) и оптимизации работы с WildBerries и Ozon API.

## Конфигурация лимитов

### WildBerries API
- **wb_general**: 300 req/min, 200ms интервал, 20 burst токенов
- **wb_advertising**: 100 req/min, 600ms интервал, 5 burst токенов (консервативно)

### Ozon API
- **ozon_general**: 60 req/min, 1000ms интервал, 10 burst токенов
- **ozon_performance**: 60 req/min, 1000ms интервал, 10 burst токенов

## Использование

### Базовое применение

```python
from rate_limiter import with_rate_limit

# Перед API запросом
await with_rate_limit('wb_advertising')
# ваш API запрос здесь
```

### Обработка 429 ошибок

```python
from rate_limiter import rate_limiter

# При получении 429 ошибки
await rate_limiter.handle_429_error('wb_advertising', attempt_number)
```

### Мониторинг

```python
from rate_limiter import get_rate_limit_stats
from rate_limiter_monitor import monitor_api_usage

# Получение статистики
stats = get_rate_limit_stats()

# Детальный отчет
report = await monitor_api_usage()
```

## Алгоритм работы

1. **Token Bucket**: Использует алгоритм "корзины токенов"
2. **Burst Control**: Ограничивает пиковые нагрузки
3. **Минимальные интервалы**: Равномерное распределение запросов
4. **Экспоненциальная задержка**: При 429 ошибках

## Интеграция

Автоматически интегрирован в:
- `WildberriesAPI.get_advertising_campaigns()`
- `WildberriesAPI.get_advertising_statistics()`
- `OzonAPI.get_product_reviews()`
- `OzonAPI.get_product_stocks()`

## Мониторинг и отладка

### Команды мониторинга

```python
# Статус всех API
await monitor_api_usage()

# Тестирование rate limiter
await simulate_rate_limiting_test()

# Рекомендации по оптимизации
get_rate_limiter_recommendations()

# Сброс статистики
await reset_rate_limiter_stats()
```

### Примеры вывода

```
📊 Rate Limiter Status Report

🔹 WB_ADVERTISING
   • Запросы: 15/100 req/min
   • Burst токены: 3/5
   • Мин. интервал: 600ms
   • ✅ Низкая нагрузка: 15.0%

🔹 OZON_GENERAL
   • Запросы: 5/60 req/min
   • Burst токены: 8/10
   • Мин. интервал: 1000ms
   • ✅ Низкая нагрузка: 8.3%
```

## Рекомендации

1. **Используйте правильные API типы**:
   - `wb_advertising` для рекламного API WB
   - `ozon_general` для основного API Ozon

2. **Мониторьте нагрузку**: Проверяйте статистику при высокой активности

3. **Обрабатывайте 429 ошибки**: Всегда используйте retry с rate limiter

4. **Группируйте запросы**: Минимизируйте количество API вызовов

## Логирование

Rate limiter логирует:
- Превышения лимитов (INFO уровень)
- 429 ошибки и задержки (WARNING уровень)
- Детальную отладочную информацию (DEBUG уровень)

## Конфигурация для других API

Для добавления нового API:

```python
# В rate_limiter.py добавить в CONFIGS
'new_api': RateLimitConfig(
    requests_per_minute=120,
    min_interval_ms=500,
    burst_limit=15
)
```

## Преимущества

- ✅ Предотвращение 429 ошибок
- ✅ Оптимальное использование API лимитов
- ✅ Централизованное управление
- ✅ Детальный мониторинг
- ✅ Автоматическое восстановление после ошибок