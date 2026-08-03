"""消息中心"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from .views import render

router = APIRouter(prefix="/messages")


@router.get("")
async def messages(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    res = await db.execute(select(models.Message).where(
        models.Message.user_id == user.id).order_by(models.Message.created_at.desc()).limit(100))
    msgs = res.scalars().all()
    return await render(request, "messages.html", db, user=user, msgs=msgs)


@router.post("/read/{mid}")
async def mark_read(mid: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    m = await db.get(models.Message, mid)
    if m and m.user_id == user.id:
        m.is_read = True
        await db.commit()
    return RedirectResponse("/messages", status_code=303)


@router.post("/readall")
async def read_all(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    await db.execute(update(models.Message).where(
        models.Message.user_id == user.id, models.Message.is_read.is_(False)).values(is_read=True))
    await db.commit()
    return RedirectResponse("/messages", status_code=303)
