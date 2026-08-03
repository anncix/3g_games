"""游戏大厅：所有模块入口（模块必须从游戏大厅进入）"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from .views import render

router = APIRouter(tags=["大厅"])


@router.get("/lobby")
async def lobby(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    mods = (await db.execute(
        select(models.Module).where(models.Module.enabled.is_(True)).order_by(models.Module.sort)
    )).scalars().all()
    return await render(request, "lobby.html", db, user=user, mods=mods)
