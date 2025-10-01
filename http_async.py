#!/usr/bin/env python3
"""Единый асинхронный HTTP клиент для бота (BOT-ASYNC-FIX)"""

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Глобальный singleton клиент
_http_client: httpx.AsyncClient | None = None


def get_backend_base_url() -> str:
    """Получить базовый URL бэкенда из .env"""
    return os.getenv("BACKEND_BASE_URL", "https://justbusiness.lol/api")


def get_service_token() -> str:
    """Получить токен сервиса из .env"""
    return os.getenv("X_SERVICE_TOKEN", "")


async def init_http_client() -> httpx.AsyncClient:
    """Инициализировать глобальный HTTP клиент"""
    global _http_client

    if _http_client is not None:
        return _http_client

    # Настройки клиента для production
    timeout_config = httpx.Timeout(
        connect=10.0,  # Подключение
        read=30.0,  # Чтение ответа
        write=10.0,  # Запись запроса
        pool=60.0,  # Общий timeout для операции
    )

    limits = httpx.Limits(
        max_keepalive_connections=10,  # Пул соединений
        max_connections=20,  # Максимум соединений
        keepalive_expiry=60.0,  # TTL соединений
    )

    _http_client = httpx.AsyncClient(
        timeout=timeout_config,
        limits=limits,
        http2=True,  # Поддержка HTTP/2
        follow_redirects=True,  # Следовать редиректам
        verify=True,  # Проверка SSL
    )

    logger.info(f"HTTP клиент инициализирован: {get_backend_base_url()}")
    return _http_client


async def close_http_client():
    """Закрыть глобальный HTTP клиент"""
    global _http_client

    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None
        logger.info("HTTP клиент закрыт")


def get_auth_headers() -> dict[str, str]:
    """Получить заголовки аутентификации"""
    token = get_service_token()
    if not token:
        logger.warning("X_SERVICE_TOKEN не настроен в .env")
        return {}

    return {"X-Service-Token": token, "User-Agent": "SoVAni-Bot/1.0", "Accept": "application/json"}


async def get_json(
    endpoint: str, params: dict | None = None, headers: dict | None = None
) -> dict[str, Any] | None:
    """Выполнить GET запрос к бэкенду

    Args:
        endpoint: Эндпоинт относительно base_url (например, "/live/finance/pnl_v2")
        params: Query параметры
        headers: Дополнительные заголовки

    Returns:
        JSON ответ или None при ошибке

    """
    client = await init_http_client()
    base_url = get_backend_base_url()
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    # Объединяем заголовки
    request_headers = get_auth_headers()
    if headers:
        request_headers.update(headers)

    try:
        logger.debug(f"GET {url} params={params}")
        response = await client.get(url, params=params, headers=request_headers)

        # Логируем результат с деталями
        duration_ms = int(
            (response.elapsed.total_seconds() if hasattr(response, "elapsed") else 0) * 1000
        )
        logger.info(f"HTTP {response.status_code} GET {endpoint} {duration_ms}ms")

        if response.status_code == 200:
            return response.json()
        else:
            # При ошибках >= 400 кидаем исключение
            logger.error(f"GET {url} -> HTTP {response.status_code}: {response.text[:200]}")
            response.raise_for_status()

    except httpx.TimeoutException as e:
        logger.error(f"GET {url} -> Timeout: {e}")
        raise TimeoutError(f"Timeout при GET {endpoint}") from e
    except httpx.HTTPStatusError as e:
        logger.error(f"GET {url} -> HTTP {e.response.status_code}: {e.response.text[:100]}")
        raise e
    except Exception as e:
        logger.error(f"GET {url} -> Error: {e}")
        raise e


async def post_json(
    endpoint: str,
    json_data: dict | None = None,
    params: dict | None = None,
    headers: dict | None = None,
) -> dict[str, Any] | None:
    """Выполнить POST запрос к бэкенду

    Args:
        endpoint: Эндпоинт относительно base_url
        json_data: JSON данные для отправки
        params: Query параметры
        headers: Дополнительные заголовки

    Returns:
        JSON ответ или None при ошибке

    """
    client = await init_http_client()
    base_url = get_backend_base_url()
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    # Объединяем заголовки
    request_headers = get_auth_headers()
    request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)

    try:
        logger.debug(f"POST {url} json={bool(json_data)} params={params}")
        response = await client.post(url, json=json_data, params=params, headers=request_headers)

        # Логируем результат с деталями
        duration_ms = int(
            (response.elapsed.total_seconds() if hasattr(response, "elapsed") else 0) * 1000
        )
        logger.info(f"HTTP {response.status_code} POST {endpoint} {duration_ms}ms")

        if response.status_code == 200:
            return response.json()
        else:
            # При ошибках >= 400 кидаем исключение
            logger.error(f"POST {url} -> HTTP {response.status_code}: {response.text[:200]}")
            response.raise_for_status()

    except httpx.TimeoutException as e:
        logger.error(f"POST {url} -> Timeout: {e}")
        raise TimeoutError(f"Timeout при POST {endpoint}") from e
    except httpx.HTTPStatusError as e:
        logger.error(f"POST {url} -> HTTP {e.response.status_code}: {e.response.text[:100]}")
        raise e
    except Exception as e:
        logger.error(f"POST {url} -> Error: {e}")
        raise e


async def health_check() -> dict[str, Any]:
    """Проверить здоровье бэкенда

    Returns:
        Словарь с результатами проверки

    """
    results = {
        "backend_reachable": False,
        "health_status": None,
        "ops_health_status": None,
        "auth_configured": bool(get_service_token()),
        "base_url": get_backend_base_url(),
    }

    # Проверяем основной health
    health_data = await get_json("/health")
    if health_data:
        results["backend_reachable"] = True
        results["health_status"] = health_data.get("status", "unknown")

    # Проверяем ops health
    ops_data = await get_json("/ops/health")
    if ops_data:
        results["ops_health_status"] = ops_data.get("status", "unknown")

    return results


def format_error_message(error: Exception) -> str:
    """Форматирование ошибки для пользователя"""
    if isinstance(error, TimeoutError):
        return "⏱️ Превышен таймаут подключения"
    elif hasattr(error, "response"):
        status_code = getattr(error.response, "status_code", 0)
        if status_code == 502:
            return "🚧 Backend недоступен (502 Bad Gateway)"
        elif status_code == 503:
            return "⚠️ Backend временно недоступен (503 Service Unavailable)"
        elif status_code == 504:
            return "⏳ Backend перегружен (504 Gateway Timeout)"
        elif status_code == 401:
            return "🔐 Ошибка авторизации (401 Unauthorized)"
        elif status_code == 403:
            return "🚫 Доступ запрещен (403 Forbidden)"
        elif status_code >= 500:
            return f"💥 Ошибка сервера (HTTP {status_code})"
        elif status_code >= 400:
            return f"❌ Ошибка запроса (HTTP {status_code})"

    return f"🔌 Сетевая ошибка: {str(error)[:100]}"
