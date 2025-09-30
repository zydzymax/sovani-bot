"""
Продвинутый прогресс-бар для Telegram с визуализацией этапов обработки
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from aiogram import types
from dataclasses import dataclass
import math

logger = logging.getLogger(__name__)


@dataclass
class ProgressBar:
    current: int
    total: int
    width: int = 20
    fill_char: str = "█"
    empty_char: str = "░"

    def render(self) -> str:
        """Генерация визуального прогресс-бара"""
        if self.total == 0:
            return f"{self.empty_char * self.width} 0%"

        progress = self.current / self.total
        filled_width = int(progress * self.width)

        bar = self.fill_char * filled_width + self.empty_char * (self.width - filled_width)
        percentage = int(progress * 100)

        return f"{bar} {percentage}%"


class TelegramProgressManager:
    """Менеджер прогресса для Telegram с красивой визуализацией"""

    def __init__(self):
        self._active_jobs = {}
        self._update_intervals = {}

    async def create_progress_message(
        self,
        chat: types.Chat,
        initial_text: str = "🚀 Начинаю обработку данных..."
    ) -> types.Message:
        """Создание начального сообщения прогресса"""
        from bot import bot  # Импорт должен быть внутри функции

        message = await bot.send_message(
            chat.id,
            initial_text,
            parse_mode='Markdown'
        )

        return message

    async def update_stage_progress(
        self,
        message: types.Message,
        stage_name: str,
        stage_number: int,
        total_stages: int,
        stage_progress: int = 0,
        stage_total: int = 100,
        details: Dict[str, Any] = None
    ):
        """Обновление прогресса этапа с визуализацией"""

        # Общий прогресс по этапам
        overall_progress = ProgressBar(stage_number - 1, total_stages)

        # Прогресс текущего этапа
        current_stage_progress = ProgressBar(stage_progress, stage_total)

        # Эмодзи для этапов
        stage_emojis = {
            1: "📋",  # Инициализация
            2: "🟣",  # WB
            3: "🔵",  # Ozon
            4: "🔢"   # Агрегация
        }

        stage_emoji = stage_emojis.get(stage_number, "⚡")

        # Формируем текст
        text_lines = [
            f"{stage_emoji} **ЭТАП {stage_number}/{total_stages}: {stage_name.upper()}**",
            "",
            f"🔄 Общий прогресс: {overall_progress.render()}",
            f"⚡ Текущий этап: {current_stage_progress.render()}",
            ""
        ]

        # Добавляем детали если есть
        if details:
            for key, value in details.items():
                if key == 'current_chunk':
                    text_lines.append(f"📅 Период: {value}")
                elif key == 'chunks_processed':
                    text_lines.append(f"📊 Обработано: {value}")
                elif key == 'estimated_time':
                    text_lines.append(f"⏱️ Осталось: ~{value} мин")
                elif key == 'throughput':
                    text_lines.append(f"🚀 Скорость: {value}")
                elif key == 'errors':
                    text_lines.append(f"⚠️ Ошибок: {value}")

        # Добавляем время
        text_lines.append(f"🕐 Обновлено: {datetime.now().strftime('%H:%M:%S')}")

        text = "\\n".join(text_lines)

        try:
            await message.edit_text(text, parse_mode='Markdown')
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                logger.error(f"Ошибка обновления прогресса: {e}")

    async def update_wb_processing_progress(
        self,
        message: types.Message,
        chunk_index: int,
        total_chunks: int,
        chunk_from: str,
        chunk_to: str,
        orders_count: int = 0,
        sales_count: int = 0,
        advertising_spend: float = 0,
        start_time: datetime = None
    ):
        """Специализированное обновление для обработки WB"""

        # Рассчитываем время
        elapsed_time = ""
        estimated_remaining = ""

        if start_time:
            elapsed = datetime.now() - start_time
            elapsed_minutes = elapsed.total_seconds() / 60

            if chunk_index > 0:
                avg_time_per_chunk = elapsed_minutes / chunk_index
                remaining_chunks = total_chunks - chunk_index
                estimated_minutes = remaining_chunks * avg_time_per_chunk
                estimated_remaining = f"{estimated_minutes:.0f} мин"

            elapsed_time = f"{elapsed_minutes:.1f} мин"

        # Прогресс-бар
        progress_bar = ProgressBar(chunk_index, total_chunks, width=25)

        text = f"""🟣 **WILDBERRIES ОБРАБОТКА**

{progress_bar.render()}

📅 **Текущий период:**
{chunk_from} → {chunk_to}

📊 **Прогресс:** {chunk_index}/{total_chunks} чанков

📈 **Накоплено данных:**
• 📋 Заказов: **{orders_count:,}**
• ✅ Продаж: **{sales_count:,}**
• 💰 Реклама: **{advertising_spend:,.0f} ₽**

⏱️ **Время:**
• Прошло: {elapsed_time}
• Осталось: ~{estimated_remaining}

🔄 Получаю данные из API..."""

        try:
            await message.edit_text(text, parse_mode='Markdown')
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                logger.error(f"Ошибка обновления WB прогресса: {e}")

    async def update_ozon_processing_progress(
        self,
        message: types.Message,
        chunk_index: int,
        total_chunks: int,
        chunk_from: str,
        chunk_to: str,
        fbo_count: int = 0,
        fbs_count: int = 0,
        revenue: float = 0,
        start_time: datetime = None
    ):
        """Специализированное обновление для обработки Ozon"""

        # Рассчитываем время
        elapsed_time = ""
        estimated_remaining = ""

        if start_time:
            elapsed = datetime.now() - start_time
            elapsed_minutes = elapsed.total_seconds() / 60

            if chunk_index > 0:
                avg_time_per_chunk = elapsed_minutes / chunk_index
                remaining_chunks = total_chunks - chunk_index
                estimated_minutes = remaining_chunks * avg_time_per_chunk
                estimated_remaining = f"{estimated_minutes:.0f} мин"

            elapsed_time = f"{elapsed_minutes:.1f} мин"

        # Прогресс-бар
        progress_bar = ProgressBar(chunk_index, total_chunks, width=25)

        text = f"""🔵 **OZON ОБРАБОТКА**

{progress_bar.render()}

📅 **Текущий период:**
{chunk_from} → {chunk_to}

📊 **Прогресс:** {chunk_index}/{total_chunks} чанков

📈 **Накоплено данных:**
• 📦 FBO заказов: **{fbo_count:,}**
• 📊 FBS транзакций: **{fbs_count:,}**
• 💰 Выручка: **{revenue:,.0f} ₽**

⏱️ **Время:**
• Прошло: {elapsed_time}
• Осталось: ~{estimated_remaining}

🔄 Получаю транзакции..."""

        try:
            await message.edit_text(text, parse_mode='Markdown')
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                logger.error(f"Ошибка обновления Ozon прогресса: {e}")

    async def show_final_results(
        self,
        message: types.Message,
        result: Dict[str, Any],
        processing_time_minutes: float
    ):
        """Показ финальных результатов с красивым форматированием"""

        # Извлекаем данные
        total_revenue = result.get('total_revenue', 0)
        total_units = result.get('total_units', 0)
        net_profit = result.get('net_profit', 0)

        wb_data = result.get('wb_data', {})
        ozon_data = result.get('ozon_data', {})

        # Рассчитываем метрики
        profit_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0

        # Создаем красивый отчет
        text = f"""✅ **ОБРАБОТКА ЗАВЕРШЕНА!**

🎯 **ОСНОВНЫЕ ПОКАЗАТЕЛИ:**
💰 Общая выручка: **{total_revenue:,.0f} ₽**
📦 Всего единиц: **{total_units:,}**
🎯 Чистая прибыль: **{net_profit:,.0f} ₽**
📊 Маржинальность: **{profit_margin:.1f}%**

🟣 **WILDBERRIES:**
• 📋 Заказов: {wb_data.get('orders_count', 0):,}
• ✅ Продаж: {wb_data.get('sales_count', 0):,}
• 💰 Выручка: {wb_data.get('revenue', 0):,.0f} ₽
• 📊 Выкуп: {wb_data.get('buyout_rate', 0):.1f}%
• 🎯 Реклама: {wb_data.get('advertising_spend', 0):,.0f} ₽

🔵 **OZON:**
• 📦 Операций: {ozon_data.get('units', 0):,}
• 💰 Выручка: {ozon_data.get('revenue', 0):,.0f} ₽
• 📊 FBO: {ozon_data.get('fbo_orders_count', 0):,}
• 📈 FBS: {ozon_data.get('fbs_transactions_count', 0):,}

⏱️ **ВРЕМЯ ОБРАБОТКИ:**
🕐 {processing_time_minutes:.1f} минут

🔥 Данные получены из реальных API!"""

        try:
            await message.edit_text(text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Ошибка показа финальных результатов: {e}")

    async def show_error_message(
        self,
        message: types.Message,
        error: str,
        stage: str = "обработки",
        retry_available: bool = False
    ):
        """Показ сообщения об ошибке"""

        text = f"""❌ **ОШИБКА {stage.upper()}**

🚫 Произошла ошибка во время {stage}:

`{error[:200]}{'...' if len(error) > 200 else ''}`

⏱️ Время ошибки: {datetime.now().strftime('%H:%M:%S')}

{'🔄 Попробуйте повторить запрос' if retry_available else ''}"""

        try:
            await message.edit_text(text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Ошибка показа сообщения об ошибке: {e}")

    def create_status_summary(self, stats: Dict[str, Any]) -> str:
        """Создание краткой сводки статуса"""

        lines = ["📊 **СТАТУС СИСТЕМЫ:**", ""]

        if 'cache_stats' in stats:
            cache = stats['cache_stats']
            lines.extend([
                f"💾 Кеш: {cache.get('total_chunks', 0)} чанков",
                f"🟣 WB кеш: {cache.get('wb_chunks', 0)}",
                f"🔵 Ozon кеш: {cache.get('ozon_chunks', 0)}",
                ""
            ])

        if 'active_jobs' in stats:
            jobs = stats['active_jobs']
            lines.extend([
                f"⚡ Активных задач: {len(jobs)}",
                ""
            ])

        if 'performance' in stats:
            perf = stats['performance']
            lines.extend([
                f"🚀 Производительность:",
                f"• API запросов/мин: {perf.get('requests_per_minute', 0)}",
                f"• Средн. время чанка: {perf.get('avg_chunk_time', 0):.1f}с",
                ""
            ])

        lines.append(f"🕐 {datetime.now().strftime('%H:%M:%S')}")

        return "\\n".join(lines)


# Глобальный экземпляр
telegram_progress = TelegramProgressManager()