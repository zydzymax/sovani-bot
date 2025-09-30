"""
Генератор Excel шаблонов для загрузки себестоимости и расходов
"""

import pandas as pd
import asyncio
from datetime import datetime
from typing import List, Dict, Any
import logging
import os
from real_data_reports import RealDataFinancialReports

logger = logging.getLogger(__name__)


class CostTemplateGenerator:
    """Генератор шаблонов для загрузки данных о себестоимости и расходах"""

    def __init__(self):
        self.reports = RealDataFinancialReports()

    async def generate_cost_template(self) -> str:
        """
        Генерация Excel шаблона с всеми SKU для загрузки себестоимости и расходов

        Returns:
            str: Путь к созданному файлу шаблона
        """
        try:
            # Получаем все SKU из остатков
            wb_stocks = await self.reports._get_wb_stocks()
            ozon_stocks = await self.reports._get_ozon_stocks()

            # Создаем DataFrame с SKU
            sku_data = []
            wb_grouped = {}
            ozon_grouped = {}

            # Группируем WB по баркоду (уникальный идентификатор товара)
            for item in wb_stocks:
                barcode = item.get('barcode', '')
                if not barcode:
                    continue

                if barcode not in wb_grouped:
                    wb_grouped[barcode] = {
                        'supplierArticle': item.get('supplierArticle', ''),
                        'subject': item.get('subject', ''),
                        'category': item.get('category', ''),
                        'brand': item.get('brand', ''),
                        'total_quantity': 0,
                        'sizes': set(),
                        'barcode': barcode
                    }

                wb_grouped[barcode]['total_quantity'] += item.get('quantity', 0)
                if item.get('techSize'):
                    wb_grouped[barcode]['sizes'].add(item.get('techSize'))

            # Группируем Ozon по product_id (аналог баркода WB)
            for item in ozon_stocks:
                product_id = item.get('product_id')
                offer_id = item.get('offer_id', '')
                if not product_id:
                    continue

                if product_id not in ozon_grouped:
                    ozon_grouped[product_id] = {
                        'product_id': product_id,
                        'offer_id': offer_id,
                        'total_stock': 0,
                        'sizes': set(),
                        'base_article': offer_id.split(' ')[0] if ' ' in offer_id else offer_id
                    }

                ozon_grouped[product_id]['total_stock'] += item.get('stock', 0)
                # Извлекаем размер из offer_id
                if ' ' in offer_id:
                    size = offer_id.split(' ')[-1]
                    ozon_grouped[product_id]['sizes'].add(size)

            # Добавляем сгруппированные WB SKU
            for barcode, data in wb_grouped.items():
                sizes_str = ', '.join(sorted(data['sizes'])) if data['sizes'] else ''
                sku_data.append({
                    'Платформа': 'WB',
                    'SKU/Артикул': data['supplierArticle'],
                    'Баркод': barcode,
                    'Название': data['subject'],
                    'Доступные размеры': sizes_str,
                    'Категория': data['category'],
                    'Бренд': data['brand'],
                    'Общий остаток': data['total_quantity'],
                    'Себестоимость за шт (₽)': '',
                    'Примечание': ''
                })

            # Добавляем сгруппированные Ozon SKU
            for product_id, data in ozon_grouped.items():
                sizes_str = ', '.join(sorted(data['sizes'])) if data['sizes'] else ''
                sku_data.append({
                    'Платформа': 'Ozon',
                    'SKU/Артикул': data['base_article'],
                    'Product ID': product_id,
                    'Название': data['offer_id'],
                    'Доступные размеры': sizes_str,
                    'Категория': '',
                    'Бренд': 'SoVAni',
                    'Общий остаток': data['total_stock'],
                    'Себестоимость за шт (₽)': '',
                    'Примечание': ''
                })

            # Создаем Excel файл с несколькими листами
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'cost_template_{timestamp}.xlsx'
            filepath = f'/root/sovani_bot/templates/{filename}'

            # Создаем директорию если не существует
            os.makedirs('/root/sovani_bot/templates', exist_ok=True)

            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # Лист 1: SKU и себестоимость
                df_sku = pd.DataFrame(sku_data)
                df_sku.to_excel(writer, sheet_name='Себестоимость SKU', index=False)

                # Лист 2: Переменные расходы
                variable_costs = [
                    {'Тип расхода': 'Упаковка', 'Стоимость за единицу (₽)': '', 'Описание': 'Стоимость упаковки одного товара'},
                    {'Тип расхода': 'Логистика внутри города', 'Стоимость за единицу (₽)': '', 'Описание': 'Доставка до склада маркетплейса'},
                    {'Тип расхода': 'Брак/возвраты %', 'Стоимость за единицу (₽)': '', 'Описание': 'Процент брака от общих продаж'},
                    {'Тип расхода': 'Комиссия эквайринга %', 'Стоимость за единицу (₽)': '', 'Описание': 'Комиссия за платежи'},
                    {'Тип расхода': 'Переработка возвратов', 'Стоимость за единицу (₽)': '', 'Описание': 'Стоимость обработки возвращенных товаров'},
                ]

                df_variable = pd.DataFrame(variable_costs)
                df_variable.to_excel(writer, sheet_name='Переменные расходы', index=False)

                # Лист 3: Постоянные расходы (месячные)
                fixed_costs = [
                    {'Тип расхода': 'Аренда склада', 'Сумма в месяц (₽)': '', 'Описание': 'Ежемесячная аренда складского помещения'},
                    {'Тип расхода': 'Зарплата персонала', 'Сумма в месяц (₽)': '', 'Описание': 'Фонд оплаты труда'},
                    {'Тип расхода': 'Коммунальные услуги', 'Сумма в месяц (₽)': '', 'Описание': 'Электричество, вода, отопление'},
                    {'Тип расхода': 'Интернет и связь', 'Сумма в месяц (₽)': '', 'Описание': 'Интернет, телефония'},
                    {'Тип расхода': 'Программное обеспечение', 'Сумма в месяц (₽)': '', 'Описание': 'Подписки на сервисы, CRM'},
                    {'Тип расхода': 'Бухгалтерские услуги', 'Сумма в месяц (₽)': '', 'Описание': 'Ведение бухгалтерии'},
                    {'Тип расхода': 'Маркетинг и реклама', 'Сумма в месяц (₽)': '', 'Описание': 'Контекстная реклама, SMM'},
                    {'Тип расхода': 'Банковские услуги', 'Сумма в месяц (₽)': '', 'Описание': 'Обслуживание счетов'},
                    {'Тип расхода': 'Страхование', 'Сумма в месяц (₽)': '', 'Описание': 'Страхование товаров и ответственности'},
                    {'Тип расхода': 'Прочие административные', 'Сумма в месяц (₽)': '', 'Описание': 'Канцелярия, хозтовары'},
                ]

                df_fixed = pd.DataFrame(fixed_costs)
                df_fixed.to_excel(writer, sheet_name='Постоянные расходы', index=False)

                # Лист 4: Инструкция
                instructions = [
                    {'Инструкция по заполнению': 'Лист "Себестоимость SKU"'},
                    {'Инструкция по заполнению': '• Заполните колонку "Себестоимость за шт (₽)" для каждого SKU'},
                    {'Инструкция по заполнению': '• Себестоимость = стоимость производства + материалы + работа'},
                    {'Инструкция по заполнению': '• НЕ включайте в себестоимость маркетинг и логистику'},
                    {'Инструкция по заполнению': ''},
                    {'Инструкция по заполнению': 'Лист "Переменные расходы"'},
                    {'Инструкция по заполнению': '• Укажите расходы, которые зависят от объема продаж'},
                    {'Инструкция по заполнению': '• Стоимость указывайте за единицу товара или в процентах'},
                    {'Инструкция по заполнению': ''},
                    {'Инструкция по заполнению': 'Лист "Постоянные расходы"'},
                    {'Инструкция по заполнению': '• Укажите ежемесячные расходы, не зависящие от продаж'},
                    {'Инструкция по заполнению': '• Эти расходы будут распределены на все проданные товары'},
                    {'Инструкция по заполнению': ''},
                    {'Инструкция по заполнению': 'После заполнения отправьте файл обратно в бот'},
                ]

                df_instructions = pd.DataFrame(instructions)
                df_instructions.to_excel(writer, sheet_name='Инструкция', index=False)

            logger.info(f"Создан шаблон себестоимости: {filepath}")
            logger.info(f"SKU WB: {len([x for x in sku_data if x['Платформа'] == 'WB'])}")
            logger.info(f"SKU Ozon: {len([x for x in sku_data if x['Платформа'] == 'Ozon'])}")

            return filepath

        except Exception as e:
            logger.error(f"Ошибка создания шаблона себестоимости: {e}")
            raise

    async def process_filled_template(self, file_path: str) -> Dict[str, Any]:
        """
        Обработка заполненного пользователем шаблона

        Args:
            file_path: Путь к заполненному Excel файлу

        Returns:
            Dict с обработанными данными
        """
        try:
            # Читаем все листы
            excel_data = pd.read_excel(file_path, sheet_name=None)

            result = {
                'sku_costs': {},
                'variable_costs': {},
                'fixed_costs': {},
                'summary': {}
            }

            # Обрабатываем себестоимость SKU
            if 'Себестоимость SKU' in excel_data:
                sku_df = excel_data['Себестоимость SKU']
                for _, row in sku_df.iterrows():
                    sku = row.get('SKU/Артикул', '')
                    platform = row.get('Платформа', '')
                    cost = row.get('Себестоимость за шт (₽)', '')

                    if sku and cost and str(cost).replace('.', '').replace(',', '').isdigit():
                        result['sku_costs'][f"{platform}_{sku}"] = {
                            'platform': platform,
                            'sku': sku,
                            'name': row.get('Название', ''),
                            'cost_per_unit': float(str(cost).replace(',', '.')),
                            'current_stock': row.get('Текущий остаток', 0),
                            'note': row.get('Примечание', '')
                        }

            # Обрабатываем переменные расходы
            if 'Переменные расходы' in excel_data:
                var_df = excel_data['Переменные расходы']
                for _, row in var_df.iterrows():
                    expense_type = row.get('Тип расхода', '')
                    cost = row.get('Стоимость за единицу (₽)', '')

                    if expense_type and cost and str(cost).replace('.', '').replace(',', '').isdigit():
                        result['variable_costs'][expense_type] = {
                            'cost_per_unit': float(str(cost).replace(',', '.')),
                            'description': row.get('Описание', ''),
                            'is_percentage': '%' in expense_type
                        }

            # Обрабатываем постоянные расходы
            if 'Постоянные расходы' in excel_data:
                fixed_df = excel_data['Постоянные расходы']
                total_fixed_monthly = 0

                for _, row in fixed_df.iterrows():
                    expense_type = row.get('Тип расхода', '')
                    cost = row.get('Сумма в месяц (₽)', '')

                    if expense_type and cost and str(cost).replace('.', '').replace(',', '').isdigit():
                        monthly_cost = float(str(cost).replace(',', '.'))
                        result['fixed_costs'][expense_type] = {
                            'monthly_cost': monthly_cost,
                            'description': row.get('Описание', '')
                        }
                        total_fixed_monthly += monthly_cost

            # Подводим итоги
            result['summary'] = {
                'total_sku_with_costs': len(result['sku_costs']),
                'total_variable_costs': len(result['variable_costs']),
                'total_fixed_costs': len(result['fixed_costs']),
                'total_fixed_monthly': total_fixed_monthly,
                'processed_at': datetime.now().isoformat()
            }

            logger.info(f"Обработан шаблон: {result['summary']}")
            return result

        except Exception as e:
            logger.error(f"Ошибка обработки шаблона: {e}")
            raise

    async def save_cost_data(self, cost_data: Dict[str, Any]) -> str:
        """
        Сохранение данных о себестоимости в базу данных или файл

        Args:
            cost_data: Обработанные данные о себестоимости

        Returns:
            str: Путь к файлу с сохраненными данными
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'cost_data_{timestamp}.json'
            filepath = f'/root/sovani_bot/cost_data/{filename}'

            # Создаем директорию если не существует
            os.makedirs('/root/sovani_bot/cost_data', exist_ok=True)

            # Сохраняем в JSON
            import json
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(cost_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Данные о себестоимости сохранены: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Ошибка сохранения данных о себестоимости: {e}")
            raise

    def calculate_unit_profitability(self,
                                   sales_data: Dict[str, Any],
                                   cost_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Расчет прибыльности по каждому SKU с учетом себестоимости и расходов

        Args:
            sales_data: Данные о продажах
            cost_data: Данные о себестоимости и расходах

        Returns:
            Dict с расчетами прибыльности по SKU
        """
        try:
            profitability = {}

            # Получаем общую сумму постоянных расходов
            total_fixed_monthly = sum(
                item['monthly_cost']
                for item in cost_data.get('fixed_costs', {}).values()
            )

            # Обрабатываем каждый SKU
            for sku_key, sku_cost in cost_data.get('sku_costs', {}).items():
                sku = sku_cost['sku']
                platform = sku_cost['platform']

                # Находим данные о продажах для этого SKU
                # (здесь нужно будет интегрироваться с реальными данными продаж)

                profitability[sku_key] = {
                    'sku': sku,
                    'platform': platform,
                    'cost_per_unit': sku_cost['cost_per_unit'],
                    'revenue_per_unit': 0,  # Заполнить из данных продаж
                    'variable_costs_per_unit': 0,  # Рассчитать из переменных расходов
                    'fixed_costs_allocated': 0,  # Распределить постоянные расходы
                    'profit_per_unit': 0,
                    'profit_margin_percent': 0
                }

            return profitability

        except Exception as e:
            logger.error(f"Ошибка расчета прибыльности: {e}")
            raise


async def test_template_generator():
    """Тестирование генератора шаблонов"""
    generator = CostTemplateGenerator()

    try:
        # Тестируем генерацию шаблона
        template_path = await generator.generate_cost_template()
        print(f"Шаблон создан: {template_path}")

        # Тестируем обработку (с пустым файлом)
        # processed_data = await generator.process_filled_template(template_path)
        # print(f"Данные обработаны: {processed_data['summary']}")

    except Exception as e:
        print(f"Ошибка тестирования: {e}")


if __name__ == "__main__":
    asyncio.run(test_template_generator())