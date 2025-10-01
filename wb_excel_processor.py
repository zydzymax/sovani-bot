#!/usr/bin/env python3
"""Обработчик Excel файлов WB
Простая обработка загруженных файлов отчетов WB
"""

import logging
import os
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class WBExcelProcessor:
    """Обработчик Excel файлов Wildberries"""

    def __init__(self):
        self.upload_dir = "uploads/wb_reports"
        os.makedirs(self.upload_dir, exist_ok=True)

    async def process_sales_report(self, file_path: str) -> dict[str, Any]:
        """Обработка отчета о продажах WB

        Args:
            file_path: Путь к Excel файлу

        Returns:
            Словарь с результатами анализа

        """
        try:
            # Читаем Excel файл
            df = pd.read_excel(file_path)

            logger.info(f"Загружен файл продаж WB: {len(df)} записей")

            # Базовый анализ
            total_rows = len(df)

            # Пытаемся найти основные колонки
            revenue_columns = ["Выручка", "К доплате", "forPay", "Сумма"]
            revenue_column = None
            for col in revenue_columns:
                if col in df.columns:
                    revenue_column = col
                    break

            total_revenue = 0
            if revenue_column:
                total_revenue = df[revenue_column].sum()

            # Анализ по датам
            date_columns = ["Дата продажи", "Дата", "date", "Date"]
            date_column = None
            for col in date_columns:
                if col in df.columns:
                    date_column = col
                    break

            date_range = "Не определен"
            if date_column:
                try:
                    dates = pd.to_datetime(df[date_column])
                    min_date = dates.min().strftime("%d.%m.%Y")
                    max_date = dates.max().strftime("%d.%m.%Y")
                    date_range = f"{min_date} - {max_date}"
                except:
                    pass

            return {
                "success": True,
                "file_type": "sales",
                "total_rows": total_rows,
                "total_revenue": total_revenue,
                "revenue_column": revenue_column,
                "date_range": date_range,
                "columns": list(df.columns),
            }

        except Exception as e:
            logger.error(f"Ошибка обработки файла продаж: {e}")
            return {"success": False, "error": str(e)}

    async def process_orders_report(self, file_path: str) -> dict[str, Any]:
        """Обработка отчета о заказах WB

        Args:
            file_path: Путь к Excel файлу

        Returns:
            Словарь с результатами анализа

        """
        try:
            # Читаем Excel файл
            df = pd.read_excel(file_path)

            logger.info(f"Загружен файл заказов WB: {len(df)} записей")

            total_rows = len(df)

            # Анализ статусов заказов
            status_columns = ["Статус", "status", "Состояние"]
            status_column = None
            for col in status_columns:
                if col in df.columns:
                    status_column = col
                    break

            status_analysis = {}
            if status_column:
                status_analysis = df[status_column].value_counts().to_dict()

            # Анализ по суммам
            sum_columns = ["Цена", "Сумма заказа", "priceWithDisc", "Итого"]
            sum_column = None
            for col in sum_columns:
                if col in df.columns:
                    sum_column = col
                    break

            total_sum = 0
            if sum_column:
                total_sum = df[sum_column].sum()

            return {
                "success": True,
                "file_type": "orders",
                "total_rows": total_rows,
                "total_sum": total_sum,
                "sum_column": sum_column,
                "status_analysis": status_analysis,
                "columns": list(df.columns),
            }

        except Exception as e:
            logger.error(f"Ошибка обработки файла заказов: {e}")
            return {"success": False, "error": str(e)}

    async def process_finance_report(self, file_path: str) -> dict[str, Any]:
        """Обработка финансового отчета WB

        Args:
            file_path: Путь к Excel файлу

        Returns:
            Словарь с результатами анализа

        """
        try:
            # Читаем Excel файл
            df = pd.read_excel(file_path)

            logger.info(f"Загружен финансовый файл WB: {len(df)} записей")

            total_rows = len(df)

            # Поиск финансовых показателей
            finance_columns = ["Сумма", "К доплате", "Выручка", "К доплате продавцу"]
            finance_data = {}

            for col in finance_columns:
                if col in df.columns:
                    finance_data[col] = df[col].sum()

            # Анализ операций
            operation_columns = ["Тип операции", "Операция", "operation_type"]
            operation_column = None
            for col in operation_columns:
                if col in df.columns:
                    operation_column = col
                    break

            operation_analysis = {}
            if operation_column:
                operation_analysis = df[operation_column].value_counts().to_dict()

            return {
                "success": True,
                "file_type": "finance",
                "total_rows": total_rows,
                "finance_data": finance_data,
                "operation_analysis": operation_analysis,
                "columns": list(df.columns),
            }

        except Exception as e:
            logger.error(f"Ошибка обработки финансового файла: {e}")
            return {"success": False, "error": str(e)}

    def format_analysis_report(self, analysis: dict[str, Any]) -> str:
        """Форматирование отчета анализа для отправки пользователю

        Args:
            analysis: Результат анализа файла

        Returns:
            Форматированный текст отчета

        """
        if not analysis["success"]:
            return f"❌ <b>Ошибка обработки файла</b>\n\n{analysis['error']}"

        file_type = analysis["file_type"]

        if file_type == "sales":
            return self._format_sales_report(analysis)
        elif file_type == "orders":
            return self._format_orders_report(analysis)
        elif file_type == "finance":
            return self._format_finance_report(analysis)
        else:
            return "❌ Неизвестный тип файла"

    def _format_sales_report(self, analysis: dict[str, Any]) -> str:
        """Форматирование отчета о продажах"""
        text = "✅ <b>Отчет о продажах WB обработан</b>\n\n"
        text += "📊 <b>Основные показатели:</b>\n"
        text += f"• Записей: {analysis['total_rows']:,}\n"

        if analysis["revenue_column"]:
            text += f"• Выручка: {analysis['total_revenue']:,.2f} ₽\n"
            text += f"• Колонка выручки: {analysis['revenue_column']}\n"

        text += f"• Период: {analysis['date_range']}\n\n"

        text += "📋 <b>Структура файла:</b>\n"
        text += f"• Колонок: {len(analysis['columns'])}\n"
        text += f"• Основные поля: {', '.join(analysis['columns'][:5])}"

        if len(analysis["columns"]) > 5:
            text += f" и еще {len(analysis['columns']) - 5}"

        return text

    def _format_orders_report(self, analysis: dict[str, Any]) -> str:
        """Форматирование отчета о заказах"""
        text = "✅ <b>Отчет о заказах WB обработан</b>\n\n"
        text += "📊 <b>Основные показатели:</b>\n"
        text += f"• Заказов: {analysis['total_rows']:,}\n"

        if analysis["sum_column"]:
            text += f"• Общая сумма: {analysis['total_sum']:,.2f} ₽\n"

        if analysis["status_analysis"]:
            text += "\n📈 <b>Анализ статусов:</b>\n"
            for status, count in list(analysis["status_analysis"].items())[:5]:
                text += f"• {status}: {count:,}\n"

        return text

    def _format_finance_report(self, analysis: dict[str, Any]) -> str:
        """Форматирование финансового отчета"""
        text = "✅ <b>Финансовый отчет WB обработан</b>\n\n"
        text += "📊 <b>Основные показатели:</b>\n"
        text += f"• Операций: {analysis['total_rows']:,}\n\n"

        if analysis["finance_data"]:
            text += "💰 <b>Финансовые данные:</b>\n"
            for field, amount in analysis["finance_data"].items():
                text += f"• {field}: {amount:,.2f} ₽\n"

        if analysis["operation_analysis"]:
            text += "\n📈 <b>Типы операций:</b>\n"
            for op_type, count in list(analysis["operation_analysis"].items())[:5]:
                text += f"• {op_type}: {count:,}\n"

        return text


# Глобальный экземпляр процессора
wb_excel_processor = WBExcelProcessor()
