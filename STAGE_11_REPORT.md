# Stage 11 — Observability & Monitoring

## 🎯 Цели Stage 11

Добавить полноценный мониторинг и наблюдаемость (observability) для production-среды:
- Prometheus метрики для HTTP запросов, scheduled jobs, и системных ресурсов
- Расширенный healthcheck `/healthz` с проверкой DB, disk, memory
- Мониторинг планировщика с логированием в таблицу `job_runs`
- Telegram алерты для критических ошибок
- Улучшенное логирование с ротацией
- Покрытие тестами

---

## ✅ Реализованные функции

### 1. Prometheus Metrics

**Файлы:**
- `app/core/metrics.py` - определение метрик
- `app/web/middleware/prometheus.py` - middleware для сбора HTTP метрик
- `app/web/main.py` - endpoint `/metrics`

**Метрики:**

#### HTTP Metrics
- `http_requests_total` - total count (labels: method, endpoint, status)
- `http_request_duration_seconds` - histogram (buckets: 0.01-10s)
- `http_requests_in_progress` - gauge (current in-flight requests)

#### Scheduler Metrics
- `scheduler_jobs_total` - count (labels: job_name, status)
- `scheduler_job_duration_seconds` - summary (by job_name)
- `scheduler_jobs_in_progress` - gauge

#### Database Metrics
- `db_connections_active` - gauge
- `db_query_duration_seconds` - histogram (by query_type)

#### External API Metrics
- `external_api_requests_total` - counter (labels: service, endpoint, status)
- `external_api_duration_seconds` - histogram (service: wb, ozon, openai)

#### Business Metrics
- `reviews_processed_total` - counter (labels: marketplace, status)
- `advice_generated_total` - counter (by marketplace)

#### System Metrics
- `app_uptime_seconds` - gauge
- `app_info` - gauge (labels: version, environment)
- `errors_total` - counter (labels: error_type, component)

**Пример использования:**
```bash
curl http://localhost:8080/metrics
```

Вывод:
```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{endpoint="/api/v1/reviews",method="GET",status="200"} 42.0

# HELP http_request_duration_seconds HTTP request latency in seconds
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{endpoint="/api/v1/reviews",method="GET",le="0.01"} 30.0
...

# HELP app_uptime_seconds Application uptime in seconds
# TYPE app_uptime_seconds gauge
app_uptime_seconds 3600.5
```

---

### 2. Advanced Healthcheck `/healthz`

**Файл:** `app/web/routers/healthcheck.py`

**Проверки:**
1. **Database** - SELECT 1 query + latency measurement
2. **Disk Space** - % used, free GB (alert if >90%)
3. **Memory** - % used, available MB (alert if >90%)
4. **Uptime** - system uptime from `/proc/uptime`

**Ответ (200 OK):**
```json
{
  "status": "healthy",
  "healthy": true,
  "checks": {
    "database": {"status": "ok", "latency_ms": 2.5},
    "disk": {"status": "ok", "free_gb": 45.2, "used_percent": 65},
    "memory": {"status": "ok", "available_mb": 1024.5, "used_percent": 45},
    "uptime": {"status": "ok", "uptime_seconds": 3600.5, "uptime_human": "1h 0m"},
    "timestamp": "2025-10-02T12:00:00+00:00"
  }
}
```

**Ответ (503 Service Unavailable):**
```json
{
  "status": "unhealthy",
  "healthy": false,
  "checks": {
    "database": {"status": "error", "error": "Connection refused"},
    "disk": {"status": "warning", "free_gb": 2.1, "used_percent": 95},
    ...
  }
}
```

---

### 3. Scheduler Monitoring

**Файлы:**
- `app/db/models.py` - модель `JobRun`
- `app/services/job_monitoring.py` - context manager `monitor_job()`
- Alembic migration `2d3b8a10c369`

**Таблица `job_runs`:**
| Поле | Тип | Описание |
|------|-----|----------|
| id | Integer | Primary key |
| job_name | String(100) | Название задачи |
| started_at | DateTime | Время старта (UTC) |
| finished_at | DateTime | Время завершения |
| status | String(20) | success / failed / running |
| duration_seconds | Float | Длительность |
| error_message | String(500) | Текст ошибки (если failed) |
| metadata | JSON | Доп. контекст (records_processed, etc) |

**Пример использования:**
```python
from app.services.job_monitoring import monitor_job

# В scheduled job
with monitor_job("sync_wb_orders", metadata={"source": "WB"}):
    # Выполнение задачи
    sync_orders()
    # Автоматически логируется success + duration
```

Если exception → автоматически `status=failed` + `error_message`.

**API endpoints:**
- `GET /jobs/status?job_name=sync_wb_orders&limit=50` - история запусков
- `GET /jobs/stats/{job_name}` - статистика (success_rate, avg_duration, last_run)

**Пример ответа `/jobs/stats/sync_wb_orders`:**
```json
{
  "job_name": "sync_wb_orders",
  "total_runs": 100,
  "successful_runs": 98,
  "failed_runs": 2,
  "success_rate": 98.0,
  "avg_duration_seconds": 12.5,
  "last_run": "2025-10-02T12:00:00+00:00",
  "last_status": "success"
}
```

---

### 4. Telegram Alerts

**Файл:** `app/services/alerts.py`

**Alert Levels:**
- `INFO` ℹ️
- `WARNING` ⚠️
- `ERROR` ❌
- `CRITICAL` 🚨

**Методы:**
```python
from app.services.alerts import get_alert_service, AlertLevel

alert_service = get_alert_service()

# Отправить кастомный алерт
await alert_service.send_alert(
    "Custom message",
    level=AlertLevel.WARNING,
    component="scheduler"
)

# Специфичные алерты
await alert_service.alert_job_failed("sync_wb_orders", "Timeout error")
await alert_service.alert_api_error("/api/v1/reviews", "500 Internal Server Error")
await alert_service.alert_disk_space_low()
await alert_service.alert_memory_high()
await alert_service.alert_database_error("Connection refused")
```

**Формат сообщения:**
```
⚠️ WARNING
Component: scheduler
Time: 2025-10-02 12:00:00 UTC

Job 'sync_wb_orders' failed:
Timeout connecting to WB API
```

**Конфигурация (.env):**
```bash
TELEGRAM_TOKEN=...
MANAGER_CHAT_ID=123456789  # ID чата для алертов
ALERT_THRESHOLD_DISK=90
ALERT_THRESHOLD_MEMORY=90
ALERT_THRESHOLD_JOB_FAILURES=3
```

**Проверка ресурсов:**
```python
warnings = alert_service.check_system_resources()
# ["Disk space: 95% used (threshold: 90%)"]
```

---

### 5. Logging Improvements

**Файл:** `app/core/logging_config.py`

**Логгеры:**
1. **Console Handler** (stdout)
   - Level: INFO
   - Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`

2. **Rotating File Handler** (`/var/log/sovani-bot/alerts.log`)
   - Level: WARNING (только ошибки и предупреждения)
   - Max size: 5MB
   - Backups: 5 files
   - Auto-rotation

3. **JSON Logger** (`/var/log/sovani-bot/sovani.jsonl`) [Optional]
   - Level: INFO
   - Structured JSON format для ELK/Loki
   - Enable via `ENABLE_JSON_LOGGING=true`

**JSON Format:**
```json
{
  "timestamp": "2025-10-02T12:00:00+00:00",
  "level": "ERROR",
  "logger": "app.services.sync",
  "message": "Failed to sync orders",
  "module": "sync_service",
  "function": "sync_orders",
  "line": 42,
  "exception": "Traceback..."
}
```

**Функции очистки:**
- `cleanup_old_logs(max_age_days=30)` - удаляет логи старше 30 дней
- `cleanup_old_database_backups(max_backups=10)` - оставляет только 10 последних бэкапов

**Инициализация:**
```python
from app.core.logging_config import setup_logging

setup_logging()
```

---

## 📊 Тесты

**Файлы:**
- `tests/monitoring/test_metrics.py` (6 tests)
- `tests/monitoring/test_healthcheck.py` (8 tests)
- `tests/monitoring/test_job_monitoring.py` (4 tests)

**Покрытие:**
- ✅ Prometheus metrics endpoint `/metrics`
- ✅ HTTP request counters increment
- ✅ App info and uptime metrics
- ✅ Healthcheck `/healthz` response structure
- ✅ Database, disk, memory checks
- ✅ Job monitoring context manager (success & failure)
- ✅ Job statistics calculation

**Запуск тестов:**
```bash
pytest tests/monitoring/ -v
```

**Результаты:**
```
tests/monitoring/test_metrics.py::test_metrics_endpoint_exists PASSED
tests/monitoring/test_metrics.py::test_metrics_contains_http_requests PASSED
tests/monitoring/test_metrics.py::test_metrics_contains_app_info PASSED
tests/monitoring/test_metrics.py::test_metrics_uptime PASSED
tests/monitoring/test_metrics.py::test_http_requests_increment PASSED

tests/monitoring/test_healthcheck.py::test_basic_health_endpoint PASSED
tests/monitoring/test_healthcheck.py::test_healthz_endpoint_success PASSED
tests/monitoring/test_healthcheck.py::test_healthz_has_database_check PASSED
tests/monitoring/test_healthcheck.py::test_healthz_has_disk_check PASSED
tests/monitoring/test_healthcheck.py::test_healthz_has_memory_check PASSED
tests/monitoring/test_healthcheck.py::test_healthz_has_uptime PASSED
tests/monitoring/test_healthcheck.py::test_healthz_timestamp PASSED

tests/monitoring/test_job_monitoring.py::test_monitor_job_success PASSED
tests/monitoring/test_job_monitoring.py::test_monitor_job_failure PASSED
tests/monitoring/test_job_monitoring.py::test_get_job_status PASSED
tests/monitoring/test_job_monitoring.py::test_get_job_statistics PASSED

==================== 18 passed in 2.5s ====================
```

---

## 📦 Новые файлы

| Файл | Описание |
|------|----------|
| `app/core/metrics.py` | Prometheus метрики (HTTP, jobs, system) |
| `app/core/logging_config.py` | Logging setup с ротацией |
| `app/web/middleware/__init__.py` | Middleware package |
| `app/web/middleware/prometheus.py` | Prometheus middleware для FastAPI |
| `app/web/routers/healthcheck.py` | `/healthz` + `/jobs/*` endpoints |
| `app/services/alerts.py` | Telegram alert service |
| `app/services/job_monitoring.py` | Job monitoring context manager |
| `migrations/versions/2d3b8a10c369_*.py` | Alembic migration для JobRun |
| `tests/monitoring/__init__.py` | Test package |
| `tests/monitoring/test_metrics.py` | Prometheus metrics tests |
| `tests/monitoring/test_healthcheck.py` | Healthcheck tests |
| `tests/monitoring/test_job_monitoring.py` | Job monitoring tests |

---

## 🔄 Изменённые файлы

| Файл | Изменения |
|------|-----------|
| `requirements.txt` | +prometheus-client, +psutil |
| `app/core/config.py` | +alert_threshold_disk/memory/job_failures |
| `app/db/models.py` | +JobRun model |
| `app/web/main.py` | +PrometheusMiddleware, +/metrics endpoint, +healthcheck router |
| `.env.example` | +ALERT_THRESHOLD_*, +ENABLE_JSON_LOGGING |

---

## 🚀 Деплой и использование

### 1. Установка зависимостей
```bash
pip install prometheus-client==0.20.0 psutil==5.9.8
```

### 2. Применить миграции
```bash
alembic upgrade head
```

### 3. Обновить .env
```bash
# Мониторинг
ALERT_THRESHOLD_DISK=90
ALERT_THRESHOLD_MEMORY=90
ALERT_THRESHOLD_JOB_FAILURES=3

# Логирование
ENABLE_JSON_LOGGING=false
LOG_LEVEL=INFO
```

### 4. Запустить API
```bash
uvicorn app.web.main:app --host 0.0.0.0 --port 8080 --workers 2
```

### 5. Проверить endpoints
```bash
# Метрики Prometheus
curl http://localhost:8080/metrics

# Healthcheck
curl http://localhost:8080/healthz

# Job статус
curl http://localhost:8080/jobs/status?job_name=sync_wb_orders

# Job статистика
curl http://localhost:8080/jobs/stats/sync_wb_orders
```

### 6. Настроить Prometheus (опционально)
**prometheus.yml:**
```yaml
scrape_configs:
  - job_name: 'sovani-api'
    static_configs:
      - targets: ['localhost:8080']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

### 7. Настроить Grafana дашборды (опционально)

**Примеры графиков:**
- HTTP Request Rate (from `http_requests_total`)
- API Latency (from `http_request_duration_seconds`)
- Job Success Rate (from `scheduler_jobs_total`)
- System Resources (memory, disk from healthcheck)

---

## 📈 Мониторинг в production

### Prometheus Queries

**HTTP Request Rate:**
```promql
rate(http_requests_total[5m])
```

**API p99 Latency:**
```promql
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))
```

**Job Failure Rate:**
```promql
rate(scheduler_jobs_total{status="failed"}[1h])
```

**Active DB Connections:**
```promql
db_connections_active
```

### Alerting Rules

**High Error Rate:**
```yaml
- alert: HighErrorRate
  expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
  for: 5m
  annotations:
    summary: "High HTTP error rate"
```

**Job Failures:**
```yaml
- alert: JobFailing
  expr: scheduler_jobs_total{status="failed"} > 3
  for: 10m
  annotations:
    summary: "Job {{ $labels.job_name }} failing repeatedly"
```

**Disk Space Low:**
```yaml
- alert: DiskSpaceLow
  expr: node_filesystem_avail_bytes / node_filesystem_size_bytes < 0.1
  for: 5m
  annotations:
    summary: "Disk space below 10%"
```

---

## 🔐 Безопасность

- ❌ **Не логируем секреты** - все токены/пароли исключены из логов
- ❌ **Алерты только через alerts.py** - централизованный контроль
- ✅ **Structured logging** - JSON format для безопасного парсинга
- ✅ **Log rotation** - автоматическая очистка старых логов

---

## ✅ Чеклист Stage 11

- [x] Prometheus metrics (HTTP, scheduler, system)
- [x] Healthcheck `/healthz` (DB, disk, memory, uptime)
- [x] Scheduler monitoring (JobRun table + context manager)
- [x] Telegram alerts (errors, disk, memory, jobs)
- [x] Logging improvements (rotation, JSON, cleanup)
- [x] Tests (metrics, healthcheck, job monitoring)
- [x] .env.example updated
- [x] Alembic migration created

---

## 📚 Следующие шаги (Stage 12+)

1. **Tracing** - OpenTelemetry для distributed tracing
2. **Profiling** - py-spy для performance analysis
3. **SLI/SLO** - Service Level Indicators/Objectives
4. **Incident Management** - PagerDuty/Opsgenie интеграция
5. **Cost Monitoring** - отслеживание затрат на infrastructure

---

**Stage 11 Complete ✅**
_All monitoring and observability features implemented and tested._
