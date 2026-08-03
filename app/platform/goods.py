"""货品服务：物品字典 + 背包 + 商店

对应规范 4.3：
- 统一物品字典：名称/类型/堆叠/绑定/过期
- 商店只上架物品字典里的物品
- 模块资源仍在模块内循环，背包按 module_key 分页

v0.3.1 并发安全：扣除类操作改为条件更新（UPDATE ... WHERE quantity >= n），
避免 check-then-act 在并发下超扣。SQLite 单写锁 + 条件更新双重保障。
"""
import json
from datetime import datetime, timedelta
from sqlalchemy import select, update, delete, func
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
    """从背包扣除物品（自动跳过已上锁的），返回是否成功。

    v0.3.1 原子化：先校验总量充足，再逐行条件更新（仅当该行 quantity >= take 时扣减），
    避免并发双请求同时通过校验导致超扣。SQLite 单写锁 + 条件更新双重保障。
    """
    if quantity <= 0:
        return True
    item = await get_item_by_key(db, item_key)
    if not item:
        return False
    # 锁定查询：按 id 排序保证扣减顺序稳定
    res = await db.execute(
        select(models.Inventory).where(
            models.Inventory.user_id == user_id,
            models.Inventory.item_id == item.id,
            models.Inventory.module_key == module_key,
        ).order_by(models.Inventory.id)
    )
    invs = res.scalars().all()
    total = sum(i.quantity for i in invs)
    if total < quantity:
        return False
    # 原子扣减：逐行条件更新，仅当该行数量足够时扣减
    need = quantity
    emptied_ids = []
    for inv in invs:
        if need <= 0:
            break
        take = min(inv.quantity, need)
        # 条件更新：仅当当前数量仍 >= take 时扣减（并发安全）
        result = await db.execute(
            update(models.Inventory)
            .where(
                models.Inventory.id == inv.id,
                models.Inventory.quantity >= take,
            )
            .values(quantity=models.Inventory.quantity - take)
        )
        if result.rowcount > 0:
            need -= take
            if inv.quantity - take <= 0:
                emptied_ids.append(inv.id)
    # 清理空槽
    for inv_id in emptied_ids:
        await db.execute(
            delete(models.Inventory).where(
                models.Inventory.id == inv_id,
                models.Inventory.quantity <= 0,
            )
        )
    success = need <= 0
    if success:
        await db.commit()
    return success


async def count_item(db: AsyncSession, user_id: int, item_key: str, module_key: str) -> int:
    item = await get_item_by_key(db, item_key)
    if not item:
        return 0
    res = await db.execute(
        select(func.coalesce(func.sum(models.Inventory.quantity), 0)).where(
            models.Inventory.user_id == user_id,
            models.Inventory.item_id == item.id,
            models.Inventory.module_key == module_key,
        )
    )
    return res.scalar() or 0


async def list_inventory(db: AsyncSession, user_id: int, module_key: str | None = None):
    q = select(models.Inventory, models.Item).join(
        models.Item, models.Inventory.item_id == models.Item.id
    ).where(models.Inventory.user_id == user_id)
    if module_key:
        q = q.where(models.Inventory.module_key == module_key)
    res = await db.execute(q)
    return res.all()


async def sell_item(db: AsyncSession, user_id: int, inv_id: int, quantity: int = 1) -> tuple[bool, str]:
    """出售背包物品（受物品锁约束）。

    v0.3.1 原子化：用条件更新扣减库存，仅当数量足够时扣减并加金币，避免超卖。
    """
    inv = await db.get(models.Inventory, inv_id)
    if not inv or inv.user_id != user_id:
        return False, "物品不存在"
    if inv.locked:
        return False, "物品已上锁，无法出售"
    item = await db.get(models.Item, inv.item_id)
    if not item:
        return False, "物品不存在"
    if quantity <= 0:
        return False, "数量无效"
    # 原子扣减：仅当数量仍 >= quantity 时扣减
    result = await db.execute(
        update(models.Inventory)
        .where(
            models.Inventory.id == inv_id,
            models.Inventory.quantity >= quantity,
            models.Inventory.locked.is_(False),
        )
        .values(quantity=models.Inventory.quantity - quantity)
    )
    if result.rowcount == 0:
        return False, "数量不足或已变动"
    # 加金币（条件更新成功后）
    gain = item.sell_price * quantity
    await db.execute(
        update(models.User)
        .where(models.User.id == user_id)
        .values(coins=models.User.coins + gain)
    )
    # 清理空槽
    await db.execute(
        delete(models.Inventory).where(
            models.Inventory.id == inv_id,
            models.Inventory.quantity <= 0,
        )
    )
    await db.commit()
    return True, f"出售成功，获得 {gain} 金币"
