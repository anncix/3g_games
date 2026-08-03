"""客服：FAQ / 提单 / 申诉 / 操作日志查询（对应规范 6）"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from ..platform import log
from .views import render

router = APIRouter(prefix="/support", tags=["客服"])

FAQ = [
    ("如何防止被偷？", "在物品锁管理或地块详情中给资源上锁，上锁后禁止被翻/偷/消耗/出售。"),
    ("金币有什么用？", "金币是平台公共货币，用于购买装扮、基础道具、种子食材花种、加速等。模块资源仍在模块内循环。"),
    ("图标怎么点亮？", "图标由平台统一判定。达到条件(如收获10次、餐厅3星)会自动点亮，模块不能直接点亮。"),
    ("被误封/被盗怎么办？", "在客服页提交申诉工单，选择对应分类，客服会通过操作日志查询处理。"),
    ("如何关闭陌生人私聊？", "在设置→隐私锁中，将“谁能私聊”设为仅好友或无人。"),
]


@router.get("")
async def support_home(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    tickets = []
    if user:
        res = await db.execute(select(models.SupportTicket).where(
            models.SupportTicket.user_id == user.id).order_by(models.SupportTicket.created_at.desc()))
        tickets = res.scalars().all()
    return await render(request, "support/home.html", db, user=user, faq=FAQ, tickets=tickets)


@router.get("/new")
async def new_ticket_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return await render(request, "support/new.html", db, user=user)


@router.post("/new")
async def new_ticket(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    db.add(models.SupportTicket(
        user_id=user.id,
        category=form.get("category", "account"),
        title=form.get("title", "").strip()[:64],
        content=form.get("content", "").strip()[:500],
    ))
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True, msg="工单已提交，客服会尽快处理", back_href="/support", back_text="返回客服")


@router.get("/logs")
async def my_logs(request: Request, db: AsyncSession = Depends(get_db)):
    """操作日志查询（申诉用）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    logs = await log.recent_logs(db, user.id, 100)
    return await render(request, "support/logs.html", db, user=user, logs=logs)
