"""纵横四海模块

老味道点：城市节点+航线推进 / 任务驱动 / 遭遇结算 / 装备长期成长
"""
import json
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

router = APIRouter(prefix="/games/sea", tags=["纵横四海"])
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
    # 当前船只（载重影响贸易）
    current_ship = (await db.execute(select(models.SeaShip).where(
        models.SeaShip.name == st.ship_name))).scalar_one_or_none()
    return await render(request, "sea/home.html", db, user=user, st=st, city=city, quests=quests,
                        todo=todo, equips=equips, current_ship=current_ship)


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


# ============================================================
# v0.1.9：纵横四海补全路由（船只/副本/贸易/宠物/宝石/卡片/圣痕/装备套装/主线任务）
# 引用 v0.1.5~v0.1.8 入库但此前未被路由使用的 14 张资料表
# ============================================================

async def _today_open_day() -> int:
    """返回今日开放编号：1=周一...6=周六, 0=周日（与 seed open_days 口径一致）"""
    return datetime.utcnow().isoweekday() % 7


# ---------- 船只系统（SeaShip）----------
@router.get("/ships")
async def ships_list(request: Request, db: AsyncSession = Depends(get_db)):
    """列表页：14 艘船，标记已拥有"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    ships = (await db.execute(select(models.SeaShip).order_by(models.SeaShip.price))).scalars().all()
    owned_keys = set()
    for sp in ships:
        if await goods.count_item(db, user.id, f"sea_{sp.key}", MODULE_KEY) > 0:
            owned_keys.add(sp.key)
    return await render(request, "sea/ships.html", db, user=user, st=st,
                        ships=ships, owned_keys=owned_keys)


@router.post("/ships/buy/{ship_key}")
async def ship_buy(ship_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """操作页：购买船只（铜贝走 user.coins；金贝因模型无 gems 字段，回退用 user.coins）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    ship = await db.get(models.SeaShip, ship_key)
    if not ship:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="船只不存在", back_href="/games/sea/ships", back_text="返回船坞")
    item_key = f"sea_{ship.key}"
    if await goods.count_item(db, user.id, item_key, MODULE_KEY) > 0:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="已拥有该船", back_href="/games/sea/ships", back_text="返回船坞")
    if user.coins < ship.price:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"金币不足，需{ship.price}（{ship.currency}）",
                            back_href="/games/sea/ships", back_text="返回船坞")
    user.coins -= ship.price
    await goods.ensure_item(db, item_key, ship.name, "ship", MODULE_KEY, False,
                            ship.price, f"船只·载重{ship.load}·消耗{ship.consume_per_100}铜/百海里")
    await goods.add_item(db, user.id, item_key, MODULE_KEY, 1)
    st = await get_state(db, user.id)
    st.ship_name = ship.name  # 设为当前座船
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "ship_buy", ship_key)
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"购入{ship.name}！载重{ship.load}，消耗{ship.consume_per_100}铜/百海里",
                        back_href="/games/sea/ships", back_text="返回船坞")


# ---------- 副本系统（SeaDungeon）----------
@router.get("/dungeons")
async def dungeons_list(request: Request, db: AsyncSession = Depends(get_db)):
    """列表页：10 个副本，显示难度/等级要求/开放日"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    dungeons = (await db.execute(select(models.SeaDungeon))).scalars().all()
    today = await _today_open_day()
    info = []
    for d in dungeons:
        city = await db.get(models.SeaCity, d.entry_city)
        level_reqs = json.loads(d.level_reqs or "[]")
        diffs = json.loads(d.difficulties or "[]")
        open_days = json.loads(d.open_days or "[]")
        min_lvl = min(level_reqs) if level_reqs else 0
        is_open = (not open_days) or (today in open_days)
        # 玩家可挑战的最高难度档
        tier = -1
        for i, lr in enumerate(level_reqs):
            if st.level >= lr:
                tier = i
        can = is_open and tier >= 0 and not st.traveling_to
        info.append({"d": d, "city": city, "diffs": diffs, "level_reqs": level_reqs,
                     "is_open": is_open, "can": can, "tier": tier, "min_lvl": min_lvl})
    return await render(request, "sea/dungeons.html", db, user=user, st=st,
                        info=info, today=today)


@router.post("/dungeon/{dungeon_key}")
async def dungeon_challenge(dungeon_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """操作页：挑战副本（战力影响胜率，胜则得经验+掉落）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    d = await db.get(models.SeaDungeon, dungeon_key)
    if not d:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="副本不存在", back_href="/games/sea/dungeons", back_text="返回副本")
    if st.traveling_to:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="航行中无法挑战", back_href="/games/sea/dungeons", back_text="返回副本")
    open_days = json.loads(d.open_days or "[]")
    if open_days and (await _today_open_day()) not in open_days:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="今日未开放", back_href="/games/sea/dungeons", back_text="返回副本")
    level_reqs = json.loads(d.level_reqs or "[]")
    exps = json.loads(d.exps or "[]")
    diffs = json.loads(d.difficulties or "[]")
    drops = json.loads(d.drops or "[]")
    tier = -1
    for i, lr in enumerate(level_reqs):
        if st.level >= lr:
            tier = i
    if tier < 0:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"等级不足，需{min(level_reqs) if level_reqs else 0}级",
                            back_href="/games/sea/dungeons", back_text="返回副本")
    # 遭遇结算：战力影响成功率
    win = random.random() < min(0.9, 0.5 + st.power * 0.01)
    diff_name = diffs[tier] if tier < len(diffs) else f"难度{tier+1}"
    if win:
        exp_gain = exps[tier] if tier < len(exps) else 100
        st.exp += exp_gain
        need = st.level * 100
        while st.exp >= need:
            st.exp -= need
            st.level += 1
            need = st.level * 100
        drop_names = []
        for dk in drops:
            await goods.add_item(db, user.id, dk, MODULE_KEY, 1)
            it = await goods.get_item_by_key(db, dk)
            drop_names.append(it.name if it else dk)
        await events.emit(db, user.id, MODULE_KEY, "ranking", {"metric": "level", "score": st.level})
        msg = f"挑战{d.name}({diff_name})成功！经验+{exp_gain}"
        if drop_names:
            msg += "，掉落：" + "、".join(drop_names)
        ok = True
    else:
        msg = f"挑战{d.name}({diff_name})失败，强化装备再来"
        ok = False
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "dungeon", f"{dungeon_key}:{'win' if win else 'lose'}")
    return await render(request, "result.html", db, user=user, ok=ok, msg=msg,
                        back_href="/games/sea/dungeons", back_text="返回副本")


# ---------- 贸易系统（SeaCitySpecialty）----------
SPEC_BUY_PRICE = 50  # 每单位特产收购价

@router.get("/trade")
async def trade_market(request: Request, db: AsyncSession = Depends(get_db)):
    """列表页：当前港口特产，可买可卖（跨区域差价获利）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    city = await db.get(models.SeaCity, st.current_city)
    spec = await db.get(models.SeaCitySpecialty, st.current_city)
    specialties = []
    if spec:
        names = json.loads(spec.specialties or "[]")
        for i, nm in enumerate(names):
            specialties.append({"key": f"{spec.city_key}__{i}", "name": nm,
                                "buy_price": SPEC_BUY_PRICE})
    # 玩家持有的特产（背包 sea_spec_*）
    owned = []
    inv = await goods.list_inventory(db, user.id, MODULE_KEY)
    for inv_row, item in inv:
        if item.key.startswith("sea_spec_"):
            src_city = item.key[len("sea_spec_"):].rsplit("_", 1)[0]
            src_spec = await db.get(models.SeaCitySpecialty, src_city)
            src_region = src_spec.region if src_spec else "未知"
            cur_region = spec.region if spec else "未知"
            sell_price = 120 if src_region != cur_region else 30
            owned.append({"item_key": item.key, "name": item.name, "qty": inv_row.quantity,
                          "src_region": src_region, "sell_price": sell_price})
    cur_region = spec.region if spec else "未知"
    return await render(request, "sea/trade.html", db, user=user, st=st, city=city,
                        spec=spec, specialties=specialties, owned=owned, cur_region=cur_region)


@router.post("/trade/buy/{specialty_key}")
async def trade_buy(specialty_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """操作页：购入特产（扣除金币，入背包）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    spec = await db.get(models.SeaCitySpecialty, st.current_city)
    if not spec:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="本港无特产可购", back_href="/games/sea/trade", back_text="返回贸易")
    names = json.loads(spec.specialties or "[]")
    try:
        src_city, idx_s = specialty_key.rsplit("__", 1)
        idx = int(idx_s)
    except ValueError:
        src_city, idx = "", -1
    if src_city != spec.city_key or idx < 0 or idx >= len(names):
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="特产不存在", back_href="/games/sea/trade", back_text="返回贸易")
    name = names[idx]
    if user.coins < SPEC_BUY_PRICE:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"金币不足，需{SPEC_BUY_PRICE}", back_href="/games/sea/trade", back_text="返回贸易")
    item_key = f"sea_spec_{spec.city_key}_{idx}"
    user.coins -= SPEC_BUY_PRICE
    await goods.ensure_item(db, item_key, name, "trade", MODULE_KEY, True, 0,
                            f"特产·{spec.city_name}·{spec.region}")
    await goods.add_item(db, user.id, item_key, MODULE_KEY, 1)
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "trade_buy", f"{spec.city_key}:{name}")
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"购入{name}，花费{SPEC_BUY_PRICE}金币",
                        back_href="/games/sea/trade", back_text="返回贸易")


@router.post("/trade/sell")
async def trade_sell(request: Request, db: AsyncSession = Depends(get_db)):
    """操作页：售出全部持有特产（跨区域差价获利）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    spec = await db.get(models.SeaCitySpecialty, st.current_city)
    cur_region = spec.region if spec else "未知"
    inv = await goods.list_inventory(db, user.id, MODULE_KEY)
    total = 0
    sold = []
    for inv_row, item in list(inv):
        if not item.key.startswith("sea_spec_"):
            continue
        src_city = item.key[len("sea_spec_"):].rsplit("_", 1)[0]
        src_spec = await db.get(models.SeaCitySpecialty, src_city)
        src_region = src_spec.region if src_spec else "未知"
        price = 120 if src_region != cur_region else 30
        gain = price * inv_row.quantity
        total += gain
        sold.append(f"{item.name}×{inv_row.quantity}")
        await goods.remove_item(db, user.id, item.key, MODULE_KEY, inv_row.quantity)
    if not sold:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="没有可售特产", back_href="/games/sea/trade", back_text="返回贸易")
    user.coins += total
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "trade_sell", f"coins={total}")
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"售出{'、'.join(sold)}，获得{total}金币（当前区域：{cur_region}）",
                        back_href="/games/sea/trade", back_text="返回贸易")


# ---------- 宠物图鉴（SeaPet + SeaPetSkill + SeaMount + SeaWing + SeaFollower）----------
@router.get("/pets")
async def pets_album(request: Request, db: AsyncSession = Depends(get_db)):
    """列表页：60 只宠物图鉴 + 23 种宠物技能 + 坐骑/羽翼/随从图鉴"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    pets = (await db.execute(select(models.SeaPet))).scalars().all()
    pet_skills = (await db.execute(select(models.SeaPetSkill))).scalars().all()
    mounts = (await db.execute(select(models.SeaMount))).scalars().all()
    wings = (await db.execute(select(models.SeaWing))).scalars().all()
    followers = (await db.execute(select(models.SeaFollower))).scalars().all()
    owned_keys = set()
    for p in pets:
        if await goods.count_item(db, user.id, f"sea_pet_{p.key}", MODULE_KEY) > 0:
            owned_keys.add(p.key)
    return await render(request, "sea/pets.html", db, user=user, st=st,
                        pets=pets, pet_skills=pet_skills, owned_keys=owned_keys,
                        mounts=mounts, wings=wings, followers=followers)


# ---------- 宝石（SeaGem）----------
@router.get("/gems")
async def gems_list(request: Request, db: AsyncSession = Depends(get_db)):
    """列表页：60 颗宝石，按 tier 分组"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    gems = (await db.execute(select(models.SeaGem).order_by(models.SeaGem.tier, models.SeaGem.key))).scalars().all()
    tier_names = {1: "碎片", 2: "小", 3: "中", 4: "大", 5: "完美"}
    gem_list = []
    for g in gems:
        gem_list.append({"g": g, "slots": json.loads(g.slots or "[]"),
                         "tier_name": tier_names.get(g.tier, str(g.tier))})
    return await render(request, "sea/gems.html", db, user=user, st=st,
                        gem_list=gem_list, tier_names=tier_names)


# ---------- 卡片（SeaCard）----------
@router.get("/cards")
async def cards_list(request: Request, db: AsyncSession = Depends(get_db)):
    """列表页：21 张卡片，附魔部位/普通精致效果/掉落来源"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    cards = (await db.execute(select(models.SeaCard))).scalars().all()
    return await render(request, "sea/cards.html", db, user=user, st=st, cards=cards)


# ---------- 圣痕（SeaHolyMark）----------
@router.get("/holymarks")
async def holymarks_list(request: Request, db: AsyncSession = Depends(get_db)):
    """列表页：40 枚圣痕（10 种 × 4 品质）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    marks = (await db.execute(select(models.SeaHolyMark))).scalars().all()
    quality_order = {"白": 0, "绿": 1, "蓝": 2, "紫": 3}
    marks_sorted = sorted(marks, key=lambda m: (m.name, quality_order.get(m.quality, 9)))
    return await render(request, "sea/holymarks.html", db, user=user, st=st, marks=marks_sorted)


# ---------- 装备套装（SeaEquipSet + SeaEquipPiece）----------
@router.get("/equipsets")
async def equipsets_list(request: Request, db: AsyncSession = Depends(get_db)):
    """列表页：24 套装备套装，点击展开件名（SeaEquipPiece）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    sets = (await db.execute(select(models.SeaEquipSet).order_by(models.SeaEquipSet.level_req))).scalars().all()
    pieces = (await db.execute(select(models.SeaEquipPiece))).scalars().all()
    pieces_by_set = {}
    for p in pieces:
        pieces_by_set.setdefault(p.set_key, []).append(p)
    info = []
    for s in sets:
        sp = pieces_by_set.get(s.key, [])
        info.append({"s": s, "pieces": sp})
    return await render(request, "sea/equipsets.html", db, user=user, st=st, info=info)


# ---------- 主线任务链（SeaMainQuest）----------
@router.get("/mainquests")
async def mainquests_list(request: Request, db: AsyncSession = Depends(get_db)):
    """列表页：12 条主线任务链，环数/奖励/顺序"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    quests = (await db.execute(select(models.SeaMainQuest).order_by(models.SeaMainQuest.sort))).scalars().all()
    return await render(request, "sea/mainquests.html", db, user=user, st=st, quests=quests)
