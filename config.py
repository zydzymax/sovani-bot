"""
Конфигурационный файл для SoVAni Bot
Содержит все настройки и константы
"""

import os
from typing import Optional


class Config:
    """Основные настройки бота"""
    
    # Токены API - ТОЛЬКО через переменные окружения (БЕЗОПАСНОСТЬ)
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

    # Wildberries API токены (НОВЫЕ 04.09.2025)
    WB_FEEDBACKS_TOKEN = os.getenv("WB_FEEDBACKS_TOKEN")  # отзывы/вопросы/чат с покупателем
    WB_ADS_TOKEN = os.getenv("WB_ADS_TOKEN")  # продвижение (реклама)
    WB_STATS_TOKEN = os.getenv("WB_STATS_TOKEN")  # статистика и финансы
    WB_SUPPLY_TOKEN = os.getenv("WB_SUPPLY_TOKEN")  # поставки и возвраты
    WB_ANALYTICS_TOKEN = os.getenv("WB_ANALYTICS_TOKEN")  # аналитика и документы
    WB_CONTENT_TOKEN = os.getenv("WB_CONTENT_TOKEN")  # контент, цены и скидки

    # Путь к приватному ключу для JWT подписи WB API
    WB_PRIVATE_KEY_PATH = "/root/sovani_bot/wb_private_key.pem"

    # Ozon API (обновленные ключи)
    OZON_CLIENT_ID = os.getenv("OZON_CLIENT_ID")
    OZON_API_KEY_ADMIN = os.getenv("OZON_API_KEY_ADMIN")

    # ChatGPT API для обработки отзывов
    CHATGPT_API_KEY = os.getenv("CHATGPT_API_KEY", None)  # Нужно установить через переменную окружения

    # Совместимость с legacy кодом
    WB_API_TOKEN = WB_FEEDBACKS_TOKEN  # По умолчанию для основного API
    WB_REPORTS_TOKEN = WB_STATS_TOKEN  # По умолчанию для отчетов
    OZON_API_KEY = OZON_API_KEY_ADMIN  # По умолчанию для основного Ozon API
    
    # Ozon Performance API (для рекламы)
    OZON_PERF_CLIENT_ID = os.getenv("OZON_PERF_CLIENT_ID")
    OZON_PERF_CLIENT_SECRET = os.getenv("OZON_PERF_CLIENT_SECRET")

    # OpenAI API
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4")
    
    # Telegram настройки
    MANAGER_CHAT_ID = int(os.getenv("MANAGER_CHAT_ID", "0"))  # ID чата менеджера для уведомлений
    
    # Бизнес настройки
    COST_PRICE = float(os.getenv("COST_PRICE", "600"))  # Себестоимость товара по умолчанию в рублях
    
    # Настройки проверки отзывов
    REVIEW_CHECK_HOUR = int(os.getenv("REVIEW_CHECK_HOUR", "6"))  # Час проверки отзывов (0-23)
    REVIEW_CHECK_MINUTE = int(os.getenv("REVIEW_CHECK_MINUTE", "0"))  # Минута проверки отзывов
    
    # Настройки Wildberries остатков
    WB_MIN_STOCK_DAYS = int(os.getenv("WB_MIN_STOCK_DAYS", "14"))  # Минимальное покрытие для WB в днях
    
    # Настройки Ozon остатков  
    OZON_MIN_STOCK_DAYS = int(os.getenv("OZON_MIN_STOCK_DAYS", "56"))  # Минимальное покрытие для Ozon в днях
    
    # Пути к файлам
    REPORTS_DIR = os.getenv("REPORTS_DIR", "reports")
    LOG_FILE = os.getenv("LOG_FILE", "sovani_bot.log")
    DB_FILE = os.getenv("DB_FILE", "sovani_bot.db")
    
    # Настройки логирования
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Настройки планировщика
    TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
    
    @classmethod
    def validate_config(cls) -> bool:
        """Валидация обязательных настроек"""
        required_fields = [
            ('TELEGRAM_TOKEN', cls.TELEGRAM_TOKEN),
            ('WB_FEEDBACKS_TOKEN', cls.WB_FEEDBACKS_TOKEN),
            ('OPENAI_API_KEY', cls.OPENAI_API_KEY),
            ('MANAGER_CHAT_ID', cls.MANAGER_CHAT_ID)
        ]
        
        missing_fields = []
        for field_name, field_value in required_fields:
            if not field_value or (field_name == 'MANAGER_CHAT_ID' and field_value == 0):
                missing_fields.append(field_name)
        
        if missing_fields:
            print(f"❌ Отсутствуют обязательные настройки: {', '.join(missing_fields)}")
            return False
        
        print("✅ Конфигурация валидна")
        return True
    
    @classmethod
    def print_config_status(cls):
        """Вывод статуса конфигурации"""
        print("🔧 Статус конфигурации SoVAni Bot:")
        print(f"  Telegram Token: {'✅ Настроен' if cls.TELEGRAM_TOKEN else '❌ Не настроен'}")
        print(f"  WB Feedbacks Token: {'✅ Настроен' if cls.WB_FEEDBACKS_TOKEN else '❌ Не настроен'}")
        print(f"  WB Stats Token: {'✅ Настроен' if cls.WB_STATS_TOKEN else '❌ Не настроен'}")
        print(f"  WB Ads Token: {'✅ Настроен' if cls.WB_ADS_TOKEN else '❌ Не настроен'}")
        print(f"  WB Supply Token: {'✅ Настроен' if cls.WB_SUPPLY_TOKEN else '❌ Не настроен'}")
        print(f"  WB Analytics Token: {'✅ Настроен' if cls.WB_ANALYTICS_TOKEN else '❌ Не настроен'}")
        print(f"  WB Content Token: {'✅ Настроен' if cls.WB_CONTENT_TOKEN else '❌ Не настроен'}")
        print(f"  Ozon API: {'✅ Настроен' if cls.OZON_CLIENT_ID and cls.OZON_API_KEY_ADMIN else '❌ Не настроен'}")
        print(f"  Ozon Performance: {'✅ Настроен' if cls.OZON_PERF_CLIENT_ID and cls.OZON_PERF_CLIENT_SECRET else '❌ Не настроен'}")
        print(f"  OpenAI API: {'✅ Настроен' if cls.OPENAI_API_KEY else '❌ Не настроен'}")
        print(f"  Manager Chat ID: {'✅ Настроен' if cls.MANAGER_CHAT_ID != 0 else '❌ Не настроен'}")
        print(f"  Себестоимость: {cls.COST_PRICE} ₽")
        print(f"  Проверка отзывов: {cls.REVIEW_CHECK_HOUR:02d}:{cls.REVIEW_CHECK_MINUTE:02d}")


# Дополнительные константы
class APIUrls:
    """URL-адреса API различных сервисов"""
    
    # Wildberries API URLs
    WB_BASE_URL = "https://suppliers-api.wildberries.ru"
    WB_FEEDBACKS_URL = f"{WB_BASE_URL}/api/v1/feedbacks"
    WB_QUESTIONS_URL = f"{WB_BASE_URL}/api/v1/questions"
    WB_FEEDBACK_ANSWER_URL = f"{WB_BASE_URL}/api/v1/feedbacks/answer"
    
    # Wildberries Statistics API (для отчетов)
    WB_STATS_BASE_URL = "https://statistics-api.wildberries.ru"
    WB_SALES_REPORT_URL = f"{WB_STATS_BASE_URL}/api/v5/supplier/reportDetailByPeriod"
    WB_STOCKS_REPORT_URL = f"{WB_STATS_BASE_URL}/api/v1/supplier/stocks"
    
    # Ozon API URLs
    OZON_BASE_URL = "https://api-seller.ozon.ru"
    OZON_REPORTS_URL = f"{OZON_BASE_URL}/v1/report"
    
    # OpenAI API
    OPENAI_BASE_URL = "https://api.openai.com/v1"


class Messages:
    """Шаблоны сообщений бота"""
    
    STARTUP_MESSAGE = """🤖 <b>SoVAni Bot запущен!</b>

✅ Автоматическая проверка отзывов включена (каждый день в {hour:02d}:{minute:02d})
✅ Обработка команд активна
✅ Анализ отчетов доступен

Используйте /help для получения справки."""
    
    ERROR_NO_REPORTS = """⚠️ Файлы отчетов не найдены в папке {reports_dir}/

Убедитесь, что загружены следующие файлы:
• wb_sales.xlsx - отчет продаж Wildberries
• wb_stock.xlsx - отчет остатков Wildberries  
• ozon_sales.xlsx - отчет продаж Ozon
• ozon_stock.xlsx - отчет остатков Ozon"""
    
    API_ERROR = """⚠️ Ошибка при обращении к API {platform}: {error}

Проверьте настройки токенов или попробуйте позже."""
    
    REVIEW_NOTIFICATION = """📝 <b>Новый отзыв на товар {sku}</b> – {stars}{media_info}:
"{review_text}"

<b>Предложенный ответ:</b> {answer}"""
    
    QUESTION_NOTIFICATION = """❓ <b>Вопрос от покупателя по {sku}:</b>
"{question_text}"

<b>Предложенный ответ:</b> {answer}"""


# Валидация конфигурации при импорте модуля
if __name__ == "__main__":
    Config.print_config_status()
    Config.validate_config()