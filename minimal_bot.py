#!/usr/bin/env python3
"""Minimal Telegram bot with TMA button only"""

import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, types
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

# Load .env file
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get token from environment - try multiple names
TOKEN = (
    os.getenv("TELEGRAM_BOT_TOKEN") or 
    os.getenv("TG_BOT_TOKEN") or 
    os.getenv("TELEGRAM_TOKEN") or
    os.getenv("BOT_TOKEN")
)
if not TOKEN:
    raise RuntimeError(f"No bot token found. Checked: TELEGRAM_BOT_TOKEN, TG_BOT_TOKEN, TELEGRAM_TOKEN, BOT_TOKEN")

logger.info(f"Bot token loaded: {TOKEN[:10]}...")

# Initialize bot
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)


@dp.message_handler(commands=["start", "help"])
async def send_welcome(message: types.Message):
    """Send welcome message with TMA button"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    
    # Web App button
    web_app_button = KeyboardButton(
        text="📊 Открыть SoVAni Analytics",
        web_app=WebAppInfo(url="https://app.justbusiness.lol/")
    )
    keyboard.add(web_app_button)
    
    await message.answer(
        "🎆 <b>Добро пожаловать в SoVAni Bot!</b>\n\n"
        "📊 Нажмите кнопку ниже чтобы открыть аналитику\n"
        "💡 Все данные загружаются из WB и Ozon API",
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def main():
    """Start bot"""
    logger.info("Starting minimal TMA bot...")
    try:
        await dp.start_polling()
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
