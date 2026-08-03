"""商店：只上架物品字典里的物品（对应规范 4.3）"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from ..platform import goods, log
from .views import render

router = APIRouter(prefix="/shop", tags=["商店"])


@router.get("")
async def shop(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    m = request.query_params.get("m", "platform")
    # 按模块筛选上架物品
    res = await db.execute(select(models.ShopItem, models.Item).join(
        models.Item, models.ShopItem.item_id == models.Item.id
    ).where(models.ShopItem.enabled.is_(True), models.Item.module_key == m))
    items = res.all()
    # 若商店为空，自动按物品字典补一些种子/食材/花种/道具
    if not items:
        await _auto_stock(db, m)
        res = await db.execute(select(models.ShopItem, models.Item).join(
            models.Item, models.ShopItem.item_id == models.Item.id
        ).where(models.ShopItem.enabled.is_(True), models.Item.module_key == m))
        items = res.all()
    return await render(request, "shop.html", db, user=user, m=m, items=items)


async def _auto_stock(db: AsyncSession, m: str):
    """自动按物品字典上架该模块的消耗品"""
    res = await db.execute(select(models.Item).where(models.Item.module_key == m))
    for item in res.scalars().all():
        price = max(1, item.sell_price * 2)
        db.add(models.ShopItem(item_id=item.id, price=price, currency="金币", stock=-1,
                               category="prop" if item.type in ("crop", "ingredient", "flower") else item.type))
    await db.commit()


@router.post("/buy/{shop_id}")
async def buy(shop_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    m = request.query_params.get("m", "platform")
    si = await db.get(models.ShopItem, shop_id)
    if not si or not si.enabled:
        return await render(request, "result.html", db, user=user, ok=False, msg="商品不存在", back_href=f"/shop?m={m}", back_text="返回商店")
    if user.coins < si.price:
        return await render(request, "result.html", db, user=user, ok=False, msg="金币不足", back_href=f"/shop?m={m}", back_text="返回商店")
    item = await db.get(models.Item, si.item_id)
    user.coins -= si.price
    # 物品归入其所属模块的背包（以物品字典的 module_key 为准，更稳健）
    await goods.add_item(db, user.id, item.key, item.module_key, 1)
    await db.commit()
    await log.record(db, user.id, "platform", "shop_buy", item.key)
    return await render(request, "result.html", db, user=user, ok=True, msg=f"购买{item.name}×1", back_href=f"/shop?m={m}", back_text="返回商店")
