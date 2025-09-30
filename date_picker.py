"""
Утилиты для выбора дат и периодов в Telegram боте
"""

import calendar
from datetime import datetime, timedelta, date
from typing import Tuple, Optional, Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging

logger = logging.getLogger(__name__)

# Константы для ограничений по маркетплейсам
WB_MAX_DAYS = 176  # Максимум для WB API
OZON_MAX_DAYS = 180  # Максимум для Ozon API (более гибкий)
DEFAULT_MAX_DAYS = 365  # По умолчанию для общих отчетов


class DatePicker:
    """Класс для создания календарных интерфейсов выбора дат"""

    @staticmethod
    def get_predefined_periods_menu() -> InlineKeyboardMarkup:
        """Меню с предустановленными периодами"""
        kb = InlineKeyboardMarkup(row_width=2)

        # Быстрые периоды
        kb.add(
            InlineKeyboardButton("📅 Сегодня", callback_data="period:today"),
            InlineKeyboardButton("📅 Вчера", callback_data="period:yesterday")
        )
        kb.add(
            InlineKeyboardButton("📅 7 дней", callback_data="period:7d"),
            InlineKeyboardButton("📅 30 дней", callback_data="period:30d")
        )
        kb.add(
            InlineKeyboardButton("📅 Текущая неделя", callback_data="period:current_week"),
            InlineKeyboardButton("📅 Текущий месяц", callback_data="period:current_month")
        )
        kb.add(
            InlineKeyboardButton("📅 Прошлая неделя", callback_data="period:last_week"),
            InlineKeyboardButton("📅 Прошлый месяц", callback_data="period:last_month")
        )

        # Кастомный период
        kb.add(
            InlineKeyboardButton("🗓️ Выбрать даты", callback_data="period:custom")
        )

        return kb

    @staticmethod
    def get_calendar_keyboard(year: int, month: int, selection_type: str = "from") -> InlineKeyboardMarkup:
        """
        Создание календаря для выбора даты

        Args:
            year: Год
            month: Месяц (1-12)
            selection_type: 'from' для начальной даты, 'to' для конечной
        """
        kb = InlineKeyboardMarkup()

        # Название месяца и года
        month_name = calendar.month_name[month]
        kb.add(InlineKeyboardButton(
            f"📅 {month_name} {year}",
            callback_data="calendar:ignore"
        ))

        # Навигация по месяцам
        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1

        kb.add(
            InlineKeyboardButton("◀️", callback_data=f"calendar:{selection_type}:{prev_year}:{prev_month}"),
            InlineKeyboardButton("📆", callback_data="calendar:ignore"),
            InlineKeyboardButton("▶️", callback_data=f"calendar:{selection_type}:{next_year}:{next_month}")
        )

        # Дни недели
        weekdays = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
        kb.add(*[InlineKeyboardButton(day, callback_data="calendar:ignore") for day in weekdays])

        # Календарная сетка
        cal = calendar.monthcalendar(year, month)
        today = datetime.now().date()

        # Определяем минимальную доступную дату в зависимости от контекста
        if context and 'wb' in context.lower():
            max_days = WB_MAX_DAYS
        elif context and 'ozon' in context.lower():
            max_days = OZON_MAX_DAYS
        else:
            max_days = DEFAULT_MAX_DAYS

        min_allowed_date = today - timedelta(days=max_days)

        for week in cal:
            week_buttons = []
            for day in week:
                if day == 0:
                    week_buttons.append(InlineKeyboardButton(" ", callback_data="calendar:ignore"))
                else:
                    current_date = date(year, month, day)

                    # Проверяем доступность даты
                    is_too_old = current_date < min_allowed_date
                    is_future = current_date > today

                    if is_too_old or is_future:
                        # Недоступная дата - серая и без callback
                        text = f"🚫{day}"
                        callback_data = "calendar:ignore"
                    elif current_date == today:
                        # Сегодняшний день
                        text = f"🔵{day}"
                        callback_data = f"calendar:select:{selection_type}:{year}:{month}:{day}"
                    else:
                        # Доступная дата
                        text = str(day)
                        callback_data = f"calendar:select:{selection_type}:{year}:{month}:{day}"

                    week_buttons.append(InlineKeyboardButton(text, callback_data=callback_data))
            kb.add(*week_buttons)

        # Кнопки управления
        kb.add(
            InlineKeyboardButton("❌ Отмена", callback_data="calendar:cancel"),
            InlineKeyboardButton("📅 Быстрые периоды", callback_data="calendar:quick")
        )

        return kb

    @staticmethod
    def parse_predefined_period(period_code: str) -> Tuple[str, str]:
        """
        Преобразование кода периода в даты

        Args:
            period_code: Код периода (today, yesterday, 7d, etc.)

        Returns:
            Tuple[date_from, date_to] в формате YYYY-MM-DD
        """
        today = datetime.now().date()

        if period_code == "today":
            return today.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")

        elif period_code == "yesterday":
            yesterday = today - timedelta(days=1)
            return yesterday.strftime("%Y-%m-%d"), yesterday.strftime("%Y-%m-%d")

        elif period_code.endswith("d"):
            # Периоды в днях (7d, 30d, etc.)
            days = int(period_code[:-1])
            start_date = today - timedelta(days=days-1)
            return start_date.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")

        elif period_code == "current_week":
            # Текущая неделя (понедельник - воскресенье)
            start_week = today - timedelta(days=today.weekday())
            end_week = start_week + timedelta(days=6)
            return start_week.strftime("%Y-%m-%d"), end_week.strftime("%Y-%m-%d")

        elif period_code == "last_week":
            # Прошлая неделя
            last_monday = today - timedelta(days=today.weekday() + 7)
            last_sunday = last_monday + timedelta(days=6)
            return last_monday.strftime("%Y-%m-%d"), last_sunday.strftime("%Y-%m-%d")

        elif period_code == "current_month":
            # Текущий месяц (до сегодняшнего дня)
            start_month = today.replace(day=1)
            end_month = today  # Заканчиваем сегодняшним днем, чтобы избежать будущих дат
            return start_month.strftime("%Y-%m-%d"), end_month.strftime("%Y-%m-%d")

        elif period_code == "last_month":
            # Прошлый месяц
            if today.month == 1:
                start_month = today.replace(year=today.year - 1, month=12, day=1)
                end_month = today.replace(day=1) - timedelta(days=1)
            else:
                start_month = today.replace(month=today.month - 1, day=1)
                end_month = today.replace(day=1) - timedelta(days=1)
            return start_month.strftime("%Y-%m-%d"), end_month.strftime("%Y-%m-%d")

        else:
            # По умолчанию - последние 7 дней
            start_date = today - timedelta(days=6)
            return start_date.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")

    @staticmethod
    def format_period_description(date_from: str, date_to: str) -> str:
        """
        Создание описания периода на русском языке

        Args:
            date_from: Начальная дата (YYYY-MM-DD)
            date_to: Конечная дата (YYYY-MM-DD)

        Returns:
            Описание периода
        """
        try:
            from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
            to_date = datetime.strptime(date_to, "%Y-%m-%d").date()

            # Форматы дат
            from_formatted = from_date.strftime("%d.%m.%Y")
            to_formatted = to_date.strftime("%d.%m.%Y")

            # Сегодня/вчера
            today = datetime.now().date()
            yesterday = today - timedelta(days=1)

            if from_date == to_date == today:
                return "Сегодня"
            elif from_date == to_date == yesterday:
                return "Вчера"
            elif from_date == to_date:
                return f"{from_formatted}"

            # Разница в днях
            delta = (to_date - from_date).days + 1

            if delta <= 7:
                return f"Последние {delta} дн. ({from_formatted} - {to_formatted})"
            elif delta <= 31:
                return f"Последние {delta} дн. ({from_formatted} - {to_formatted})"
            else:
                return f"{from_formatted} - {to_formatted}"

        except Exception as e:
            logger.error(f"Ошибка форматирования периода: {e}")
            return f"{date_from} - {date_to}"

    @staticmethod
    def validate_date_range(date_from: str, date_to: str, context: str = None) -> Tuple[bool, str]:
        """
        Валидация диапазона дат

        Args:
            date_from: Начальная дата
            date_to: Конечная дата
            context: Контекст отчета для определения лимитов (wb_financial, ozon_financial, etc.)

        Returns:
            Tuple[is_valid, error_message]
        """
        try:
            from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
            to_date = datetime.strptime(date_to, "%Y-%m-%d").date()

            # Определяем максимальный период в зависимости от контекста
            if context and 'wb' in context.lower():
                max_days = WB_MAX_DAYS
                marketplace = "WB"
            elif context and 'ozon' in context.lower():
                max_days = OZON_MAX_DAYS
                marketplace = "Ozon"
            else:
                max_days = DEFAULT_MAX_DAYS
                marketplace = "общих отчетов"

            # Проверка логики дат
            if from_date > to_date:
                return False, "Начальная дата не может быть позже конечной"

            # Проверка диапазона с учетом маркетплейса
            period_days = (to_date - from_date).days
            if period_days > max_days:
                return False, f"Максимальный период для {marketplace}: {max_days} дней"

            # Проверка на будущие даты
            today = datetime.now().date()
            if from_date > today or to_date > today:
                return False, "Нельзя выбрать будущие даты"

            # Проверка на слишком старые даты с учетом маркетплейса
            min_date = today - timedelta(days=max_days)
            if from_date < min_date:
                return False, f"Слишком старая дата для {marketplace} (максимум {max_days} дней назад)"

            return True, ""

        except ValueError:
            return False, "Неверный формат даты"


class DateRangeManager:
    """Менеджер для сохранения выбранных дат в процессе диалога"""

    def __init__(self):
        self.user_selections: Dict[int, Dict[str, Any]] = {}

    def start_date_selection(self, user_id: int, context: str = "report"):
        """Начало выбора диапазона дат"""
        self.user_selections[user_id] = {
            'context': context,
            'date_from': None,
            'date_to': None,
            'step': 'from'  # 'from', 'to', 'complete'
        }

    def set_date_from(self, user_id: int, date_from: str):
        """Установка начальной даты"""
        if user_id in self.user_selections:
            self.user_selections[user_id]['date_from'] = date_from
            self.user_selections[user_id]['step'] = 'to'

    def set_date_to(self, user_id: int, date_to: str):
        """Установка конечной даты"""
        if user_id in self.user_selections:
            self.user_selections[user_id]['date_to'] = date_to
            self.user_selections[user_id]['step'] = 'complete'

    def get_selection(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получение выбранных дат"""
        return self.user_selections.get(user_id)

    def clear_selection(self, user_id: int):
        """Очистка выбора"""
        if user_id in self.user_selections:
            del self.user_selections[user_id]

    def is_complete(self, user_id: int) -> bool:
        """Проверка завершенности выбора"""
        selection = self.user_selections.get(user_id)
        return selection and selection.get('step') == 'complete'


# Глобальный менеджер дат
date_range_manager = DateRangeManager()


def get_enhanced_period_menu() -> InlineKeyboardMarkup:
    """Расширенное меню выбора периодов"""
    return DatePicker.get_predefined_periods_menu()


def get_calendar_for_date_selection(year: int = None, month: int = None, selection_type: str = "from", context: str = None) -> InlineKeyboardMarkup:
    """Получение календаря для выбора даты"""
    if year is None or month is None:
        now = datetime.now()
        year, month = now.year, now.month

    return DatePicker.get_calendar_keyboard(year, month, selection_type)