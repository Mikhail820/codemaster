import aiosqlite
import json
from datetime import datetime
from typing import Optional, Dict, Any

DB_PATH = "codemaster.db"


class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    async def connect(self):
        return await aiosqlite.connect(self.db_path)

    # ---------- INIT / MIGRATION ----------

    async def init_db(self):
        async with await self.connect() as db:
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    referrer_id INTEGER,
                    trial_days INTEGER DEFAULT 10,
                    paid_days INTEGER DEFAULT 0,
                    bonus_days INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'ACTIVE',
                    is_sub_active BOOLEAN DEFAULT 1,
                    is_premium BOOLEAN DEFAULT 0,
                    expired_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS bots (
                    bot_token_encrypted TEXT PRIMARY KEY,
                    owner_id INTEGER,
                    config_json TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    event TEXT,
                    payload TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_users_referrer
                ON users (referrer_id);

                CREATE INDEX IF NOT EXISTS idx_users_status
                ON users (status);

                CREATE INDEX IF NOT EXISTS idx_audit_user
                ON audit_log (user_id);
                """
            )
            await db.commit()

    # ---------- USERS ----------

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        async with await self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def create_user(self, user_id: int, referrer_id: Optional[int] = None):
        async with await self.connect() as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO users (user_id, referrer_id)
                VALUES (?, ?)
                """,
                (user_id, referrer_id),
            )
            await db.commit()

    async def update_user_fields(self, user_id: int, **fields):
        if not fields:
            return
        columns = ", ".join([f"{k} = ?" for k in fields.keys()])
        values = list(fields.values())
        values.append(user_id)

        async with await self.connect() as db:
            await db.execute(
                f"UPDATE users SET {columns} WHERE user_id = ?",
                values,
            )
            await db.commit()

    # ---------- DAYS MANAGEMENT ----------

    async def add_trial_days(self, user_id: int, days: int):
        async with await self.connect() as db:
            await db.execute(
                "UPDATE users SET trial_days = trial_days + ? WHERE user_id = ?",
                (days, user_id),
            )
            await db.commit()

    async def add_paid_days(self, user_id: int, days: int):
        async with await self.connect() as db:
            await db.execute(
                "UPDATE users SET paid_days = paid_days + ? WHERE user_id = ?",
                (days, user_id),
            )
            await db.commit()

    async def add_bonus_days(self, user_id: int, days: int):
        async with await self.connect() as db:
            await db.execute(
                "UPDATE users SET bonus_days = bonus_days + ? WHERE user_id = ?",
                (days, user_id),
            )
            await db.commit()

    async def consume_day(self, user_id: int, source: str):
        """
        source: 'trial' | 'paid' | 'bonus'
        """
        column_map = {
            "trial": "trial_days",
            "paid": "paid_days",
            "bonus": "bonus_days",
        }
        column = column_map[source]

        async with await self.connect() as db:
            await db.execute(
                f"""
                UPDATE users
                SET {column} = {column} - 1
                WHERE user_id = ? AND {column} > 0
                """,
                (user_id,),
            )
            await db.commit()

    # ---------- BOTS ----------

    async def create_bot(
        self,
        bot_token_encrypted: str,
        owner_id: int,
        config: Dict[str, Any],
    ):
        async with await self.connect() as db:
            await db.execute(
                """
                INSERT INTO bots (bot_token_encrypted, owner_id, config_json)
                VALUES (?, ?, ?)
                """,
                (bot_token_encrypted, owner_id, json.dumps(config)),
            )
            await db.commit()

    async def delete_bots_by_owner(self, owner_id: int):
        async with await self.connect() as db:
            await db.execute(
                "DELETE FROM bots WHERE owner_id = ?",
                (owner_id,),
            )
            await db.commit()

    # ---------- AUDIT ----------

    async def log_event(
        self,
        user_id: int,
        event: str,
        payload: Optional[Dict[str, Any]] = None,
    ):
        async with await self.connect() as db:
            await db.execute(
                """
                INSERT INTO audit_log (user_id, event, payload)
                VALUES (?, ?, ?)
                """,
                (
                    user_id,
                    event,
                    json.dumps(payload) if payload else None,
                ),
            )
            await db.commit()

    # ---------- UTILS ----------

    async def set_expired(self, user_id: int):
        async with await self.connect() as db:
            await db.execute(
                """
                UPDATE users
                SET status = 'EXPIRED',
                    expired_at = ?
                WHERE user_id = ?
                """,
                (datetime.utcnow().isoformat(), user_id),
            )
            await db.commit()

    async def get_expired_users_older_than(self, days: int):
        async with await self.connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM users
                WHERE status = 'EXPIRED'
                AND expired_at <= datetime('now', ?)
                """,
                (f"-{days} days",),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
