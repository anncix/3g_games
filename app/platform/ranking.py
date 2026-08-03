"""排行服务：模块上报分数，平台统一展示"""
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models


async def submit_score(db: AsyncSession, user_id: int, module_key: str, metric: str,
                       score: float, period: str = "total"):
    res = await db.execute(
        select(models.RankingEntry).where(
            models.RankingEntry.module_key == module_key,
            models.RankingEntry.metric == metric,
            models.RankingEntry.period == period,
            models.RankingEntry.user_id == user_id,
        )
    )
    entry = res.scalar_one_or_none()
    if entry:
        # total 取最大值，周期榜取累计（这里简化为最大）
        entry.score = max(entry.score, score) if period == "total" else entry.score + score
        entry.updated_at = datetime.utcnow()
    else:
        db.add(models.RankingEntry(module_key=module_key, metric=metric, period=period,
                                    user_id=user_id, score=score, updated_at=datetime.utcnow()))
    await db.commit()


async def top_n(db: AsyncSession, module_key: str, metric: str, period: str = "total", n: int = 20):
    res = await db.execute(
        select(models.RankingEntry, models.User).join(
            models.User, models.RankingEntry.user_id == models.User.id
        ).where(
            models.RankingEntry.module_key == module_key,
            models.RankingEntry.metric == metric,
            models.RankingEntry.period == period,
        ).order_by(models.RankingEntry.score.desc()).limit(n)
    )
    return res.all()
