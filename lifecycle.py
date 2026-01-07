import asyncio
from datetime import datetime, timedelta
import database as db

class LifecycleManager:
    @staticmethod
    async def get_user_status(user_id: int, is_subscribed: bool):
        """Определяет текущий статус на основе подписки и баланса"""
        async with db.aiosqlite.connect(db.DB_PATH) as conn:
            conn.row_factory = db.aiosqlite.Row
            async with conn.execute(
                "SELECT trial_days_balance, paid_days_balance, bonus_days_balance FROM users WHERE user_id = ?", 
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return "frozen"

                # Если нет подписки — сразу заморозка (дни не тратим)
                if not is_subscribed:
                    return "frozen"

                total_days = row['trial_days_balance'] + row['paid_days_balance'] + row['bonus_days_balance']
                
                if total_days > 0:
                    return "active"
                elif total_days > -3: # Режим последнего шанса (3 дня)
                    return "expired"
                else:
                    return "deleted"

    @staticmethod
    async def daily_billing():
        """Фоновая задача: раз в сутки списывает 1 день у всех активных ботов"""
        while True:
            # Ждем 24 часа (или меньше для тестов)
            await asyncio.sleep(86400) 
            
            async with db.aiosqlite.connect(db.DB_PATH) as conn:
                conn.row_factory = db.aiosqlite.Row
                # Берем всех, кто не заморожен
                async with conn.execute("SELECT user_id, trial_days_balance, paid_days_balance, bonus_days_balance FROM users WHERE current_status = 'active'") as cursor:
                    users = await cursor.fetchall()
                    
                    for user in users:
                        uid = user['user_id']
                        # Логика очереди списания: Trial -> Paid -> Bonus
                        if user['trial_days_balance'] > 0:
                            await db.add_days_transaction(uid, 'consumption', -1, 'trial')
                        elif user['paid_days_balance'] > 0:
                            await db.add_days_transaction(uid, 'consumption', -1, 'paid')
                        elif user['bonus_days_balance'] > 0:
                            await db.add_days_transaction(uid, 'consumption', -1, 'bonus')
                        else:
                            # Дни кончились — меняем статус
                            await conn.execute("UPDATE users SET current_status = 'expired' WHERE user_id = ?", (uid,))
                await conn.commit()
