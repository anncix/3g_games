"""操作留痕：可追溯（客服/申诉）"""
from sqlalchemy.ext.asyncio import AsyncSession
from .. import models


async def record(db: AsyncSession, user_id: int, module_key: str, action: str, detail: str = ""):
    db.add(models.OperationLog(user_id=user_id, module_key=module_key, action=action, detail=detail))
    await db.commit()


async def recent_logs(db: AsyncSession, user_id: int, limit: int = 50):
    from sqlalchemy import select
    res = await db.execute(
        select(models.OperationLog).where(models.OperationLog.user_id == user_id)
        .order_by(models.OperationLog.created_at.desc()).limit(limit)
    )
    return res.scalars().all()
