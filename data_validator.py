"""
🔍 МОДУЛЬ ВАЛИДАЦИИ ДАННЫХ - ФИНАЛЬНАЯ ПРОВЕРКА КАЧЕСТВА

Проверяет корректность данных перед агрегацией и формированием отчетов.
Предотвращает попадание некорректных данных в финальные расчеты.
"""

import logging
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime, date
import re

logger = logging.getLogger(__name__)

class DataValidator:
    """Валидатор данных для системы аналитики маркетплейсов"""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate_financial_data(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Валидация финансовых данных WB и Ozon

        Args:
            data: Словарь с финансовыми данными

        Returns:
            Tuple[bool, List[str]]: (is_valid, error_messages)
        """
        self.errors = []

        # 1. Проверка структуры данных
        required_keys = ['wb_data', 'ozon_data']
        for key in required_keys:
            if key not in data:
                self.errors.append(f"❌ Отсутствует ключ {key}")

        if self.errors:
            return False, self.errors

        # 2. Валидация данных WB
        wb_valid, wb_errors = self._validate_wb_data(data['wb_data'])
        if not wb_valid:
            self.errors.extend([f"WB: {err}" for err in wb_errors])

        # 3. Валидация данных Ozon
        ozon_valid, ozon_errors = self._validate_ozon_data(data['ozon_data'])
        if not ozon_valid:
            self.errors.extend([f"Ozon: {err}" for err in ozon_errors])

        # 4. Кросс-валидация данных
        cross_valid, cross_errors = self._cross_validate_data(data)
        if not cross_valid:
            self.errors.extend(cross_errors)

        return len(self.errors) == 0, self.errors

    def _validate_wb_data(self, wb_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Валидация данных WB"""
        errors = []

        # Проверка структуры WB данных
        expected_keys = ['sales', 'orders', 'supplies', 'stocks', 'advertising']

        for key in expected_keys:
            if key not in wb_data:
                errors.append(f"Отсутствует секция {key}")
                continue

            if not isinstance(wb_data[key], list):
                errors.append(f"Секция {key} должна быть списком")

        # Валидация sales
        if 'sales' in wb_data:
            sales_valid, sales_errors = self._validate_wb_sales(wb_data['sales'])
            errors.extend(sales_errors)

        # Валидация orders
        if 'orders' in wb_data:
            orders_valid, orders_errors = self._validate_wb_orders(wb_data['orders'])
            errors.extend(orders_errors)

        return len(errors) == 0, errors

    def _validate_wb_sales(self, sales: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """Валидация продаж WB"""
        errors = []

        for i, sale in enumerate(sales):
            # Проверка обязательных полей
            required_fields = ['date', 'saleID', 'forPay']
            for field in required_fields:
                if field not in sale:
                    errors.append(f"Sale {i}: отсутствует поле {field}")

            # Валидация типов данных
            if 'forPay' in sale:
                if not isinstance(sale['forPay'], (int, float)):
                    errors.append(f"Sale {i}: forPay должно быть числом, получено {type(sale['forPay'])}")
                elif sale['forPay'] < 0:
                    errors.append(f"Sale {i}: forPay не может быть отрицательным: {sale['forPay']}")

            # Валидация даты
            if 'date' in sale:
                date_valid, date_error = self._validate_date_format(sale['date'])
                if not date_valid:
                    errors.append(f"Sale {i}: {date_error}")

        return len(errors) == 0, errors

    def _validate_wb_orders(self, orders: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """Валидация заказов WB"""
        errors = []

        for i, order in enumerate(orders):
            # Проверка обязательных полей
            required_fields = ['date', 'odid', 'totalPrice']
            for field in required_fields:
                if field not in order:
                    errors.append(f"Order {i}: отсутствует поле {field}")

            # Валидация цены
            if 'totalPrice' in order:
                if not isinstance(order['totalPrice'], (int, float)):
                    errors.append(f"Order {i}: totalPrice должно быть числом")
                elif order['totalPrice'] < 0:
                    errors.append(f"Order {i}: totalPrice не может быть отрицательной")

        return len(errors) == 0, errors

    def _validate_ozon_data(self, ozon_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Валидация данных Ozon"""
        errors = []

        # Проверка структуры Ozon данных
        expected_keys = ['fbo', 'fbs']

        for key in expected_keys:
            if key not in ozon_data:
                errors.append(f"Отсутствует секция {key}")
                continue

            if not isinstance(ozon_data[key], list):
                errors.append(f"Секция {key} должна быть списком")

        # Валидация FBO данных
        if 'fbo' in ozon_data:
            fbo_valid, fbo_errors = self._validate_ozon_orders(ozon_data['fbo'], 'FBO')
            errors.extend(fbo_errors)

        # Валидация FBS данных
        if 'fbs' in ozon_data:
            fbs_valid, fbs_errors = self._validate_ozon_orders(ozon_data['fbs'], 'FBS')
            errors.extend(fbs_errors)

        return len(errors) == 0, errors

    def _validate_ozon_orders(self, orders: List[Dict[str, Any]], order_type: str) -> Tuple[bool, List[str]]:
        """Валидация заказов Ozon (FBO/FBS)"""
        errors = []

        for i, order in enumerate(orders):
            # Проверка структуры заказа
            if not isinstance(order, dict):
                errors.append(f"{order_type} {i}: заказ должен быть словарем")
                continue

            # Проверка обязательных полей
            required_fields = ['posting_number', 'status', 'in_process_at']
            for field in required_fields:
                if field not in order:
                    errors.append(f"{order_type} {i}: отсутствует поле {field}")

            # Валидация продуктов в заказе
            if 'products' in order:
                if not isinstance(order['products'], list):
                    errors.append(f"{order_type} {i}: products должно быть списком")
                else:
                    for j, product in enumerate(order['products']):
                        if 'price' in product:
                            if not isinstance(product['price'], (str, int, float)):
                                errors.append(f"{order_type} {i} product {j}: price должно быть числом или строкой")

        return len(errors) == 0, errors

    def _cross_validate_data(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Кросс-валидация данных между платформами"""
        errors = []

        # Проверка консистентности дат
        wb_dates = self._extract_dates_from_wb(data.get('wb_data', {}))
        ozon_dates = self._extract_dates_from_ozon(data.get('ozon_data', {}))

        if wb_dates and ozon_dates:
            wb_min, wb_max = min(wb_dates), max(wb_dates)
            ozon_min, ozon_max = min(ozon_dates), max(ozon_dates)

            # Предупреждение о больших расхождениях в датах
            from datetime import timedelta
            if abs(wb_min - ozon_min) > timedelta(days=7):
                errors.append(f"⚠️ Большое расхождение в минимальных датах: WB {wb_min}, Ozon {ozon_min}")

        return len(errors) == 0, errors

    def _validate_date_format(self, date_str: str) -> Tuple[bool, str]:
        """Валидация формата даты"""
        if not isinstance(date_str, str):
            return False, f"Дата должна быть строкой, получено {type(date_str)}"

        # Поддерживаемые форматы дат
        date_patterns = [
            r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',  # ISO with time
            r'^\d{4}-\d{2}-\d{2}$',  # ISO date only
            r'^\d{2}\.\d{2}\.\d{4}$',  # DD.MM.YYYY
        ]

        for pattern in date_patterns:
            if re.match(pattern, date_str):
                return True, ""

        return False, f"Неподдерживаемый формат даты: {date_str}"

    def _extract_dates_from_wb(self, wb_data: Dict[str, Any]) -> List[date]:
        """Извлечение дат из данных WB"""
        dates = []

        for section in ['sales', 'orders']:
            if section in wb_data:
                for item in wb_data[section]:
                    if 'date' in item:
                        try:
                            # Парсинг ISO даты
                            date_str = item['date']
                            if 'T' in date_str:
                                parsed_date = datetime.fromisoformat(date_str.split('T')[0]).date()
                            else:
                                parsed_date = datetime.fromisoformat(date_str).date()
                            dates.append(parsed_date)
                        except:
                            continue

        return dates

    def _extract_dates_from_ozon(self, ozon_data: Dict[str, Any]) -> List[date]:
        """Извлечение дат из данных Ozon"""
        dates = []

        for section in ['fbo', 'fbs']:
            if section in ozon_data:
                for item in ozon_data[section]:
                    if 'in_process_at' in item:
                        try:
                            # Парсинг ISO даты
                            date_str = item['in_process_at']
                            if 'T' in date_str:
                                parsed_date = datetime.fromisoformat(date_str.split('T')[0]).date()
                            else:
                                parsed_date = datetime.fromisoformat(date_str).date()
                            dates.append(parsed_date)
                        except:
                            continue

        return dates

    def get_validation_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Получение сводки валидации"""
        is_valid, errors = self.validate_financial_data(data)

        # Подсчет статистики данных
        wb_stats = self._get_wb_stats(data.get('wb_data', {}))
        ozon_stats = self._get_ozon_stats(data.get('ozon_data', {}))

        return {
            'is_valid': is_valid,
            'errors_count': len(errors),
            'errors': errors,
            'wb_stats': wb_stats,
            'ozon_stats': ozon_stats,
            'total_revenue': wb_stats.get('total_revenue', 0) + ozon_stats.get('total_revenue', 0),
            'validation_timestamp': datetime.now().isoformat()
        }

    def _get_wb_stats(self, wb_data: Dict[str, Any]) -> Dict[str, Any]:
        """Статистика данных WB"""
        stats = {
            'sales_count': len(wb_data.get('sales', [])),
            'orders_count': len(wb_data.get('orders', [])),
            'total_revenue': sum(sale.get('forPay', 0) for sale in wb_data.get('sales', []) if isinstance(sale.get('forPay'), (int, float)))
        }
        return stats

    def _get_ozon_stats(self, ozon_data: Dict[str, Any]) -> Dict[str, Any]:
        """Статистика данных Ozon"""
        total_revenue = 0
        total_orders = 0

        for section in ['fbo', 'fbs']:
            if section in ozon_data:
                orders = ozon_data[section]
                total_orders += len(orders)

                # Подсчет выручки по продуктам
                for order in orders:
                    if isinstance(order, dict) and 'products' in order:
                        for product in order['products']:
                            if isinstance(product, dict) and 'price' in product:
                                try:
                                    price = float(product['price'])
                                    total_revenue += price
                                except:
                                    continue

        stats = {
            'fbo_count': len(ozon_data.get('fbo', [])),
            'fbs_count': len(ozon_data.get('fbs', [])),
            'total_orders': total_orders,
            'total_revenue': total_revenue
        }
        return stats

# Глобальный экземпляр валидатора
validator = DataValidator()

def validate_data_before_aggregation(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Основная функция для валидации данных перед агрегацией

    Args:
        data: Данные для валидации

    Returns:
        Dict с результатами валидации
    """
    logger.info("🔍 Запуск финальной валидации данных")

    try:
        summary = validator.get_validation_summary(data)

        if summary['is_valid']:
            logger.info(f"✅ Валидация успешна! WB: {summary['wb_stats']['sales_count']} продаж, Ozon: {summary['ozon_stats']['total_orders']} заказов")
            logger.info(f"💰 Общая выручка: {summary['total_revenue']:.2f} ₽")
        else:
            logger.error(f"❌ Обнаружено {summary['errors_count']} ошибок валидации:")
            for error in summary['errors']:
                logger.error(f"   • {error}")

        return summary

    except Exception as e:
        logger.error(f"❌ Критическая ошибка валидации: {e}")
        return {
            'is_valid': False,
            'errors_count': 1,
            'errors': [f"Критическая ошибка валидации: {str(e)}"],
            'validation_timestamp': datetime.now().isoformat()
        }