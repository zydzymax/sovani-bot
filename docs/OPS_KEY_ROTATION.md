# OPS: Ротация ORG_TOKENS_ENCRYPTION_KEY (Fernet)

## Цели

- Безопасно заменить ключ шифрования токенов маркетплейсов
- Исключить простои и потери доступа к маркетплейсам
- Обеспечить zero-downtime ротацию

## Принцип

Ротация выполняется в два этапа:
1. **Двойное чтение**: сервис читает старым и новым ключом, пишет новым
2. **Перешифровка**: массово пересохраняем все токены новым ключом
3. **Переключение**: удаляем старый ключ из конфига

## Предварительные требования

- Доступ к production ENV (Kubernetes secrets, .env файл, etc.)
- Доступ к БД для запуска миграционного скрипта
- Права на перезапуск сервисов
- Backup БД перед операцией (обязательно!)

## Шаги ротации

### 1. Подготовить новый ключ

Сгенерируйте новый Base64-ключ Fernet:

```bash
python3 - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

Пример вывода:
```
ZK8vQ7xK_9X3jN2mP4lW8sR5tY6uH1oI2aS3dF4gH5j=
```

### 2. Обновить ENV с двумя ключами

Добавьте новый ключ в конфигурацию БЕЗ удаления старого:

```bash
# .env или Kubernetes secret
ORG_TOKENS_ENCRYPTION_KEY=<старый_ключ>          # НЕ МЕНЯЕМ!
ORG_TOKENS_ENCRYPTION_KEY_NEXT=<новый_ключ>     # ДОБАВЛЯЕМ
```

**Kubernetes:**
```bash
kubectl create secret generic sovani-bot-secrets \
  --from-literal=ORG_TOKENS_ENCRYPTION_KEY='<старый>' \
  --from-literal=ORG_TOKENS_ENCRYPTION_KEY_NEXT='<новый>' \
  --dry-run=client -o yaml | kubectl apply -f -
```

### 3. Обновить код credentials-сервиса (если не реализовано)

Модифицируйте `app/services/credentials.py`:

```python
from app.core.config import get_settings

def _get_fernet_dual():
    """Get Fernet with dual-key support (current + next)."""
    settings = get_settings()
    current_key = settings.org_tokens_encryption_key.encode()

    # Check if rotation in progress
    next_key = getattr(settings, 'org_tokens_encryption_key_next', None)
    if next_key:
        # Dual-key mode: try current first, fallback to next
        from cryptography.fernet import MultiFernet
        return MultiFernet([
            Fernet(current_key),
            Fernet(next_key.encode())
        ])
    else:
        # Single-key mode
        return Fernet(current_key)

def _get_fernet_write():
    """Get Fernet for WRITE operations (always use NEXT if available)."""
    settings = get_settings()
    next_key = getattr(settings, 'org_tokens_encryption_key_next', None)

    if next_key:
        # During rotation: write with NEW key
        return Fernet(next_key.encode())
    else:
        # Normal mode: write with current key
        current_key = settings.org_tokens_encryption_key.encode()
        return Fernet(current_key)

def decrypt_credentials(encrypted_json: str) -> dict:
    """Decrypt with dual-key support."""
    fernet = _get_fernet_dual()
    decrypted = fernet.decrypt(encrypted_json.encode())
    return json.loads(decrypted.decode())

def encrypt_credentials(creds: dict) -> str:
    """Encrypt with write key (NEXT during rotation)."""
    fernet = _get_fernet_write()
    json_bytes = json.dumps(creds).encode()
    encrypted = fernet.encrypt(json_bytes)
    return encrypted.decode()
```

### 4. Перезапустить сервисы

Перезапустите приложение для применения новых ENV:

```bash
# Docker
docker-compose restart web

# Kubernetes
kubectl rollout restart deployment sovani-bot

# Systemd
sudo systemctl restart sovani-bot
```

**Проверка**: убедитесь, что сервис читает оба ключа:
```bash
# Проверить логи на наличие ошибок декодирования
tail -f /var/log/sovani-bot/app.log | grep -i "fernet\|decrypt"
```

### 5. Массовая перешифровка

Создайте и запустите миграционный скрипт:

```python
# scripts/rotate_encryption_key.py
"""Re-encrypt all org credentials with new key."""
from sqlalchemy import select, update
from app.db.session import SessionLocal
from app.db.models import Organization
from app.services.credentials import decrypt_credentials, encrypt_credentials

def rotate_all_credentials():
    db = SessionLocal()
    try:
        stmt = select(Organization).where(Organization.encrypted_credentials.isnot(None))
        orgs = db.execute(stmt).scalars().all()

        rotated = 0
        errors = 0

        for org in orgs:
            try:
                # Decrypt with dual-key (old or new)
                creds = decrypt_credentials(org.encrypted_credentials)

                # Re-encrypt with NEW key
                new_encrypted = encrypt_credentials(creds)

                # Update
                org.encrypted_credentials = new_encrypted
                db.commit()

                rotated += 1
                print(f"✓ Org {org.id} ({org.name}): credentials re-encrypted")

            except Exception as e:
                errors += 1
                print(f"✗ Org {org.id}: {e}")
                db.rollback()

        print(f"\n{'='*60}")
        print(f"Rotation complete: {rotated} success, {errors} errors")
        print(f"{'='*60}")

    finally:
        db.close()

if __name__ == "__main__":
    rotate_all_credentials()
```

Запуск:
```bash
export ORG_TOKENS_ENCRYPTION_KEY='<старый>'
export ORG_TOKENS_ENCRYPTION_KEY_NEXT='<новый>'
python scripts/rotate_encryption_key.py
```

Ожидаемый вывод:
```
✓ Org 1 (Acme Corp): credentials re-encrypted
✓ Org 2 (Beta LLC): credentials re-encrypted
============================================================
Rotation complete: 2 success, 0 errors
============================================================
```

### 6. Переключить ключи

После успешной перешифровки ВСЕХ записей:

```bash
# Обновите ENV: новый ключ становится основным
ORG_TOKENS_ENCRYPTION_KEY=<новый_ключ>          # ЗАМЕНЯЕМ на новый
# ORG_TOKENS_ENCRYPTION_KEY_NEXT=<удалить>      # УДАЛЯЕМ
```

**Kubernetes:**
```bash
kubectl create secret generic sovani-bot-secrets \
  --from-literal=ORG_TOKENS_ENCRYPTION_KEY='<новый>' \
  --dry-run=client -o yaml | kubectl apply -f -
```

### 7. Перезапустить сервисы финально

```bash
# Перезапуск с обновлённым конфигом
kubectl rollout restart deployment sovani-bot
# или
sudo systemctl restart sovani-bot
```

### 8. Проверки после ротации

#### 8.1. Smoke-тест расшифровки

```bash
# Проверить, что API маркетплейсов работает
curl -H "Authorization: Bearer $JWT" \
  http://localhost:8000/api/v1/dashboard?date_from=2025-01-01&date_to=2025-01-31
```

Должны вернуться данные с маркетплейсов (требует валидных токенов).

#### 8.2. Проверка БД

```sql
-- Убедиться, что encrypted_credentials не содержит открытых токенов
SELECT id, name,
       SUBSTR(encrypted_credentials, 1, 50) as encrypted_sample
FROM organizations
WHERE encrypted_credentials IS NOT NULL;
```

Все значения должны быть вида `gAAAAA...` (Base64 Fernet).

#### 8.3. Проверка логов

```bash
# Не должно быть ошибок декодирования
tail -n 100 /var/log/sovani-bot/app.log | grep -i "decrypt\|fernet\|invalid token"
```

#### 8.4. Функциональные тесты

```bash
# Прогнать integration-тесты с реальными токенами
pytest tests/integration/test_marketplace_api.py -v
```

## Аварийный откат

Если после переключения возникли проблемы:

### 1. Вернуть старый ключ

```bash
# Вернуть ENV к предыдущему состоянию
ORG_TOKENS_ENCRYPTION_KEY=<старый_ключ>
ORG_TOKENS_ENCRYPTION_KEY_NEXT=<новый_ключ>  # вернуть для двойного чтения
```

### 2. Перезапустить сервисы

```bash
kubectl rollout undo deployment sovani-bot
# или
sudo systemctl restart sovani-bot
```

### 3. Восстановить из backup (крайний случай)

Если БД повреждена:
```bash
# Восстановить snapshot БД ПЕРЕД ротацией
pg_restore -d sovani_prod backup_before_rotation.dump
```

### 4. Повторить ротацию

После выявления проблемы повторите шаги 1-8 с исправлениями.

## Логи и аудит

Все операции с ключами шифрования логируются:

```python
logger.info(
    "Encryption key rotation",
    extra={
        "action": "key_rotation",
        "org_id": org.id,
        "status": "success",  # or "failed"
        "credentials_fields": list(creds.keys()),  # НЕ логируем значения!
    }
)
```

**ВАЖНО**: Логи маскируют секреты согласно `app/core/logging_config.py` (Stage 4).

## Частота ротации

Рекомендуемая частота:
- **Production**: каждые 90 дней
- **Staging**: каждые 180 дней
- **Dev**: не требуется (используются тестовые ключи)

## Безопасность

1. **Никогда не коммитить ключи в Git**
   - Используйте `.env.example` с placeholder-значениями
   - Реальные ключи только в secrets-менеджере

2. **Ограничить доступ к ENV**
   - Kubernetes secrets с RBAC
   - Read-only доступ для приложения

3. **Backup перед ротацией**
   - Автоматический snapshot БД
   - Хранить backup минимум 30 дней

4. **Мониторинг**
   - Алерт на ошибки декодирования (Prometheus metric)
   - Дашборд с метриками ротации

## Контрольный чеклист

- [ ] Создан backup БД
- [ ] Сгенерирован новый Fernet-ключ
- [ ] Обновлены ENV с `ORG_TOKENS_ENCRYPTION_KEY_NEXT`
- [ ] Перезапущены сервисы (двойное чтение активно)
- [ ] Запущен скрипт массовой перешифровки
- [ ] Проверен вывод скрипта (0 errors)
- [ ] Обновлены ENV (новый ключ стал основным)
- [ ] Удалён `ORG_TOKENS_ENCRYPTION_KEY_NEXT` из ENV
- [ ] Перезапущены сервисы финально
- [ ] Smoke-тест API маркетплейсов успешен
- [ ] Логи не содержат ошибок декодирования
- [ ] Integration-тесты зелёные
- [ ] Задокументирована дата ротации в runbook

## См. также

- [Stage 19.4 SAFE Cutover Report](../STAGE_19_4_SAFE_CUTOVER.md)
- [Credentials Encryption Implementation](../app/services/credentials.py)
- [Security Logging Configuration](../app/core/logging_config.py)
