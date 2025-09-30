from .api_client import _get, money, split_long, range_preset

def reviews_summary():
    j = _get("/reviews/stats")
    p = j.get("percentages", {})
    out=["<b>Отзывы — статистика</b>",
         f"Позитив: {p.get('positive',0)}%, Нейтрал: {p.get('neutral',0)}%, Негатив: {p.get('negative',0)}%"]
    return "\n".join(out)

def reviews_new_last24():
    # берём по created_at за последние 24 ч
    from datetime import datetime, timedelta
    import pytz
    from .api_client import MSK
    now = datetime.now(MSK); f = (now - timedelta(hours=24)).strftime("%Y-%m-%d")
    j = _get("/reviews", {"date_from": f})
    rows = j.get("rows",[])
    out=[f"<b>Новые отзывы (24ч):</b> {len(rows)}"]
    for r in rows[:10]:
        out.append(f"{r.get('platform').upper()} ★{r.get('rating')} {r.get('sku')}: {r.get('text')[:140]}…")
    if len(rows)>10: out.append(f"… и ещё {len(rows)-10}")
    return "\n".join(out)

def reviews_list(platform=None, rating_gte=None, rating_lte=None, status=None, limit=10, offset=0):
    j=_get("/reviews", {"platform":platform,"rating_gte":rating_gte,"rating_lte":rating_lte,"status":status,"limit":limit,"offset":offset})
    rows=j.get("rows",[])
    out=[f"<b>Отзывы {platform or ''}</b>"]
    if not rows:
        out.append("Нет данных"); return "\n".join(out)
    for r in rows:
        out.append(f"{r.get('platform').upper()} ★{r.get('rating')} [{r.get('sku')}]: {r.get('text')[:180]}… (id:{r.get('review_id')})")
    return "\n".join(out)