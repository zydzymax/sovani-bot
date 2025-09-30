import os, requests, datetime as dt, pytz
from dateutil.relativedelta import relativedelta

API_BASE = os.getenv("API_BASE","https://justbusiness.lol/api").rstrip("/")
SERVICE_TOKEN = os.getenv("INTERNAL_API_TOKEN","")
MSK = pytz.timezone(os.getenv("TZ","Europe/Moscow"))

def _get(path, params=None, timeout=20):
    """Синхронная функция для получения данных"""
    try:
        headers = {"Authorization": f"Bearer {SERVICE_TOKEN}"} if SERVICE_TOKEN else {}
        response = requests.get(f"{API_BASE}{path}", params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {}

async def _get_async(path, params=None, timeout=20):
    """Асинхронная замена requests.get на http_async"""
    try:
        import http_async
        result = await http_async.get_json(path, params=params)
        return result
    except Exception as e:
        raise

def dstr(d): return d.strftime("%Y-%m-%d")

def range_preset(preset:str):
    now = dt.datetime.now(MSK)
    if preset=="today":
        f = now.replace(hour=0,minute=0,second=0,microsecond=0); t=now
    elif preset=="yesterday":
        y = now - dt.timedelta(days=1)
        f = y.replace(hour=0,minute=0,second=0,microsecond=0); t=f+dt.timedelta(days=1)
    elif preset=="7d":
        f = now - dt.timedelta(days=7); t=now
    else:
        f = now - dt.timedelta(days=30); t=now
    return dstr(f), dstr(t)

def money(v):
    try: return f"{float(v):,.0f} ₽".replace(",", " ")
    except: return str(v)

def split_long(text, limit=3500):
    parts=[]
    while len(text)>limit:
        cut = text.rfind("\n",0,limit)
        if cut<0: cut=limit
        parts.append(text[:cut]); text=text[cut:]
    parts.append(text)
    return parts

