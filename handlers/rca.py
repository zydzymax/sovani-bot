import os
API_BASE = os.getenv("API_BASE","https://justbusiness.lol/api").rstrip("/")
SERVICE_TOKEN = os.getenv("INTERNAL_API_TOKEN","")

async def _get_async(path, params=None):
    """Асинхронная замена requests.get на http_async"""
    try:
        import http_async
        result = await http_async.get_json(path, params=params)
        return result
    except Exception as e:
        raise

async def finance(date_from, date_to):
    st = await _get_async("/diag/finance_status", {"date_from":date_from,"date_to":date_to})
    return st

async def inventory():
    st = await _get_async("/diag/inventory_status")
    return st

async def ads(date_from, date_to):
    st = await _get_async("/diag/ads_status")
    return st

async def reviews():
    st = await _get_async("/diag/reviews_status")
    return st