"""
Модуль для работы с базой данных SQLite
Создает и управляет таблицами для хранения отзывов, вопросов, шаблонов и аналитики
"""

import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import json

logger = logging.getLogger(__name__)

DB_PATH = 'sovani_bot.db'


def get_connection():
    """Получение соединения с базой данных"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Для доступа к колонкам по именам
    return conn


def init_db():
    """Инициализация базы данных - создание всех необходимых таблиц"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Таблица отзывов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id TEXT PRIMARY KEY,
                sku TEXT NOT NULL,
                text TEXT,
                rating INTEGER NOT NULL,
                has_media BOOLEAN DEFAULT FALSE,
                answer TEXT,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                answered BOOLEAN DEFAULT FALSE
            )
        ''')
        
        # Таблица вопросов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id TEXT PRIMARY KEY,
                sku TEXT NOT NULL,
                text TEXT NOT NULL,
                answer TEXT,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                answered BOOLEAN DEFAULT FALSE
            )
        ''')
        
        # Таблица шаблонов ответов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stars INTEGER NOT NULL,
                has_text BOOLEAN DEFAULT FALSE,
                has_media BOOLEAN DEFAULT FALSE,
                template_text TEXT NOT NULL,
                description TEXT
            )
        ''')
        
        # Таблица P&L данных (расширенная для детального разбора)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pnl (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                period_date DATE NOT NULL,
                date_from DATE NOT NULL,
                date_to DATE NOT NULL,
                sku TEXT,  -- NULL для общих итогов, конкретный SKU для детализации
                platform TEXT NOT NULL,  -- 'WB', 'OZON', 'TOTAL'
                revenue REAL DEFAULT 0,  -- Фактическая выручка (доставленные товары для Ozon)
                units_sold INTEGER DEFAULT 0,
                cogs REAL DEFAULT 0,
                profit REAL DEFAULT 0,
                ad_costs REAL DEFAULT 0,
                -- Детальные поля для Ozon
                orders_revenue REAL DEFAULT 0,  -- Общая сумма заказов
                orders_units INTEGER DEFAULT 0,  -- Общее количество заказанных единиц
                commission REAL DEFAULT 0,      -- Комиссия платформы
                promo_costs REAL DEFAULT 0,     -- Промо-акции
                returns_cost REAL DEFAULT 0,    -- Возвраты
                logistics_costs REAL DEFAULT 0, -- Логистика и упаковка
                other_costs REAL DEFAULT 0,     -- Прочие расходы
                transaction_count INTEGER DEFAULT 0,  -- Количество транзакций
                operation_breakdown TEXT,       -- JSON с детальным разбором операций
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица рекомендаций по пополнению
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS replenishment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT NOT NULL,
                platform TEXT NOT NULL,  -- 'WB', 'OZON'
                warehouse TEXT,  -- для Ozon указывается склад
                size TEXT,  -- для WB указывается размер
                current_stock INTEGER DEFAULT 0,
                daily_sales REAL DEFAULT 0,
                cover_days REAL DEFAULT 0,
                recommended_qty INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        logger.info("База данных инициализирована успешно")
        
        # Заполняем базовые шаблоны, если их еще нет
        _populate_default_templates(cursor, conn)
        
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def _populate_default_templates(cursor, conn):
    """Заполнение базовых шаблонов ответов"""
    cursor.execute('SELECT COUNT(*) FROM templates')
    if cursor.fetchone()[0] > 0:
        return  # Шаблоны уже есть
    
    default_templates = [
        # 5 звезд без текста
        (5, False, False, "Спасибо за высокую оценку! 🌟 Очень рады, что товар вам понравился! Команда SoVAni всегда старается для наших клиентов ❤️"),
        # 5 звезд без текста, с фото
        (5, False, True, "Вау! Спасибо за 5 звезд и прекрасное фото! 📸✨ Вы просто супер! Команда SoVAni от всей души благодарит вас! 🥰"),
        # 4 звезды без текста  
        (4, False, False, "Спасибо за хорошую оценку! 😊 Рады, что товар понравился. Всегда стремимся стать еще лучше! Команда SoVAni 💙"),
        # 4 звезды без текста, с фото
        (4, False, True, "Спасибо за 4 звезды и отличное фото! 📷 Выглядит замечательно! Команда SoVAni ценит ваш выбор! ⭐"),
        # 3 звезды без текста
        (3, False, False, "Спасибо за оценку! Надеемся, что товар служит вам хорошо. Если есть вопросы - всегда готовы помочь! Команда SoVAni 🤝"),
        # 2 звезды без текста
        (2, False, False, "Спасибо за честную оценку. Жаль, что не все идеально. Если есть проблемы - пишите, обязательно поможем! Команда SoVAni стремится к совершенству 💪"),
        # 1 звезда без текста
        (1, False, False, "Очень расстроены, что товар не оправдал ожиданий 😔 Свяжитесь с нами - разберемся и поможем! Каждый клиент важен для SoVAni 🙏"),
    ]
    
    cursor.executemany(
        'INSERT INTO templates (stars, has_text, has_media, template_text) VALUES (?, ?, ?, ?)',
        default_templates
    )
    conn.commit()
    logger.info("Базовые шаблоны ответов добавлены")


# Функции для работы с отзывами
def save_review(review_data: Dict[str, Any]) -> bool:
    """Сохранение отзыва в базу данных"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO reviews 
            (id, sku, text, rating, has_media, answer, date, answered)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            review_data['id'],
            review_data['sku'],
            review_data['text'],
            review_data['rating'],
            review_data['has_media'],
            review_data['answer'],
            review_data['date'],
            review_data['answered']
        ))
        conn.commit()
        logger.info(f"Отзыв {review_data['id']} сохранен")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения отзыва: {e}")
        return False
    finally:
        conn.close()


def get_review(review_id: str) -> Optional[Dict[str, Any]]:
    """Получение отзыва по ID"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM reviews WHERE id = ?', (review_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Ошибка получения отзыва: {e}")
        return None
    finally:
        conn.close()


def mark_review_answered(review_id: str) -> bool:
    """Отметка отзыва как отвеченного"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE reviews SET answered = TRUE WHERE id = ?', (review_id,))
        conn.commit()
        logger.info(f"Отзыв {review_id} отмечен как отвеченный")
        return True
    except Exception as e:
        logger.error(f"Ошибка обновления отзыва: {e}")
        return False
    finally:
        conn.close()


def review_exists(review_id: str) -> bool:
    """Проверка существования отзыва"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM reviews WHERE id = ?', (review_id,))
        return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Ошибка проверки отзыва: {e}")
        return False
    finally:
        conn.close()


# Функции для работы с вопросами
def save_question(question_data: Dict[str, Any]) -> bool:
    """Сохранение вопроса в базу данных"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO questions 
            (id, sku, text, answer, date, answered)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            question_data['id'],
            question_data['sku'],
            question_data['text'],
            question_data['answer'],
            question_data['date'],
            question_data['answered']
        ))
        conn.commit()
        logger.info(f"Вопрос {question_data['id']} сохранен")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения вопроса: {e}")
        return False
    finally:
        conn.close()


def get_question(question_id: str) -> Optional[Dict[str, Any]]:
    """Получение вопроса по ID"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM questions WHERE id = ?', (question_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Ошибка получения вопроса: {e}")
        return None
    finally:
        conn.close()


def mark_question_answered(question_id: str) -> bool:
    """Отметка вопроса как отвеченного"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE questions SET answered = TRUE WHERE id = ?', (question_id,))
        conn.commit()
        logger.info(f"Вопрос {question_id} отмечен как отвеченный")
        return True
    except Exception as e:
        logger.error(f"Ошибка обновления вопроса: {e}")
        return False
    finally:
        conn.close()


def question_exists(question_id: str) -> bool:
    """Проверка существования вопроса"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM questions WHERE id = ?', (question_id,))
        return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Ошибка проверки вопроса: {e}")
        return False
    finally:
        conn.close()


# Функции для работы с шаблонами
def get_template(stars: int, has_text: bool, has_media: bool) -> Optional[str]:
    """Получение шаблона ответа по параметрам"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT template_text FROM templates 
            WHERE stars = ? AND has_text = ? AND has_media = ?
            LIMIT 1
        ''', (stars, has_text, has_media))
        row = cursor.fetchone()
        return row['template_text'] if row else None
    except Exception as e:
        logger.error(f"Ошибка получения шаблона: {e}")
        return None
    finally:
        conn.close()


# Функции для работы с P&L данными
def save_pnl_data(pnl_data: List[Dict[str, Any]], date_from: str = None, date_to: str = None) -> bool:
    """Сохранение расширенных P&L данных с детальным разбором"""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Определяем период
        today = datetime.now().date()
        period_date_from = datetime.strptime(date_from, '%Y-%m-%d').date() if date_from else today
        period_date_to = datetime.strptime(date_to, '%Y-%m-%d').date() if date_to else today

        # Очищаем старые данные за этот период
        cursor.execute('DELETE FROM pnl WHERE date_from = ? AND date_to = ?',
                      (period_date_from, period_date_to))

        # Добавляем новые данные
        for data in pnl_data:
            # Сериализуем operation_breakdown в JSON
            operation_breakdown_json = json.dumps(data.get('operation_breakdown', {})) if data.get('operation_breakdown') else None

            cursor.execute('''
                INSERT INTO pnl
                (period_date, date_from, date_to, sku, platform, revenue, units_sold, cogs, profit,
                 ad_costs, orders_revenue, orders_units, commission, promo_costs, returns_cost,
                 logistics_costs, other_costs, transaction_count, operation_breakdown)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                today,  # период обновления
                period_date_from,  # начало периода данных
                period_date_to,    # конец периода данных
                data.get('sku'),
                data['platform'],
                data['revenue'],
                data['units_sold'],
                data['cogs'],
                data['profit'],
                data.get('ad_costs', 0),
                data.get('orders_revenue', 0),
                data.get('orders_units', 0),
                data.get('commission', 0),
                data.get('promo_costs', 0),
                data.get('returns_cost', 0),
                data.get('logistics_costs', 0),
                data.get('other_costs', 0),
                data.get('transaction_count', 0),
                operation_breakdown_json
            ))

        conn.commit()
        logger.info(f"Сохранено {len(pnl_data)} записей P&L за период {period_date_from} - {period_date_to}")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения P&L: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


# Функции для работы с рекомендациями по пополнению
def save_replenishment_data(replenishment_data: List[Dict[str, Any]]) -> bool:
    """Сохранение рекомендаций по пополнению"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Очищаем старые рекомендации
        cursor.execute('DELETE FROM replenishment')
        
        # Добавляем новые рекомендации
        for data in replenishment_data:
            cursor.execute('''
                INSERT INTO replenishment 
                (sku, platform, warehouse, size, current_stock, daily_sales, 
                 cover_days, recommended_qty)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['sku'],
                data['platform'],
                data.get('warehouse'),
                data.get('size'),
                data['current_stock'],
                data['daily_sales'],
                data['cover_days'],
                data['recommended_qty']
            ))
        
        conn.commit()
        logger.info(f"Сохранено {len(replenishment_data)} рекомендаций по пополнению")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения рекомендаций: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def get_latest_pnl() -> List[Dict[str, Any]]:
    """Получение последних P&L данных"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM pnl
            WHERE period_date = (SELECT MAX(period_date) FROM pnl)
            ORDER BY platform, sku
        ''')
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Ошибка получения P&L: {e}")
        return []
    finally:
        conn.close()


def get_cumulative_pnl(days: int = 30) -> Dict[str, Any]:
    """Получение нарастающего итога P&L за указанное количество дней"""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Получаем все данные за последние N дней
        cursor.execute('''
            SELECT platform,
                   SUM(revenue) as total_revenue,
                   SUM(units_sold) as total_units,
                   SUM(cogs) as total_cogs,
                   SUM(profit) as total_profit,
                   SUM(ad_costs) as total_ad_costs,
                   SUM(orders_revenue) as total_orders_revenue,
                   SUM(orders_units) as total_orders_units,
                   SUM(commission) as total_commission,
                   SUM(promo_costs) as total_promo_costs,
                   SUM(returns_cost) as total_returns_cost,
                   SUM(logistics_costs) as total_logistics_costs,
                   SUM(other_costs) as total_other_costs,
                   COUNT(*) as records_count,
                   MIN(date_from) as earliest_date,
                   MAX(date_to) as latest_date
            FROM pnl
            WHERE date_from >= date('now', '-{} days')
              AND sku IS NULL  -- только общие итоги по платформам
            GROUP BY platform
            ORDER BY platform
        '''.format(days))

        rows = cursor.fetchall()

        # Формируем структуру данных
        result = {
            'period_days': days,
            'platforms': {},
            'total': {
                'revenue': 0, 'units': 0, 'cogs': 0, 'profit': 0,
                'ad_costs': 0, 'orders_revenue': 0, 'orders_units': 0,
                'commission': 0, 'promo_costs': 0, 'returns_cost': 0,
                'logistics_costs': 0, 'other_costs': 0, 'records_count': 0
            }
        }

        # Обрабатываем данные по платформам
        for row in rows:
            platform = row['platform']
            platform_data = dict(row)

            # Вычисляем процент выкупа для Ozon
            if platform == 'OZON' and platform_data['total_orders_revenue'] > 0:
                buyout_rate = (platform_data['total_revenue'] / platform_data['total_orders_revenue']) * 100
                platform_data['buyout_rate'] = buyout_rate
            else:
                platform_data['buyout_rate'] = 0

            result['platforms'][platform] = platform_data

            # Добавляем к общему итогу
            result['total']['revenue'] += platform_data['total_revenue']
            result['total']['units'] += platform_data['total_units']
            result['total']['cogs'] += platform_data['total_cogs']
            result['total']['profit'] += platform_data['total_profit']
            result['total']['ad_costs'] += platform_data['total_ad_costs']
            result['total']['orders_revenue'] += platform_data['total_orders_revenue']
            result['total']['orders_units'] += platform_data['total_orders_units']
            result['total']['commission'] += platform_data['total_commission']
            result['total']['promo_costs'] += platform_data['total_promo_costs']
            result['total']['returns_cost'] += platform_data['total_returns_cost']
            result['total']['logistics_costs'] += platform_data['total_logistics_costs']
            result['total']['other_costs'] += platform_data['total_other_costs']
            result['total']['records_count'] += platform_data['records_count']

        # Получаем общую информацию о периоде
        if rows:
            cursor.execute('''
                SELECT MIN(date_from) as earliest_date, MAX(date_to) as latest_date
                FROM pnl
                WHERE date_from >= date('now', '-{} days')
            '''.format(days))

            period_info = cursor.fetchone()
            result['period_from'] = period_info['earliest_date']
            result['period_to'] = period_info['latest_date']

        logger.info(f"Получен нарастающий итог P&L за {days} дней")
        return result

    except Exception as e:
        logger.error(f"Ошибка получения нарастающего итога P&L: {e}")
        return {'platforms': {}, 'total': {}, 'period_days': days}
    finally:
        conn.close()


def get_pnl_history(days: int = 7) -> List[Dict[str, Any]]:
    """Получение истории P&L данных по дням"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT date_from, date_to, platform,
                   revenue, units_sold, profit, ad_costs,
                   orders_revenue, orders_units, commission,
                   promo_costs, returns_cost, logistics_costs
            FROM pnl
            WHERE date_from >= date('now', '-{} days')
              AND sku IS NULL  -- только общие итоги
            ORDER BY date_from DESC, platform
        '''.format(days))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Ошибка получения истории P&L: {e}")
        return []
    finally:
        conn.close()


def get_replenishment_recommendations() -> List[Dict[str, Any]]:
    """Получение рекомендаций по пополнению"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM replenishment 
            WHERE recommended_qty > 0
            ORDER BY platform, sku, size, warehouse
        ''')
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Ошибка получения рекомендаций: {e}")
        return []
    finally:
        conn.close()


# Служебные функции
def get_latest_reviews(limit: int = 10) -> List[Dict[str, Any]]:
    """Получение последних отзывов"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM reviews 
            ORDER BY date DESC 
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Ошибка получения отзывов: {e}")
        return []
    finally:
        conn.close()


def cleanup_old_data(days: int = 30):
    """Очистка старых данных (старше указанного количества дней)"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Удаляем старые отвеченные отзывы и вопросы
        cursor.execute('''
            DELETE FROM reviews 
            WHERE answered = TRUE AND date < datetime('now', '-{} days')
        '''.format(days))
        
        cursor.execute('''
            DELETE FROM questions 
            WHERE answered = TRUE AND date < datetime('now', '-{} days')
        '''.format(days))
        
        # Удаляем старые P&L данные
        cursor.execute('''
            DELETE FROM pnl 
            WHERE period_date < date('now', '-{} days')
        '''.format(days))
        
        conn.commit()
        logger.info(f"Очистка данных старше {days} дней выполнена")
        
    except Exception as e:
        logger.error(f"Ошибка очистки данных: {e}")
    finally:
        conn.close()