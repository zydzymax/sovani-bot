#!/usr/bin/env python3
"""
Обработчик данных о себестоимости и интеграция с финансовыми расчетами
Связывает данные из шаблонов себестоимости с реальными продажами
"""

import json
import pandas as pd
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import os
import glob

from real_data_reports import RealDataFinancialReports
from expenses import ExpenseManager, ExpenseType, CalculationType

logger = logging.getLogger(__name__)


class CostDataProcessor:
    """Процессор данных о себестоимости и расходах"""

    def __init__(self):
        self.reports = RealDataFinancialReports()
        self.expense_manager = ExpenseManager()

        # Создаем директории
        os.makedirs('/root/sovani_bot/cost_data', exist_ok=True)
        os.makedirs('/root/sovani_bot/processed_costs', exist_ok=True)

    async def process_cost_template_file(self, template_file_path: str) -> Dict[str, Any]:
        """
        Обработка заполненного пользователем шаблона себестоимости

        Args:
            template_file_path: Путь к Excel файлу с заполненными данными

        Returns:
            Dict с обработанными и валидированными данными
        """
        try:
            logger.info(f"Обработка шаблона себестоимости: {template_file_path}")

            # Читаем все листы Excel файла
            excel_data = pd.read_excel(template_file_path, sheet_name=None)

            result = {
                'sku_costs': {},
                'variable_costs': {},
                'fixed_costs': {},
                'validation_errors': [],
                'statistics': {},
                'processed_at': datetime.now().isoformat()
            }

            # Обрабатываем лист "Себестоимость SKU"
            if 'Себестоимость SKU' in excel_data:
                result['sku_costs'] = self._process_sku_costs(excel_data['Себестоимость SKU'], result['validation_errors'])

            # Обрабатываем лист "Переменные расходы"
            if 'Переменные расходы' in excel_data:
                result['variable_costs'] = self._process_variable_costs(excel_data['Переменные расходы'], result['validation_errors'])

            # Обрабатываем лист "Постоянные расходы"
            if 'Постоянные расходы' in excel_data:
                result['fixed_costs'] = self._process_fixed_costs(excel_data['Постоянные расходы'], result['validation_errors'])

            # Генерируем статистику
            result['statistics'] = self._generate_cost_statistics(result)

            # Сохраняем обработанные данные
            processed_file_path = await self._save_processed_cost_data(result)
            result['processed_file_path'] = processed_file_path

            # Интегрируем с системой расходов
            await self._integrate_with_expense_manager(result)

            logger.info(f"Шаблон обработан: {len(result['sku_costs'])} SKU, {len(result['validation_errors'])} ошибок")
            return result

        except Exception as e:
            logger.error(f"Ошибка обработки шаблона себестоимости: {e}")
            raise

    def _process_sku_costs(self, sku_df: pd.DataFrame, validation_errors: List[str]) -> Dict[str, Any]:
        """Обработка данных о себестоимости SKU"""
        sku_costs = {}

        for index, row in sku_df.iterrows():
            try:
                platform = str(row.get('Платформа', '')).strip()
                sku = str(row.get('SKU/Артикул', '')).strip()
                cost_str = str(row.get('Себестоимость за шт (₽)', '')).strip()

                # Пропускаем пустые строки
                if not sku or not cost_str or cost_str in ['', 'nan', 'NaN']:
                    continue

                # Валидация и конвертация стоимости
                try:
                    cost = float(cost_str.replace(',', '.').replace(' ', ''))
                    if cost < 0:
                        validation_errors.append(f"Отрицательная себестоимость для SKU {sku}: {cost}")
                        continue
                    if cost == 0:
                        validation_errors.append(f"Нулевая себестоимость для SKU {sku}")
                        continue

                except ValueError:
                    validation_errors.append(f"Некорректная себестоимость для SKU {sku}: {cost_str}")
                    continue

                # Создаем ключ для SKU
                sku_key = f"{platform.lower()}_{sku}"

                sku_costs[sku_key] = {
                    'platform': platform,
                    'sku': sku,
                    'name': str(row.get('Название', '')).strip(),
                    'cost_per_unit': cost,
                    'barcode': str(row.get('Баркод', '')).strip(),
                    'product_id': str(row.get('Product ID', '')).strip(),
                    'category': str(row.get('Категория', '')).strip(),
                    'brand': str(row.get('Бренд', '')).strip(),
                    'current_stock': self._safe_int(row.get('Общий остаток', 0)),
                    'sizes': str(row.get('Доступные размеры', '')).strip(),
                    'note': str(row.get('Примечание', '')).strip(),
                    'processed_at': datetime.now().isoformat()
                }

            except Exception as e:
                validation_errors.append(f"Ошибка обработки строки {index + 1}: {e}")

        return sku_costs

    def _process_variable_costs(self, var_df: pd.DataFrame, validation_errors: List[str]) -> Dict[str, Any]:
        """Обработка переменных расходов"""
        variable_costs = {}

        for index, row in var_df.iterrows():
            try:
                expense_type = str(row.get('Тип расхода', '')).strip()
                cost_str = str(row.get('Стоимость за единицу (₽)', '')).strip()

                if not expense_type or not cost_str or cost_str in ['', 'nan', 'NaN']:
                    continue

                try:
                    cost = float(cost_str.replace(',', '.').replace(' ', '').replace('%', ''))
                    if cost < 0:
                        validation_errors.append(f"Отрицательный расход для {expense_type}: {cost}")
                        continue

                except ValueError:
                    validation_errors.append(f"Некорректная стоимость для {expense_type}: {cost_str}")
                    continue

                # Определяем тип расчета
                is_percentage = '%' in str(row.get('Тип расхода', '')) or '%' in cost_str

                variable_costs[expense_type] = {
                    'cost_per_unit': cost,
                    'description': str(row.get('Описание', '')).strip(),
                    'is_percentage': is_percentage,
                    'calculation_type': 'percent_revenue' if is_percentage else 'per_unit',
                    'expense_category': self._categorize_expense_type(expense_type),
                    'processed_at': datetime.now().isoformat()
                }

            except Exception as e:
                validation_errors.append(f"Ошибка обработки переменного расхода строка {index + 1}: {e}")

        return variable_costs

    def _process_fixed_costs(self, fixed_df: pd.DataFrame, validation_errors: List[str]) -> Dict[str, Any]:
        """Обработка постоянных расходов"""
        fixed_costs = {}

        for index, row in fixed_df.iterrows():
            try:
                expense_type = str(row.get('Тип расхода', '')).strip()
                cost_str = str(row.get('Сумма в месяц (₽)', '')).strip()

                if not expense_type or not cost_str or cost_str in ['', 'nan', 'NaN']:
                    continue

                try:
                    monthly_cost = float(cost_str.replace(',', '.').replace(' ', ''))
                    if monthly_cost < 0:
                        validation_errors.append(f"Отрицательный месячный расход для {expense_type}: {monthly_cost}")
                        continue

                except ValueError:
                    validation_errors.append(f"Некорректная месячная сумма для {expense_type}: {cost_str}")
                    continue

                fixed_costs[expense_type] = {
                    'monthly_cost': monthly_cost,
                    'daily_cost': monthly_cost / 30,  # Примерный дневной расход
                    'description': str(row.get('Описание', '')).strip(),
                    'expense_category': self._categorize_expense_type(expense_type),
                    'processed_at': datetime.now().isoformat()
                }

            except Exception as e:
                validation_errors.append(f"Ошибка обработки постоянного расхода строка {index + 1}: {e}")

        return fixed_costs

    def _safe_int(self, value, default=0) -> int:
        """Безопасная конвертация в int"""
        try:
            return int(float(str(value))) if value and str(value) not in ['', 'nan', 'NaN'] else default
        except (ValueError, TypeError):
            return default

    def _categorize_expense_type(self, expense_type: str) -> str:
        """Категоризация типов расходов"""
        expense_type_lower = expense_type.lower()

        if any(word in expense_type_lower for word in ['упаковка', 'логистика', 'доставка', 'хранение']):
            return 'logistics'
        elif any(word in expense_type_lower for word in ['реклама', 'маркетинг', 'smm', 'контекст']):
            return 'marketing'
        elif any(word in expense_type_lower for word in ['аренда', 'зарплата', 'коммунальные', 'интернет']):
            return 'fixed_operational'
        elif any(word in expense_type_lower for word in ['брак', 'возврат', 'переработка']):
            return 'returns_defects'
        elif any(word in expense_type_lower for word in ['комиссия', 'эквайринг', 'банк']):
            return 'financial_fees'
        else:
            return 'other'

    def _generate_cost_statistics(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Генерация статистики по обработанным данным"""
        stats = {
            'total_sku_count': len(result['sku_costs']),
            'total_variable_costs': len(result['variable_costs']),
            'total_fixed_costs': len(result['fixed_costs']),
            'validation_errors_count': len(result['validation_errors']),
            'platforms': {},
            'cost_ranges': {},
            'monthly_fixed_total': 0
        }

        # Статистика по платформам
        for sku_data in result['sku_costs'].values():
            platform = sku_data['platform']
            if platform not in stats['platforms']:
                stats['platforms'][platform] = {'count': 0, 'total_cost': 0, 'avg_cost': 0}

            stats['platforms'][platform]['count'] += 1
            stats['platforms'][platform]['total_cost'] += sku_data['cost_per_unit']

        # Рассчитываем средние стоимости
        for platform_data in stats['platforms'].values():
            if platform_data['count'] > 0:
                platform_data['avg_cost'] = platform_data['total_cost'] / platform_data['count']

        # Общая сумма постоянных расходов
        stats['monthly_fixed_total'] = sum(
            cost_data['monthly_cost'] for cost_data in result['fixed_costs'].values()
        )

        # Диапазоны себестоимости
        if result['sku_costs']:
            costs = [sku['cost_per_unit'] for sku in result['sku_costs'].values()]
            stats['cost_ranges'] = {
                'min_cost': min(costs),
                'max_cost': max(costs),
                'avg_cost': sum(costs) / len(costs),
                'median_cost': sorted(costs)[len(costs) // 2]
            }

        return stats

    async def _save_processed_cost_data(self, result: Dict[str, Any]) -> str:
        """Сохранение обработанных данных"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'processed_cost_data_{timestamp}.json'
        filepath = f'/root/sovani_bot/processed_costs/{filename}'

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"Обработанные данные сохранены: {filepath}")
        return filepath

    async def _integrate_with_expense_manager(self, result: Dict[str, Any]):
        """Интеграция обработанных данных с системой управления расходами"""
        try:
            # Добавляем переменные расходы в систему
            for expense_name, expense_data in result['variable_costs'].items():
                calculation_type = CalculationType.PERCENT_OF_REVENUE if expense_data['is_percentage'] else CalculationType.PER_UNIT
                expense_type = ExpenseType.LOGISTICS if 'логистика' in expense_name.lower() else ExpenseType.OTHER

                self.expense_manager.add_expense(
                    name=expense_name,
                    expense_type=expense_type,
                    calculation_type=calculation_type,
                    amount=expense_data['cost_per_unit'],
                    description=expense_data['description'],
                    category=expense_data['expense_category']
                )

            # Добавляем постоянные расходы
            for expense_name, expense_data in result['fixed_costs'].items():
                expense_type = ExpenseType.FIXED

                self.expense_manager.add_expense(
                    name=expense_name,
                    expense_type=expense_type,
                    calculation_type=CalculationType.FIXED_AMOUNT,
                    amount=expense_data['monthly_cost'],
                    description=expense_data['description'],
                    category=expense_data['expense_category']
                )

            logger.info("Данные интегрированы с системой управления расходами")

        except Exception as e:
            logger.error(f"Ошибка интеграции с системой расходов: {e}")

    async def calculate_enhanced_pnl(self, date_from: str, date_to: str,
                                   cost_data_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Расчет улучшенного P&L с учетом данных о себестоимости

        Args:
            date_from: Дата начала периода
            date_to: Дата окончания периода
            cost_data_file: Путь к файлу с обработанными данными о себестоимости

        Returns:
            Расширенные данные P&L с детализацией по SKU
        """
        try:
            # Получаем базовые P&L данные
            base_pnl = await self.reports.calculate_real_pnl(date_from, date_to)

            # Загружаем данные о себестоимости если есть
            cost_data = None
            if cost_data_file and os.path.exists(cost_data_file):
                with open(cost_data_file, 'r', encoding='utf-8') as f:
                    cost_data = json.load(f)
            elif not cost_data_file:
                # Ищем последний файл с данными о себестоимости
                cost_files = glob.glob('/root/sovani_bot/processed_costs/processed_cost_data_*.json')
                if cost_files:
                    latest_file = max(cost_files, key=os.path.getctime)
                    with open(latest_file, 'r', encoding='utf-8') as f:
                        cost_data = json.load(f)
                        logger.info(f"Используется файл себестоимости: {latest_file}")

            enhanced_pnl = base_pnl.copy()

            if cost_data:
                # Улучшаем расчеты с учетом детальной себестоимости
                enhanced_pnl['cost_data_used'] = True
                enhanced_pnl['cost_data_statistics'] = cost_data.get('statistics', {})
                enhanced_pnl['enhanced_calculations'] = await self._enhance_calculations_with_cost_data(
                    base_pnl, cost_data, date_from, date_to
                )
            else:
                enhanced_pnl['cost_data_used'] = False
                logger.warning("Данные о себестоимости не найдены, используются базовые расчеты")

            return enhanced_pnl

        except Exception as e:
            logger.error(f"Ошибка расчета улучшенного P&L: {e}")
            raise

    async def _enhance_calculations_with_cost_data(self, base_pnl: Dict[str, Any],
                                                 cost_data: Dict[str, Any],
                                                 date_from: str, date_to: str) -> Dict[str, Any]:
        """Улучшение расчетов с учетом детальных данных о себестоимости"""

        enhanced = {
            'improved_cogs': 0,
            'sku_profitability': {},
            'cost_breakdown': {},
            'margin_analysis': {}
        }

        # TODO: Здесь будет детальный расчет себестоимости по каждому проданному SKU
        # когда станут доступны детальные данные продаж по товарам

        # Пока используем агрегированные данные
        total_units_sold = base_pnl['total']['units']
        if total_units_sold > 0 and cost_data.get('sku_costs'):
            # Рассчитываем среднюю себестоимость
            total_cost = sum(sku['cost_per_unit'] for sku in cost_data['sku_costs'].values())
            avg_cost = total_cost / len(cost_data['sku_costs'])
            enhanced['improved_cogs'] = avg_cost * total_units_sold

            logger.info(f"Улучшенная себестоимость: {enhanced['improved_cogs']} (средняя: {avg_cost} * {total_units_sold} ед.)")
        else:
            enhanced['improved_cogs'] = base_pnl['total']['cogs']

        return enhanced

    def get_latest_cost_data_file(self) -> Optional[str]:
        """Получение пути к последнему файлу с данными о себестоимости"""
        try:
            cost_files = glob.glob('/root/sovani_bot/processed_costs/processed_cost_data_*.json')
            if cost_files:
                return max(cost_files, key=os.path.getctime)
            return None
        except Exception as e:
            logger.error(f"Ошибка поиска файлов себестоимости: {e}")
            return None

    async def generate_cost_summary_report(self) -> str:
        """Генерация сводного отчета по всем загруженным данным о себестоимости"""
        try:
            latest_file = self.get_latest_cost_data_file()
            if not latest_file:
                return "❌ Данные о себестоимости не найдены"

            with open(latest_file, 'r', encoding='utf-8') as f:
                cost_data = json.load(f)

            stats = cost_data.get('statistics', {})

            report = f"""📊 <b>СВОДКА ПО СЕБЕСТОИМОСТИ</b>
<i>Обновлено: {datetime.fromisoformat(cost_data['processed_at']).strftime('%d.%m.%Y %H:%M')}</i>

📦 <b>SKU с себестоимостью:</b> {stats.get('total_sku_count', 0)}
💰 <b>Переменные расходы:</b> {stats.get('total_variable_costs', 0)} типов
🏢 <b>Постоянные расходы:</b> {stats.get('total_fixed_costs', 0)} типов
⚠️ <b>Ошибки валидации:</b> {stats.get('validation_errors_count', 0)}

💵 <b>ПОСТОЯННЫЕ РАСХОДЫ В МЕСЯЦ:</b>
<b>{stats.get('monthly_fixed_total', 0):,.0f} ₽</b>"""

            # Добавляем статистику по платформам
            platforms = stats.get('platforms', {})
            if platforms:
                report += "\n\n📈 <b>ПО ПЛАТФОРМАМ:</b>"
                for platform, data in platforms.items():
                    report += f"\n• {platform}: {data['count']} SKU, ср. себестоимость {data['avg_cost']:.0f} ₽"

            # Диапазоны себестоимости
            cost_ranges = stats.get('cost_ranges', {})
            if cost_ranges:
                report += f"""

💎 <b>ДИАПАЗОН СЕБЕСТОИМОСТИ:</b>
• Минимум: {cost_ranges.get('min_cost', 0):.0f} ₽
• Максимум: {cost_ranges.get('max_cost', 0):.0f} ₽
• Среднее: {cost_ranges.get('avg_cost', 0):.0f} ₽"""

            # Ошибки валидации
            validation_errors = cost_data.get('validation_errors', [])
            if validation_errors:
                report += f"\n\n⚠️ <b>ОШИБКИ ВАЛИДАЦИИ:</b>"
                for error in validation_errors[:5]:  # Показываем только первые 5
                    report += f"\n• {error}"
                if len(validation_errors) > 5:
                    report += f"\n... и еще {len(validation_errors) - 5} ошибок"

            return report

        except Exception as e:
            logger.error(f"Ошибка генерации сводки себестоимости: {e}")
            return f"❌ Ошибка генерации сводки: {e}"


# Глобальный экземпляр для использования в боте
cost_processor = CostDataProcessor()


async def test_cost_processor():
    """Тестирование процессора данных о себестоимости"""
    try:
        # Тестируем генерацию сводки
        summary = await cost_processor.generate_cost_summary_report()
        print("=== СВОДКА ПО СЕБЕСТОИМОСТИ ===")
        print(summary)

        # Тестируем расчет улучшенного P&L
        enhanced_pnl = await cost_processor.calculate_enhanced_pnl('2024-09-01', '2024-09-07')
        print(f"\n=== УЛУЧШЕННЫЙ P&L ===")
        print(f"Использованы данные о себестоимости: {enhanced_pnl.get('cost_data_used', False)}")
        if enhanced_pnl.get('enhanced_calculations'):
            print(f"Улучшенная себестоимость: {enhanced_pnl['enhanced_calculations']['improved_cogs']}")

    except Exception as e:
        print(f"Ошибка тестирования: {e}")


if __name__ == "__main__":
    asyncio.run(test_cost_processor())