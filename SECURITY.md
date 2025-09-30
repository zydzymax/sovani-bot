# 🔒 SECURITY POLICY

## Конфигурация и секреты

### ⚠️ КРИТИЧЕСКИ ВАЖНО

**НИКОГДА не коммитьте в Git:**
- Токены API (Telegram, Wildberries, Ozon, OpenAI)
- Приватные ключи (`.pem`, `.key`)
- Файлы `.env` с реальными значениями
- Базы данных (`.db`, `.sqlite`)
- Логи (`.log`)
- Бэкапы и временные файлы

### ✅ Правильная работа с секретами

1. **Используйте только переменные окружения:**
   ```bash
   export TELEGRAM_TOKEN="your_token_here"
   export WB_FEEDBACKS_TOKEN="your_wb_token"
   export OZON_CLIENT_ID="your_ozon_id"
   export OZON_API_KEY_ADMIN="your_ozon_key"
   export OPENAI_API_KEY="your_openai_key"
   ```

2. **Для постоянного использования создайте `.env` файл (локально):**
   ```bash
   # .env (НИКОГДА не коммитить!)
   TELEGRAM_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   WB_FEEDBACKS_TOKEN=eyJhbGc...
   WB_STATS_TOKEN=eyJhbGc...
   OZON_CLIENT_ID=12345
   OZON_API_KEY_ADMIN=abc-def-ghi
   OPENAI_API_KEY=sk-...
   MANAGER_CHAT_ID=123456789
   ```

3. **Загрузите переменные окружения:**
   ```bash
   # Для systemd service
   EnvironmentFile=/root/sovani_bot/.env

   # Или вручную
   export $(cat .env | xargs)
   ```

4. **Используйте `.env.example` как шаблон:**
   ```bash
   cp .env.example .env
   # Затем заполните реальными значениями
   ```

## Защита приватных ключей

### WB Private Key для JWT

Приватный ключ Wildberries (`wb_private_key.pem`) должен:
- Храниться вне Git репозитория
- Иметь права доступа 600 (только владелец может читать)
- Быть указан в `.gitignore`

```bash
# Правильные права доступа
chmod 600 /root/sovani_bot/wb_private_key.pem
```

## Проверка репозитория на утечки

### Перед пушем в Git

```bash
# Проверьте статус - нет ли чувствительных файлов
git status

# Проверьте что добавляете в коммит
git diff --staged

# Проверьте содержимое файлов
git show :path/to/file
```

### Поиск утечек в истории Git

Если секреты случайно попали в историю:

```bash
# Найти файлы в истории
git log --all --full-history -- "*.env"
git log --all --full-history -- "*.pem"

# Удалить из истории (ОСТОРОЖНО!)
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all

# Или используйте BFG Repo-Cleaner
bfg --delete-files .env
```

**После очистки истории:**
```bash
git push origin --force --all
git push origin --force --tags
```

## API Rate Limiting

### Wildberries API
- Лимит: **60 запросов/минуту** на большинство эндпоинтов
- Статистика API: **1 запрос/минуту** для `/api/v1/supplier/incomes`, `/sales`
- Используйте chunking для больших периодов

### Ozon API
- Лимит: зависит от метода (обычно **200-1000 запросов/минуту**)
- FBS методы более лимитированы

### OpenAI API
- Лимит: зависит от тарифа
- Рекомендуем exponential backoff при 429 ошибках

## Логирование

### Что НЕ логировать

❌ **НИКОГДА не логируйте:**
- Токены API
- Приватные ключи
- Пароли
- Полные телефоны/email клиентов
- Финансовые данные клиентов (только агрегированные)

### Маскирование чувствительных данных

```python
# Правильно
logger.info(f"WB Token: {token[:8]}...{token[-4:]}")  # Показываем только часть

# Неправильно
logger.info(f"WB Token: {token}")  # Полный токен в логах
```

## Обработка ошибок API

Не раскрывайте детали ошибок пользователю:

```python
# Правильно
except Exception as e:
    logger.error(f"API error: {str(e)}")
    await message.answer("Произошла ошибка. Попробуйте позже.")

# Неправильно
except Exception as e:
    await message.answer(f"Ошибка: {str(e)}")  # Может содержать токены/URL
```

## Systemd Service Security

```ini
[Service]
# Запуск от непривилегированного пользователя (рекомендуется)
User=sovani
Group=sovani

# Ограничение ресурсов
MemoryLimit=512M
CPUQuota=50%

# Защита файловой системы
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/root/sovani_bot

# Переменные окружения
EnvironmentFile=/root/sovani_bot/.env
```

## Обновление зависимостей

Регулярно обновляйте зависимости для исправления уязвимостей:

```bash
# Проверка устаревших пакетов
pip list --outdated

# Обновление
pip install --upgrade aiogram aiohttp sqlalchemy

# Проверка уязвимостей (если установлен)
pip-audit
# или
safety check
```

## Резервное копирование

```bash
# База данных
cp sovani_bot.db sovani_bot.db.backup_$(date +%Y%m%d)

# Конфигурация (БЕЗ СЕКРЕТОВ!)
tar -czf config_backup_$(date +%Y%m%d).tar.gz \
  --exclude='.env' \
  --exclude='*.pem' \
  --exclude='*.key' \
  config.py celery_config.py
```

## Отчетность об уязвимостях

Если вы обнаружили уязвимость:
1. **НЕ создавайте публичный issue**
2. Свяжитесь с владельцем репозитория напрямую
3. Опишите проблему и возможные последствия
4. Дайте время на исправление (обычно 90 дней)

## Чеклист безопасности

Перед production deployment:

- [ ] Все секреты в переменных окружения (не в коде)
- [ ] `.env` в `.gitignore`
- [ ] Приватные ключи имеют права 600
- [ ] История Git проверена на утечки
- [ ] Rate limiting настроен
- [ ] Логи не содержат чувствительных данных
- [ ] Ошибки не раскрывают внутренние детали
- [ ] Зависимости обновлены
- [ ] Бэкапы настроены
- [ ] Systemd service с ограничениями ресурсов

---

**Последнее обновление:** 2025-09-30
**Версия:** 1.0
