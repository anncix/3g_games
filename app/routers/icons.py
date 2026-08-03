"""图标展示"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from .views import render

router = APIRouter(prefix="/icons")


@router.get("")
async def icons_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    icons = (await db.execute(select(models.Icon).order_by(models.Icon.source, models.Icon.id))).scalars().all()
    lit_ids = set()
    res = await db.execute(select(models.UserIcon).where(models.UserIcon.user_id == user.id, models.UserIcon.lit.is_(True)))
    for ui in res.scalars().all():
        lit_ids.add(ui.icon_id)
    return await render(request, "icons.html", db, user=user, icons=icons, lit_ids=lit_ids)
