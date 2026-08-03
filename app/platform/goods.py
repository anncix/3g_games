"""货品服务：物品字典 + 背包 + 商店

对应规范 4.3：
- 统一物品字典：名称/类型/堆叠/绑定/过期
- 商店只上架物品字典里的物品
- 模块资源仍在模块内循环，背包按 module_key 分页
"""
import json
from datetime import datetime, timedelta
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models, config


async def get_item_by_key(db: AsyncSession, key: str) -> models.Item | None:
    res = await db.execute(select(models.Item).where(models.Item.key == key))
    return res.scalar_one_or_none()


async def ensure_item(db: AsyncSession, key: str, name: str, type: str, module_key: str = "platform",
                      stackable: bool = True, sell_price: int = 0, description: str = "") -> models.Item:
    item = await get_item_by_key(db, key)
    if item:
        return item
    item = models.Item(key=key, name=name, type=type, module_key=module_key,
                       stackable=stackable, sell_price=sell_price, description=description)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def add_item(db: AsyncSession, user_id: int, item_key: str, module_key: str, quantity: int = 1) -> int:
    """向背包增加物品，返回实际增加数量"""
    if quantity <= 0:
        return 0
    item = await get_item_by_key(db, item_key)
    if not item:
        return 0
    res = await db.execute(
        select(models.Inventory).where(
            models.Inventory.user_id == user_id,
            models.Inventory.item_id == item.id,
            models.Inventory.module_key == module_key,
        )
    )
    inv = res.scalar_one_or_none()
    added = quantity
    if inv:
        if item.stackable:
            inv.quantity = min(inv.quantity + quantity, config.STACK_LIMIT)
        else:
            # 不可堆叠：新建槽位
            for _ in range(quantity):
                db.add(models.Inventory(user_id=user_id, item_id=item.id, module_key=module_key, quantity=1,
                                        expires_at=(datetime.utcnow() + timedelta(seconds=item.expires)) if item.expires else None))
    else:
        expires_at = (datetime.utcnow() + timedelta(seconds=item.expires)) if item.expires else None
        db.add(models.Inventory(user_id=user_id, item_id=item.id, module_key=module_key,
                                quantity=quantity if item.stackable else 1, expires_at=expires_at))
        if not item.stackable and quantity > 1:
            for _ in range(quantity - 1):
                db.add(models.Inventory(user_id=user_id, item_id=item.id, module_key=module_key, quantity=1, expires_at=expires_at))
    await db.commit()
    return added


async def remove_item(db: AsyncSession, user_id: int, item_key: str, module_key: str, quantity: int = 1) -> bool:
    """从背包扣除物品（自动跳过已上锁的），返回是否成功"""
    item = await get_item_by_key(db, item_key)
    if not item:
        return False
    res = await db.execute(
        select(models.Inventory).where(
            models.Inventory.user_id == user_id,
            models.Inventory.item_id == item.id,
            models.Inventory.module_key == module_key,
        )
    )
    invs = res.scalars().all()
    total = sum(i.quantity for i in invs)
    if total < quantity:
        return False
    need = quantity
    for inv in invs:
        if need <= 0:
            break
        take = min(inv.quantity, need)
        inv.quantity -= take
        need -= take
        if inv.quantity <= 0:
            await db.delete(inv)
    await db.commit()
    return True


async def count_item(db: AsyncSession, user_id: int, item_key: str, module_key: str) -> int:
    item = await get_item_by_key(db, item_key)
    if not item:
        return 0
    res = await db.execute(
        select(models.Inventory).where(
            models.Inventory.user_id == user_id,
            models.Inventory.item_id == item.id,
            models.Inventory.module_key == module_key,
        )
    )
    return sum(i.quantity for i in res.scalars().all())


async def list_inventory(db: AsyncSession, user_id: int, module_key: str | None = None):
    q = select(models.Inventory, models.Item).join(
        models.Item, models.Inventory.item_id == models.Item.id
    ).where(models.Inventory.user_id == user_id)
    if module_key:
        q = q.where(models.Inventory.module_key == module_key)
    res = await db.execute(q)
    return res.all()


async def sell_item(db: AsyncSession, user_id: int, inv_id: int, quantity: int = 1) -> tuple[bool, str]:
    """出售背包物品（受物品锁约束）"""
    inv = await db.get(models.Inventory, inv_id)
    if not inv or inv.user_id != user_id:
        return False, "物品不存在"
    if inv.locked:
        return False, "物品已上锁，无法出售"
    item = await db.get(models.Item, inv.item_id)
    if not item:
        return False, "物品不存在"
    if inv.quantity < quantity:
        return False, "数量不足"
    inv.quantity -= quantity
    user = await db.get(models.User, user_id)
    user.coins += item.sell_price * quantity
    if inv.quantity <= 0:
        await db.delete(inv)
    await db.commit()
    return True, f"出售成功，获得 {item.sell_price * quantity} 金币"
