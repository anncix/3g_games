"""事件总线：模块只能上报事件，不可直接修改平台数据

对应规范 5.5：
- 模块只能上报事件，不可直接修改：消息中心/活动进度/图标点亮/成就完成/排行分数
- 本模块是模块与平台交互的唯一合法通道
"""
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from . import icons, ranking, log


async def emit(db: AsyncSession, user_id: int, module_key: str, event: str, payload: dict | None = None):
    """统一事件上报入口。

    event 取值（模块→平台）：
      - message:           发消息给用户     payload: {to_id, type, title, content}
      - icon_light:        请求点亮图标     payload: {icon_key}
      - achievement:       推进成就         payload: {key, delta|absolute}
      - ranking:           上报排行分数     payload: {metric, score, period}
      - activity_progress: 推进活动进度     payload: {activity_id, delta}
      - interact_notify:   互动提醒         payload: {to_id, content}
    """
    payload = payload or {}
    if event == "message":
        db.add(models.Message(
            user_id=payload["to_id"], type=payload.get("type", "system"),
            title=payload.get("title", ""), content=payload.get("content", ""),
            module_key=module_key,
        ))
        await db.commit()
    elif event == "icon_light":
        await icons.light_icon(db, user_id, payload["icon_key"])
    elif event == "achievement":
        await icons.progress_achievement(
            db, user_id, payload["key"],
            delta=payload.get("delta", 1),
            absolute=payload.get("absolute", False),
        )
    elif event == "ranking":
        await ranking.submit_score(
            db, user_id, module_key, payload["metric"], payload["score"], payload.get("period", "total")
        )
    elif event == "activity_progress":
        ap = await db.get(models.ActivityProgress, payload["activity_id"])  # 复合主键改为查询
        # ActivityProgress 用自增 id；这里简化：按 activity_id+user_id 查
        from sqlalchemy import select
        res = await db.execute(
            select(models.ActivityProgress).where(
                models.ActivityProgress.activity_id == payload["activity_id"],
                models.ActivityProgress.user_id == user_id,
            )
        )
        ap = res.scalar_one_or_none()
        if ap:
            ap.progress += payload.get("delta", 1)
        else:
            db.add(models.ActivityProgress(
                activity_id=payload["activity_id"], user_id=user_id,
                progress=payload.get("delta", 1),
            ))
        await db.commit()
    elif event == "interact_notify":
        db.add(models.Message(
            user_id=payload["to_id"], type="interact",
            title=payload.get("title", "互动提醒"), content=payload.get("content", ""),
            module_key=module_key,
        ))
        await db.commit()
    # 操作留痕：所有事件默认记录
    await log.record(db, user_id, module_key, event, str(payload))


async def notify(db: AsyncSession, to_id: int, module_key: str, title: str, content: str, type: str = "interact"):
    """便捷方法：发一条平台消息"""
    db.add(models.Message(user_id=to_id, type=type, title=title, content=content, module_key=module_key))
    await db.commit()
