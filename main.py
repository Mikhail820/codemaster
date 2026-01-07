import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import database as db
from lifecycle import LifecycleManager
from config import BOT_TOKEN, CHANNEL_ID

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)

# Инициализация бота и диспетчера
# Используем DefaultBotProperties для автоматической поддержки Markdown/HTML
bot = Bot(
    token=BOT_TOKEN, 
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    # 1. Регистрация/проверка пользователя в БД
    await db.add_user(user_id)
    
    # 2. Проверка подписки на канал (реальный вызов API Telegram)
    is_sub = False
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            is_sub = True
    except Exception as e:
        logging.error(f"Ошибка проверки подписки: {e}")

    # 3. Получение статуса через Lifecycle
    status = await LifecycleManager.get_user_status(user_id, is_sub)
    
    # 4. Логика ответов
    if status == "active":
        await message.answer(
            f"<b>Добро пожаловать в CodeMaster!</b>\n\n"
            f"Ваш статус: 🟢 ACTIVE\n"
            f"Вы можете управлять своими ботами-визитками."
        )
    elif status == "frozen":
        await message.answer(
            f"❄️ <b>Ваш аккаунт заморожен.</b>\n\n"
            f"Для активации необходимо подписаться на наш канал: {CHANNEL_ID}\n"
            f"После подписки снова введите /start"
        )
    elif status == "expired":
        await message.answer(
            f"⏳ <b>Дни обслуживания закончились.</b>\n\n"
            f"Пополните баланс или пригласите друзей, чтобы получить бонусные дни!"
        )

async def on_startup():
    # Инициализируем таблицы БД
    await db.init_db()
    logging.info("--- СИСТЕМА ЗАПУЩЕНА И БАЗА ДАННЫХ ГОТОВА ---")

async def main():
    dp.startup.register(on_startup)
    
    # Запускаем две независимые задачи:
    # 1. Обработка сообщений (Polling)
    # 2. Ежедневный биллинг (списание дней)
    await asyncio.gather(
        dp.start_polling(bot),
        LifecycleManager.daily_billing()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("--- СИСТЕМА ОСТАНОВЛЕНА ---")
