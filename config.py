import os
from dotenv import load_dotenv

# Загружаем переменные из файла .env
load_dotenv()

# Токен Мастер-бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_token_here")

# ID канала для проверки подписки
CHANNEL_ID = os.getenv("CHANNEL_ID", "@your_channel")

# Секретный ключ для шифрования (тот, что из database.py)
CRYPTO_KEY = os.getenv("CRYPTO_KEY", "your-base64-key-here=")

# Режим отладки (True/False)
DEBUG = os.getenv("DEBUG", "True") == "True"
