"""背包：平台统一入口，按 module_key 分页（对应规范 5.4）"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user
from ..platform import goods, locks
from .views import render

router = APIRouter(prefix="/inventory")

MODULES = [("platform", "平台"), ("farm", "农场"), ("town", "小镇"), ("garden", "花园"), ("sea", "航海")]


@router.get("")
async def inventory(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    m = request.query_params.get("m", "platform")
    rows = await goods.list_inventory(db, user.id, m)
    return await render(request, "inventory.html", db, user=user, m=m, rows=rows, modules=MODULES)


@router.post("/sell/{inv_id}")
async def sell(inv_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    m = request.query_params.get("m", "platform")
    form = await request.form()
    qty = int(form.get("qty", 1))
    ok, msg = await goods.sell_item(db, user.id, inv_id, qty)
    return await render(request, "result.html", db, user=user, ok=ok, msg=msg, back_href=f"/inventory?m={m}", back_text="返回背包")


@router.post("/lock/{inv_id}")
async def toggle_inv_lock(inv_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """物品锁：禁止被消耗/出售"""
    from sqlalchemy import select
    from .. import models
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    m = request.query_params.get("m", "platform")
    inv = await db.get(models.Inventory, inv_id)
    if inv and inv.user_id == user.id:
        item = await db.get(models.Item, inv.item_id)
        inv.locked = not inv.locked
        await locks.toggle_item_lock(db, user.id, m, item.key)
    return RedirectResponse(f"/inventory?m={m}", status_code=303)
