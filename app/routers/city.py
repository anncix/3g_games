"""同城：按城市展示玩家（受隐私锁约束）"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from ..platform import locks
from .views import render

router = APIRouter(prefix="/city")


@router.get("")
async def city_home(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    q = request.query_params.get("q", "").strip()
    users = []
    if q:
        res = await db.execute(select(models.User).where(models.User.city == q, models.User.id != user.id).limit(50))
    else:
        res = await db.execute(select(models.User).where(models.User.id != user.id).limit(50))
    for u in res.scalars().all():
        pl = await locks.get_privacy_lock(db, u.id)
        if pl.show_in_city:
            users.append(u)
    return await render(request, "city.html", db, user=user, q=q, users=users)
