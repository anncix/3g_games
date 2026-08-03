"""设置：隐私锁 / 物品锁管理 / 消息开关 / 黑名单 / 账号（对应规范 6）"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from ..platform import locks
from .views import render

router = APIRouter(prefix="/settings")


async def _get_settings(db: AsyncSession, user_id: int) -> models.Settings:
    s = await db.get(models.Settings, user_id)
    if not s:
        s = models.Settings(user_id=user_id)
        db.add(s)
        await db.commit()
        await db.refresh(s)
    return s


@router.get("")
async def settings_home(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    pl = await locks.get_privacy_lock(db, user.id)
    s = await _get_settings(db, user.id)
    return await render(request, "settings.html", db, user=user, pl=pl, s=s)


@router.post("/privacy")
async def update_privacy(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    pl = await locks.get_privacy_lock(db, user.id)
    pl.allow_visit = int(form.get("allow_visit", 0))
    pl.allow_guestbook = int(form.get("allow_guestbook", 0))
    pl.allow_chat = int(form.get("allow_chat", 0))
    pl.show_in_city = form.get("show_in_city") == "on"
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True, msg="隐私锁已更新", back_href="/settings", back_text="返回设置")


@router.post("/notify")
async def update_notify(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    s = await _get_settings(db, user.id)
    s.notify_message = form.get("notify_message") == "on"
    s.notify_activity = form.get("notify_activity") == "on"
    s.notify_interact = form.get("notify_interact") == "on"
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True, msg="提醒设置已更新", back_href="/settings", back_text="返回设置")


@router.get("/itemlocks")
async def item_locks_page(request: Request, db: AsyncSession = Depends(get_db)):
    """物品锁管理入口"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    lks = await locks.list_item_locks(db, user.id)
    return await render(request, "item_locks.html", db, user=user, lks=lks)


@router.post("/itemlocks/{lid}")
async def unlock_item(lid: int, request: Request, db: AsyncSession = Depends(get_db)):
    from .. import models
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    lk = await db.get(models.ItemLock, lid)
    if lk and lk.user_id == user.id:
        lk.locked = False
        await db.commit()
    return RedirectResponse("/settings/itemlocks", status_code=303)


@router.post("/profile")
async def update_profile(request: Request, db: AsyncSession = Depends(get_db)):
    """账号基础信息"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    user.nickname = form.get("nickname", user.nickname).strip()[:32]
    user.signature = form.get("signature", "").strip()[:128]
    user.city = form.get("city", "").strip()[:32]
    user.gender = int(form.get("gender", 0))
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True, msg="资料已更新", back_href="/settings", back_text="返回设置")
