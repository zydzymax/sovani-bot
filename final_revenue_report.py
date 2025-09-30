#!/usr/bin/env python3
"""
Финальный отчет по проверке выручки WB и Ozon за период 2025-08-16 → 2025-09-15
"""

import asyncio
import json
import sys
import os
from datetime import date, datetime
from typing import Dict, Any

# Добавляем путь к корневой директории проекта
sys.path.insert(0, os.path.dirname(__file__))

async def main():
    """Создаем финальный отчет"""
    print("📊 ФИНАЛЬНЫЙ ОТЧЕТ ПО ПРОВЕРКЕ ВЫРУЧКИ")
    print("="*60)

    # Параметры проверки
    period_from = "2025-08-16"
    period_to = "2025-09-15"
    expected_wb = 72105.0
    expected_ozon = 439318.0

    print(f"🗓  Период: {period_from} → {period_to}")
    print(f"🎯 Ожидаемая выручка WB: {expected_wb:,.2f} ₽")
    print(f"🎯 Ожидаемая выручка Ozon: {expected_ozon:,.2f} ₽")
    print(f"🎯 Общая ожидаемая выручка: {expected_wb + expected_ozon:,.2f} ₽")
    print()

    # Результаты проверки
    results = {}

    # === WILDBERRIES API ===
    print("🟢 WILDBERRIES API РЕЗУЛЬТАТЫ:")
    print("-" * 30)

    try:
        from api_clients.wb.stats_client import WBStatsClient
        wb_client = WBStatsClient()
        wb_sales = await wb_client.sales(date(2025, 8, 16), date(2025, 9, 15))

        wb_revenue = sum(sale.get('forPay', 0) for sale in wb_sales)
        wb_sales_count = len(wb_sales)

        results['wb'] = {
            'status': 'success',
            'revenue': wb_revenue,
            'sales_count': wb_sales_count,
            'api_working': True
        }

        print(f"✅ API подключение: Успешно")
        print(f"💰 Реальная выручка: {wb_revenue:,.2f} ₽")
        print(f"📦 Количество продаж: {wb_sales_count}")

        # Анализ разницы
        wb_diff = wb_revenue - expected_wb
        wb_diff_pct = (wb_diff / expected_wb * 100) if expected_wb > 0 else 0

        print(f"📊 Разница с ожиданием: {wb_diff:+,.2f} ₽ ({wb_diff_pct:+.2f}%)")

        if abs(wb_diff_pct) <= 5:
            print("🎯 Результат: ✅ Соответствует ожиданиям")
        elif abs(wb_diff_pct) <= 15:
            print("🎯 Результат: ⚠️ Близко к ожиданиям")
        else:
            print("🎯 Результат: ❌ Значительно отличается")

    except Exception as e:
        print(f"❌ API подключение: Ошибка - {e}")
        print("⚠️  WB API токен истек или неверный")

        results['wb'] = {
            'status': 'error',
            'error': str(e),
            'api_working': False,
            'revenue': 0
        }

    print()

    # === OZON API ===
    print("🟠 OZON API РЕЗУЛЬТАТЫ:")
    print("-" * 30)

    try:
        from api_clients.ozon.sales_client import OzonSalesClient
        ozon_client = OzonSalesClient()

        # Используем Analytics API (единственный рабочий метод)
        analytics_data = await ozon_client.get_analytics_data(
            date(2025, 8, 16),
            date(2025, 9, 15),
            ['revenue']
        )

        ozon_revenue = 0.0
        data_rows = analytics_data.get('result', {}).get('data', [])

        for row in data_rows:
            metrics = row.get('metrics', [])
            if metrics:
                revenue = float(metrics[0] or 0)
                ozon_revenue += revenue

        results['ozon'] = {
            'status': 'success',
            'revenue': ozon_revenue,
            'records_count': len(data_rows),
            'api_working': True,
            'method': 'analytics'
        }

        print(f"✅ API подключение: Успешно")
        print(f"💰 Реальная выручка: {ozon_revenue:,.2f} ₽")
        print(f"📊 Записей аналитики: {len(data_rows)}")
        print(f"🔧 Метод получения: Analytics API")

        # Анализ разницы
        ozon_diff = ozon_revenue - expected_ozon
        ozon_diff_pct = (ozon_diff / expected_ozon * 100) if expected_ozon > 0 else 0

        print(f"📊 Разница с ожиданием: {ozon_diff:+,.2f} ₽ ({ozon_diff_pct:+.2f}%)")

        if abs(ozon_diff_pct) <= 5:
            print("🎯 Результат: ✅ Соответствует ожиданиям")
        elif abs(ozon_diff_pct) <= 15:
            print("🎯 Результат: ⚠️ Близко к ожиданиям")
        else:
            print("🎯 Результат: ❌ Значительно отличается")

    except Exception as e:
        print(f"❌ API подключение: Ошибка - {e}")

        results['ozon'] = {
            'status': 'error',
            'error': str(e),
            'api_working': False,
            'revenue': 0
        }

    print()

    # === ОБЩИЕ ВЫВОДЫ ===
    print("📈 ОБЩИЕ ВЫВОДЫ:")
    print("="*60)

    total_real_revenue = results.get('wb', {}).get('revenue', 0) + results.get('ozon', {}).get('revenue', 0)
    total_expected_revenue = expected_wb + expected_ozon

    print(f"💰 Общая реальная выручка: {total_real_revenue:,.2f} ₽")
    print(f"🎯 Общая ожидаемая выручка: {total_expected_revenue:,.2f} ₽")

    if total_real_revenue > 0:
        total_diff = total_real_revenue - total_expected_revenue
        total_diff_pct = (total_diff / total_expected_revenue * 100) if total_expected_revenue > 0 else 0
        print(f"📊 Общая разница: {total_diff:+,.2f} ₽ ({total_diff_pct:+.2f}%)")

    print("\n🔍 ДЕТАЛЬНЫЙ АНАЛИЗ:")
    print("-" * 30)

    if results.get('wb', {}).get('api_working'):
        print("✅ WB API: Работает корректно")
    else:
        print("❌ WB API: Требует обновления токена")

    if results.get('ozon', {}).get('api_working'):
        print("✅ Ozon API: Работает корректно")
        ozon_revenue = results.get('ozon', {}).get('revenue', 0)
        if ozon_revenue > expected_ozon:
            print(f"💡 Ozon показывает выручку выше ожидаемой на {ozon_revenue - expected_ozon:+,.2f} ₽")
            print("   Это может означать:")
            print("   • Рост продаж")
            print("   • Включение дополнительных периодов")
            print("   • Разные методы подсчета")
    else:
        print("❌ Ozon API: Проблемы с подключением")

    # === РЕКОМЕНДАЦИИ ===
    print("\n💡 РЕКОМЕНДАЦИИ:")
    print("-" * 30)

    if not results.get('wb', {}).get('api_working'):
        print("🔧 WB: Обновить API токен для статистики")

    if results.get('ozon', {}).get('api_working'):
        ozon_revenue = results.get('ozon', {}).get('revenue', 0)
        if ozon_revenue != expected_ozon:
            print("🔍 Ozon: Проанализировать причины расхождения в выручке")

    print("📊 Общее: Рассмотреть разные методы подсчета выручки")

    # === СОХРАНЕНИЕ РЕЗУЛЬТАТОВ ===
    final_report = {
        'timestamp': datetime.now().isoformat(),
        'period': {
            'from': period_from,
            'to': period_to
        },
        'expected': {
            'wb': expected_wb,
            'ozon': expected_ozon,
            'total': expected_wb + expected_ozon
        },
        'actual': {
            'wb': results.get('wb', {}).get('revenue', 0),
            'ozon': results.get('ozon', {}).get('revenue', 0),
            'total': total_real_revenue
        },
        'api_status': {
            'wb': results.get('wb', {}).get('api_working', False),
            'ozon': results.get('ozon', {}).get('api_working', False)
        },
        'details': results
    }

    os.makedirs('reports', exist_ok=True)
    report_file = f"reports/final_revenue_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(final_report, f, ensure_ascii=False, indent=2)

    print(f"\n📄 Полный отчет сохранен: {report_file}")
    print("="*60)

    return final_report

if __name__ == "__main__":
    try:
        report = asyncio.run(main())
        print("\n✅ Проверка выручки завершена успешно!")

    except KeyboardInterrupt:
        print("\n⚠️  Проверка прервана пользователем")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        sys.exit(1)