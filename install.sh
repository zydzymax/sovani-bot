#!/bin/bash

# Скрипт установки и запуска SoVAni Bot
# Автоматически устанавливает зависимости и настраивает сервис

set -e

echo "🤖 Установка SoVAni Telegram Bot"
echo "=================================="

# Проверяем, что мы в правильной директории
if [ ! -f "bot.py" ]; then
    echo "❌ Ошибка: Запустите скрипт из директории с ботом"
    exit 1
fi

# Устанавливаем Python зависимости
echo "📦 Установка Python зависимостей..."
pip3 install -r requirements.txt

# Создаем директорию для отчетов
echo "📁 Создание директории для отчетов..."
mkdir -p reports
chmod 755 reports

# Проверяем конфигурацию
echo "🔧 Проверка конфигурации..."
python3 -c "from config import Config; Config.print_config_status(); Config.validate_config()" || {
    echo "❌ Ошибка конфигурации. Проверьте настройки в config.py"
    echo "💡 Не забудьте указать:"
    echo "   - OPENAI_API_KEY (в переменных окружения или .env)"
    echo "   - MANAGER_CHAT_ID (ID вашего Telegram чата)"
    exit 1
}

# Копируем systemd service файл
echo "⚙️ Настройка systemd сервиса..."
sudo cp sovani-bot.service /etc/systemd/system/
sudo systemctl daemon-reload

# Инициализируем базу данных
echo "🗄️ Инициализация базы данных..."
python3 -c "from db import init_db; init_db()"

# Тестируем подключения к API
echo "🔌 Тестирование API подключений..."
python3 -c "
import asyncio
from api_clients import test_wb_connection, test_ozon_connection
from ai_reply import test_openai_connection

async def test_apis():
    wb_ok = await test_wb_connection()
    ozon_ok = await test_ozon_connection()
    openai_ok = await test_openai_connection()
    
    print(f'WB API: {\"✅ OK\" if wb_ok else \"❌ Ошибка\"}')
    print(f'Ozon API: {\"✅ OK\" if ozon_ok else \"❌ Ошибка\"}')
    print(f'OpenAI API: {\"✅ OK\" if openai_ok else \"❌ Ошибка\"}')
    
    return wb_ok or ozon_ok  # Хотя бы один маркетплейс должен работать

asyncio.run(test_apis())
" || echo "⚠️ Некоторые API могут быть недоступны. Проверьте токены."

# Предлагаем запустить сервис
echo ""
echo "✅ Установка завершена!"
echo ""
echo "🚀 Для запуска бота как сервиса выполните:"
echo "   sudo systemctl enable sovani-bot"
echo "   sudo systemctl start sovani-bot"
echo ""
echo "📊 Для проверки статуса:"
echo "   sudo systemctl status sovani-bot"
echo ""
echo "📝 Для просмотра логов:"
echo "   sudo journalctl -u sovani-bot -f"
echo ""
echo "🔧 Для ручного запуска (в режиме отладки):"
echo "   python3 bot.py"
echo ""
echo "💡 Не забудьте:"
echo "   1. Указать OPENAI_API_KEY и MANAGER_CHAT_ID в переменных окружения"
echo "   2. Загрузить файлы отчетов в папку reports/"
echo "   3. Запустить бота командой /start в Telegram"