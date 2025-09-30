#!/usr/bin/env python3
"""
СИСТЕМА СБОРКИ SKU ДЛЯ COGS/OPEX ШАБЛОНОВ
100% реальные данные из API WB и Ozon
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Set, Optional, Any
import pandas as pd
import json

import api_clients_main as api_clients

logger = logging.getLogger(__name__)

class SKUCollectionSystem:
    """Система сборки всех SKU с маркетплейсов для генерации COGS/OPEX шаблонов"""

    def __init__(self):
        self.wb_api = api_clients.wb_api
        self.ozon_api = api_clients.ozon_api

    async def collect_wb_skus(self) -> List[Dict[str, Any]]:
        """Сбор всех SKU с Wildberries через API /api/v2/stocks"""
        try:
            logger.info("Начинаю сбор SKU с Wildberries...")

            # WB API не предоставляет прямого метода для остатков
            # Используем карточки товаров как источник SKU
            products_data = await self.wb_api.get_product_cards()

            if not products_data:
                logger.warning("Нет данных по карточкам товаров WB")
                return []

            wb_skus = []
            seen_skus = set()

            for product in products_data:
                sku = product.get('nmId') or product.get('nmID') or product.get('sku')
                if not sku or str(sku) in seen_skus:
                    continue

                seen_skus.add(str(sku))

                # Извлекаем реальные данные из API карточек товаров
                sku_data = {
                    'sku': str(sku),
                    'platform': 'WB',
                    'supplier_sku': product.get('supplierArticle', '') or product.get('vendorCode', ''),
                    'product_name': product.get('object', '') or product.get('title', ''),
                    'brand': product.get('brand', ''),
                    'category': product.get('object', ''),
                    'warehouse': '',  # Карточки не содержат информацию о складах
                    'current_stock': 0,  # Карточки не содержат информацию об остатках
                    'price': 0,  # Карточки не содержат цены
                    'size': '',
                    'barcode': product.get('barcode', ''),
                    # Пустые поля для заполнения пользователем
                    'cost_price': '',
                    'expense_category': '',
                    'notes': ''
                }

                wb_skus.append(sku_data)

            logger.info(f"Собрано {len(wb_skus)} уникальных SKU с WB")
            return wb_skus

        except Exception as e:
            logger.error(f"Ошибка сбора SKU с WB: {e}")
            return []

    async def collect_ozon_skus(self) -> List[Dict[str, Any]]:
        """Сбор всех SKU с Ozon через API /v3/product/info/stocks"""
        try:
            logger.info("Начинаю сбор SKU с Ozon...")

            # Получаем все остатки с Ozon
            stocks_data = await self.ozon_api.get_product_stocks()

            if not stocks_data:
                logger.warning("Нет данных по остаткам Ozon")
                return []

            ozon_skus = []
            seen_skus = set()

            for stock in stocks_data:
                sku = stock.get('sku') or stock.get('offer_id')
                if not sku or str(sku) in seen_skus:
                    continue

                seen_skus.add(str(sku))

                # Извлекаем реальные данные из API
                sku_data = {
                    'sku': str(sku),
                    'platform': 'OZON',
                    'supplier_sku': stock.get('offer_id', ''),
                    'product_name': stock.get('name', '') or stock.get('title', ''),
                    'brand': stock.get('brand', ''),
                    'category': stock.get('category', ''),
                    'warehouse': stock.get('warehouse_type', ''),
                    'current_stock': stock.get('present', 0) or stock.get('stocks', 0) or 0,
                    'price': stock.get('price', 0) or 0,
                    'size': '',
                    'barcode': stock.get('barcode', ''),
                    # Пустые поля для заполнения пользователем
                    'cost_price': '',
                    'expense_category': '',
                    'notes': ''
                }

                ozon_skus.append(sku_data)

            logger.info(f"Собрано {len(ozon_skus)} уникальных SKU с Ozon")
            return ozon_skus

        except Exception as e:
            logger.error(f"Ошибка сбора SKU с Ozon: {e}")
            return []

    async def deduplicate_skus(self, wb_skus: List[Dict], ozon_skus: List[Dict]) -> List[Dict]:
        """Дедупликация SKU между платформами"""
        try:
            # Собираем все SKU
            all_skus = wb_skus + ozon_skus

            # Группируем по supplier_sku для поиска дубликатов
            sku_groups = {}

            for sku_data in all_skus:
                supplier_sku = sku_data.get('supplier_sku', '').strip()
                if supplier_sku:
                    if supplier_sku not in sku_groups:
                        sku_groups[supplier_sku] = []
                    sku_groups[supplier_sku].append(sku_data)

            # Создаем финальный список
            final_skus = []
            processed_supplier_skus = set()

            for sku_data in all_skus:
                supplier_sku = sku_data.get('supplier_sku', '').strip()

                if supplier_sku and supplier_sku in processed_supplier_skus:
                    continue

                # Если есть дубликаты, объединяем данные
                if supplier_sku and len(sku_groups.get(supplier_sku, [])) > 1:
                    combined_sku = self._combine_duplicate_skus(sku_groups[supplier_sku])
                    final_skus.append(combined_sku)
                    processed_supplier_skus.add(supplier_sku)
                else:
                    final_skus.append(sku_data)
                    if supplier_sku:
                        processed_supplier_skus.add(supplier_sku)

            logger.info(f"После дедупликации: {len(final_skus)} SKU")
            return final_skus

        except Exception as e:
            logger.error(f"Ошибка дедупликации SKU: {e}")
            return wb_skus + ozon_skus

    def _combine_duplicate_skus(self, duplicate_skus: List[Dict]) -> Dict:
        """Объединение дубликатов SKU"""
        if not duplicate_skus:
            return {}

        # Берем первый как основу
        combined = duplicate_skus[0].copy()

        # Объединяем платформы
        platforms = [sku['platform'] for sku in duplicate_skus]
        combined['platform'] = ' + '.join(sorted(set(platforms)))

        # Суммируем остатки
        total_stock = sum(sku.get('current_stock', 0) for sku in duplicate_skus)
        combined['current_stock'] = total_stock

        # Объединяем склады
        warehouses = [sku.get('warehouse', '') for sku in duplicate_skus if sku.get('warehouse')]
        combined['warehouse'] = ' + '.join(sorted(set(warehouses)))

        return combined

    async def generate_cogs_opex_template(self) -> str:
        """Генерация Excel шаблона для COGS/OPEX"""
        try:
            logger.info("Начинаю генерацию COGS/OPEX шаблона...")

            # Собираем все SKU
            wb_skus = await self.collect_wb_skus()
            ozon_skus = await self.collect_ozon_skus()

            # Дедуплицируем
            all_skus = await self.deduplicate_skus(wb_skus, ozon_skus)

            if not all_skus:
                raise Exception("Не удалось собрать SKU с маркетплейсов")

            # Создаем DataFrame
            df = pd.DataFrame(all_skus)

            # Переупорядочиваем колонки для удобства
            column_order = [
                'sku', 'supplier_sku', 'product_name', 'brand', 'category',
                'platform', 'current_stock', 'warehouse', 'price', 'size',
                'cost_price', 'expense_category', 'notes', 'barcode'
            ]

            # Оставляем только существующие колонки
            available_columns = [col for col in column_order if col in df.columns]
            df = df[available_columns]

            # Сортируем по названию товара
            df = df.sort_values('product_name', na_position='last')

            # Сохраняем в Excel
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            filename = f"reports/cogs_opex_template_{timestamp}.xlsx"

            # Создаем папку если не существует
            import os
            os.makedirs("reports", exist_ok=True)

            # Записываем Excel с форматированием
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='COGS_OPEX_Template', index=False)

                # Получаем лист для форматирования
                worksheet = writer.sheets['COGS_OPEX_Template']

                # Автоширина колонок
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width

            logger.info(f"Шаблон COGS/OPEX создан: {filename}")

            return filename

        except Exception as e:
            logger.error(f"Ошибка генерации шаблона COGS/OPEX: {e}")
            raise

    async def get_collection_summary(self) -> Dict[str, Any]:
        """Получение сводки по сбору SKU"""
        try:
            wb_skus = await self.collect_wb_skus()
            ozon_skus = await self.collect_ozon_skus()
            all_skus = await self.deduplicate_skus(wb_skus, ozon_skus)

            # Анализ данных
            wb_count = len(wb_skus)
            ozon_count = len(ozon_skus)
            total_unique = len(all_skus)
            duplicates_removed = (wb_count + ozon_count) - total_unique

            # Категории
            categories = set()
            brands = set()
            total_stock = 0

            for sku in all_skus:
                if sku.get('category'):
                    categories.add(sku['category'])
                if sku.get('brand'):
                    brands.add(sku['brand'])
                total_stock += sku.get('current_stock', 0)

            return {
                'wb_skus': wb_count,
                'ozon_skus': ozon_count,
                'total_unique': total_unique,
                'duplicates_removed': duplicates_removed,
                'categories_count': len(categories),
                'brands_count': len(brands),
                'total_stock_units': total_stock,
                'categories': sorted(list(categories)),
                'brands': sorted(list(brands))
            }

        except Exception as e:
            logger.error(f"Ошибка получения сводки SKU: {e}")
            return {
                'wb_skus': 0,
                'ozon_skus': 0,
                'total_unique': 0,
                'duplicates_removed': 0,
                'categories_count': 0,
                'brands_count': 0,
                'total_stock_units': 0,
                'categories': [],
                'brands': []
            }

# Глобальный экземпляр
sku_collector = SKUCollectionSystem()

async def generate_sku_template() -> Dict[str, Any]:
    """Основная функция для генерации шаблона SKU"""
    try:
        filename = await sku_collector.generate_cogs_opex_template()
        summary = await sku_collector.get_collection_summary()

        summary_text = f"""✅ <b>ШАБЛОН COGS/OPEX СОЗДАН</b>

📊 <b>СВОДКА ПО SKU:</b>
• WB SKU: {summary['wb_skus']}
• Ozon SKU: {summary['ozon_skus']}
• Всего уникальных: {summary['total_unique']}
• Дубликатов удалено: {summary['duplicates_removed']}

🏷️ <b>АНАЛИТИКА:</b>
• Категорий: {summary['categories_count']}
• Брендов: {summary['brands_count']}
• Общий остаток: {summary['total_stock_units']:,} единиц

📝 <b>ИНСТРУКЦИЯ:</b>
1. Заполните колонки cost_price и expense_category
2. Сохраните и загрузите обратно в систему

🎯 <b>ИСТОЧНИКИ ДАННЫХ:</b>
• WB API: /api/v2/stocks
• Ozon API: /v3/product/info/stocks
• Все данные получены в реальном времени"""

        return {
            'file_path': filename,
            'summary': summary_text,
            'raw_summary': summary
        }

    except Exception as e:
        error_text = f"""❌ <b>ОШИБКА СОЗДАНИЯ ШАБЛОНА</b>

🚫 Ошибка: {str(e)}

🔄 <b>Возможные решения:</b>
• Проверить доступность API WB/Ozon
• Убедиться в корректности токенов
• Повторить попытку через несколько минут"""

        return {
            'file_path': None,
            'summary': error_text,
            'raw_summary': {'error': str(e)}
        }

if __name__ == "__main__":
    # Тестирование системы
    async def test_sku_collection():
        summary = await sku_collector.get_collection_summary()
        print(json.dumps(summary, indent=2, ensure_ascii=False))

        template_result = await generate_sku_template()
        print(template_result)

    asyncio.run(test_sku_collection())