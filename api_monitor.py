#!/usr/bin/env python3
"""Мониторинг доступности API и уведомления"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_clients_main import ozon_api, wb_api

logger = logging.getLogger(__name__)


class APIMonitor:
    """Монитор состояния API интеграций"""

    def __init__(self):
        self.status_history = []
        self.last_notification = {}

    async def check_all_apis(self) -> dict[str, dict]:
        """Проверка состояния всех API"""
        results = {
            "timestamp": datetime.now(),
            "wildberries": await self._check_wb_api(),
            "ozon": await self._check_ozon_api(),
        }

        # Сохраняем в историю
        self.status_history.append(results)

        # Ограничиваем историю последними 24 часами
        cutoff_time = datetime.now() - timedelta(hours=24)
        self.status_history = [
            status for status in self.status_history if status["timestamp"] > cutoff_time
        ]

        return results

    async def _check_wb_api(self) -> dict:
        """Проверка WB API"""
        try:
            is_available = await wb_api.test_api_availability()
            status = wb_api.get_api_status()

            return {
                "available": is_available,
                "status_message": status["status_message"],
                "last_check": status["last_check"],
                "api_name": "WildBerries",
            }
        except Exception as e:
            return {
                "available": False,
                "status_message": f"Ошибка проверки: {e}",
                "last_check": datetime.now(),
                "api_name": "WildBerries",
            }

    async def _check_ozon_api(self) -> dict:
        """Проверка Ozon API"""
        try:
            # Простая проверка Ozon API
            stocks = await ozon_api.get_product_stocks()
            is_available = len(stocks) >= 0  # Даже пустой ответ означает что API работает

            return {
                "available": is_available,
                "status_message": f"Ozon API доступен, получено {len(stocks)} остатков",
                "last_check": datetime.now(),
                "api_name": "Ozon",
            }
        except Exception as e:
            return {
                "available": False,
                "status_message": f"Ozon API недоступен: {e}",
                "last_check": datetime.now(),
                "api_name": "Ozon",
            }

    def get_status_summary(self) -> dict:
        """Получение сводки статуса API"""
        if not self.status_history:
            return {"overall_status": "unknown", "message": "Нет данных мониторинга", "details": {}}

        latest = self.status_history[-1]

        wb_available = latest["wildberries"]["available"]
        ozon_available = latest["ozon"]["available"]

        if wb_available and ozon_available:
            overall_status = "all_ok"
            message = "✅ Все API работают"
        elif ozon_available:
            overall_status = "ozon_only"
            message = "⚠️ Работает только Ozon API"
        elif wb_available:
            overall_status = "wb_only"
            message = "⚠️ Работает только WildBerries API"
        else:
            overall_status = "all_down"
            message = "❌ Все API недоступны"

        return {
            "overall_status": overall_status,
            "message": message,
            "details": {"wildberries": latest["wildberries"], "ozon": latest["ozon"]},
            "last_check": latest["timestamp"],
        }

    def get_fallback_recommendations(self) -> list[str]:
        """Получение рекомендаций по fallback режиму"""
        summary = self.get_status_summary()
        recommendations = []

        if summary["overall_status"] == "all_ok":
            recommendations.append("🟢 Все системы работают в штатном режиме")

        elif summary["overall_status"] == "ozon_only":
            recommendations.extend(
                [
                    "⚠️ WildBerries API недоступен - работаем только с Ozon",
                    "📝 Отзывы и вопросы WB временно недоступны",
                    "📊 Статистика WB временно недоступна",
                    "🔄 Рекомендуется обратиться в техподдержку WB",
                    "📱 Уведомите пользователей о временных ограничениях",
                ]
            )

        elif summary["overall_status"] == "wb_only":
            recommendations.extend(
                [
                    "⚠️ Ozon API недоступен - работаем только с WildBerries",
                    "📊 Статистика Ozon временно недоступна",
                    "🔄 Проверьте настройки Ozon API",
                ]
            )

        else:  # all_down
            recommendations.extend(
                [
                    "❌ Все API недоступны - критическая ситуация",
                    "🚨 Немедленно проверьте подключение к интернету",
                    "🔧 Проверьте конфигурацию токенов",
                    "📞 Обратитесь в техподдержку платформ",
                    "👥 Уведомите пользователей о технических работах",
                ]
            )

        return recommendations

    async def generate_status_report(self) -> str:
        """Генерация отчета о состоянии API"""
        await self.check_all_apis()
        summary = self.get_status_summary()
        recommendations = self.get_fallback_recommendations()

        report_lines = [
            "📊 ОТЧЕТ О СОСТОЯНИИ API",
            "=" * 40,
            f"🕐 Время проверки: {summary['last_check'].strftime('%Y-%m-%d %H:%M:%S')}",
            f"📈 Общий статус: {summary['message']}",
            "",
            "🔍 ДЕТАЛИ ПО API:",
        ]

        for api_name, details in summary["details"].items():
            status_icon = "✅" if details["available"] else "❌"
            report_lines.extend(
                [
                    f"{status_icon} {details['api_name']}:",
                    f"   Статус: {details['status_message']}",
                    f"   Проверено: {details['last_check'].strftime('%H:%M:%S') if details['last_check'] else 'Никогда'}",
                    "",
                ]
            )

        report_lines.extend(["💡 РЕКОМЕНДАЦИИ:", ""])

        for i, recommendation in enumerate(recommendations, 1):
            report_lines.append(f"{i}. {recommendation}")

        # Добавляем историю доступности за последние часы
        if len(self.status_history) > 1:
            report_lines.extend(["", "📈 ИСТОРИЯ ДОСТУПНОСТИ (последние проверки):", ""])

            for status in self.status_history[-5:]:  # Последние 5 проверок
                wb_icon = "✅" if status["wildberries"]["available"] else "❌"
                ozon_icon = "✅" if status["ozon"]["available"] else "❌"
                time_str = status["timestamp"].strftime("%H:%M")
                report_lines.append(f"{time_str}: WB {wb_icon} | Ozon {ozon_icon}")

        return "\n".join(report_lines)


# Глобальный экземпляр монитора
api_monitor = APIMonitor()


async def main():
    """Тестирование монитора"""
    report = await api_monitor.generate_status_report()
    print(report)


if __name__ == "__main__":
    asyncio.run(main())
