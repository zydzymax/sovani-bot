from .api_client import _get_async, money

async def stock_snapshot(platform=None, warehouse=None, limit=20):
    j=await _get_async("/inventory/stock_snapshot", {"platform":platform,"warehouse":warehouse,"limit":limit})
    rows=j.get("rows",[])
    out=["<b>Остатки</b>"]
    if not rows:
        out.append("Нет данных"); return "\n".join(out)
    for r in rows[:20]:
        out.append(f"{r.get('platform')} {r.get('warehouse_code','?')} — {r.get('sku')}: {int(r.get('available',0))} шт")
    if len(rows)>20: out.append(f"… и ещё {len(rows)-20}")
    return "\n".join(out)

async def repl_recommendations(horizon_days=14, platform=None, warehouse=None):
    j=await _get_async("/inventory/replenishment", {"horizon_days":horizon_days,"platform":platform,"warehouse":warehouse})
    rows=j.get("rows",[])
    out=[f"<b>Рекомендации по поставкам (горизонт {horizon_days} д)</b>"]
    if not rows:
        out.append("Нет данных"); return "\n".join(out)
    for r in rows[:20]:
        note=r.get("note","")
        out.append(f"{r.get('platform')} {r.get('warehouse_code','?')} — {r.get('sku')}: к заказу {int(r.get('to_order',0))} (покрытие {r.get('cover_days',0)}д) {note}")
    if len(rows)>20: out.append(f"… и ещё {len(rows)-20}")
    return "\n".join(out)