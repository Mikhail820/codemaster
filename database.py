import aiosqlite
import json
from datetime import datetime, date
from cryptography.fernet import Fernet

# В 2026 году безопасность — приоритет. 
# Ключ шифрования для токенов клиентов (храни его в .env)
# SECRET_KEY = Fernet.generate_key() 
SECRET_KEY = b'your-secure-base64-key-here='
cipher = Fernet(SECRET_KEY)

DB_PATH = "codemaster_v1.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # 1. ТАБЛИЦА ПОЛЬЗОВАТЕЛЕЙ И БАЛАНСОВ
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, -- Telegram ID
            referrer_id INTEGER,
            trial_days_balance INTEGER DEFAULT 10,
            paid_days_balance INTEGER DEFAULT 0,
            bonus_days_balance INTEGER DEFAULT 0,
            current_status TEXT DEFAULT 'frozen', -- active/frozen/expired/deleted
            is_sub_active BOOLEAN DEFAULT 0,
            is_premium BOOLEAN DEFAULT 0,
            cohort_date DATE DEFAULT (CURRENT_DATE),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (referrer_id) REFERENCES users(user_id)
        )''')

        # 2. ЖУРНАЛ ОПЕРАЦИЙ (Твой аудит)
        await db.execute('''CREATE TABLE IF NOT EXISTS days_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT, -- 'grant', 'purchase', 'referral', 'consumption'
            days_change INTEGER,
            balance_type TEXT, -- 'trial', 'paid', 'bonus'
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')

        # 3. БОТЫ КЛИЕНТОВ (Шифрованные)
        await db.execute('''CREATE TABLE IF NOT EXISTS bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER,
            token_encrypted TEXT NOT NULL,
            config_json TEXT DEFAULT '{}',
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (owner_id) REFERENCES users(user_id)
        )''')

        # 4. РЕФЕРАЛЬНЫЕ СОБЫТИЯ
        await db.execute('''CREATE TABLE IF NOT EXISTS referral_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER UNIQUE,
            stage TEXT, -- 'registered', 'bot_created', 'first_payment'
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')

        await db.commit()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def encrypt_token(token: str) -> str:
    return cipher.encrypt(token.encode()).decode()

async def add_days_transaction(user_id, t_type, change, b_type):
    """Фиксирует каждое изменение баланса в аудите"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO days_transactions (user_id, type, days_change, balance_type) VALUES (?, ?, ?, ?)",
            (user_id, t_type, change, b_type)
        )
        # Здесь же обновляем основной баланс в таблице users (логика упрощена)
        query = f"UPDATE users SET {b_type}_days_balance = {b_type}_days_balance + ? WHERE user_id = ?"
        await db.execute(query, (change, user_id))
        await db.commit()
      
