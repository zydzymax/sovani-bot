#!/usr/bin/env python3
"""Telegram bot launcher - minimal version without legacy imports"""

import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.logging import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Load token from .env
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in .env")

logger.info(f"Starting bot with token: {BOT_TOKEN[:10]}...")

# Initialize bot
bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


# Simple test handler
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    """Handler for /start command"""
    await message.answer(
        "👋 Привет! Бот SoVAni запущен.\n\n"
        "Доступные команды:\n"
        "/start - Это сообщение\n"
        "/status - Статус системы"
    )


@dp.message_handler(commands=['status'])
async def cmd_status(message: types.Message):
    """Handler for /status command"""
    try:
        # Check database
        from app.core.database import get_db
        db = next(get_db())

        await message.answer(
            "✅ Бот работает\n"
            "✅ База данных подключена\n"
            f"🤖 Токен: {BOT_TOKEN[:10]}..."
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


async def on_startup(dp):
    """On startup"""
    logger.info("Bot started successfully!")


async def on_shutdown(dp):
    """On shutdown"""
    logger.info("Bot shutting down...")
    await bot.close()


if __name__ == '__main__':
    executor.start_polling(
        dp,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True
    )
