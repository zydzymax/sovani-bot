# finance_handlers.py
import datetime as dt
import os

import pytz

API_BASE = os.getenv("API_BASE", "https://justbusiness.lol/api").rstrip("/")

MSK = pytz.timezone(os.getenv("TZ", "Europe/Moscow"))


def _dstr(d):
    return d.strftime("%Y-%m-%d")


def preset_range(preset: str):
    now = dt.datetime.now(MSK)
    if preset == "today":
        f = now.replace(hour=0, minute=0, second=0, microsecond=0)
        t = now
    elif preset == "yesterday":
        y = now - dt.timedelta(days=1)
        f = y.replace(hour=0, minute=0, second=0, microsecond=0)
        t = f + dt.timedelta(days=1) - dt.timedelta(seconds=1)
    elif preset == "7d":
        t = now
        f = now - dt.timedelta(days=7)
    elif preset == "30d":
        t = now
        f = now - dt.timedelta(days=30)
    else:
        t = now
        f = now - dt.timedelta(days=7)
    return _dstr(f), _dstr(t)


async def _get_async(path, params=None, timeout=15):
    """Асинхронная замена requests.get на http_async"""
    try:
        import http_async

        result = await http_async.get_json(path, params=params)
        return result
    except Exception:
        # НИКАКИХ ФЕЙКОВЫХ ДАННЫХ! При ошибках API - прозрачная отчетность об ошибке
        raise


# ВСЕ ФЕЙКОВЫЕ ФУНКЦИИ УДАЛЕНЫ!
# СИСТЕМА РАБОТАЕТ ТОЛЬКО С РЕАЛЬНЫМИ ДАННЫМИ ИЗ API


def fmt_money(v):
    try:
        return f"{float(v):,.0f} ₽".replace(",", " ")
    except:
        return str(v)


def split_msgs(text, limit=3500):
    parts = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        cut = cut if cut != -1 else limit
        parts.append(text[:cut])
        text = text[cut:]
    parts.append(text)
    return parts


async def report_pnl(date_from, date_to, group_by="day"):
    data = await _get_async(
        "/finance/pnl", params={"date_from": date_from, "date_to": date_to, "group_by": group_by}
    )
    rows = data.get("rows", [])
    total = {
        "revenue": sum(r.get("revenue", 0) for r in rows),
        "returns": sum(r.get("returns", 0) for r in rows),
        "mp_commission": sum(r.get("mp_commission", 0) for r in rows),
        "logistics": sum(r.get("logistics", 0) for r in rows),
        "cogs": sum(r.get("cogs", 0) for r in rows),
        "ads": sum(r.get("ads", 0) for r in rows),
        "opex": sum(r.get("opex", 0) for r in rows),
        "gross_profit": sum(r.get("gross_profit", 0) for r in rows),
        "net_profit": sum(r.get("net_profit", 0) for r in rows),
    }
    lines = [f"<b>P&L {date_from} → {date_to}</b>"]
    lines.append(
        "Выручка: <b>{}</b>\nВозвраты: {}\nКомиссия МП: {}\nЛогистика: {}\nCOGS: {}\nРеклама: {}\nOPEX: {}\n<b>Валовая прибыль:</b> {}\n<b>Чистая прибыль:</b> {}".format(
            fmt_money(total["revenue"]),
            fmt_money(total["returns"]),
            fmt_money(total["mp_commission"]),
            fmt_money(total["logistics"]),
            fmt_money(total["cogs"]),
            fmt_money(total["ads"]),
            fmt_money(total["opex"]),
            fmt_money(total["gross_profit"]),
            fmt_money(total["net_profit"]),
        )
    )
    if group_by == "day" and rows:
        lines.append("\n<b>По дням:</b>")
        for r in rows[-14:]:  # последние 14 строк, чтобы влезало
            lines.append(
                "{} — выручка {}, рекл {}, чистая {}".format(
                    r.get("key"),
                    fmt_money(r.get("revenue", 0)),
                    fmt_money(r.get("ads", 0)),
                    fmt_money(r.get("net_profit", 0)),
                )
            )
    return "\n".join(lines)


async def report_dds(date_from, date_to):
    data = await _get_async("/finance/dds", params={"date_from": date_from, "date_to": date_to})
    rows = data.get("rows", [])
    total_in = sum(r.get("in", 0) for r in rows)
    total_out = sum(r.get("out", 0) for r in rows)
    net = total_in - total_out
    lines = [f"<b>DDS {date_from} → {date_to}</b>"]
    lines.append(
        f"Поступления: <b>{fmt_money(total_in)}</b>\nСписания: {fmt_money(total_out)}\n<b>Чистый поток:</b> {fmt_money(net)}"
    )
    # агрегируем по типам если есть поле type
    agg = {}
    for r in rows:
        t = r.get("type", "прочее")
        agg.setdefault(t, {"in": 0, "out": 0})
        agg[t]["in"] += r.get("in", 0)
        agg[t]["out"] += r.get("out", 0)
    if agg:
        lines.append("\n<b>По категориям:</b>")
        for t, v in agg.items():
            lines.append(f"{t}: +{fmt_money(v['in'])} / -{fmt_money(v['out'])}")
    return "\n".join(lines)


async def report_romi(date_from, date_to):
    data = await _get_async("/finance/romi", params={"date_from": date_from, "date_to": date_to})
    rows = data.get("rows", [])
    total_cost = sum(r.get("ads_cost", 0) for r in rows)
    total_profit = sum(r.get("attributed_profit", 0) for r in rows)
    romi = (total_profit / total_cost) if total_cost > 0 else 0
    lines = [f"<b>ROMI {date_from} → {date_to}</b>"]
    lines.append(
        f"Затраты на рекламу: {fmt_money(total_cost)}\nПрибыль, атрибутированная рекламе: {fmt_money(total_profit)}\n<b>ROMI:</b> {romi:.2f}"
    )
    # Топ кампаний
    rows = sorted(rows, key=lambda r: r.get("attributed_profit", 0), reverse=True)[:10]
    if rows:
        lines.append("\n<b>Топ кампаний:</b>")
        for r in rows:
            key = r.get("key", "-")
            lines.append(
                f"{key}: ROMI {r.get('romi',0):.2f}, cost {fmt_money(r.get('ads_cost',0))}, profit {fmt_money(r.get('attributed_profit',0))}"
            )
    return "\n".join(lines)
