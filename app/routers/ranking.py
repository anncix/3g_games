"""排行榜（模块上报分数，平台统一展示）"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from ..platform import ranking
from .views import render

router = APIRouter(prefix="/ranking")


@router.get("")
async def ranking_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    m = request.query_params.get("m", "farm")
    metric = request.query_params.get("metric", "")
    # 模块对应主指标
    default_metric = {"farm": "harvest", "town": "dishes", "garden": "flower_lit", "sea": "level"}.get(m, "level")
    metric = metric or default_metric
    rows = await ranking.top_n(db, m, metric, "total", 20)
    return await render(request, "ranking.html", db, user=user, m=m, metric=metric, rows=rows)
