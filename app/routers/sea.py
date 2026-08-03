"""纵横四海模块

老味道点：城市节点+航线推进 / 任务驱动 / 遭遇结算 / 装备长期成长
"""
import random
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from ..platform import goods, icons, events, log
from .views import render

router = APIRouter(prefix="/games/sea")
MODULE_KEY = "sea"


async def get_state(db: AsyncSession, user_id: int) -> models.SeaState:
    st = await db.get(models.SeaState, user_id)
    if not st:
        st = models.SeaState(user_id=user_id)
        db.add(st)
        await db.commit()
        await db.refresh(st)
    return st


@router.get("")
async def sea_home(request: Request, db: AsyncSession = Depends(get_db)):
    """模块首页"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    # 完成航行
    if st.traveling_to and st.travel_arrive_at and datetime.utcnow() >= st.travel_arrive_at:
        st.current_city = st.traveling_to
        st.traveling_to = ""
        st.travel_arrive_at = None
        await db.commit()
    city = await db.get(models.SeaCity, st.current_city)
    # 当前城市可接任务数
    quests = (await db.execute(select(models.SeaQuest).where(
        models.SeaQuest.user_id == user.id, models.SeaQuest.status == "pending"))).scalars().all()
    todo = len(quests)
    if st.traveling_to: todo += 1
    # 装备
    equips = (await db.execute(select(models.SeaUserEquip).where(
        models.SeaUserEquip.user_id == user.id, models.SeaUserEquip.equipped.is_(True)))).scalars().all()
    return await render(request, "sea/home.html", db, user=user, st=st, city=city, quests=quests, todo=todo, equips=equips)


@router.get("/map")
async def sea_map(request: Request, db: AsyncSession = Depends(get_db)):
    """列表页：城市航线图"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    cities = (await db.execute(select(models.SeaCity))).scalars().all()
    routes = (await db.execute(select(models.SeaRoute).where(models.SeaRoute.from_city == st.current_city))).scalars().all()
    route_info = []
    for r in routes:
        to = await db.get(models.SeaCity, r.to_city)
        can = st.level >= r.required_level and not st.traveling_to
        route_info.append({"route": r, "to": to, "can": can})
    return await render(request, "sea/map.html", db, user=user, st=st, cities=cities, route_info=route_info)


@router.post("/travel/{to_city}")
async def travel(to_city: str, request: Request, db: AsyncSession = Depends(get_db)):
    """操作页：航行"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if st.traveling_to:
        return await render(request, "result.html", db, user=user, ok=False, msg="正在航行中", back_href="/games/sea", back_text="返回")
    route = (await db.execute(select(models.SeaRoute).where(
        models.SeaRoute.from_city == st.current_city, models.SeaRoute.to_city == to_city))).scalar_one_or_none()
    if not route:
        return await render(request, "result.html", db, user=user, ok=False, msg="没有这条航线", back_href="/games/sea/map", back_text="返回航线图")
    if st.level < route.required_level:
        return await render(request, "result.html", db, user=user, ok=False, msg=f"等级不足，需{route.required_level}级", back_href="/games/sea/map", back_text="返回航线图")
    to = await db.get(models.SeaCity, to_city)
    st.traveling_to = to_city
    st.travel_arrive_at = datetime.utcnow() + timedelta(seconds=route.travel_seconds)
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "travel", f"{st.current_city}->{to_city}")
    return await render(request, "result.html", db, user=user, ok=True, msg=f"启航前往{to.name}，约{route.travel_seconds}秒到达", back_href="/games/sea", back_text="返回首页")


@router.get("/quests")
async def quests_list(request: Request, db: AsyncSession = Depends(get_db)):
    """列表页：当前任务"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    quests = (await db.execute(select(models.SeaQuest).where(
        models.SeaQuest.user_id == user.id).order_by(models.SeaQuest.created_at.desc()))).scalars().all()
    # 若当前城市无待办任务，自动生成
    pending_here = [q for q in quests if q.status == "pending" and q.city_key == st.current_city]
    if not pending_here and not st.traveling_to:
        await _gen_quest(db, user.id, st.current_city)
        await db.commit()
        quests = (await db.execute(select(models.SeaQuest).where(
            models.SeaQuest.user_id == user.id).order_by(models.SeaQuest.created_at.desc()))).scalars().all()
    return await render(request, "sea/quests.html", db, user=user, st=st, quests=quests)


async def _gen_quest(db: AsyncSession, user_id: int, city_key: str):
    city = await db.get(models.SeaCity, city_key)
    types = ["encounter", "battle", "trade"]
    titles = {"encounter": f"{city.name}的奇遇", "battle": f"清剿{city.name}海盗", "trade": f"{city.name}贸易委托"}
    t = random.choice(types)
    db.add(models.SeaQuest(user_id=user_id, city_key=city_key, title=titles[t], type=t,
                           reward_exp=20, reward_coins=50))


@router.post("/quest/{qid}")
async def do_quest(qid: int, request: Request, db: AsyncSession = Depends(get_db)):
    """操作页+结果页：执行任务（遭遇结算）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    q = await db.get(models.SeaQuest, qid)
    if not q or q.user_id != user.id or q.status != "pending":
        return await render(request, "result.html", db, user=user, ok=False, msg="任务不可用", back_href="/games/sea/quests", back_text="返回任务")
    if q.city_key != st.current_city:
        return await render(request, "result.html", db, user=user, ok=False, msg="不在该城市，无法执行", back_href="/games/sea/quests", back_text="返回任务")
    # 遭遇结算：战力影响成功率
    win = random.random() < min(0.9, 0.5 + st.power * 0.01)
    if win:
        q.status = "done"
        st.exp += q.reward_exp
        user.coins += q.reward_coins
        need = st.level * 100
        while st.exp >= need:
            st.exp -= need
            st.level += 1
            need = st.level * 100
        await events.emit(db, user.id, MODULE_KEY, "ranking", {"metric": "level", "score": st.level})
        # 到达商旅之城成就
        if st.current_city == "trade_c":
            await events.emit(db, user.id, MODULE_KEY, "achievement", {"key": "achv_explorer"})
        if st.level >= 5:
            await events.emit(db, user.id, MODULE_KEY, "icon_light", {"icon_key": "icon_captain"})
        msg = f"任务成功！经验+{q.reward_exp}，金币+{q.reward_coins}"
        ok = True
    else:
        q.status = "failed"
        msg = "任务失败，战力不足，强化装备再来"
        ok = False
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "quest", f"{qid}:{q.status}")
    return await render(request, "result.html", db, user=user, ok=ok, msg=msg, back_href="/games/sea/quests", back_text="返回任务")


@router.get("/shop")
async def equip_shop(request: Request, db: AsyncSession = Depends(get_db)):
    """装备商店（长期成长线）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    equips = (await db.execute(select(models.SeaEquipment))).scalars().all()
    owned_keys = set()
    res = await db.execute(select(models.SeaUserEquip).where(models.SeaUserEquip.user_id == user.id))
    for ue in res.scalars().all():
        owned_keys.add(ue.equip_key)
    return await render(request, "sea/shop.html", db, user=user, st=st, equips=equips, owned_keys=owned_keys)


@router.post("/buy/{equip_key}")
async def buy_equip(equip_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    eq = await db.get(models.SeaEquipment, equip_key)
    if not eq:
        return await render(request, "result.html", db, user=user, ok=False, msg="装备不存在", back_href="/games/sea/shop", back_text="返回商店")
    if user.coins < eq.price:
        return await render(request, "result.html", db, user=user, ok=False, msg="金币不足", back_href="/games/sea/shop", back_text="返回商店")
    owned = (await db.execute(select(models.SeaUserEquip).where(
        models.SeaUserEquip.user_id == user.id, models.SeaUserEquip.equip_key == equip_key))).scalar_one_or_none()
    if owned:
        return await render(request, "result.html", db, user=user, ok=False, msg="已拥有", back_href="/games/sea/shop", back_text="返回商店")
    user.coins -= eq.price
    st = await get_state(db, user.id)
    db.add(models.SeaUserEquip(user_id=user.id, equip_key=equip_key, slot=eq.slot, equipped=True))
    st.power += eq.stat
    await goods.ensure_item(db, f"sea_equip_{equip_key}", eq.name, "equip", MODULE_KEY, False)
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "buy_equip", equip_key)
    return await render(request, "result.html", db, user=user, ok=True, msg=f"购入{eq.name}，战力+{eq.stat}", back_href="/games/sea/shop", back_text="返回商店")


@router.get("/rules")
async def rules(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return await render(request, "sea/rules.html", db, user=user)
