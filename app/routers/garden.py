"""魔法花园模块

老味道点：成长阶段操作(发芽/花苗/花蕾/盛开) / 合成花种 / 花谱点亮核心目标 / 偷花送花展示
"""
import json
from datetime import datetime

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from ..platform import goods, icons, events, locks, friends as fsvc, log
from .views import render

router = APIRouter(prefix="/games/garden")
MODULE_KEY = "garden"


async def get_state(db: AsyncSession, user_id: int) -> models.GardenState:
    st = await db.get(models.GardenState, user_id)
    if not st:
        st = models.GardenState(user_id=user_id)
        db.add(st)
        await db.flush()  # 应用默认值
        for i in range(st.pot_count):
            db.add(models.GardenPot(user_id=user_id, slot=i))
        await db.commit()
        await db.refresh(st)
    return st


def flower_stage(pot: models.GardenPot, flower: models.Flower | None) -> str:
    if not pot.flower_key or not pot.planted_at or not flower:
        return "空盆"
    elapsed = (datetime.utcnow() - pot.planted_at).total_seconds()
    if elapsed >= flower.grow_seconds:
        return "盛开"
    stage_idx = min(int(elapsed / (flower.grow_seconds / flower.stages)) + 1, flower.stages)
    names = ["", "发芽", "花苗", "花蕾", "盛开"]
    return names[min(stage_idx, len(names)-1)]


def remain(pot: models.GardenPot, flower: models.Flower | None) -> int:
    if not pot.flower_key or not pot.planted_at or not flower:
        return 0
    return max(0, int(flower.grow_seconds - (datetime.utcnow() - pot.planted_at).total_seconds()))


@router.get("")
async def garden_home(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    pots = (await db.execute(select(models.GardenPot).where(
        models.GardenPot.user_id == user.id).order_by(models.GardenPot.slot))).scalars().all()
    pot_info = []
    todo = 0
    for p in pots:
        f = await db.get(models.Flower, p.flower_key) if p.flower_key else None
        stage = flower_stage(p, f)
        if stage == "盛开": todo += 1
        pot_info.append({"pot": p, "flower": f, "stage": stage, "remain": remain(p, f)})
    # 花谱
    flowers = (await db.execute(select(models.Flower))).scalars().all()
    collection = {}
    res = await db.execute(select(models.FlowerCollection).where(models.FlowerCollection.user_id == user.id))
    for c in res.scalars().all():
        collection[c.flower_key] = c.lit
    lit_count = sum(1 for v in collection.values() if v)
    return await render(request, "garden/home.html", db, user=user, st=st, pot_info=pot_info,
                        flowers=flowers, collection=collection, lit_count=lit_count, todo=todo)


@router.get("/pots")
async def pots_list(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    pots = (await db.execute(select(models.GardenPot).where(
        models.GardenPot.user_id == user.id).order_by(models.GardenPot.slot))).scalars().all()
    pot_info = []
    for p in pots:
        f = await db.get(models.Flower, p.flower_key) if p.flower_key else None
        locked = await locks.is_item_locked(db, user.id, MODULE_KEY, f"pot_{p.slot}")
        pot_info.append({"pot": p, "flower": f, "stage": flower_stage(p, f), "remain": remain(p, f), "locked": locked})
    flowers = (await db.execute(select(models.Flower))).scalars().all()
    return await render(request, "garden/pots.html", db, user=user, st=st, pot_info=pot_info, flowers=flowers)


@router.get("/pot/{slot}")
async def pot_detail(slot: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    res = await db.execute(select(models.GardenPot).where(
        models.GardenPot.user_id == user.id, models.GardenPot.slot == slot))
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(404)
    f = await db.get(models.Flower, p.flower_key) if p.flower_key else None
    locked = await locks.is_item_locked(db, user.id, MODULE_KEY, f"pot_{p.slot}")
    flowers = (await db.execute(select(models.Flower))).scalars().all() if not p.flower_key else []
    seeds = []
    for fl in (flowers if flowers else []):
        n = await goods.count_item(db, user.id, fl.seed_item_key, MODULE_KEY)
        if n > 0: seeds.append((fl, n))
    return await render(request, "garden/pot_detail.html", db, user=user, pot=p, flower=f,
                        stage=flower_stage(p, f), remain=remain(p, f), locked=locked, flowers=flowers, seeds=seeds)


@router.post("/plant/{slot}")
async def plant(slot: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    await get_state(db, user.id)  # 确保花盆已初始化
    form = await request.form()
    key = form.get("flower_key")
    fl = await db.get(models.Flower, key)
    if not fl:
        return await render(request, "result.html", db, user=user, ok=False, msg="花种不存在", back_href=f"/games/garden/pot/{slot}", back_text="返回")
    if not await goods.remove_item(db, user.id, fl.seed_item_key, MODULE_KEY, 1):
        return await render(request, "result.html", db, user=user, ok=False, msg="没有该花种，去合成或购买", back_href="/games/garden/craft", back_text="去合成")
    res = await db.execute(select(models.GardenPot).where(
        models.GardenPot.user_id == user.id, models.GardenPot.slot == slot))
    p = res.scalar_one_or_none()
    if not p:
        return await render(request, "result.html", db, user=user, ok=False, msg="花盆不存在", back_href="/games/garden/pots", back_text="返回花盆")
    p.flower_key = key
    p.planted_at = datetime.utcnow()
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "plant", f"slot{slot}:{key}")
    return await render(request, "result.html", db, user=user, ok=True, msg=f"种下{fl.name}，约{fl.grow_seconds}秒盛开", back_href=f"/games/garden/pot/{slot}", back_text="返回")


@router.post("/harvest/{slot}")
async def harvest(slot: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    res = await db.execute(select(models.GardenPot).where(
        models.GardenPot.user_id == user.id, models.GardenPot.slot == slot))
    p = res.scalar_one_or_none()
    fl = await db.get(models.Flower, p.flower_key) if p and p.flower_key else None
    if not fl or flower_stage(p, fl) != "盛开":
        return await render(request, "result.html", db, user=user, ok=False, msg="还未盛开", back_href=f"/games/garden/pot/{slot}", back_text="返回")
    await goods.add_item(db, user.id, fl.harvest_item_key, MODULE_KEY, 2)
    # 花谱点亮（核心目标）— 通过事件上报，平台统一判定
    coll = (await db.execute(select(models.FlowerCollection).where(
        models.FlowerCollection.user_id == user.id, models.FlowerCollection.flower_key == fl.key))).scalar_one_or_none()
    if not coll:
        db.add(models.FlowerCollection(user_id=user.id, flower_key=fl.key, lit=True))
    st = await get_state(db, user.id)
    st.exp += 15
    if st.exp >= st.level * 80:
        st.exp -= st.level * 80
        st.level += 1
    p.flower_key = ""
    p.planted_at = None
    await db.commit()
    # 花谱点亮数达标点亮图标
    lit_count = (await db.execute(select(models.FlowerCollection).where(
        models.FlowerCollection.user_id == user.id))).scalars().all()
    if len(lit_count) >= 3:
        await events.emit(db, user.id, MODULE_KEY, "icon_light", {"icon_key": "icon_gardener"})
    await events.emit(db, user.id, MODULE_KEY, "achievement", {"key": "achv_flower_master", "delta": 1})
    await events.emit(db, user.id, MODULE_KEY, "ranking", {"metric": "flower_lit", "score": 1})
    await log.record(db, user.id, MODULE_KEY, "harvest", fl.key)
    return await render(request, "result.html", db, user=user, ok=True, msg=f"收获{fl.name}×2，花谱已点亮！", back_href="/games/garden/pots", back_text="返回花盆")


@router.post("/lock/{slot}")
async def toggle_lock(slot: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    locked = await locks.toggle_item_lock(db, user.id, MODULE_KEY, f"pot_{slot}")
    return RedirectResponse(f"/games/garden/pot/{slot}", status_code=303)


@router.get("/craft")
async def craft_page(request: Request, db: AsyncSession = Depends(get_db)):
    """合成花种"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    flowers = (await db.execute(select(models.Flower))).scalars().all()
    info = []
    for fl in flowers:
        recipe = json.loads(fl.recipe) if fl.recipe else {}
        mats = []
        can = True
        for k, n in recipe.items():
            cnt = await goods.count_item(db, user.id, k, MODULE_KEY)
            mats.append((k, n, cnt))
            if cnt < n: can = False
        info.append({"fl": fl, "mats": mats, "can": can, "need_recipe": bool(recipe)})
    return await render(request, "garden/craft.html", db, user=user, info=info)


@router.post("/craft/{key}")
async def craft(key: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    fl = await db.get(models.Flower, key)
    if not fl or not fl.recipe:
        return await render(request, "result.html", db, user=user, ok=False, msg="该花种无法合成", back_href="/games/garden/craft", back_text="返回合成")
    recipe = json.loads(fl.recipe)
    for k, n in recipe.items():
        if await goods.count_item(db, user.id, k, MODULE_KEY) < n:
            return await render(request, "result.html", db, user=user, ok=False, msg=f"材料不足：{k}", back_href="/games/garden/craft", back_text="返回合成")
    for k, n in recipe.items():
        await goods.remove_item(db, user.id, k, MODULE_KEY, n)
    await goods.add_item(db, user.id, fl.seed_item_key, MODULE_KEY, 1)
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "craft", key)
    return await render(request, "result.html", db, user=user, ok=True, msg=f"合成{fl.name}种子×1", back_href="/games/garden/craft", back_text="返回合成")


@router.get("/collection")
async def collection(request: Request, db: AsyncSession = Depends(get_db)):
    """花谱（核心目标）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    flowers = (await db.execute(select(models.Flower))).scalars().all()
    lit_keys = set()
    res = await db.execute(select(models.FlowerCollection).where(models.FlowerCollection.user_id == user.id))
    for c in res.scalars().all():
        if c.lit: lit_keys.add(c.flower_key)
    return await render(request, "garden/collection.html", db, user=user, flowers=flowers, lit_keys=lit_keys)


@router.get("/visit/{uid}")
async def visit_garden(uid: int, request: Request, db: AsyncSession = Depends(get_db)):
    """访问好友花园（可偷花/送花）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if await fsvc.is_blocked(db, uid, user.id):
        return await render(request, "result.html", db, user=user, ok=False, msg="对方已拉黑你", back_href="/friends", back_text="返回好友")
    host = await db.get(models.User, uid)
    pots = (await db.execute(select(models.GardenPot).where(
        models.GardenPot.user_id == uid).order_by(models.GardenPot.slot))).scalars().all()
    pot_info = []
    for p in pots:
        f = await db.get(models.Flower, p.flower_key) if p.flower_key else None
        mature = flower_stage(p, f) == "盛开"
        locked = await locks.is_item_locked(db, uid, MODULE_KEY, f"pot_{p.slot}")
        already = await _already_stolen(db, user.id, p.id)
        pot_info.append({"pot": p, "flower": f, "mature": mature, "locked": locked, "already": already})
    # 我拥有的花（用于送花）
    my_flowers = []
    invs = await goods.list_inventory(db, user.id, MODULE_KEY)
    for inv, item in invs:
        if item.type == "flower" and inv.quantity > 0:
            my_flowers.append((item, inv.quantity))
    return await render(request, "garden/visit.html", db, user=user, host=host, pot_info=pot_info, my_flowers=my_flowers)


async def _already_stolen(db: AsyncSession, thief_id: int, pot_id: int) -> bool:
    res = await db.execute(select(models.OperationLog).where(
        models.OperationLog.user_id == thief_id, models.OperationLog.module_key == MODULE_KEY,
        models.OperationLog.action == "steal_flower", models.OperationLog.detail == str(pot_id)))
    return res.scalar_one_or_none() is not None


@router.post("/steal/{pot_id}")
async def steal_flower(pot_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    p = await db.get(models.GardenPot, pot_id)
    if not p or p.user_id == user.id:
        return await render(request, "result.html", db, user=user, ok=False, msg="不能偷自己的", back_href="/games/garden", back_text="返回")
    if await locks.is_item_locked(db, p.user_id, MODULE_KEY, f"pot_{p.slot}"):
        return await render(request, "result.html", db, user=user, ok=False, msg="🔒 花盆已上锁", back_href=f"/games/garden/visit/{p.user_id}", back_text="返回")
    if await _already_stolen(db, user.id, p.id):
        return await render(request, "result.html", db, user=user, ok=False, msg="已偷过这盆", back_href=f"/games/garden/visit/{p.user_id}", back_text="返回")
    fl = await db.get(models.Flower, p.flower_key) if p.flower_key else None
    if not fl or flower_stage(p, fl) != "盛开":
        return await render(request, "result.html", db, user=user, ok=False, msg="还没盛开", back_href=f"/games/garden/visit/{p.user_id}", back_text="返回")
    await goods.add_item(db, user.id, fl.harvest_item_key, MODULE_KEY, 1)
    p.flower_key = ""
    p.planted_at = None
    await events.emit(db, user.id, MODULE_KEY, "interact_notify",
                      {"to_id": p.user_id, "title": "被偷花", "content": f"{user.nickname} 偷了你的 {fl.name}"})
    await log.record(db, user.id, MODULE_KEY, "steal_flower", str(pot_id))
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True, msg=f"偷到{fl.name}×1", back_href=f"/games/garden/visit/{p.user_id}", back_text="继续逛")


@router.post("/gift/{uid}/{item_key}")
async def gift_flower(uid: int, item_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """送花"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if not await goods.remove_item(db, user.id, item_key, MODULE_KEY, 1):
        return await render(request, "result.html", db, user=user, ok=False, msg="你没有这朵花", back_href=f"/games/garden/visit/{uid}", back_text="返回")
    await goods.add_item(db, uid, item_key, MODULE_KEY, 1)
    item = await goods.get_item_by_key(db, item_key)
    await events.emit(db, user.id, MODULE_KEY, "interact_notify",
                      {"to_id": uid, "title": "收到鲜花", "content": f"{user.nickname} 送给你 {item.name} ×1"})
    await log.record(db, user.id, MODULE_KEY, "gift", f"{uid}:{item_key}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True, msg=f"送出{item.name}×1", back_href=f"/games/garden/visit/{uid}", back_text="返回")


@router.get("/rules")
async def rules(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return await render(request, "garden/rules.html", db, user=user)
