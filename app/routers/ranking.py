"""排行榜（模块上报分数，平台统一展示 + 多榜直查 State 表）"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from .views import render

router = APIRouter(prefix="/ranking")


# 多榜配置：metric -> 中文名。对应 State 表直查，Top 10
METRIC_TABS = [
    ("level", "等级榜"),
    ("farm", "农场收获榜"),
    ("garden", "花园等级榜"),
    ("martial", "精武堂战力榜"),
    ("sea", "纵横四海榜"),
]
_VALID_METRICS = {k for k, _ in METRIC_TABS}


@router.get("")
async def ranking_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    # 优先使用 ?metric=farm|garden|martial|sea|level（默认 level）
    # 兼容旧链接 ?m=farm：m 在新榜集合内时映射为对应 metric
    metric = request.query_params.get("metric", "")
    m = request.query_params.get("m", "")
    if metric not in _VALID_METRICS:
        metric = m if m in _VALID_METRICS else "level"
    rows = await _top10(db, metric)
    label = dict(METRIC_TABS).get(metric, "等级榜")
    return await render(request, "ranking/index.html", db, user=user,
                        metric=metric, label=label, tabs=METRIC_TABS, rows=rows)


async def _top10(db: AsyncSession, metric: str):
    """根据 metric 直接查询对应 State 表，返回 [(user, score), ...] Top 10"""
    if metric == "farm":
        res = await db.execute(
            select(models.FarmState, models.User).join(
                models.User, models.FarmState.user_id == models.User.id
            ).order_by(models.FarmState.harvest_count.desc()).limit(10)
        )
        return [(u, s.harvest_count) for s, u in res.all()]
    if metric == "garden":
        res = await db.execute(
            select(models.GardenState, models.User).join(
                models.User, models.GardenState.user_id == models.User.id
            ).order_by(models.GardenState.level.desc()).limit(10)
        )
        return [(u, s.level) for s, u in res.all()]
    if metric == "martial":
        res = await db.execute(
            select(models.MartialState, models.User).join(
                models.User, models.MartialState.user_id == models.User.id
            ).order_by(models.MartialState.level.desc()).limit(10)
        )
        return [(u, s.level) for s, u in res.all()]
    if metric == "sea":
        res = await db.execute(
            select(models.SeaState, models.User).join(
                models.User, models.SeaState.user_id == models.User.id
            ).order_by(models.SeaState.level.desc()).limit(10)
        )
        return [(u, s.level) for s, u in res.all()]
    # 默认等级榜：各模块等级之和（User 无 level 字段，用四模块等级求和）
    sums = {}
    for StateModel in (models.FarmState, models.GardenState, models.MartialState, models.SeaState):
        res = await db.execute(select(StateModel))
        for s in res.scalars():
            sums[s.user_id] = sums.get(s.user_id, 0) + s.level
    if not sums:
        return []
    top = sorted(sums.items(), key=lambda x: x[1], reverse=True)[:10]
    if not top:
        return []
    res = await db.execute(select(models.User).where(models.User.id.in_([uid for uid, _ in top])))
    users = {u.id: u for u in res.scalars()}
    return [(users[uid], score) for uid, score in top if uid in users]
