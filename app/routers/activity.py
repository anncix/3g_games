"""活动 + 每日签到"""
from datetime import datetime
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from ..platform import events, log
from .views import render

router = APIRouter(prefix="/activity")


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
