from datetime import datetime, timedelta
from typing import Optional

from database import Database


STATUS_ACTIVE = "ACTIVE"
STATUS_FROZEN = "FROZEN"
STATUS_EXPIRED = "EXPIRED"
STATUS_DELETED = "DELETED"


class LifecycleEngine:
    """
    Единственный источник правды о состоянии пользователя и его бота.
    """

    def __init__(self, db: Database):
        self.db = db

    # ---------- CORE ----------

    async def resolve_status(self, user_id: int) -> str:
        """
        Главный метод.
        Определяет и обновляет статус пользователя.
        """
        user = await self.db.get_user(user_id)
        if not user:
            return STATUS_DELETED

        # 1. Нет подписки → FROZEN
        if not user["is_sub_active"]:
            if user["status"] != STATUS_FROZEN:
                await self._set_status(user_id, STATUS_FROZEN)
            return STATUS_FROZEN

        # 2. Есть дни?
        total_days = self._total_days(user)

        if total_days > 0:
            # Premium-триггер
            is_premium = user["bonus_days"] >= 30
            if user["is_premium"] != int(is_premium):
                await self.db.update_user_fields(
                    user_id,
                    is_premium=int(is_premium),
                )

            if user["status"] != STATUS_ACTIVE:
                await self._set_status(user_id, STATUS_ACTIVE)

            return STATUS_ACTIVE

        # 3. Дней нет → EXPIRED
        if user["status"] != STATUS_EXPIRED:
            await self.db.set_expired(user_id)

        return STATUS_EXPIRED

    # ---------- DAILY CONSUMPTION ----------

    async def consume_daily(self, user_id: int) -> Optional[str]:
        """
        Вызывается 1 раз в сутки scheduler'ом.
        Списывает 1 день по очереди: Trial → Paid → Bonus
        """
        user = await self.db.get_user(user_id)
        if not user:
            return None

        # если заморожен или удалён — не списываем
        if user["status"] in (STATUS_FROZEN, STATUS_DELETED):
            return user["status"]

        if user["trial_days"] > 0:
            await self.db.consume_day(user_id, "trial")
        elif user["paid_days"] > 0:
            await self.db.consume_day(user_id, "paid")
        elif user["bonus_days"] > 0:
            await self.db.consume_day(user_id, "bonus")

        return await self.resolve_status(user_id)

    # ---------- DELETE LOGIC ----------

    async def should_delete(self, user_id: int) -> bool:
        """
        Проверяет, пора ли удалять пользователя и его ботов.
        """
        user = await self.db.get_user(user_id)
        if not user:
            return True

        if user["status"] != STATUS_EXPIRED:
            return False

        expired_at = user["expired_at"]
        if not expired_at:
            return False

        expired_time = datetime.fromisoformat(expired_at)
        return datetime.utcnow() >= expired_time + timedelta(days=7)

    async def delete_user(self, user_id: int):
        """
        Полное удаление пользователя и его ботов.
        """
        await self.db.delete_bots_by_owner(user_id)
        await self.db.update_user_fields(user_id, status=STATUS_DELETED)
        await self.db.log_event(user_id, "USER_DELETED")

    # ---------- HELPERS ----------

    def _total_days(self, user: dict) -> int:
        return (
            user["trial_days"]
            + user["paid_days"]
            + user["bonus_days"]
        )

    async def _set_status(self, user_id: int, status: str):
        await self.db.update_user_fields(user_id, status=status)
        await self.db.log_event(
            user_id,
            "STATUS_CHANGED",
            {"status": status},
            )
