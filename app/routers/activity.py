"""活动 + 每日签到"""
from datetime import datetime
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from ..platform import events, goods, log
from .views import render

router = APIRouter(prefix="/activity", tags=["活动"])


# 限时活动（内联定义，不入库）：key/name/desc/active/type
# type: exp 双倍经验 / contest 竞赛 / login 每日登录礼
TIMED_EVENTS = [
    {"key": "double_exp", "name": "双倍经验周", "desc": "所有模块经验×2", "active": True, "type": "exp"},
    {"key": "harvest_race", "name": "农场收获赛", "desc": "本周农场收获榜Top10获奖", "active": True, "type": "contest"},
    {"key": "festival_login", "name": "节日登录礼", "desc": "每日登录领礼包", "active": True, "type": "login"},
    {"key": "guild_war", "name": "帮派争霸赛", "desc": "精武堂帮战积分榜", "active": False, "type": "contest"},
]


@router.get("")
async def activity_home(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    acts = (await db.execute(select(models.Activity).where(
        models.Activity.enabled.is_(True), models.Activity.end_at > datetime.utcnow()))).scalars().all()
    return await render(request, "activity.html", db, user=user, acts=acts)


@router.post("/signin")
async def daily_signin(request: Request, db: AsyncSession = Depends(get_db)):
    """每日签到（简化：当天可签一次，按工单记录判断）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    # 用操作日志判断今天是否已签
    res = await db.execute(select(models.OperationLog).where(
        models.OperationLog.user_id == user.id, models.OperationLog.action == "signin",
        models.OperationLog.detail == today))
    if res.scalar_one_or_none():
        return await render(request, "result.html", db, user=user, ok=False, msg="今天已签到", back_href="/activity", back_text="返回活动")
    user.coins += 50
    await events.emit(db, user.id, "platform", "icon_light", {"icon_key": "icon_signin"})
    await log.record(db, user.id, "platform", "signin", today)
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True, msg="签到成功，+50金币", back_href="/activity", back_text="返回活动")


@router.get("/events")
async def timed_events(request: Request, db: AsyncSession = Depends(get_db)):
    """限时活动列表"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    # 查今日已领取的 login 类活动（detail 格式：event_key:YYYY-MM-DD）
    claimed = set()
    res = await db.execute(select(models.OperationLog).where(
        models.OperationLog.user_id == user.id,
        models.OperationLog.action == "event_claim",
        models.OperationLog.detail.like(f"%:{today}"),
    ))
    for row in res.scalars():
        claimed.add(row.detail.split(":")[0])
    return await render(request, "activity/events.html", db, user=user,
                        events=TIMED_EVENTS, claimed=claimed, today=today)


@router.post("/events/claim/{event_key}")
async def claim_event_gift(event_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """领取活动礼包（仅 login 类活动，每日一次）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    event = next((e for e in TIMED_EVENTS if e["key"] == event_key), None)
    if not event:
        return await render(request, "result.html", db, user=user, ok=False, msg="活动不存在",
                            back_href="/activity/events", back_text="返回活动")
    if not event["active"]:
        return await render(request, "result.html", db, user=user, ok=False, msg="活动未开启",
                            back_href="/activity/events", back_text="返回活动")
    if event["type"] != "login":
        return await render(request, "result.html", db, user=user, ok=False, msg="该活动不支持领取礼包",
                            back_href="/activity/events", back_text="返回活动")
    today = datetime.utcnow().strftime("%Y-%m-%d")
    detail = f"{event_key}:{today}"
    # 防止重复领取：按操作日志查今日是否已领
    res = await db.execute(select(models.OperationLog).where(
        models.OperationLog.user_id == user.id, models.OperationLog.action == "event_claim",
        models.OperationLog.detail == detail))
    if res.scalar_one_or_none():
        return await render(request, "result.html", db, user=user, ok=False, msg="今日已领取该活动礼包",
                            back_href="/activity/events", back_text="返回活动")
    # 发放礼包：平台金币 + 节日礼包道具
    user.coins += 88
    await goods.ensure_item(db, "festival_gift", "节日礼包", "prop",
                            module_key="platform", description="节日登录礼活动奖励")
    await goods.add_item(db, user.id, "festival_gift", "platform", 1)
    await log.record(db, user.id, "platform", "event_claim", detail)
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg="领取成功：节日礼包×1，金币+88",
                        back_href="/activity/events", back_text="返回活动")
