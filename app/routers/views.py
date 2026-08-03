"""共享视图助手：统一渲染上下文（当前用户 + 未读消息数 + 顶层导航）"""
from fastapi import Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..deps import templates


async def render(request: Request, template: str, db: AsyncSession | None = None, **ctx):
    user = ctx.get("user")
    unread = 0
    if user and db:
        res = await db.execute(
            select(func.count(models.Message.id)).where(
                models.Message.user_id == user.id, models.Message.is_read.is_(False)
            )
        )
        unread = res.scalar() or 0
    return templates.TemplateResponse(request, template, {
        "request": request,
        "user": user,
        "unread": unread,
        **ctx,
    })
