"""加锁服务：隐私锁 + 物品锁

对应规范 4.2：
- 隐私锁：影响访问和交流
- 物品锁：上锁后禁止翻/偷/消耗/出售，必须用户主动解锁
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models


async def get_privacy_lock(db: AsyncSession, user_id: int) -> models.PrivacyLock:
    pl = await db.get(models.PrivacyLock, user_id)
    if not pl:
        pl = models.PrivacyLock(user_id=user_id)
        db.add(pl)
        await db.commit()
    return pl


async def can_visit(db: AsyncSession, visitor_id: int, host_id: int) -> bool:
    """是否允许访问主页（结合隐私锁 + 黑名单）"""
    if visitor_id == host_id:
        return True
    from .friends import is_blocked, are_friends
    if await is_blocked(db, host_id, visitor_id):
        return False
    pl = await get_privacy_lock(db, host_id)
    if pl.allow_visit == 2:  # 无人
        return False
    if pl.allow_visit == 1 and not await are_friends(db, host_id, visitor_id):  # 仅好友
        return False
    return True


async def can_guestbook(db: AsyncSession, visitor_id: int, host_id: int) -> bool:
    if visitor_id == host_id:
        return True
    from .friends import is_blocked, are_friends
    if await is_blocked(db, host_id, visitor_id):
        return False
    pl = await get_privacy_lock(db, host_id)
    if pl.allow_guestbook == 2:
        return False
    if pl.allow_guestbook == 1 and not await are_friends(db, host_id, visitor_id):
        return False
    return True


async def can_chat(db: AsyncSession, from_id: int, to_id: int) -> bool:
    from .friends import is_blocked, are_friends
    if await is_blocked(db, to_id, from_id):
        return False
    pl = await get_privacy_lock(db, to_id)
    if pl.allow_chat == 2:
        return False
    if pl.allow_chat == 1 and not await are_friends(db, to_id, from_id):
        return False
    return True


# ---------------- 物品锁 ----------------
async def is_item_locked(db: AsyncSession, user_id: int, module_key: str, item_ref: str) -> bool:
    res = await db.execute(
        select(models.ItemLock).where(
            models.ItemLock.user_id == user_id,
            models.ItemLock.module_key == module_key,
            models.ItemLock.item_ref == item_ref,
            models.ItemLock.locked.is_(True),
        )
    )
    return res.scalar_one_or_none() is not None


async def toggle_item_lock(db: AsyncSession, user_id: int, module_key: str, item_ref: str) -> bool:
    res = await db.execute(
        select(models.ItemLock).where(
            models.ItemLock.user_id == user_id,
            models.ItemLock.module_key == module_key,
            models.ItemLock.item_ref == item_ref,
        )
    )
    lock = res.scalar_one_or_none()
    if lock:
        lock.locked = not lock.locked
    else:
        lock = models.ItemLock(user_id=user_id, module_key=module_key, item_ref=item_ref, locked=True)
        db.add(lock)
    await db.commit()
    return lock.locked


async def list_item_locks(db: AsyncSession, user_id: int, module_key: str | None = None):
    q = select(models.ItemLock).where(models.ItemLock.user_id == user_id, models.ItemLock.locked.is_(True))
    if module_key:
        q = q.where(models.ItemLock.module_key == module_key)
    res = await db.execute(q)
    return res.scalars().all()
