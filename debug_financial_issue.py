#!/usr/bin/env python3
"""
Отладочный скрипт для выявления источника неправильных финансовых данных
"""

import asyncio
import logging
from datetime import datetime, timedelta

from real_data_reports import RealDataFinancialReports

# Настройка логирования для видимости всех деталей
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def debug_financial_data():
    """Отладка финансовых данных"""

    reports = RealDataFinancialReports()

    # Тестируем небольшой период - последние 5 дней
    today = datetime.now().date()
    test_from = (today - timedelta(days=5)).strftime('%Y-%m-%d')
    test_to = today.strftime('%Y-%m-%d')

    print(f"=== ОТЛАДКА ФИНАНСОВЫХ ДАННЫХ ===")
    print(f"Период: {test_from} - {test_to}")
    print("="*50)

    try:
        # Получаем WB данные
        print("\n1. Тестируем WB данные...")
        wb_data = await reports.get_real_wb_data(test_from, test_to)
        print(f"WB результат: revenue={wb_data.get('revenue', 0):,.0f}, units={wb_data.get('units', 0)}")

        # Получаем Ozon данные
        print("\n2. Тестируем Ozon данные...")
        ozon_data = await reports.get_real_ozon_sales(test_from, test_to)
        print(f"Ozon результат: revenue={ozon_data.get('revenue', 0):,.0f}, units={ozon_data.get('units', 0)}")

        # Полный отчет
        print("\n3. Генерируем полный отчет...")
        full_report = await reports.calculate_real_pnl(test_from, test_to)

        print(f"\n=== ИТОГОВЫЙ ОТЧЕТ ===")
        print(f"Общая выручка: {full_report.get('revenue', 0):,.0f} ₽")
        print(f"Общие единицы: {full_report.get('units', 0)}")

        # Данные по платформам
        wb_platform = full_report.get('wb_breakdown', {})
        ozon_platform = full_report.get('ozon_breakdown', {})

        print(f"\nWB платформа:")
        print(f"  Выручка: {wb_platform.get('orders_revenue', 0):,.0f} ₽")
        print(f"  Единицы: {wb_platform.get('orders_units', 0)}")

        print(f"\nOzon платформа:")
        print(f"  Выручка: {ozon_platform.get('orders_revenue', 0):,.0f} ₽")
        print(f"  Единицы: {ozon_platform.get('orders_units', 0)}")

    except Exception as e:
        print(f"ОШИБКА: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_financial_data())