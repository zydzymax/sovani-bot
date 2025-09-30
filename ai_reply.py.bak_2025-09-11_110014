"""
Модуль для генерации ответов на отзывы и вопросы с помощью OpenAI ChatGPT
Использует фирменный стиль SoVAni: дружелюбный, с юмором, профессиональный
"""

import logging
from typing import Dict, Any, Optional
import openai
import asyncio
from config import Config
from db import get_template

logger = logging.getLogger(__name__)

# Инициализация OpenAI
openai.api_key = Config.OPENAI_API_KEY


def get_system_prompt(review_data: Dict[str, Any]) -> str:
    """Генерация системного промпта в зависимости от данных отзыва"""
    
    rating = review_data.get('rating', 3)
    has_media = review_data.get('has_media', False)
    platform = review_data.get('platform', 'WB')
    
    base_prompt = """Ты - менеджер по работе с клиентами бренда SoVAni, дружелюбный и профессиональный помощник. 

Бренд SoVAni:
- Молодой и современный бренд
- Дружелюбный и открытый стиль общения
- Использует легкий юмор, но остается профессиональным
- Ценит каждого клиента
- Всегда готов помочь и решить проблемы

Твоя задача - написать ответ на отзыв покупателя."""
    
    # Настройки в зависимости от рейтинга
    if rating >= 5:
        tone_instruction = """
Стиль ответа для 5 звезд:
- Искренняя радость и благодарность
- Выражай восторг, но не переигрывай
- Можешь использовать эмодзи умеренно (1-2 шт.)
- Подчеркни, что команда SoVAni старается для клиентов
"""
    elif rating == 4:
        tone_instruction = """
Стиль ответа для 4 звезд:
- Благодарность за хорошую оценку
- Легкая мотивация стать еще лучше
- Дружелюбный тон
- Покажи, что ценишь честную оценку
"""
    elif rating == 3:
        tone_instruction = """
Стиль ответа для 3 звезд:
- Спокойная благодарность
- Предложение помощи
- Готовность улучшаться
- Не показывай разочарование
"""
    elif rating == 2:
        tone_instruction = """
Стиль ответа для 2 звезд:
- Сожаление о проблемах
- Готовность помочь и разобраться
- Покажи, что SoVAni стремится к совершенству
- Предложи связаться для решения вопросов
"""
    else:  # rating == 1
        tone_instruction = """
Стиль ответа для 1 звезды:
- Искренние извинения
- Готовность разобраться в ситуации
- Предложение конкретной помощи
- Подчеркни важность каждого клиента для SoVAni
- Предложи личный контакт для решения
"""
    
    media_instruction = ""
    if has_media:
        media_instruction = "\n- Обязательно поблагодари за фото/видео (они помогают другим покупателям)"
    
    length_instruction = "\n\nОтвет должен быть коротким (максимум 2-3 предложения), естественным и искренним."
    
    return base_prompt + tone_instruction + media_instruction + length_instruction


async def generate_review_reply(review: Dict[str, Any]) -> str:
    """Генерация ответа на отзыв"""
    
    # Сначала попробуем найти готовый шаблон для отзывов без текста
    review_text = review.get('text', '').strip()
    rating = review.get('rating', 0)
    has_media = review.get('has_media', False)
    
    if not review_text:
        # Отзыв без текста - используем шаблон
        template = get_template(rating, False, has_media)
        if template:
            logger.info(f"Использован шаблон для отзыва без текста ({rating} звезд)")
            return template
    
    # Отзыв с текстом - генерируем через ChatGPT
    try:
        system_prompt = get_system_prompt(review)
        
        user_message = f"""
Отзыв покупателя:
Рейтинг: {rating} звезд
Текст: "{review_text}"
{f'К отзыву приложено фото/видео' if has_media else ''}
Товар: {review.get('sku', 'N/A')}

Напиши подходящий ответ от лица бренда SoVAni.
"""
        
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: openai.ChatCompletion.create(
                model=Config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=200,
                temperature=0.8,
                timeout=30
            )
        )
        
        generated_answer = response.choices[0].message.content.strip()
        logger.info(f"Сгенерирован ответ на отзыв через ChatGPT")
        return generated_answer
        
    except openai.error.RateLimitError:
        logger.warning("OpenAI: превышен лимит запросов")
        return get_fallback_review_response(rating, has_media)
    
    except openai.error.InvalidRequestError as e:
        logger.error(f"OpenAI: некорректный запрос - {e}")
        return get_fallback_review_response(rating, has_media)
    
    except Exception as e:
        logger.error(f"Ошибка генерации ответа на отзыв: {e}")
        return get_fallback_review_response(rating, has_media)


async def generate_question_reply(question: Dict[str, Any]) -> str:
    """Генерация ответа на вопрос покупателя"""
    
    try:
        system_prompt = """Ты - менеджер по работе с клиентами бренда SoVAni.

Бренд SoVAni:
- Молодой и современный бренд
- Дружелюбный, открытый стиль общения  
- Профессиональный подход
- Всегда готов помочь и дать полезную информацию

Твоя задача - ответить на вопрос покупателя о товаре.

Стиль ответа:
- Дружелюбный и полезный
- Конкретная информация (если знаешь)
- Если не знаешь точного ответа - предложи связаться напрямую
- Поблагодари за интерес к товару
- Максимум 2-3 предложения

Избегай:
- Излишне длинных объяснений
- Технического жаргона
- Неуверенности в тоне"""
        
        question_text = question.get('text', '')
        sku = question.get('sku', 'N/A')
        
        user_message = f"""
Вопрос покупателя о товаре {sku}:
"{question_text}"

Напиши полезный ответ от лица бренда SoVAni.
"""
        
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: openai.ChatCompletion.create(
                model=Config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=150,
                temperature=0.7,
                timeout=30
            )
        )
        
        generated_answer = response.choices[0].message.content.strip()
        logger.info(f"Сгенерирован ответ на вопрос через ChatGPT")
        return generated_answer
        
    except openai.error.RateLimitError:
        logger.warning("OpenAI: превышен лимит запросов")
        return get_fallback_question_response()
    
    except Exception as e:
        logger.error(f"Ошибка генерации ответа на вопрос: {e}")
        return get_fallback_question_response()


def get_fallback_review_response(rating: int, has_media: bool = False) -> str:
    """Резервный ответ на отзыв при ошибке ChatGPT"""
    
    media_part = " Спасибо за фото!" if has_media else ""
    
    if rating >= 5:
        return f"Спасибо за отличную оценку!{media_part} Команда SoVAni очень рада, что товар понравился! ⭐"
    elif rating == 4:
        return f"Благодарим за хорошую оценку!{media_part} Стараемся становиться еще лучше! 😊"
    elif rating == 3:
        return f"Спасибо за отзыв!{media_part} Если есть вопросы - всегда готовы помочь!"
    elif rating == 2:
        return f"Спасибо за честность.{media_part} Свяжитесь с нами - разберемся и поможем!"
    else:
        return f"Сожалеем, что не оправдали ожидания.{media_part} Напишите нам - обязательно поможем! 🙏"


def get_fallback_question_response() -> str:
    """Резервный ответ на вопрос при ошибке ChatGPT"""
    return "Спасибо за интерес к нашему товару! Для получения подробной информации свяжитесь с нами напрямую - с радостью поможем! 😊"


async def test_openai_connection() -> bool:
    """Тестирование подключения к OpenAI API"""
    try:
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Привет! Это тест."}],
                max_tokens=10,
                timeout=15
            )
        )
        
        if response and response.choices:
            logger.info("OpenAI API: соединение успешно")
            return True
            
    except openai.error.AuthenticationError:
        logger.error("OpenAI API: неверный API ключ")
    except openai.error.RateLimitError:
        logger.warning("OpenAI API: превышен лимит запросов")
        return True  # Подключение работает, но лимит
    except Exception as e:
        logger.error(f"OpenAI API: ошибка соединения - {e}")
    
    return False


# Дополнительные утилиты для работы с контекстом
def truncate_text(text: str, max_length: int = 500) -> str:
    """Обрезка длинного текста для экономии токенов"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


def clean_review_text(text: str) -> str:
    """Очистка текста отзыва от лишних символов"""
    if not text:
        return ""
    
    # Убираем лишние пробелы и переносы строк
    cleaned = " ".join(text.strip().split())
    
    # Ограничиваем длину
    return truncate_text(cleaned, 400)


# Кэш для часто используемых ответов (опционально)
_response_cache = {}

async def get_cached_response(key: str, generator_func, *args, **kwargs) -> str:
    """Получение ответа с кэшированием"""
    if key in _response_cache:
        logger.info(f"Использован кэшированный ответ: {key}")
        return _response_cache[key]
    
    response = await generator_func(*args, **kwargs)
    _response_cache[key] = response
    
    # Ограничиваем размер кэша
    if len(_response_cache) > 100:
        # Удаляем случайный элемент
        _response_cache.pop(next(iter(_response_cache)))
    
    return response