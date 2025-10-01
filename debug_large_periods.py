"""🚨 КРИТИЧЕСКАЯ ДИАГНОСТИКА ПРОБЛЕМЫ С БОЛЬШИМИ ПЕРИОДАМИ

Детальный анализ проблемы с данными при запросе больших периодов (01.01.2025 - сегодня)
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta

# Настройка детального логирования
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/root/sovani_bot/debug_large_periods.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class LargePeriodDebugger:
    """Отладчик для проблем с большими периодами данных"""

    def __init__(self):
        self.debug_data = {
            "api_calls": [],
            "chunk_results": [],
            "aggregation_steps": [],
            "final_results": {},
        }

    async def diagnose_large_period_issue(
        self, date_from: str = "2025-01-01", date_to: str = "2025-09-24"
    ):
        """Полная диагностика проблемы с большими периодами"""
        logger.critical("🚨 НАЧАЛО КРИТИЧЕСКОЙ ДИАГНОСТИКИ")
        logger.critical(f"🔍 Период: {date_from} -> {date_to}")

        # 1. ДИАГНОСТИКА API ПОДКЛЮЧЕНИЙ
        logger.critical("=" * 80)
        logger.critical("1️⃣ ДИАГНОСТИКА API ПОДКЛЮЧЕНИЙ")
        logger.critical("=" * 80)

        api_status = await self._diagnose_api_connections()
        self.debug_data["api_status"] = api_status

        # 2. ДИАГНОСТИКА CHUNKING ЛОГИКИ
        logger.critical("=" * 80)
        logger.critical("2️⃣ ДИАГНОСТИКА CHUNKING ЛОГИКИ")
        logger.critical("=" * 80)

        chunking_analysis = await self._diagnose_chunking_logic(date_from, date_to)
        self.debug_data["chunking_analysis"] = chunking_analysis

        # 3. ДИАГНОСТИКА ПРЯМЫХ API ЗАПРОСОВ
        logger.critical("=" * 80)
        logger.critical("3️⃣ ДИАГНОСТИКА ПРЯМЫХ API ЗАПРОСОВ")
        logger.critical("=" * 80)

        direct_api_results = await self._diagnose_direct_api_calls(date_from, date_to)
        self.debug_data["direct_api_results"] = direct_api_results

        # 4. ДИАГНОСТИКА STAGED PROCESSOR
        logger.critical("=" * 80)
        logger.critical("4️⃣ ДИАГНОСТИКА STAGED PROCESSOR")
        logger.critical("=" * 80)

        staged_results = await self._diagnose_staged_processor(date_from, date_to)
        self.debug_data["staged_results"] = staged_results

        # 5. ФИНАЛЬНЫЙ АНАЛИЗ
        logger.critical("=" * 80)
        logger.critical("5️⃣ ФИНАЛЬНЫЙ АНАЛИЗ ПРОБЛЕМЫ")
        logger.critical("=" * 80)

        analysis = self._analyze_root_cause()

        return analysis

    async def _diagnose_api_connections(self):
        """Диагностика состояния API подключений"""
        results = {}

        try:
            from config import Config

            logger.debug(f"WB_FEEDBACKS_TOKEN length: {len(Config.WB_FEEDBACKS_TOKEN)}")
            logger.debug(f"WB_ADS_TOKEN length: {len(Config.WB_ADS_TOKEN)}")
            logger.debug(f"WB_STATS_TOKEN length: {len(Config.WB_STATS_TOKEN)}")
            logger.debug(f"OZON_CLIENT_ID: {Config.OZON_CLIENT_ID}")

            # Проверка WB API
            from api_clients_main import WBBusinessAPI

            wb_client = WBBusinessAPI()

            logger.debug("🔗 Тестируем WB API...")
            wb_campaigns = await wb_client.get_advertising_campaigns()
            results["wb_campaigns_count"] = len(wb_campaigns.get("campaigns", []))
            logger.debug(f"WB кампаний найдено: {results['wb_campaigns_count']}")

            # Проверка Ozon API
            from api_clients_main import OzonAPI

            ozon_client = OzonAPI()
            logger.debug("🔗 Тестируем Ozon API...")

            # Простой тест подключения
            results["ozon_client_id"] = ozon_client.CLIENT_ID
            logger.debug(f"Ozon Client ID: {results['ozon_client_id']}")

            results["api_connections_ok"] = True

        except Exception as e:
            logger.error(f"❌ Ошибка API подключений: {e}")
            results["api_connections_ok"] = False
            results["error"] = str(e)

        return results

    async def _diagnose_chunking_logic(self, date_from: str, date_to: str):
        """Диагностика логики разбиения на чанки"""
        results = {}

        try:
            from api_chunking import APIChunker

            chunker = APIChunker()

            # Анализируем chunking для разных API
            for api_type in ["wb_sales", "wb_orders", "wb_advertising", "ozon_fbo", "ozon_fbs"]:
                logger.debug(f"📊 Анализ chunking для {api_type}")

                chunks = chunker.split_date_range(date_from, date_to, api_type)
                logger.debug(f"   Количество чанков: {len(chunks)}")

                results[api_type] = {"chunk_count": len(chunks), "chunks": chunks}

                # Детальный анализ каждого чанка
                for i, (chunk_from, chunk_to) in enumerate(chunks):
                    days_in_chunk = (
                        datetime.strptime(chunk_to, "%Y-%m-%d")
                        - datetime.strptime(chunk_from, "%Y-%m-%d")
                    ).days
                    logger.debug(
                        f"   Чанк {i+1}: {chunk_from} -> {chunk_to} ({days_in_chunk} дней)"
                    )

        except Exception as e:
            logger.error(f"❌ Ошибка chunking анализа: {e}")
            results["error"] = str(e)

        return results

    async def _diagnose_direct_api_calls(self, date_from: str, date_to: str):
        """Диагностика прямых вызовов API"""
        results = {}

        try:
            logger.debug("🔍 ПРЯМЫЕ ЗАПРОСЫ К API")

            # 1. Прямой запрос WB Sales
            logger.debug("📈 Тестируем WB Sales API...")
            wb_sales_result = await self._test_wb_sales_direct(date_from, date_to)
            results["wb_sales"] = wb_sales_result

            # 2. Прямой запрос WB Orders
            logger.debug("📦 Тестируем WB Orders API...")
            wb_orders_result = await self._test_wb_orders_direct(date_from, date_to)
            results["wb_orders"] = wb_orders_result

            # 3. Прямой запрос Ozon FBO
            logger.debug("🏪 Тестируем Ozon FBO API...")
            ozon_fbo_result = await self._test_ozon_fbo_direct(date_from, date_to)
            results["ozon_fbo"] = ozon_fbo_result

        except Exception as e:
            logger.error(f"❌ Ошибка прямых API запросов: {e}")
            results["error"] = str(e)

        return results

    async def _test_wb_sales_direct(self, date_from: str, date_to: str):
        """Прямой тест WB Sales API"""
        try:
            from api_clients.wb.sales_client import WBSalesAPI
            from config import Config

            client = WBSalesAPI(Config.WB_STATS_TOKEN)

            # Тестируем один небольшой чанк
            test_chunk_to = (
                datetime.strptime(date_from, "%Y-%m-%d") + timedelta(days=30)
            ).strftime("%Y-%m-%d")

            logger.debug(f"   Запрос WB Sales: {date_from} -> {test_chunk_to}")

            sales_data = await client.get_sales_data(date_from, test_chunk_to)

            result = {
                "success": True,
                "sales_count": len(sales_data) if sales_data else 0,
                "sample_data": sales_data[:3] if sales_data else [],
                "total_revenue": (
                    sum(sale.get("forPay", 0) for sale in sales_data) if sales_data else 0
                ),
            }

            logger.debug(
                f"   ✅ WB Sales результат: {result['sales_count']} продаж, {result['total_revenue']} ₽"
            )

            return result

        except Exception as e:
            logger.error(f"   ❌ WB Sales ошибка: {e}")
            return {"success": False, "error": str(e)}

    async def _test_wb_orders_direct(self, date_from: str, date_to: str):
        """Прямой тест WB Orders API"""
        try:
            from api_clients.wb.orders_client import WBOrdersAPI
            from config import Config

            client = WBOrdersAPI(Config.WB_STATS_TOKEN)

            test_chunk_to = (
                datetime.strptime(date_from, "%Y-%m-%d") + timedelta(days=30)
            ).strftime("%Y-%m-%d")

            logger.debug(f"   Запрос WB Orders: {date_from} -> {test_chunk_to}")

            orders_data = await client.get_orders_data(date_from, test_chunk_to)

            result = {
                "success": True,
                "orders_count": len(orders_data) if orders_data else 0,
                "sample_data": orders_data[:3] if orders_data else [],
            }

            logger.debug(f"   ✅ WB Orders результат: {result['orders_count']} заказов")

            return result

        except Exception as e:
            logger.error(f"   ❌ WB Orders ошибка: {e}")
            return {"success": False, "error": str(e)}

    async def _test_ozon_fbo_direct(self, date_from: str, date_to: str):
        """Прямой тест Ozon FBO API"""
        try:
            from api_clients.ozon.sales_client import OzonSalesAPI

            client = OzonSalesAPI()

            test_chunk_to = (
                datetime.strptime(date_from, "%Y-%m-%d") + timedelta(days=30)
            ).strftime("%Y-%m-%d")

            logger.debug(f"   Запрос Ozon FBO: {date_from} -> {test_chunk_to}")

            fbo_data = await client.get_fbo_orders(date_from, test_chunk_to)

            result = {
                "success": True,
                "orders_count": len(fbo_data) if fbo_data else 0,
                "sample_data": fbo_data[:3] if fbo_data else [],
            }

            logger.debug(f"   ✅ Ozon FBO результат: {result['orders_count']} заказов")

            return result

        except Exception as e:
            logger.error(f"   ❌ Ozon FBO ошибка: {e}")
            return {"success": False, "error": str(e)}

    async def _diagnose_staged_processor(self, date_from: str, date_to: str):
        """Диагностика Staged Processor"""
        results = {}

        try:
            from staged_processor import StagedDataProcessor

            logger.debug("🔄 Тестируем Staged Processor...")

            processor = StagedDataProcessor()

            # Создаем тестовое задание
            job_id = f"debug_{datetime.now().strftime('%H%M%S')}"

            logger.debug(f"   Создано задание: {job_id}")
            logger.debug(f"   Период: {date_from} -> {date_to}")

            # НЕ запускаем полный процессор, только анализируем его состояние
            results = {
                "processor_available": True,
                "job_id": job_id,
                "period": f"{date_from} -> {date_to}",
                "note": "Полный запуск не выполнялся для избежания длительного ожидания",
            }

            logger.debug("   ✅ Staged Processor готов к работе")

        except Exception as e:
            logger.error(f"   ❌ Staged Processor ошибка: {e}")
            results = {"success": False, "error": str(e)}

        return results

    def _analyze_root_cause(self):
        """Анализ корневой причины проблемы"""
        logger.critical("🔍 АНАЛИЗ КОРНЕВОЙ ПРИЧИНЫ")

        issues_found = []
        recommendations = []

        # Анализ API подключений
        if not self.debug_data.get("api_status", {}).get("api_connections_ok", False):
            issues_found.append("❌ API подключения не работают корректно")
            recommendations.append("Проверить токены и доступность API")

        # Анализ chunking
        chunking_data = self.debug_data.get("chunking_analysis", {})
        for api_type, data in chunking_data.items():
            if isinstance(data, dict) and data.get("chunk_count", 0) > 20:
                issues_found.append(
                    f"⚠️ Слишком много чанков для {api_type}: {data.get('chunk_count')}"
                )
                recommendations.append(f"Увеличить размер чанков для {api_type}")

        # Анализ API результатов
        api_results = self.debug_data.get("direct_api_results", {})
        for api_name, result in api_results.items():
            if isinstance(result, dict):
                if not result.get("success", False):
                    issues_found.append(f"❌ {api_name} API не возвращает данные")
                    recommendations.append(f"Исправить {api_name} API интеграцию")
                elif result.get("sales_count", 0) == 0 and result.get("orders_count", 0) == 0:
                    issues_found.append(f"⚠️ {api_name} возвращает пустые данные")
                    recommendations.append(f"Проверить период и фильтры для {api_name}")

        logger.critical(f"🚨 НАЙДЕНО ПРОБЛЕМ: {len(issues_found)}")
        for issue in issues_found:
            logger.critical(f"   {issue}")

        logger.critical(f"💡 РЕКОМЕНДАЦИИ: {len(recommendations)}")
        for rec in recommendations:
            logger.critical(f"   {rec}")

        return {
            "issues_found": issues_found,
            "recommendations": recommendations,
            "debug_data": self.debug_data,
            "root_cause_identified": len(issues_found) > 0,
        }

    def save_debug_report(self, analysis_result):
        """Сохранение отчета диагностики"""
        report_path = "/root/sovani_bot/debug_report.json"

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(analysis_result, f, ensure_ascii=False, indent=2, default=str)

        logger.critical(f"📋 Отчет сохранен: {report_path}")


async def main():
    """Главная функция диагностики"""
    debugger = LargePeriodDebugger()

    # Диагностируем период с 01.01.2025 по сегодня
    today = datetime.now().strftime("%Y-%m-%d")

    analysis = await debugger.diagnose_large_period_issue("2025-01-01", today)

    debugger.save_debug_report(analysis)

    return analysis


if __name__ == "__main__":
    results = asyncio.run(main())
    print("🚨 ДИАГНОСТИКА ЗАВЕРШЕНА!")
