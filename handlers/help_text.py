def help_text():
    parts = [
        "<b>SoVAni Bot — меню</b>",
        "📊 /reports — P&L, DDS, ROMI, Топ товары",
        "🔍 /check_reviews — новые отзывы за 24ч",
        "💬 /reviews_wb — отзывы WB; /reviews_oz — отзывы Ozon",
        "📦 /stock — остатки; /repl — рекомендации по поставкам",
        "💰 /finance — сводка KPI",
        "⚙️ /settings — базовые настройки (для админов)",
    ]
    return "\n".join(parts)
