"""后台管理系统

对应规范：模块注册(上下架/排序) / 客服工单处理 / 操作日志查询 / 用户管理 / 活动/商店管理
入口：/admin （需 is_admin）
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..platform import log
from .views import render

router = APIRouter(prefix="/admin")


@router.get("")
async def admin_home(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user or not user.is_admin:
        return RedirectResponse("/login", status_code=303)
    user_count = (await db.execute(select(func.count(models.User.id)))).scalar() or 0
    ticket_open = (await db.execute(select(func.count(models.SupportTicket.id)).where(
        models.SupportTicket.status == "open"))).scalar() or 0
    msg_count = (await db.execute(select(func.count(models.Message.id)))).scalar() or 0
    modules = (await db.execute(select(models.Module).order_by(models.Module.sort))).scalars().all()
    return await render(request, "admin/home.html", db, user=user, user_count=user_count,
                        ticket_open=ticket_open, msg_count=msg_count, modules=modules)


@router.get("/users")
async def admin_users(request: Request, db: AsyncSession = Depends(get_db)):
    user = await require_admin(await get_current_user(request, db))
    res = await db.execute(select(models.User).order_by(models.User.id))
    users = res.scalars().all()
    return await render(request, "admin/users.html", db, user=user, users=users)


class _CoinAdjust:
    pass


@router.post("/users/{uid}/coins")
async def adjust_coins(uid: int, request: Request, db: AsyncSession = Depends(get_db)):
    admin = await require_admin(await get_current_user(request, db))
    form = await request.form()
    delta = int(form.get("delta", 0))
    u = await db.get(models.User, uid)
    if u:
        u.coins = max(0, u.coins + delta)
        await log.record(db, admin.id, "platform", "admin_adjust_coins", f"{uid}:{delta}")
        await db.commit()
    return RedirectResponse("/admin/users", status_code=303)


@router.post("/users/{uid}/admin")
async def toggle_admin(uid: int, request: Request, db: AsyncSession = Depends(get_db)):
    admin = await require_admin(await get_current_user(request, db))
    u = await db.get(models.User, uid)
    if u and u.id != admin.id:
        u.is_admin = not u.is_admin
        await db.commit()
    return RedirectResponse("/admin/users", status_code=303)


@router.get("/modules")
async def admin_modules(request: Request, db: AsyncSession = Depends(get_db)):
    user = await require_admin(await get_current_user(request, db))
    mods = (await db.execute(select(models.Module).order_by(models.Module.sort))).scalars().all()
    return await render(request, "admin/modules.html", db, user=user, mods=mods)


@router.post("/modules/{key}/toggle")
async def toggle_module(key: str, request: Request, db: AsyncSession = Depends(get_db)):
    admin = await require_admin(await get_current_user(request, db))
    m = await db.get(models.Module, key)
    if m:
        m.enabled = not m.enabled
        await log.record(db, admin.id, "platform", "admin_toggle_module", f"{key}:{m.enabled}")
        await db.commit()
    return RedirectResponse("/admin/modules", status_code=303)


@router.post("/modules/{key}/sort")
async def sort_module(key: str, request: Request, db: AsyncSession = Depends(get_db)):
    admin = await require_admin(await get_current_user(request, db))
    form = await request.form()
    m = await db.get(models.Module, key)
    if m:
        m.sort = int(form.get("sort", m.sort))
        await db.commit()
    return RedirectResponse("/admin/modules", status_code=303)


@router.get("/tickets")
async def admin_tickets(request: Request, db: AsyncSession = Depends(get_db)):
    user = await require_admin(await get_current_user(request, db))
    res = await db.execute(select(models.SupportTicket, models.User).join(
        models.User, models.SupportTicket.user_id == models.User.id
    ).order_by(models.SupportTicket.created_at.desc()))
    tickets = res.all()
    return await render(request, "admin/tickets.html", db, user=user, tickets=tickets)


@router.post("/tickets/{tid}/reply")
async def reply_ticket(tid: int, request: Request, db: AsyncSession = Depends(get_db)):
    admin = await require_admin(await get_current_user(request, db))
    form = await request.form()
    t = await db.get(models.SupportTicket, tid)
    if t:
        t.reply = form.get("reply", "").strip()[:500]
        t.status = "replied"
        await log.record(db, admin.id, "platform", "admin_reply_ticket", str(tid))
        await db.commit()
    return RedirectResponse("/admin/tickets", status_code=303)


@router.get("/logs")
async def admin_logs(request: Request, db: AsyncSession = Depends(get_db)):
    """全站操作日志查询"""
    user = await require_admin(await get_current_user(request, db))
    res = await db.execute(select(models.OperationLog, models.User).join(
        models.User, models.OperationLog.user_id == models.User.id
    ).order_by(models.OperationLog.created_at.desc()).limit(200))
    logs = res.all()
    return await render(request, "admin/logs.html", db, user=user, logs=logs)


@router.get("/shop")
async def admin_shop(request: Request, db: AsyncSession = Depends(get_db)):
    user = await require_admin(await get_current_user(request, db))
    res = await db.execute(select(models.ShopItem, models.Item).join(
        models.Item, models.ShopItem.item_id == models.Item.id))
    items = res.all()
    return await render(request, "admin/shop.html", db, user=user, items=items)


@router.post("/shop/{sid}/toggle")
async def toggle_shop(sid: int, request: Request, db: AsyncSession = Depends(get_db)):
    admin = await require_admin(await get_current_user(request, db))
    si = await db.get(models.ShopItem, sid)
    if si:
        si.enabled = not si.enabled
        await db.commit()
    return RedirectResponse("/admin/shop", status_code=303)
