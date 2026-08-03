"""图标与成就服务

对应规范 4.4：
- 图标：身份展示，点亮即展示
- 成就：记录/目标，可有进度/奖励
- 模块不能直接点亮图标，只能触发条件，由平台统一判定
"""
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models


async def get_icon_by_key(db: AsyncSession, key: str) -> models.Icon | None:
    res = await db.execute(select(models.Icon).where(models.Icon.key == key))
    return res.scalar_one_or_none()


async def ensure_icon(db: AsyncSession, key: str, name: str, description: str = "",
                      source: str = "platform", trigger: str = "") -> models.Icon:
    icon = await get_icon_by_key(db, key)
    if icon:
        return icon
    icon = models.Icon(key=key, name=name, description=description, source=source, trigger=trigger)
    db.add(icon)
    await db.commit()
    await db.refresh(icon)
    return icon


async def light_icon(db: AsyncSession, user_id: int, icon_key: str) -> bool:
    """平台统一判定点亮。模块通过 events 上报，由平台调用本函数。"""
    icon = await get_icon_by_key(db, icon_key)
    if not icon:
        return False
    res = await db.execute(
        select(models.UserIcon).where(
            models.UserIcon.user_id == user_id, models.UserIcon.icon_id == icon.id
        )
    )
    ui = res.scalar_one_or_none()
    if ui and ui.lit:
        return True
    if ui:
        ui.lit = True
        ui.lit_at = datetime.utcnow()
    else:
        db.add(models.UserIcon(user_id=user_id, icon_id=icon.id, lit=True, lit_at=datetime.utcnow()))
    await db.commit()
    return True


async def list_user_icons(db: AsyncSession, user_id: int):
    res = await db.execute(
        select(models.UserIcon, models.Icon).join(
            models.Icon, models.UserIcon.icon_id == models.Icon.id
        ).where(models.UserIcon.user_id == user_id, models.UserIcon.lit.is_(True))
    )
    return res.all()


# ---------------- 成就 ----------------
async def get_achievement_by_key(db: AsyncSession, key: str):
    res = await db.execute(select(models.Achievement).where(models.Achievement.key == key))
    return res.scalar_one_or_none()


async def ensure_achievement(db: AsyncSession, key: str, name: str, description: str = "",
                             target: int = 1, reward_coins: int = 0, source: str = "platform"):
    a = await get_achievement_by_key(db, key)
    if a:
        return a
    a = models.Achievement(key=key, name=name, description=description, target=target,
                           reward_coins=reward_coins, source=source)
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


async def progress_achievement(db: AsyncSession, user_id: int, key: str, delta: int = 1,
                               absolute: bool = False) -> bool:
    """推进成就进度，达标自动完成（不自动领奖）。返回是否刚刚完成。"""
    a = await get_achievement_by_key(db, key)
    if not a:
        return False
    res = await db.execute(
        select(models.UserAchievement).where(
            models.UserAchievement.user_id == user_id, models.UserAchievement.achievement_id == a.id
        )
    )
    ua = res.scalar_one_or_none()
    just_completed = False
    if ua:
        ua.progress = delta if absolute else ua.progress + delta
        if ua.progress >= a.target and not ua.completed:
            ua.completed = True
            ua.completed_at = datetime.utcnow()
            just_completed = True
    else:
        prog = delta if absolute else delta
        completed = prog >= a.target
        ua = models.UserAchievement(user_id=user_id, achievement_id=a.id, progress=prog,
                                     completed=completed, completed_at=datetime.utcnow() if completed else None)
        db.add(ua)
        just_completed = completed
    await db.commit()
    return just_completed


async def claim_reward(db: AsyncSession, user_id: int, achievement_id: int) -> tuple[bool, str]:
    ua = await db.get(models.UserAchievement, achievement_id)
    if not ua or ua.user_id != user_id:
        return False, "成就不存在"
    if not ua.completed:
        return False, "尚未达成"
    if ua.reward_claimed:
        return False, "奖励已领取"
    a = await db.get(models.Achievement, ua.achievement_id)
    user = await db.get(models.User, user_id)
    user.coins += a.reward_coins
    ua.reward_claimed = True
    await db.commit()
    return True, f"领取 {a.reward_coins} 金币"
