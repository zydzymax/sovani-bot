#!/usr/bin/env python3
"""ОТЧЕТ ПО ОГРАНИЧЕНИЯМ OZON API
Итоговый анализ максимальных периодов и рекомендации
"""


def print_ozon_api_limits_report():
    """Выводит итоговый отчет по ограничениям Ozon API"""
    print("📊 ИТОГОВЫЙ ОТЧЕТ: ОГРАНИЧЕНИЯ OZON API")
    print("=" * 70)
    print()

    print("🎯 МАКСИМАЛЬНЫЕ ПЕРИОДЫ ПО ЭНДПОИНТАМ:")
    print()

    # Таблица с ограничениями
    endpoints = [
        {
            "name": "Transaction Totals API",
            "endpoint": "/v3/finance/transaction/totals",
            "max_period": "3+ года",
            "status": "✅ Без ограничений",
            "notes": "Работает с любыми датами, даже с 2022 года",
        },
        {
            "name": "Analytics API",
            "endpoint": "/v1/analytics/data",
            "max_period": "3+ года",
            "status": "✅ Без ограничений",
            "notes": "Но данные есть только с апреля 2025",
        },
        {
            "name": "Transaction List API",
            "endpoint": "/v3/finance/transaction/list",
            "max_period": "30 дней",
            "status": "⚠️ СТРОГИЙ ЛИМИТ",
            "notes": "Ошибка: 'too long period, only one month allowed'",
        },
        {
            "name": "FBO Orders API",
            "endpoint": "/v2/posting/fbo/list",
            "max_period": "2 года",
            "status": "✅ Почти без ограничений",
            "notes": "3+ года возвращает 0 заказов (нет данных)",
        },
        {
            "name": "Realization API v2",
            "endpoint": "/v2/finance/realization",
            "max_period": "По месяцам",
            "status": "⚠️ МЕСЯЧНЫЙ ФОРМАТ",
            "notes": "Только {year, month}, доступно март-август 2025",
        },
    ]

    for endpoint in endpoints:
        print(f"🔹 {endpoint['name']}")
        print(f"   Эндпоинт: {endpoint['endpoint']}")
        print(f"   Максимальный период: {endpoint['max_period']}")
        print(f"   Статус: {endpoint['status']}")
        print(f"   Примечания: {endpoint['notes']}")
        print()

    print("=" * 70)
    print("📋 РЕАЛЬНЫЕ ДАННЫЕ:")
    print()

    print("💰 ФИНАНСОВЫЕ ПОКАЗАТЕЛИ (тест 29.09.2025):")
    print("   • 7 дней:   86,278 ₽")
    print("   • 30 дней:  426,426 ₽")
    print("   • 90 дней:  1,518,212 ₽")
    print("   • 180 дней: 3,105,053 ₽")
    print("   • 365 дней: 6,458,423 ₽")
    print("   • 2 года:   8,194,474 ₽")
    print("   • 3 года:   8,206,331 ₽")
    print()

    print("📅 ДОСТУПНОСТЬ ДАННЫХ:")
    print("   • Realization v2: март 2025 - август 2025 (6 месяцев)")
    print("   • Analytics: апрель 2025 - сентябрь 2025")
    print("   • Transactions: до 3+ лет назад")
    print("   • FBO Orders: до 2 лет назад")
    print()

    print("=" * 70)
    print("⚠️ КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ:")
    print()

    print("1. 🚫 TRANSACTION LIST API:")
    print("   • Максимум 30 дней за запрос")
    print("   • Для больших периодов нужна разбивка по месяцам")
    print()

    print("2. 🗓️ REALIZATION API V2:")
    print("   • Только формат {year, month}")
    print("   • Нельзя указать диапазон дат")
    print("   • Текущий месяц часто недоступен")
    print()

    print("3. 📊 ANALYTICS API:")
    print("   • Принимает любые даты")
    print("   • Но возвращает данные только с апреля 2025")
    print("   • Более ранние периоды дают те же результаты")
    print()

    print("=" * 70)
    print("✅ РЕКОМЕНДАЦИИ ДЛЯ КАЛЕНДАРЯ БОТА:")
    print()

    print("📅 ПРЕДЛАГАЕМЫЕ ОГРАНИЧЕНИЯ:")
    print("   • Минимальная дата: 01.03.2025 (начало доступных данных)")
    print("   • Максимальный период: 6 месяцев")
    print("   • Исключить текущий месяц из выбора")
    print()

    print("🔧 ТЕХНИЧЕСКАЯ РЕАЛИЗАЦИЯ:")
    print("   • Transaction Totals: любые периоды ≤ 6 месяцев")
    print("   • Analytics: любые периоды (но данные ограничены)")
    print("   • Transaction List: автоматическая разбивка по месяцам")
    print("   • Realization v2: запросы по месяцам в цикле")
    print("   • FBO Orders: любые периоды ≤ 6 месяцев")
    print()

    print("🎯 ОПТИМАЛЬНАЯ КОНФИГУРАЦИЯ:")
    print("   • Диапазон дат: 01.03.2025 - конец прошлого месяца")
    print("   • Максимальный период: 180 дней")
    print("   • Рекомендуемый период: до 90 дней")
    print()

    print("=" * 70)
    print("🏁 ЗАКЛЮЧЕНИЕ:")
    print()
    print("Ozon API имеет более гибкие ограничения по периодам, чем WB API:")
    print("• WB: максимум 176 дней")
    print("• Ozon: до 3+ лет (но реальные данные с марта 2025)")
    print()
    print("Рекомендуется установить ограничение в 180 дней для единообразия")
    print("и учета реальной доступности данных.")


if __name__ == "__main__":
    print_ozon_api_limits_report()
