"""好友系统服务（全站共用）"""
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models


async def are_friends(db: AsyncSession, user_id: int, other_id: int) -> bool:
    if user_id == other_id:
        return True
    res = await db.execute(
        select(models.Friend).where(
            models.Friend.user_id == user_id, models.Friend.friend_id == other_id
        )
    )
    return res.scalar_one_or_none() is not None


async def is_blocked(db: AsyncSession, user_id: int, other_id: int) -> bool:
    res = await db.execute(
        select(models.Blacklist).where(
            models.Blacklist.user_id == user_id, models.Blacklist.blocked_id == other_id
        )
    )
    return res.scalar_one_or_none() is not None


async def add_friend(db: AsyncSession, user_id: int, friend_id: int, group: str = "我的好友"):
    if user_id == friend_id:
        return False, "不能加自己"
    if await is_blocked(db, friend_id, user_id):
        return False, "对方已将你拉黑"
    exists = await are_friends(db, user_id, friend_id)
    if exists:
        return False, "已经是好友了"
    db.add(models.Friend(user_id=user_id, friend_id=friend_id, group_name=group))
    await db.commit()
    return True, "添加成功"


async def remove_friend(db: AsyncSession, user_id: int, friend_id: int):
    await db.execute(
        delete(models.Friend).where(
            models.Friend.user_id == user_id, models.Friend.friend_id == friend_id
        )
    )
    await db.commit()
    return True, "已删除"


async def block_user(db: AsyncSession, user_id: int, blocked_id: int):
    if user_id == blocked_id:
        return False, "不能拉黑自己"
    if await is_blocked(db, user_id, blocked_id):
        return False, "已在黑名单"
    db.add(models.Blacklist(user_id=user_id, blocked_id=blocked_id))
    # 同时删好友
    await db.execute(
        delete(models.Friend).where(
            ((models.Friend.user_id == user_id) & (models.Friend.friend_id == blocked_id))
            | ((models.Friend.user_id == blocked_id) & (models.Friend.friend_id == user_id))
        )
    )
    await db.commit()
    return True, "已拉黑"


async def list_friends(db: AsyncSession, user_id: int):
    res = await db.execute(
        select(models.Friend).where(models.Friend.user_id == user_id)
    )
    return res.scalars().all()


async def record_visit(db: AsyncSession, host_id: int, visitor_id: int):
    if host_id == visitor_id:
        return
    db.add(models.Visit(host_id=host_id, visitor_id=visitor_id))
    await db.commit()
