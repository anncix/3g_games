"""好友系统（全站共用）"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from ..platform import friends as svc
from .views import render

router = APIRouter(prefix="", tags=["好友"])


@router.get("/friends")
async def friends_list(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    frs = await svc.list_friends(db, user.id)
    # 查好友用户信息
    friends_data = []
    for f in frs:
        u = await db.get(models.User, f.friend_id)
        if u:
            friends_data.append((f, u))
    # 黑名单
    bls = (await db.execute(
        select(models.Blacklist).where(models.Blacklist.user_id == user.id)
    )).scalars().all()
    bl_users = [(b, await db.get(models.User, b.blocked_id)) for b in bls]
    return await render(request, "friends.html", db, user=user, friends_data=friends_data, bl_users=bl_users)


@router.get("/friends/add/{uid}")
async def add_friend_page(uid: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    ok, msg = await svc.add_friend(db, user.id, uid)
    return await render(request, "result.html", db, user=user, ok=ok, msg=msg, back_href=f"/u/{uid}", back_text="返回主页")


@router.get("/friends/del/{uid}")
async def del_friend_confirm(uid: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    other = await db.get(models.User, uid)
    return await render(request, "confirm.html", db, user=user,
                        action=f"/friends/del/{uid}", text=f"删除好友 {other.nickname if other else uid}")


@router.post("/friends/del/{uid}")
async def del_friend(uid: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    await svc.remove_friend(db, user.id, uid)
    return RedirectResponse("/friends", status_code=303)


@router.get("/friends/block/{uid}")
async def block_confirm(uid: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    other = await db.get(models.User, uid)
    return await render(request, "confirm.html", db, user=user,
                        action=f"/friends/block/{uid}", text=f"拉黑 {other.nickname if other else uid}",
                        confirm_risk=True)


@router.post("/friends/block/{uid}")
async def block_user(uid: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    ok, msg = await svc.block_user(db, user.id, uid)
    return await render(request, "result.html", db, user=user, ok=ok, msg=msg, back_href="/friends", back_text="返回好友")


@router.post("/friends/unblock/{uid}")
async def unblock(uid: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    from sqlalchemy import delete
    await db.execute(delete(models.Blacklist).where(
        models.Blacklist.user_id == user.id, models.Blacklist.blocked_id == uid))
    await db.commit()
    return RedirectResponse("/friends", status_code=303)


@router.get("/friends/search")
async def search_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    q = request.query_params.get("q", "").strip()
    results = []
    if q:
        res = await db.execute(
            select(models.User).where(
                (models.User.username.contains(q)) | (models.User.nickname.contains(q))
            ).limit(20)
        )
        results = [u for u in res.scalars().all() if u.id != user.id]
    return await render(request, "friends_search.html", db, user=user, q=q, results=results)
