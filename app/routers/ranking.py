"""排行榜（模块上报分数，平台统一展示 + 多榜直查 State 表）"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from .views import render

router = APIRouter(prefix="/ranking", tags=["排行"])


# 多榜配置：metric -> 中文名。v0.3.1 统一读 RankingEntry，State 表作兜底
# (metric, 中文名, RankingEntry.module_key, RankingEntry.metric, State 兜底配置)
METRIC_TABS = [
    ("level", "等级榜"),
    ("farm", "农场收获榜"),
    ("garden", "花园等级榜"),
    ("martial", "精武堂战力榜"),
    ("sea", "纵横四海榜"),
]
_VALID_METRICS = {k for k, _ in METRIC_TABS}

# v0.3.1 排行榜统一读 RankingEntry 表的映射（module_key, metric_name）
# 与 platform/ranking.py submit_score 上报的 key 对齐
_RANKING_MAP = {
    "farm": ("farm", "harvest"),
    "garden": ("garden", "level"),
    "martial": ("martial", "level"),
    "sea": ("sea", "level"),
}


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


async def _ranking_top10(db: AsyncSession, module_key: str, metric_name: str, n: int = 10):
    """v0.3.1 统一从 RankingEntry 表读 Top N。"""
    res = await db.execute(
        select(models.RankingEntry, models.User).join(
            models.User, models.RankingEntry.user_id == models.User.id
        ).where(
            models.RankingEntry.module_key == module_key,
            models.RankingEntry.metric == metric_name,
            models.RankingEntry.period == "total",
        ).order_by(models.RankingEntry.score.desc()).limit(n)
    )
    return [(u, e.score) for e, u in res.all()]


async def _state_fallback(db: AsyncSession, metric: str):
    """v0.3.1 State 表兜底：RankingEntry 无数据时回退直查 State 表。"""
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
    return []


async def _top10(db: AsyncSession, metric: str):
    """v0.3.1 双轨合一：优先读 RankingEntry，无数据时回退 State 表。

    修复之前 flower_lit 链接失效的根因：页面直查 State 表与模块上报 RankingEntry 不一致。
    """
    # 模块榜：优先 RankingEntry，兜底 State
    if metric in _RANKING_MAP:
        mk, mn = _RANKING_MAP[metric]
        rows = await _ranking_top10(db, mk, mn)
        if rows:
            return rows
        return await _state_fallback(db, metric)
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
