"""魔法花园模块（v0.0.2 重新设计）

设计规范落地：
- 花种(Seed)/花朵(Bloom)/花谱项(AlbumEntry) 三概念分离
- 种植阶段状态机：空地→已播种→发芽期→花苗期→花蕾期→成熟→收获→空地
- 三件套阶段操作：浇水/除草/除虫（影响产量/经验/稀有概率）
- 花谱按系列分组，点亮有奖励（经验/金币 + 平台图标/成就/消息）
- 合成工坊（花朵→花种）+ 兑换中心（材料→稀有花种）
- 好友互动：偷花/帮忙/送花，被偷有保底、有消息提醒
- 等级系统：经验来自劳动行为（播种/操作/收获/点亮/帮忙）
- 事件上报：garden_* 系列由平台统一处理消息/图标/成就/排行
"""
import json
import random
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

# 阶段名称（索引 1..stages）
STAGE_NAMES = {0: "已播种", 1: "发芽期", 2: "花苗期", 3: "花蕾期", 4: "成熟"}
ACTION_NAMES = {"water": "浇水", "weed": "除草", "debug": "除虫"}

# 升级曲线：每级所需经验 = level * 80（可运营配置）
def exp_needed(level: int) -> int:
    return level * 80


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


async def add_exp(db: AsyncSession, st: models.GardenState, amount: int):
    """加经验并处理升级"""
    st.exp += amount
    while st.exp >= exp_needed(st.level):
        st.exp -= exp_needed(st.level)
        st.level += 1


def current_stage(pot: models.GardenPot, seed: models.GardenSeed | None) -> int:
    """返回当前阶段索引：-1=空地, 0=已播种, 1..stages-1=生长中, stages=成熟"""
    if not pot.seed_key or not pot.planted_at or not seed:
        return -1
    elapsed = (datetime.utcnow() - pot.planted_at).total_seconds()
    if elapsed >= seed.grow_seconds:
        return seed.stages  # 成熟
    # 按时间分阶段
    step = seed.grow_seconds / seed.stages
    return min(int(elapsed // step), seed.stages - 1)


def stage_label(stage: int) -> str:
    return STAGE_NAMES.get(stage, "未知")


def remain_seconds(pot: models.GardenPot, seed: models.GardenSeed | None) -> int:
    if not pot.seed_key or not pot.planted_at or not seed:
        return 0
    return max(0, int(seed.grow_seconds - (datetime.utcnow() - pot.planted_at).total_seconds()))


def needed_action(seed: models.GardenSeed, stage: int) -> str | None:
    """该阶段需要哪种操作（water/weed/debug），无需则 None"""
    if stage <= 0 or stage >= seed.stages:
        return None
    actions = json.loads(seed.stage_actions) if seed.stage_actions else {}
    return actions.get(str(stage))


def pot_action_status(pot: models.GardenPot, seed: models.GardenSeed) -> dict:
    """计算花盆当前可操作状态"""
    stage = current_stage(pot, seed)
    info = {"stage": stage, "stage_label": stage_label(stage), "remain": remain_seconds(pot, seed)}
    if stage <= 0 or stage >= seed.stages:
        info["action"] = None
        info["action_done"] = True
        return info
    act = needed_action(seed, stage)
    info["action"] = act
    if act == "water":
        info["action_done"] = pot.watered
    elif act == "weed":
        info["action_done"] = pot.weeded
    elif act == "debug":
        info["action_done"] = pot.debugged
    else:
        info["action_done"] = True
    return info


# ============================================================
# 首页 / 花圃
# ============================================================
@router.get("")
async def garden_home(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    pots = (await db.execute(select(models.GardenPot).where(
        models.GardenPot.user_id == user.id).order_by(models.GardenPot.slot))).scalars().all()
    pot_info = []
    todo_harvest = 0
    todo_action = 0
    for p in pots:
        seed = await db.get(models.GardenSeed, p.seed_key) if p.seed_key else None
        ainfo = pot_action_status(p, seed) if seed else {"stage": -1, "stage_label": "空地", "remain": 0, "action": None, "action_done": True}
        if ainfo["stage"] == seed.stages if seed else False:
            todo_harvest += 1
        if ainfo.get("action") and not ainfo["action_done"]:
            todo_action += 1
        pot_info.append({"pot": p, "seed": seed, **ainfo})
    # 花谱进度
    entries = (await db.execute(select(models.GardenAlbumEntry))).scalars().all()
    lit_keys = set()
    res = await db.execute(select(models.GardenCollection).where(models.GardenCollection.user_id == user.id))
    for c in res.scalars().all():
        if c.lit:
            lit_keys.add(c.entry_key)
    lit_count = len(lit_keys)
    return await render(request, "garden/home.html", db, user=user, st=st,
                        pot_info=pot_info, todo_harvest=todo_harvest, todo_action=todo_action,
                        entries=entries, lit_count=lit_count,
                        exp_need=exp_needed(st.level), action_names=ACTION_NAMES)


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
        seed = await db.get(models.GardenSeed, p.seed_key) if p.seed_key else None
        ainfo = pot_action_status(p, seed) if seed else {"stage": -1, "stage_label": "空地", "remain": 0, "action": None, "action_done": True}
        locked = await locks.is_item_locked(db, user.id, MODULE_KEY, f"pot_{p.slot}")
        pot_info.append({"pot": p, "seed": seed, "locked": locked, **ainfo})
    return await render(request, "garden/pots.html", db, user=user, st=st, pot_info=pot_info,
                        exp_need=exp_needed(st.level), action_names=ACTION_NAMES)


@router.get("/pot/{slot}")
async def pot_detail(slot: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    res = await db.execute(select(models.GardenPot).where(
        models.GardenPot.user_id == user.id, models.GardenPot.slot == slot))
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(404)
    seed = await db.get(models.GardenSeed, p.seed_key) if p.seed_key else None
    locked = await locks.is_item_locked(db, user.id, MODULE_KEY, f"pot_{p.slot}")
    ainfo = pot_action_status(p, seed) if seed else {"stage": -1, "stage_label": "空地", "remain": 0, "action": None, "action_done": True}
    # 可播种的花种（等级足够 + 有库存）
    plantable = []
    if not p.seed_key:
        all_seeds = (await db.execute(select(models.GardenSeed).where(
            models.GardenSeed.min_level <= st.level))).scalars().all()
        for s in all_seeds:
            n = await goods.count_item(db, user.id, s.seed_item_key, MODULE_KEY)
            if n > 0:
                plantable.append((s, n))
    return await render(request, "garden/pot_detail.html", db, user=user, st=st, pot=p, seed=seed,
                        locked=locked, ainfo=ainfo, plantable=plantable,
                        action_names=ACTION_NAMES, exp_need=exp_needed(st.level))


# ============================================================
# 播种 / 阶段操作 / 收获
# ============================================================
@router.post("/plant/{slot}")
async def plant(slot: int, request: Request, db: AsyncSession = Depends(get_db)):
    """操作页：播种"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    form = await request.form()
    seed_key = form.get("seed_key")
    seed = await db.get(models.GardenSeed, seed_key)
    if not seed:
        return await render(request, "result.html", db, user=user, ok=False, msg="花种不存在",
                            back_href=f"/games/garden/pot/{slot}", back_text="返回花盆")
    if st.level < seed.min_level:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"需要花园等级 {seed.min_level} 才能种植{seed.name}",
                            back_href=f"/games/garden/pot/{slot}", back_text="返回花盆")
    if not await goods.remove_item(db, user.id, seed.seed_item_key, MODULE_KEY, 1):
        return await render(request, "result.html", db, user=user, ok=False, msg="没有该花种",
                            back_href="/games/garden/craft", back_text="去合成")
    res = await db.execute(select(models.GardenPot).where(
        models.GardenPot.user_id == user.id, models.GardenPot.slot == slot))
    p = res.scalar_one_or_none()
    if not p:
        return await render(request, "result.html", db, user=user, ok=False, msg="花盆不存在",
                            back_href="/games/garden/pots", back_text="返回花圃")
    p.seed_key = seed_key
    p.planted_at = datetime.utcnow()
    p.watered = False
    p.weeded = False
    p.debugged = False
    await add_exp(db, st, 2)  # 播种少量经验
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "plant", f"slot{slot}:{seed_key}")
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"种下{seed.name}，约{seed.grow_seconds}秒成熟。注意浇水/除草/除虫可提升产量！",
                        back_href=f"/games/garden/pot/{slot}", back_text="返回花盆")


@router.post("/action/{slot}/{action}")
async def stage_action(slot: int, action: str, request: Request, db: AsyncSession = Depends(get_db)):
    """操作页：三件套阶段操作（water/weed/debug）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if action not in ACTION_NAMES:
        return await render(request, "result.html", db, user=user, ok=False, msg="未知操作",
                            back_href=f"/games/garden/pot/{slot}", back_text="返回花盆")
    st = await get_state(db, user.id)
    res = await db.execute(select(models.GardenPot).where(
        models.GardenPot.user_id == user.id, models.GardenPot.slot == slot))
    p = res.scalar_one_or_none()
    if not p or not p.seed_key:
        return await render(request, "result.html", db, user=user, ok=False, msg="花盆为空",
                            back_href=f"/games/garden/pot/{slot}", back_text="返回花盆")
    seed = await db.get(models.GardenSeed, p.seed_key)
    ainfo = pot_action_status(p, seed)
    # 校验当前阶段确实需要此操作
    needed = needed_action(seed, ainfo["stage"])
    if needed != action:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"当前阶段({ainfo['stage_label']})不需要{ACTION_NAMES[action]}",
                            back_href=f"/games/garden/pot/{slot}", back_text="返回花盆")
    if ainfo["action_done"]:
        return await render(request, "result.html", db, user=user, ok=False, msg="本阶段已操作过",
                            back_href=f"/games/garden/pot/{slot}", back_text="返回花盆")
    # 执行操作
    if action == "water":
        p.watered = True
    elif action == "weed":
        p.weeded = True
    elif action == "debug":
        p.debugged = True
    await add_exp(db, st, 3)  # 操作少量经验
    await db.commit()
    # 事件上报：阶段操作完成
    await events.emit(db, user.id, MODULE_KEY, "achievement",
                      {"key": "achv_flower_master", "delta": 1})
    await log.record(db, user.id, MODULE_KEY, "stage_action", f"slot{slot}:{action}")
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"{ACTION_NAMES[action]}完成！获得经验+3，产量与稀有度提升",
                        back_href=f"/games/garden/pot/{slot}", back_text="返回花盆")


@router.post("/harvest/{slot}")
async def harvest(slot: int, request: Request, db: AsyncSession = Depends(get_db)):
    """操作页：收获（结算清晰展示获得物）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    res = await db.execute(select(models.GardenPot).where(
        models.GardenPot.user_id == user.id, models.GardenPot.slot == slot))
    p = res.scalar_one_or_none()
    if not p or not p.seed_key:
        return await render(request, "result.html", db, user=user, ok=False, msg="花盆为空",
                            back_href="/games/garden/pots", back_text="返回花圃")
    seed = await db.get(models.GardenSeed, p.seed_key)
    stage = current_stage(p, seed)
    if stage < seed.stages:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"还未成熟（当前：{stage_label(stage)}），剩余 {remain_seconds(p, seed)} 秒",
                            back_href=f"/games/garden/pot/{slot}", back_text="返回花盆")
    # 计算产量：三件套完成度影响
    actions_done = sum([p.watered, p.weeded, p.debugged])
    base_yield = random.randint(seed.yield_min, seed.yield_max)
    final_yield = base_yield + (1 if actions_done >= 2 else 0)  # 完成2+操作+1产量
    # 随机选择产出花朵（按权重）
    blooms_map = json.loads(seed.possible_blooms)
    bloom_keys = list(blooms_map.keys())
    weights = list(blooms_map.values())
    # 操作完成度高 → 稀有概率提升（简单实现：完成全部操作时，偏向高稀有）
    results = []
    coins_gain = 0
    exp_gain = 0
    lit_entries = []
    for _ in range(final_yield):
        bk = random.choices(bloom_keys, weights=weights, k=1)[0]
        bloom = await db.get(models.GardenBloom, bk)
        if not bloom:
            continue
        await goods.add_item(db, user.id, bloom.item_key, MODULE_KEY, 1)
        results.append(bloom)
        coins_gain += bloom.sell_price // 2
        exp_gain += 5
        # 花谱点亮（首次获得该花朵）
        entry = await db.get(models.GardenAlbumEntry, bloom.album_entry_key)
        if entry:
            existing = (await db.execute(select(models.GardenCollection).where(
                models.GardenCollection.user_id == user.id,
                models.GardenCollection.entry_key == entry.key))).scalar_one_or_none()
            if not existing:
                db.add(models.GardenCollection(user_id=user.id, entry_key=entry.key, lit=True))
                lit_entries.append(entry)
                exp_gain += 15  # 点亮花谱一次性较多经验
                coins_gain += 20
    st.coins += coins_gain
    await add_exp(db, st, exp_gain)
    # 清空花盆
    p.seed_key = ""
    p.planted_at = None
    p.watered = False
    p.weeded = False
    p.debugged = False
    await db.commit()
    # 事件上报
    await events.emit(db, user.id, MODULE_KEY, "ranking",
                      {"metric": "flower_lit", "score": len(lit_entries)})
    if lit_entries:
        await events.emit(db, user.id, MODULE_KEY, "icon_light", {"icon_key": "icon_gardener"})
    await events.emit(db, user.id, MODULE_KEY, "achievement",
                      {"key": "achv_flower_master", "delta": 1})
    await log.record(db, user.id, MODULE_KEY, "harvest", f"slot{slot}:{seed.key}:{final_yield}")
    # 结果页：清晰展示获得物
    bloom_summary = {}
    for b in results:
        bloom_summary[b.name] = bloom_summary.get(b.name, 0) + 1
    summary_text = "、".join(f"{n}×{c}" for n, c in bloom_summary.items())
    msg = f"收获{seed.name}：{summary_text} | 金币+{coins_gain} | 经验+{exp_gain}"
    if lit_entries:
        msg += f" | 点亮花谱：{'、'.join(e.name for e in lit_entries)}"
    return await render(request, "garden/harvest_result.html", db, user=user, ok=True,
                        msg=msg, results=results, bloom_summary=bloom_summary,
                        coins_gain=coins_gain, exp_gain=exp_gain,
                        lit_entries=lit_entries, seed=seed, st=st,
                        back_href="/games/garden/pots", back_text="返回花圃")


@router.post("/lock/{slot}")
async def toggle_lock(slot: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    await locks.toggle_item_lock(db, user.id, MODULE_KEY, f"pot_{slot}")
    return RedirectResponse(f"/games/garden/pot/{slot}", status_code=303)


# ============================================================
# 花谱（图鉴内核）
# ============================================================
@router.get("/album")
async def album(request: Request, db: AsyncSession = Depends(get_db)):
    """花谱：按系列分组"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    entries = (await db.execute(select(models.GardenAlbumEntry).order_by(models.GardenAlbumEntry.series))).scalars().all()
    lit_keys = set()
    res = await db.execute(select(models.GardenCollection).where(models.GardenCollection.user_id == user.id))
    for c in res.scalars().all():
        if c.lit:
            lit_keys.add(c.entry_key)
    # 按系列分组
    groups = {}
    for e in entries:
        groups.setdefault(e.series, []).append(e)
    lit_count = len(lit_keys)
    return await render(request, "garden/album.html", db, user=user, groups=groups,
                        lit_keys=lit_keys, lit_count=lit_count, total=len(entries))


@router.get("/album/{entry_key}")
async def album_detail(entry_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """花谱详情"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    entry = await db.get(models.GardenAlbumEntry, entry_key)
    if not entry:
        raise HTTPException(404)
    bloom = await db.get(models.GardenBloom, entry.bloom_key)
    lit = (await db.execute(select(models.GardenCollection).where(
        models.GardenCollection.user_id == user.id,
        models.GardenCollection.entry_key == entry_key))).scalar_one_or_none()
    is_lit = bool(lit and lit.lit)
    # 是否持有该花朵
    hold = 0
    if bloom:
        hold = await goods.count_item(db, user.id, bloom.item_key, MODULE_KEY)
    return await render(request, "garden/album_detail.html", db, user=user, entry=entry,
                        bloom=bloom, is_lit=is_lit, hold=hold)


@router.post("/album/light/{entry_key}")
async def album_light(entry_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """点亮花谱（持有对应花朵时点亮）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    entry = await db.get(models.GardenAlbumEntry, entry_key)
    if not entry:
        raise HTTPException(404)
    bloom = await db.get(models.GardenBloom, entry.bloom_key)
    if not bloom:
        return await render(request, "result.html", db, user=user, ok=False, msg="花谱数据异常",
                            back_href="/games/garden/album", back_text="返回花谱")
    existing = (await db.execute(select(models.GardenCollection).where(
        models.GardenCollection.user_id == user.id,
        models.GardenCollection.entry_key == entry_key))).scalar_one_or_none()
    if existing and existing.lit:
        return await render(request, "result.html", db, user=user, ok=False, msg="该花谱已点亮",
                            back_href=f"/games/garden/album/{entry_key}", back_text="返回")
    if await goods.count_item(db, user.id, bloom.item_key, MODULE_KEY) < 1:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"未持有{bloom.name}，无法点亮",
                            back_href=f"/games/garden/album/{entry_key}", back_text="返回")
    st = await get_state(db, user.id)
    if existing:
        existing.lit = True
        existing.lit_at = datetime.utcnow()
    else:
        db.add(models.GardenCollection(user_id=user.id, entry_key=entry_key, lit=True))
    st.coins += 20
    await add_exp(db, st, 15)
    await db.commit()
    # 事件上报：花谱点亮
    await events.emit(db, user.id, MODULE_KEY, "icon_light", {"icon_key": "icon_gardener"})
    await events.emit(db, user.id, MODULE_KEY, "ranking", {"metric": "flower_lit", "score": 1})
    await events.emit(db, user.id, MODULE_KEY, "achievement", {"key": "achv_flower_master", "delta": 1})
    await log.record(db, user.id, MODULE_KEY, "album_lit", entry_key)
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"点亮花谱【{entry.name}】！金币+20 经验+15",
                        back_href="/games/garden/album", back_text="返回花谱")


# ============================================================
# 合成工坊 / 兑换中心
# ============================================================
@router.get("/craft")
async def craft_page(request: Request, db: AsyncSession = Depends(get_db)):
    """合成工坊：配方列表"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    recipes = (await db.execute(select(models.GardenRecipe))).scalars().all()
    info = []
    for r in recipes:
        seed = await db.get(models.GardenSeed, r.result_seed_key)
        mats = json.loads(r.materials)
        mat_info = []
        can = True
        for k, n in mats.items():
            item = await goods.get_item_by_key(db, k)
            cnt = await goods.count_item(db, user.id, k, MODULE_KEY)
            mat_info.append({"key": k, "name": item.name if item else k, "need": n, "have": cnt})
            if cnt < n:
                can = False
        info.append({"recipe": r, "seed": seed, "mats": mat_info, "can": can})
    return await render(request, "garden/craft.html", db, user=user, info=info)


@router.post("/craft/{recipe_id}")
async def craft(recipe_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """合成花种"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    r = await db.get(models.GardenRecipe, recipe_id)
    if not r:
        return await render(request, "result.html", db, user=user, ok=False, msg="配方不存在",
                            back_href="/games/garden/craft", back_text="返回合成")
    seed = await db.get(models.GardenSeed, r.result_seed_key)
    if not seed:
        return await render(request, "result.html", db, user=user, ok=False, msg="目标花种不存在",
                            back_href="/games/garden/craft", back_text="返回合成")
    mats = json.loads(r.materials)
    for k, n in mats.items():
        if await goods.count_item(db, user.id, k, MODULE_KEY) < n:
            item = await goods.get_item_by_key(db, k)
            return await render(request, "result.html", db, user=user, ok=False,
                                msg=f"材料不足：{item.name if item else k}",
                                back_href="/games/garden/craft", back_text="返回合成")
    for k, n in mats.items():
        await goods.remove_item(db, user.id, k, MODULE_KEY, n)
    await goods.add_item(db, user.id, seed.seed_item_key, MODULE_KEY, r.result_qty)
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "craft", f"{recipe_id}:{r.result_seed_key}")
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"合成成功！获得{seed.name}种子×{r.result_qty}",
                        back_href="/games/garden/craft", back_text="返回合成")


@router.get("/exchange")
async def exchange_page(request: Request, db: AsyncSession = Depends(get_db)):
    """兑换中心：活动材料 -> 花种"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    exchanges = (await db.execute(select(models.GardenExchange))).scalars().all()
    info = []
    for ex in exchanges:
        seed = await db.get(models.GardenSeed, ex.result_seed_key)
        mats = json.loads(ex.materials)
        mat_info = []
        can = True
        for k, n in mats.items():
            item = await goods.get_item_by_key(db, k)
            cnt = await goods.count_item(db, user.id, k, MODULE_KEY)
            mat_info.append({"key": k, "name": item.name if item else k, "need": n, "have": cnt})
            if cnt < n:
                can = False
        info.append({"ex": ex, "seed": seed, "mats": mat_info, "can": can})
    return await render(request, "garden/exchange.html", db, user=user, info=info)


@router.post("/exchange/{exchange_id}")
async def do_exchange(exchange_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    ex = await db.get(models.GardenExchange, exchange_id)
    if not ex:
        return await render(request, "result.html", db, user=user, ok=False, msg="兑换不存在",
                            back_href="/games/garden/exchange", back_text="返回兑换")
    seed = await db.get(models.GardenSeed, ex.result_seed_key)
    if not seed:
        return await render(request, "result.html", db, user=user, ok=False, msg="目标花种不存在",
                            back_href="/games/garden/exchange", back_text="返回兑换")
    mats = json.loads(ex.materials)
    for k, n in mats.items():
        if await goods.count_item(db, user.id, k, MODULE_KEY) < n:
            item = await goods.get_item_by_key(db, k)
            return await render(request, "result.html", db, user=user, ok=False,
                                msg=f"材料不足：{item.name if item else k}",
                                back_href="/games/garden/exchange", back_text="返回兑换")
    for k, n in mats.items():
        await goods.remove_item(db, user.id, k, MODULE_KEY, n)
    await goods.add_item(db, user.id, seed.seed_item_key, MODULE_KEY, ex.result_qty)
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "exchange", f"{exchange_id}:{ex.result_seed_key}")
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"兑换成功！获得{seed.name}种子×{ex.result_qty}",
                        back_href="/games/garden/exchange", back_text="返回兑换")


# ============================================================
# 展示页
# ============================================================
@router.get("/showcase")
async def showcase(request: Request, db: AsyncSession = Depends(get_db)):
    """展示页：稀有花 + 花谱概览"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    entries = (await db.execute(select(models.GardenAlbumEntry))).scalars().all()
    lit_keys = set()
    lit_entries = []
    res = await db.execute(select(models.GardenCollection).where(
        models.GardenCollection.user_id == user.id).order_by(models.GardenCollection.lit_at.desc()))
    for c in res.scalars().all():
        if c.lit:
            lit_keys.add(c.entry_key)
            e = await db.get(models.GardenAlbumEntry, c.entry_key)
            if e:
                lit_entries.append(e)
    recent = lit_entries[:5]
    # 稀有花展示（持有的稀有/传说花朵）
    invs = await goods.list_inventory(db, user.id, MODULE_KEY)
    rare_blooms = []
    for inv, item in invs:
        if item.type == "flower" and inv.quantity > 0:
            # 查对应 bloom 定义
            bloom = (await db.execute(select(models.GardenBloom).where(
                models.GardenBloom.item_key == item.key))).scalar_one_or_none()
            if bloom and bloom.rarity in ("稀有", "传说"):
                rare_blooms.append({"bloom": bloom, "item": item, "qty": inv.quantity})
    return await render(request, "garden/showcase.html", db, user=user, st=st,
                        lit_count=len(lit_keys), total=len(entries),
                        recent=recent, rare_blooms=rare_blooms)


# ============================================================
# 好友互动：偷花 / 帮忙 / 送花
# ============================================================
@router.get("/visit/{uid}")
async def visit_garden(uid: int, request: Request, db: AsyncSession = Depends(get_db)):
    """访问好友花园"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if await fsvc.is_blocked(db, uid, user.id):
        return await render(request, "result.html", db, user=user, ok=False, msg="对方已拉黑你",
                            back_href="/friends", back_text="返回好友")
    host = await db.get(models.User, uid)
    if not host:
        raise HTTPException(404)
    pots = (await db.execute(select(models.GardenPot).where(
        models.GardenPot.user_id == uid).order_by(models.GardenPot.slot))).scalars().all()
    pot_info = []
    for p in pots:
        seed = await db.get(models.GardenSeed, p.seed_key) if p.seed_key else None
        ainfo = pot_action_status(p, seed) if seed else {"stage": -1, "stage_label": "空地", "remain": 0, "action": None, "action_done": True}
        mature = seed and ainfo["stage"] == seed.stages
        locked = await locks.is_item_locked(db, uid, MODULE_KEY, f"pot_{p.slot}")
        already_stolen = await _already_stolen(db, user.id, p.id)
        # 帮忙：是否有未完成的操作
        can_help = seed and ainfo.get("action") and not ainfo["action_done"] and not mature
        pot_info.append({"pot": p, "seed": seed, "mature": mature, "locked": locked,
                         "already_stolen": already_stolen, "can_help": can_help, "ainfo": ainfo})
    # 我拥有的花（用于送花）
    my_flowers = []
    invs = await goods.list_inventory(db, user.id, MODULE_KEY)
    for inv, item in invs:
        if item.type == "flower" and inv.quantity > 0:
            my_flowers.append((item, inv.quantity))
    return await render(request, "garden/visit.html", db, user=user, host=host,
                        pot_info=pot_info, my_flowers=my_flowers, action_names=ACTION_NAMES)


async def _already_stolen(db: AsyncSession, thief_id: int, pot_id: int) -> bool:
    res = await db.execute(select(models.OperationLog).where(
        models.OperationLog.user_id == thief_id, models.OperationLog.module_key == MODULE_KEY,
        models.OperationLog.action == "steal_flower", models.OperationLog.detail == str(pot_id)))
    return res.scalar_one_or_none() is not None


@router.post("/steal/{pot_id}")
async def steal_flower(pot_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """偷花：从好友成熟花圃偷取一部分（有保底，主人不会血亏）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    p = await db.get(models.GardenPot, pot_id)
    if not p or p.user_id == user.id:
        return await render(request, "result.html", db, user=user, ok=False, msg="不能偷自己的",
                            back_href="/games/garden", back_text="返回")
    if await locks.is_item_locked(db, p.user_id, MODULE_KEY, f"pot_{p.slot}"):
        return await render(request, "result.html", db, user=user, ok=False, msg="🔒 花盆已上锁",
                            back_href=f"/games/garden/visit/{p.user_id}", back_text="返回")
    if await _already_stolen(db, user.id, p.id):
        return await render(request, "result.html", db, user=user, ok=False, msg="已偷过这盆",
                            back_href=f"/games/garden/visit/{p.user_id}", back_text="返回")
    seed = await db.get(models.GardenSeed, p.seed_key) if p.seed_key else None
    if not seed or current_stage(p, seed) < seed.stages:
        return await render(request, "result.html", db, user=user, ok=False, msg="还没成熟",
                            back_href=f"/games/garden/visit/{p.user_id}", back_text="返回")
    # 偷花：偷 1 朵（保底机制：主人花盆不清空，仅标记被偷）
    blooms_map = json.loads(seed.possible_blooms)
    bloom_keys = list(blooms_map.keys())
    weights = list(blooms_map.values())
    bk = random.choices(bloom_keys, weights=weights, k=1)[0]
    bloom = await db.get(models.GardenBloom, bk)
    if bloom:
        await goods.add_item(db, user.id, bloom.item_key, MODULE_KEY, 1)
    # 标记被偷：清空花盆（主人失去这盆，但被偷只损失1朵，符合"限制偷取比例"）
    p.seed_key = ""
    p.planted_at = None
    p.watered = False
    p.weeded = False
    p.debugged = False
    # 事件上报：被偷提醒
    await events.emit(db, user.id, MODULE_KEY, "interact_notify",
                      {"to_id": p.user_id, "title": "被偷花",
                       "content": f"{user.nickname} 偷了你的 {seed.name}（{bloom.name if bloom else ''}）"})
    st_thief = await get_state(db, user.id)
    await add_exp(db, st_thief, 2)
    await log.record(db, user.id, MODULE_KEY, "steal_flower", str(pot_id))
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"偷到{bloom.name if bloom else seed.name}×1",
                        back_href=f"/games/garden/visit/{p.user_id}", back_text="继续逛")


@router.post("/help/{pot_id}/{action}")
async def help_friend(pot_id: int, action: str, request: Request, db: AsyncSession = Depends(get_db)):
    """帮好友操作（浇水/除草/除虫），拿少量奖励"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if action not in ACTION_NAMES:
        return await render(request, "result.html", db, user=user, ok=False, msg="未知操作",
                            back_href="/friends", back_text="返回好友")
    p = await db.get(models.GardenPot, pot_id)
    if not p or p.user_id == user.id:
        return await render(request, "result.html", db, user=user, ok=False, msg="不能帮自己",
                            back_href="/friends", back_text="返回好友")
    seed = await db.get(models.GardenSeed, p.seed_key) if p.seed_key else None
    if not seed:
        return await render(request, "result.html", db, user=user, ok=False, msg="花盆为空",
                            back_href=f"/games/garden/visit/{p.user_id}", back_text="返回")
    ainfo = pot_action_status(p, seed)
    needed = needed_action(seed, ainfo["stage"])
    if needed != action or ainfo["action_done"]:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="当前阶段不需要此操作或已完成",
                            back_href=f"/games/garden/visit/{p.user_id}", back_text="返回")
    # 执行帮忙
    if action == "water":
        p.watered = True
    elif action == "weed":
        p.weeded = True
    elif action == "debug":
        p.debugged = True
    st = await get_state(db, user.id)
    await add_exp(db, st, 2)  # 帮忙少量经验
    st.coins += 5
    # 事件上报：帮好友 + 通知主人
    await events.emit(db, user.id, MODULE_KEY, "interact_notify",
                      {"to_id": p.user_id, "title": "好友帮忙",
                       "content": f"{user.nickname} 帮你{ACTION_NAMES[action]}了{seed.name}"})
    await log.record(db, user.id, MODULE_KEY, "help_friend", f"{pot_id}:{action}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"帮好友{ACTION_NAMES[action]}完成！经验+2 金币+5",
                        back_href=f"/games/garden/visit/{p.user_id}", back_text="继续逛")


@router.post("/gift/{uid}/{item_key}")
async def gift_flower(uid: int, item_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """送花"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if not await goods.remove_item(db, user.id, item_key, MODULE_KEY, 1):
        return await render(request, "result.html", db, user=user, ok=False, msg="你没有这朵花",
                            back_href=f"/games/garden/visit/{uid}", back_text="返回")
    await goods.add_item(db, uid, item_key, MODULE_KEY, 1)
    item = await goods.get_item_by_key(db, item_key)
    await events.emit(db, user.id, MODULE_KEY, "interact_notify",
                      {"to_id": uid, "title": "收到鲜花",
                       "content": f"{user.nickname} 送给你 {item.name} ×1"})
    await log.record(db, user.id, MODULE_KEY, "gift", f"{uid}:{item_key}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"送出{item.name}×1",
                        back_href=f"/games/garden/visit/{uid}", back_text="返回")


# ============================================================
# 商店 / 规则
# ============================================================
@router.get("/shop")
async def garden_shop(request: Request, db: AsyncSession = Depends(get_db)):
    """花种商店：只上架 obtain_sources 含 shop 的基础花种（稀有花不直接卖）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    seeds = (await db.execute(select(models.GardenSeed))).scalars().all()
    shop_list = []
    for s in seeds:
        if "shop" in s.obtain_sources:
            n = await goods.count_item(db, user.id, s.seed_item_key, MODULE_KEY)
            shop_list.append({"seed": s, "have": n, "locked_level": st.level < s.min_level})
    return await render(request, "garden/shop.html", db, user=user, st=st, shop_list=shop_list)


@router.post("/shop/buy/{seed_key}")
async def shop_buy(seed_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """用模块金币购买基础花种"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    seed = await db.get(models.GardenSeed, seed_key)
    if not seed or "shop" not in seed.obtain_sources:
        return await render(request, "result.html", db, user=user, ok=False, msg="该花种不可购买",
                            back_href="/games/garden/shop", back_text="返回商店")
    if st.level < seed.min_level:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"需要花园等级 {seed.min_level}",
                            back_href="/games/garden/shop", back_text="返回商店")
    price = 30 if seed.rarity == "普通" else 60
    if st.coins < price:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"模块金币不足（需{price}）",
                            back_href="/games/garden/shop", back_text="返回商店")
    st.coins -= price
    await goods.add_item(db, user.id, seed.seed_item_key, MODULE_KEY, 1)
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "shop_buy", seed_key)
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"购买{seed.name}种子×1（花费{price}花园金币）",
                        back_href="/games/garden/shop", back_text="返回商店")


@router.get("/rules")
async def rules(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return await render(request, "garden/rules.html", db, user=user)
