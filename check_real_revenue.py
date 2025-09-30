#!/usr/bin/env python3
"""
Скрипт для проверки реальной выручки WB и Ozon за период 2025-08-16 → 2025-09-15

Ожидаемые результаты:
- WB: ~72,105 ₽
- Ozon: ~439,318 ₽

Использование:
    python check_real_revenue.py
"""

import asyncio
import logging
import sys
import os
from datetime import date, datetime
from typing import Dict, Any

# Добавляем путь к корневой директории проекта
sys.path.insert(0, os.path.dirname(__file__))

from api_clients.wb.stats_client import WBStatsClient
from api_clients.ozon.sales_client import OzonSalesClient

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('revenue_check.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


async def check_wb_real_data(date_from: date, date_to: date) -> Dict[str, Any]:
    """
    Проверяем реальные данные WB API за указанный период

    Args:
        date_from: Дата начала периода
        date_to: Дата окончания периода

    Returns:
        Словарь с результатами проверки WB
    """
    logger.info("🔍 Начинаем проверку WB API...")

    try:
        client = WBStatsClient()
        sales = await client.sales(date_from, date_to)

        total_revenue = 0
        total_sales_count = 0
        unique_products = set()
        sales_by_date = {}

        for sale in sales:
            # WB API возвращает forPay как итоговую выручку к доплате
            for_pay = float(sale.get('forPay', 0))
            total_revenue += for_pay
            total_sales_count += 1

            # Группируем по товарам
            nm_id = sale.get('nmId')
            if nm_id:
                unique_products.add(nm_id)

            # Группируем по датам
            sale_date = sale.get('date', '')[:10]  # Берем только дату без времени
            if sale_date:
                if sale_date not in sales_by_date:
                    sales_by_date[sale_date] = {'count': 0, 'revenue': 0}
                sales_by_date[sale_date]['count'] += 1
                sales_by_date[sale_date]['revenue'] += for_pay

            # Логируем примеры продаж для проверки
            if total_sales_count <= 5:
                logger.info(f"  Продажа #{total_sales_count}: {sale.get('supplierArticle', 'N/A')} "
                           f"на {for_pay:.2f} ₽ ({sale.get('date', 'N/A')})")

        result = {
            'platform': 'Wildberries',
            'period_from': date_from.strftime('%Y-%m-%d'),
            'period_to': date_to.strftime('%Y-%m-%d'),
            'total_revenue': total_revenue,
            'total_sales_count': total_sales_count,
            'unique_products': len(unique_products),
            'sales_by_date': sales_by_date,
            'raw_data': sales[:10] if len(sales) > 10 else sales,  # Первые 10 записей для примера
            'success': True
        }

        logger.info(f"✅ WB реальная выручка: {total_revenue:,.2f} ₽")
        logger.info(f"📊 WB количество продаж: {total_sales_count}")
        logger.info(f"🎯 WB уникальных товаров: {len(unique_products)}")

        return result

    except Exception as e:
        logger.error(f"❌ Ошибка при проверке WB API: {e}")
        return {
            'platform': 'Wildberries',
            'period_from': date_from.strftime('%Y-%m-%d'),
            'period_to': date_to.strftime('%Y-%m-%d'),
            'total_revenue': 0,
            'error': str(e),
            'success': False
        }


async def check_ozon_real_data(date_from: date, date_to: date) -> Dict[str, Any]:
    """
    Проверяем реальные данные Ozon API за указанный период

    Args:
        date_from: Дата начала периода
        date_to: Дата окончания периода

    Returns:
        Словарь с результатами проверки Ozon
    """
    logger.info("🔍 Начинаем проверку Ozon API...")

    try:
        client = OzonSalesClient()
        revenue_data = await client.get_revenue(date_from, date_to)

        # Выбираем лучшую оценку выручки
        total_revenue = revenue_data.get('best_estimate', 0)

        result = {
            'platform': 'Ozon',
            'period_from': date_from.strftime('%Y-%m-%d'),
            'period_to': date_to.strftime('%Y-%m-%d'),
            'total_revenue': total_revenue,
            'revenue_by_method': revenue_data,
            'success': True
        }

        logger.info(f"✅ Ozon реальная выручка: {total_revenue:,.2f} ₽")
        logger.info("📊 Ozon выручка по методам:")
        for method, amount in revenue_data.items():
            if method != 'best_estimate':
                logger.info(f"   {method}: {amount:,.2f} ₽")

        return result

    except Exception as e:
        logger.error(f"❌ Ошибка при проверке Ozon API: {e}")
        return {
            'platform': 'Ozon',
            'period_from': date_from.strftime('%Y-%m-%d'),
            'period_to': date_to.strftime('%Y-%m-%d'),
            'total_revenue': 0,
            'error': str(e),
            'success': False
        }


def print_summary(wb_result: Dict[str, Any], ozon_result: Dict[str, Any], expected_wb: float, expected_ozon: float):
    """Выводим итоговую сводку"""
    print("\n" + "="*60)
    print("📊 ИТОГОВАЯ СВОДКА ПРОВЕРКИ ВЫРУЧКИ")
    print("="*60)

    period = f"{wb_result.get('period_from', 'N/A')} → {wb_result.get('period_to', 'N/A')}"
    print(f"🗓  Период: {period}")
    print()

    # WB результаты
    print("🟢 WILDBERRIES:")
    if wb_result.get('success'):
        wb_revenue = wb_result.get('total_revenue', 0)
        wb_diff = wb_revenue - expected_wb
        wb_diff_pct = (wb_diff / expected_wb * 100) if expected_wb > 0 else 0

        print(f"   Реальная выручка: {wb_revenue:,.2f} ₽")
        print(f"   Ожидаемая выручка: {expected_wb:,.2f} ₽")
        print(f"   Разница: {wb_diff:+,.2f} ₽ ({wb_diff_pct:+.2f}%)")
        print(f"   Продаж: {wb_result.get('total_sales_count', 0)}")
        print(f"   Товаров: {wb_result.get('unique_products', 0)}")

        if abs(wb_diff_pct) <= 5:
            print("   ✅ Результат соответствует ожиданиям")
        elif abs(wb_diff_pct) <= 15:
            print("   ⚠️  Результат близок к ожиданиям")
        else:
            print("   ❌ Результат значительно отличается")
    else:
        print(f"   ❌ Ошибка: {wb_result.get('error', 'Неизвестная ошибка')}")

    print()

    # Ozon результаты
    print("🟠 OZON:")
    if ozon_result.get('success'):
        ozon_revenue = ozon_result.get('total_revenue', 0)
        ozon_diff = ozon_revenue - expected_ozon
        ozon_diff_pct = (ozon_diff / expected_ozon * 100) if expected_ozon > 0 else 0

        print(f"   Реальная выручка: {ozon_revenue:,.2f} ₽")
        print(f"   Ожидаемая выручка: {expected_ozon:,.2f} ₽")
        print(f"   Разница: {ozon_diff:+,.2f} ₽ ({ozon_diff_pct:+.2f}%)")

        if abs(ozon_diff_pct) <= 5:
            print("   ✅ Результат соответствует ожиданиям")
        elif abs(ozon_diff_pct) <= 15:
            print("   ⚠️  Результат близок к ожиданиям")
        else:
            print("   ❌ Результат значительно отличается")
    else:
        print(f"   ❌ Ошибка: {ozon_result.get('error', 'Неизвестная ошибка')}")

    print()

    # Общие результаты
    total_real = 0
    total_expected = expected_wb + expected_ozon

    if wb_result.get('success'):
        total_real += wb_result.get('total_revenue', 0)
    if ozon_result.get('success'):
        total_real += ozon_result.get('total_revenue', 0)

    if total_real > 0:
        print("📈 ОБЩИЕ ПОКАЗАТЕЛИ:")
        print(f"   Общая реальная выручка: {total_real:,.2f} ₽")
        print(f"   Общая ожидаемая выручка: {total_expected:,.2f} ₽")
        total_diff = total_real - total_expected
        total_diff_pct = (total_diff / total_expected * 100) if total_expected > 0 else 0
        print(f"   Общая разница: {total_diff:+,.2f} ₽ ({total_diff_pct:+.2f}%)")

    print("="*60)


async def main():
    """Основная функция"""
    print("🚀 Запуск проверки реальной выручки WB и Ozon API")
    print("=" * 60)

    # Указанный период
    date_from = date(2025, 8, 16)
    date_to = date(2025, 9, 15)

    # Ожидаемые значения
    expected_wb = 72105.0
    expected_ozon = 439318.0

    print(f"📅 Период проверки: {date_from} → {date_to}")
    print(f"🎯 Ожидаемая выручка WB: {expected_wb:,.2f} ₽")
    print(f"🎯 Ожидаемая выручка Ozon: {expected_ozon:,.2f} ₽")
    print()

    # Параллельная проверка обеих платформ
    wb_task = check_wb_real_data(date_from, date_to)
    ozon_task = check_ozon_real_data(date_from, date_to)

    wb_result, ozon_result = await asyncio.gather(wb_task, ozon_task, return_exceptions=True)

    # Обработка возможных исключений
    if isinstance(wb_result, Exception):
        logger.error(f"WB задача завершилась с ошибкой: {wb_result}")
        wb_result = {
            'platform': 'Wildberries',
            'total_revenue': 0,
            'error': str(wb_result),
            'success': False
        }

    if isinstance(ozon_result, Exception):
        logger.error(f"Ozon задача завершилась с ошибкой: {ozon_result}")
        ozon_result = {
            'platform': 'Ozon',
            'total_revenue': 0,
            'error': str(ozon_result),
            'success': False
        }

    # Выводим итоговую сводку
    print_summary(wb_result, ozon_result, expected_wb, expected_ozon)

    # Сохраняем результаты в файл
    import json
    results = {
        'timestamp': datetime.now().isoformat(),
        'period': {
            'from': date_from.strftime('%Y-%m-%d'),
            'to': date_to.strftime('%Y-%m-%d')
        },
        'expected': {
            'wb': expected_wb,
            'ozon': expected_ozon
        },
        'results': {
            'wb': wb_result,
            'ozon': ozon_result
        }
    }

    os.makedirs('reports', exist_ok=True)
    results_file = f"reports/revenue_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"📄 Детальные результаты сохранены в: {results_file}")

    return wb_result, ozon_result


if __name__ == "__main__":
    try:
        wb_result, ozon_result = asyncio.run(main())

        # Возвращаем код завершения в зависимости от результата
        if wb_result.get('success', False) or ozon_result.get('success', False):
            sys.exit(0)  # Успех хотя бы для одной платформы
        else:
            sys.exit(1)  # Обе платформы не удалось проверить

    except KeyboardInterrupt:
        print("\n⚠️  Проверка прервана пользователем")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        print(f"💥 Критическая ошибка: {e}")
        sys.exit(1)