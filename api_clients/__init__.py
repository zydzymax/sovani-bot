"""API clients for SoVAni Bot"""

from .ozon.sales_client import OzonSalesClient
from .wb.stats_client import WBStatsClient

# Создаем готовые экземпляры для использования в системе
try:
    wb_api = WBStatsClient()
    ozon_api = OzonSalesClient()
except Exception as e:
    print(f"Ошибка инициализации API клиентов: {e}")
    wb_api = None
    ozon_api = None

__all__ = ["WBStatsClient", "OzonSalesClient", "wb_api", "ozon_api"]
