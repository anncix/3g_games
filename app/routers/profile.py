"""我的家园（身份展示）+ 来访记录 + 留言板 + 我的动态"""
from datetime import datetime
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user, require_user, templates
from ..platform import friends as friend_svc, locks, icons, log
from .views import render

router = APIRouter(tags=["个人主页"])


@router.get("/my")
async def my_home(request: Request, db: AsyncSession = Depends(get_db)):
    """我的家园：主页展示 / 图标展示位 / 背包/来访/留言/动态入口"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    # 图标展示位
    user_icons = await icons.list_user_icons(db, user.id)
    return await render(request, "my_home.html", db, user=user, user_icons=user_icons)


@router.get("/u/{uid}")
async def user_profile(uid: int, request: Request, db: AsyncSession = Depends(get_db)):
    """他人主页（受隐私锁约束）"""
    me = await get_current_user(request, db)
    if not me:
        return RedirectResponse("/login", status_code=303)
    host = await db.get(models.User, uid)
    if not host:
        raise HTTPException(404, "用户不存在")
    allowed = await locks.can_visit(db, me.id, host.id)
    if not allowed:
        return await render(request, "result.html", db, user=me, ok=False,
                            msg="对方主页已设为私密", back_href="/friends", back_text="返回好友")
    # 记录来访
    await friend_svc.record_visit(db, host.id, me.id)
    host_icons = await icons.list_user_icons(db, host.id)
    is_friend = await friend_svc.are_friends(db, me.id, host.id)
    # 留言板（隐私锁）
    can_gb = await locks.can_guestbook(db, me.id, host.id)
    res = await db.execute(
        select(models.Guestbook, models.User).join(
            models.User, models.Guestbook.author_id == models.User.id
        ).where(models.Guestbook.host_id == host.id).order_by(models.Guestbook.created_at.desc()).limit(20)
    )
    gbs = res.all()
    return await render(request, "user_profile.html", db, user=me, host=host,
                        host_icons=host_icons, is_friend=is_friend, can_gb=can_gb, gbs=gbs)


@router.post("/u/{uid}/guestbook")
async def post_guestbook(uid: int, request: Request, db: AsyncSession = Depends(get_db)):
    me = await get_current_user(request, db)
    if not me:
        return RedirectResponse("/login", status_code=303)
    if not await locks.can_guestbook(db, me.id, uid):
        return await render(request, "result.html", db, user=me, ok=False,
                            msg="对方已关闭留言", back_href=f"/u/{uid}", back_text="返回主页")
    form = await request.form()
    content = form.get("content", "").strip()
    if content:
        db.add(models.Guestbook(host_id=uid, author_id=me.id, content=content[:200]))
        await db.commit()
        await log.record(db, me.id, "platform", "guestbook", f"to:{uid}")
    return RedirectResponse(f"/u/{uid}", status_code=303)


@router.get("/my/visits")
async def my_visits(request: Request, db: AsyncSession = Depends(get_db)):
    user = await require_user(await get_current_user(request, db)) if False else await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    res = await db.execute(
        select(models.Visit, models.User).join(
            models.User, models.Visit.visitor_id == models.User.id
        ).where(models.Visit.host_id == user.id).order_by(models.Visit.visited_at.desc()).limit(50)
    )
    visits = res.all()
    return await render(request, "visits.html", db, user=user, visits=visits)


@router.get("/my/guestbook")
async def my_guestbook(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    res = await db.execute(
        select(models.Guestbook, models.User).join(
            models.User, models.Guestbook.author_id == models.User.id
        ).where(models.Guestbook.host_id == user.id).order_by(models.Guestbook.created_at.desc()).limit(50)
    )
    gbs = res.all()
    return await render(request, "guestbook.html", db, user=user, gbs=gbs)


@router.get("/my/dynamics")
async def my_dynamics(request: Request, db: AsyncSession = Depends(get_db)):
    """我的动态：聚合近期操作留痕"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    logs = await log.recent_logs(db, user.id, 30)
    return await render(request, "dynamics.html", db, user=user, logs=logs)
