import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import database as db
from lifecycle import LifecycleManager

# Настройка логирования, чтобы видеть ошибки в консоли
logging.basicConfig(level=logging.INFO)

# Токен твоего Мастер-бота (потом вынесем в .env)
API_TOKEN = 'YOUR_MASTER_BOT_TOKEN'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    # Регистрация пользователя в БД, если его там нет
    await db.add_user(user_id)
    
    # Простейшая проверка подписки (Gatekeeper)
    # В реальном проекте здесь будет вызов bot.get_chat_member
    is_sub = True # Заглушка: пока считаем, что все подписаны
    
    status = await LifecycleManager.get_user_status(user_id, is_sub)
    
    if status == "active":
        await message.answer(f"Привет, Император! Твой статус: {status}. Ты можешь создать бота.")
    else:
        await message.answer(f"Твой бот заморожен или неактивен. Статус: {status}. Подпишись на канал!")

async def on_startup():
    # Создаем таблицы в БД при запуске
    await db.init_db()
    logging.info("База данных инициализирована.")

async def main():
    await on_startup()
    
    # Запускаем две задачи параллельно:
    # 1. Опрос обновлений Telegram (Polling)
    # 2. Фоновый биллинг (списание дней)
    await asyncio.gather(
        dp.start_polling(bot),
        LifecycleManager.daily_billing()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")
      
