from .api_client import _get_async, range_preset, money, split_long

async def pnl_text(date_from, date_to, group_by="day"):
    j = await _get_async("/live/finance/pnl_v2", {"date_from":date_from,"date_to":date_to,"platform":"all"})

    # New structure: {"platforms": {"wb": {...}, "ozon": {...}}, "total": {...}}
    total = j.get("total", {})
    if not total:
        # Calculate from platforms if total not available
        wb = j.get("platforms", {}).get("wb", {})
        ozon = j.get("platforms", {}).get("ozon", {})
        total = {}
        for key in ["revenue","returns","mp_commission","logistics","cogs","ads_cost","opex","gross_profit","net_profit"]:
            wb_val = wb.get(key, 0) or 0
            ozon_val = ozon.get(key, 0) or 0
            total[key] = wb_val + ozon_val

    # Map ads_cost to ads for consistency with bot expectations
    s = {
        "revenue": total.get("revenue", 0) or 0,
        "returns": total.get("returns", 0) or 0,
        "mp_commission": total.get("mp_commission", 0) or 0,
        "logistics": total.get("logistics", 0) or 0,
        "cogs": total.get("cogs", 0) or 0,
        "ads": total.get("ads_cost", 0) or 0,  # Map ads_cost to ads
        "opex": total.get("opex", 0) or 0,
        "gross_profit": total.get("gross_profit", 0) or 0,
        "net_profit": total.get("net_profit", 0) or 0
    }
    out = [f"<b>P&L {date_from} → {date_to}</b>",
           f"Выручка: <b>{money(s['revenue'])}</b>",
           f"Возвраты: {money(s['returns'])}",
           f"Комиссия МП: {money(s['mp_commission'])}",
           f"Логистика: {money(s['logistics'])}",
           f"COGS: {money(s['cogs'])}",
           f"Реклама: {money(s['ads'])}",
           f"OPEX: {money(s['opex'])}",
           f"<b>Валовая прибыль:</b> {money(s['gross_profit'])}",
           f"<b>Чистая прибыль:</b> {money(s['net_profit'])}"]

    # Add detailed platform breakdown
    platforms = j.get("platforms", {})
    if platforms:
        out.append("\n<b>📊 По платформам:</b>")

        # WB breakdown
        wb = platforms.get("wb", {})
        wb_rev = wb.get("revenue") or 0
        wb_comm = wb.get("mp_commission") or 0
        wb_returns = wb.get("returns") or 0
        out.append(f"🟦 <b>WB:</b> выручка {money(wb_rev)}, комиссия {money(wb_comm)}, возвраты {money(wb_returns)}")

        # Ozon breakdown
        ozon = platforms.get("ozon", {})
        ozon_rev = ozon.get("revenue") or 0
        ozon_comm = ozon.get("mp_commission") or 0
        ozon_returns = ozon.get("returns") or 0
        out.append(f"🟠 <b>Ozon:</b> выручка {money(ozon_rev)}, комиссия {money(ozon_comm)}, возвраты {money(ozon_returns)}")

    # Add data quality info
    sources = j.get("sources_used", {})
    missing = j.get("missing_components", [])
    if sources:
        out.append(f"\n📋 Источники: WB({sources.get('wb_sales', {}).get('records', 0)} продаж), Ozon({sources.get('ozon_sales', {}).get('source', 'N/A')})")
    if missing:
        out.append(f"⚠️ Недостающие данные: {', '.join(missing[:3])}")

    return "\n".join(out)

async def dds_text(date_from, date_to):
    # DDS not yet available in live endpoints - return placeholder
    return f"<b>DDS {date_from} → {date_to}</b>\nПоступления: 0 ₽\nСписания: 0 ₽\nЧистый поток: 0 ₽\n\n⚠️ DDS live endpoint не реализован"

async def romi_text(date_from, date_to):
    j = await _get_async("/live/ads/overview", {"date_from":date_from,"date_to":date_to})

    # Extract totals from live ads overview response
    total = j.get("total", {})
    cost = total.get("spend", 0) or 0
    # For ROMI calculation, we'd need revenue attribution data which may not be available
    # Use spend and orders for now as proxy
    orders = total.get("orders", 0) or 0
    revenue = total.get("revenue", 0) or 0

    # Simple ROMI calculation if revenue data available
    romi = (revenue / cost) if cost > 0 else 0

    out = [f"<b>ROMI {date_from} → {date_to}</b>",
           f"Рекламные расходы: {money(cost)}",
           f"Атрибутированная прибыль: {money(revenue)}",
           f"<b>ROMI:</b> {romi:.2f}"]

    # Add platform breakdown if available
    platforms = j.get("platforms", {})
    if platforms:
        out.append("\n<b>По платформам:</b>")
        for platform_name, platform_data in platforms.items():
            platform_spend = platform_data.get("spend", 0) or 0
            if platform_spend > 0:
                out.append(f"{platform_name.upper()}: {money(platform_spend)}")

    return "\n".join(out)

async def top_sku_text(date_from, date_to, limit=10):
    # Top SKU analytics not yet available in live endpoints
    return f"<b>Топ SKU {date_from} → {date_to}</b>\n⚠️ Аналитика по SKU не реализована в live endpoints"