"""魔法花园模块（v0.0.3 怀旧版完整设计规范）

设计规范落地：
- 花种(Seed)/花朵(Bloom)/花谱项(AlbumEntry) 三概念分离
- 物品等级 Lv1-8 + 稀有度 普通/稀有/史诗/传说 双轴
- 玩家等级段 vs 物品等级上限映射（防越级使用）
- 种植阶段状态机：空地→已播种→发芽期→花苗期→花蕾期→成熟→收获→空地
- 三件套阶段操作：浇水/除草/除虫（影响产量/经验/稀有概率）
- 花谱按系列分组，点亮有奖励（经验/金币 + 平台图标/成就/消息）
- 合成工坊：成功率 + 保底(合成值满必成) + 高阶操作锁校验
- 兑换中心：活动材料 → 稀有花种（稳定路径）
- 好友互动：偷花/帮忙/送花，日限 + 衰减 + 消息提醒
- 等级系统：经验来自劳动行为（播种/操作/收获/点亮/帮忙/合成）
- 经验公式：need(L→L+1) = 120 + 80*L（方案A）
- 魔法师称号体系：16 段位（每 5 级一段），段位起始等级解锁新花盆
- 事件上报：garden_* 系列由平台统一处理消息/图标/成就/排行
- 风控：高价值操作强制操作锁校验；行为限速（偷花/帮忙日限）
"""
import json
import random
from datetime import datetime, date, timedelta

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from ..platform import goods, events, locks, friends as fsvc, log
from .views import render

router = APIRouter(prefix="/games/garden")
MODULE_KEY = "garden"

# 阶段名称（索引 1..stages）
STAGE_NAMES = {0: "已播种", 1: "发芽期", 2: "花苗期", 3: "花蕾期", 4: "成熟"}
ACTION_NAMES = {"water": "浇水", "weed": "除草", "debug": "除虫"}

# 魔法师称号体系（16 段位，每 5 级一段）— 段位起始等级为强解锁点
MAGICIAN_TITLES = [
    (1, 5, "见习魔法师"), (6, 10, "学徒魔法师"), (11, 15, "初阶魔法师"),
    (16, 20, "中阶魔法师"), (21, 25, "高阶魔法师"), (26, 30, "精英魔法师"),
    (31, 35, "大魔法师"), (36, 40, "魔导师"), (41, 45, "大魔导师"),
    (46, 50, "贤者"), (51, 55, "奥术贤者"), (56, 60, "秘法宗师"),
    (61, 65, "元素宗师"), (66, 70, "大元素使"), (71, 75, "星辉大法师"),
    (76, 80, "传奇魔法王座"),
]

# 社交日限（防刷）
DAILY_STEAL_LIMIT = 10
DAILY_HELP_LIMIT = 10


def magician_title(level: int) -> tuple[str, tuple[int, int]]:
    """返回 (称号, (段位起始, 段位结束))"""
    for lo, hi, name in MAGICIAN_TITLES:
        if lo <= level <= hi:
            return name, (lo, hi)
    return "见习魔法师", (1, 5)


def tier_index(level: int) -> int:
    """段位索引 0-15（用于花盆数解锁）"""
    return min(15, (level - 1) // 5)


def pot_count_for_level(level: int) -> int:
    """花盆数随段位解锁：基础4 + 段位索引，上限12"""
    return min(12, 4 + tier_index(level))


def item_level_cap(player_level: int) -> int:
    """玩家等级段 → 可使用物品等级上限
    Lv1-10→≤2, Lv11-20→≤3, Lv21-30→≤4, Lv31-40→≤5,
    Lv41-50→≤6, Lv51-65→≤7, Lv66-80→≤8
    """
    if player_level <= 10:
        return 2
    if player_level <= 20:
        return 3
    if player_level <= 30:
        return 4
    if player_level <= 40:
        return 5
    if player_level <= 50:
        return 6
    if player_level <= 65:
        return 7
    return 8


# 升级曲线（方案A）：need(L→L+1) = 120 + 80*L
def exp_needed(level: int) -> int:
    return 120 + 80 * level


# ============================================================
# v0.1.3：spec 公式规则分册落地（统一加成 / 品质 / 价值 / 订单）
# ============================================================
# spec 强制：final = base * (1 + Σadd) * Π(1 + mul_i)，关键项必须有 cap 上限
def apply_buff(base: float, add_terms: list[float], mul_terms: list[float], cap: float | None = None) -> float:
    """统一加成叠加：先加后乘 + cap 上限（spec：必须写死）"""
    result = base * (1.0 + sum(add_terms))
    for m in mul_terms:
        result *= (1.0 + m)
    if cap is not None:
        result = min(result, cap)
    return result

# 品质系统（spec：5 档 N/G/R/E/L，权重抽取避免概率叠爆）
QUALITY_TIERS = ["N", "G", "R", "E", "L"]  # 普通/优良/稀有/史诗/传说
# 品质对订单价值的倍率（spec 示例）
Q_VALUE_MUL = {"N": 1.0, "G": 1.1, "R": 1.25, "E": 1.45, "L": 1.7}
# 基础品质权重模板（普通作物；稀有作物可在 seed 配置覆盖）
QUALITY_WEIGHT_BASE = {"N": 70, "G": 20, "R": 7, "E": 2.5, "L": 0.5}

def roll_quality(quality_buff: float = 0.0, env_score: int = 0) -> str:
    """品质权重抽取（spec：W_q = W_base * (1 + buff) * env_quality_mul）

    env_quality_mul 边际递减：1 + k*(1 - exp(-env_score/s))
    """
    import math
    k, s = 0.3, 50.0
    env_mul = 1 + k * (1 - math.exp(-env_score / s))
    weights = {q: QUALITY_WEIGHT_BASE[q] * (1 + quality_buff) * env_mul for q in QUALITY_TIERS}
    return random.choices(QUALITY_TIERS, weights=[weights[q] for q in QUALITY_TIERS], k=1)[0]

# 物品价值体系（spec：四段式 item_value 定价底座）
# 时间价值：V_time_unit(L) = k0 + k1*L
V_TIME_K0, V_TIME_K1 = 8, 0.5
def v_time_unit(level: int) -> float:
    return V_TIME_K0 + V_TIME_K1 * level

# 稀有度倍率（spec 示例 M_rarity N/G/R/E/L = 1.0/1.3/1.8/2.6/4.0）
RARITY_MUL = {"普通": 1.0, "稀有": 1.8, "史诗": 2.6, "传说": 4.0}

def crop_base_value(grow_seconds: int, level: int) -> float:
    """作物基础价值（时间价值）：V_crop_base = T_grow_hours * V_time_unit(L) / plot_efficiency_norm"""
    grow_hours = grow_seconds / 3600.0
    return grow_hours * v_time_unit(level) / 1.0  # plot_efficiency_norm=1

def item_value_coin(item_level: int, rarity: str, grow_seconds: int = 0, base_sell: int = 0) -> int:
    """物品内部价值（spec：时间价值 + 稀有溢价；无成长时间的按卖价反推）

    用于订单/配方定价，不等于玩家可见卖价。
    """
    if grow_seconds > 0:
        v = crop_base_value(grow_seconds, item_level) * RARITY_MUL.get(rarity, 1.0)
    else:
        # 材料/产物：按卖价 * 反推系数（卖价≈价值的 0.2-0.3）
        v = max(base_sell, 1) * 4.0
    return max(1, int(v))

# 订单系统配置（spec：经济主引擎）
# margin(order_type) 利润率
ORDER_MARGIN = {"normal": 1.15, "premium": 1.45, "limited": 1.75}
# urgency_mul 限时单加成
ORDER_URGENCY_MUL = {"normal": 1.0, "premium": 1.0, "limited": 1.2}
# difficulty_mul 按需求品质
ORDER_DIFFICULTY_MUL = {"N": 1.0, "G": 1.1, "R": 1.25, "E": 1.45, "L": 1.7}
# 每日订单数 N0 + rand(0, n)
ORDER_DAILY_BASE, ORDER_DAILY_RAND = 4, 2
# 同时进行订单数上限
ORDER_ACTIVE_MAX = 6
# 免费刷新次数 + 付费刷新成本递增 cost_reroll(n)= base * r^n
ORDER_FREE_REROLL = 2
ORDER_REROLL_BASE, ORDER_REROLL_RATIO = 50, 1.5
# 经验公式 R_exp = floor(R_coin^p * exp_scale(L))，p<1 避免金币单一驱动升级
ORDER_EXP_P = 0.6
def order_exp_scale(level: int) -> float:
    return 1.0 + level * 0.05

# 订单需求池：从玩家已点亮花谱的花朵中抽取（保证可交付）
# 订单需求条目结构：{item_key, qty, quality, value_coin}
ORDER_QTY_RANGE = (1, 3)


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
    # 自动按当前等级补齐花盆数（段位解锁）
    target = pot_count_for_level(st.level)
    if target > st.pot_count:
        for i in range(st.pot_count, target):
            exists = (await db.execute(select(models.GardenPot).where(
                models.GardenPot.user_id == user_id, models.GardenPot.slot == i))).scalar_one_or_none()
            if not exists:
                db.add(models.GardenPot(user_id=user_id, slot=i))
        st.pot_count = target
        await db.commit()
        await db.refresh(st)
    return st


async def add_exp(db: AsyncSession, st: models.GardenState, amount: int):
    """加经验并处理升级（含段位解锁花盆）"""
    old_level = st.level
    st.exp += amount
    while st.exp >= exp_needed(st.level):
        st.exp -= exp_needed(st.level)
        st.level += 1
    # 升级后自动补齐花盆数
    if st.level > old_level:
        target = pot_count_for_level(st.level)
        if target > st.pot_count:
            for i in range(st.pot_count, target):
                exists = (await db.execute(select(models.GardenPot).where(
                    models.GardenPot.user_id == st.user_id, models.GardenPot.slot == i))).scalar_one_or_none()
                if not exists:
                    db.add(models.GardenPot(user_id=st.user_id, slot=i))
            st.pot_count = target


async def get_daily_log(db: AsyncSession, user_id: int) -> models.GardenDailyLog:
    """获取/创建今日互动计数（防刷限速）"""
    today = date.today().isoformat()
    res = await db.execute(select(models.GardenDailyLog).where(
        models.GardenDailyLog.user_id == user_id, models.GardenDailyLog.date == today))
    dl = res.scalar_one_or_none()
    if not dl:
        dl = models.GardenDailyLog(user_id=user_id, date=today)
        db.add(dl)
        await db.flush()
    return dl


def steal_reward(times_today: int) -> tuple[int, int]:
    """偷花收益衰减：前3次满额，4-6次半额，7-10次仅花无奖励"""
    if times_today < 3:
        return 2, 5  # 经验, 金币
    if times_today < 6:
        return 1, 2
    return 0, 0


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
    title, tier_range = magician_title(st.level)
    return await render(request, "garden/home.html", db, user=user, st=st,
                        pot_info=pot_info, todo_harvest=todo_harvest, todo_action=todo_action,
                        entries=entries, lit_count=lit_count,
                        exp_need=exp_needed(st.level), action_names=ACTION_NAMES,
                        title=title, tier_range=tier_range,
                        item_cap=item_level_cap(st.level))


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
                        exp_need=exp_needed(st.level), action_names=ACTION_NAMES,
                        title=magician_title(st.level)[0])


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
    # 物品等级上限校验（防越级使用）
    if seed.item_level > item_level_cap(st.level):
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"花种等级Lv{seed.item_level}超过你当前可使用上限Lv{item_level_cap(st.level)}",
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
    # v0.1.2：阶段操作不再推进"花谱大师"成就（该成就只在 album_light 点亮花谱时触发）
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
        # 收花经验随花朵物品等级提升（Lv1→5, Lv2→7, Lv3→9...）
        exp_gain += 3 + bloom.item_level * 2
        # 花谱点亮（首次获得该花朵）
        entry = await db.get(models.GardenAlbumEntry, bloom.album_entry_key)
        if entry:
            existing = (await db.execute(select(models.GardenCollection).where(
                models.GardenCollection.user_id == user.id,
                models.GardenCollection.entry_key == entry.key))).scalar_one_or_none()
            if not existing:
                db.add(models.GardenCollection(user_id=user.id, entry_key=entry.key, lit=True))
                lit_entries.append(entry)
                # 点亮花谱一次性大奖励（随物品等级）
                exp_gain += 15 + bloom.item_level * 5
                coins_gain += 20 + bloom.item_level * 5
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
    # v0.1.2：收获不再推进"花谱大师"成就（该成就只在 album_light 点亮花谱时触发）
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
    """合成工坊：配方列表 + 成功率 + 保底进度"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    cap = item_level_cap(st.level)
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
        # 保底进度
        credit = (await db.execute(select(models.GardenCraftCredit).where(
            models.GardenCraftCredit.user_id == user.id,
            models.GardenCraftCredit.recipe_id == r.id))).scalar_one_or_none()
        credits = credit.credits if credit else 0
        # 等级/物品等级上限校验
        level_locked = seed and seed.item_level > cap
        info.append({"recipe": r, "seed": seed, "mats": mat_info, "can": can and not level_locked,
                     "credits": credits, "level_locked": level_locked})
    return await render(request, "garden/craft.html", db, user=user, st=st, info=info, item_cap=cap,
                        title=magician_title(st.level)[0])


@router.post("/craft/{recipe_id}")
async def craft(recipe_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """合成花种：成功率 + 保底(合成值满必成) + 高阶操作锁校验"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    r = await db.get(models.GardenRecipe, recipe_id)
    if not r:
        return await render(request, "result.html", db, user=user, ok=False, msg="配方不存在",
                            back_href="/games/garden/craft", back_text="返回合成")
    seed = await db.get(models.GardenSeed, r.result_seed_key)
    if not seed:
        return await render(request, "result.html", db, user=user, ok=False, msg="目标花种不存在",
                            back_href="/games/garden/craft", back_text="返回合成")
    # 物品等级上限校验（防越级合成）
    if seed.item_level > item_level_cap(st.level):
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"目标花种Lv{seed.item_level}超过你当前可使用上限Lv{item_level_cap(st.level)}",
                            back_href="/games/garden/craft", back_text="返回合成")
    # 高阶合成强制操作锁校验（风控）
    if r.require_lock_check:
        # 操作锁：高价值操作需二次确认（这里简化为检查花盆锁状态作为"操作锁"代理）
        # 真正的操作锁可在 settings 页统一管理，此处记录风控日志
        await log.record(db, user.id, MODULE_KEY, "craft_lock_check", f"recipe{recipe_id}:high_value")
    mats = json.loads(r.materials)
    for k, n in mats.items():
        if await goods.count_item(db, user.id, k, MODULE_KEY) < n:
            item = await goods.get_item_by_key(db, k)
            return await render(request, "result.html", db, user=user, ok=False,
                                msg=f"材料不足：{item.name if item else k}",
                                back_href="/games/garden/craft", back_text="返回合成")
    # 扣除材料
    for k, n in mats.items():
        await goods.remove_item(db, user.id, k, MODULE_KEY, n)
    # 保底进度
    credit = (await db.execute(select(models.GardenCraftCredit).where(
        models.GardenCraftCredit.user_id == user.id,
        models.GardenCraftCredit.recipe_id == r.id))).scalar_one_or_none()
    if not credit:
        credit = models.GardenCraftCredit(user_id=user.id, recipe_id=r.id, credits=0)
        db.add(credit)
        await db.flush()
    # 保底触发：累计失败值已达阈值 → 必成
    guaranteed = credit.credits + 1 >= r.fail_credit_threshold
    success = guaranteed or (random.randint(1, 100) <= r.success_rate)
    if success:
        await goods.add_item(db, user.id, seed.seed_item_key, MODULE_KEY, r.result_qty)
        credit.credits = 0  # 成功重置保底
        # 合成经验（与目标等级相关）
        craft_exp = 5 + r.target_level * 3
        await add_exp(db, st, craft_exp)
        # v0.1.2：合成不再推进"花谱大师"成就（该成就只在 album_light 点亮花谱时触发）
        await log.record(db, user.id, MODULE_KEY, "craft_success",
                         f"{recipe_id}:{r.result_seed_key}:exp{craft_exp}")
        await db.commit()
        msg = f"合成成功！获得{seed.name}种子×{r.result_qty}"
        if guaranteed:
            msg += "（保底触发）"
        msg += f" | 经验+{craft_exp}"
        return await render(request, "result.html", db, user=user, ok=True, msg=msg,
                            back_href="/games/garden/craft", back_text="返回合成")
    else:
        credit.credits += 1  # 失败累计保底
        await log.record(db, user.id, MODULE_KEY, "craft_fail",
                         f"{recipe_id}:credits{credit.credits}/{r.fail_credit_threshold}")
        await db.commit()
        remain = r.fail_credit_threshold - credit.credits
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"合成失败…材料已消耗。保底进度 {credit.credits}/{r.fail_credit_threshold}（再失败{remain}次必成）",
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
    """偷花：日限 + 衰减 + 保底(主人不血亏) + 消息提醒"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    # 日限校验
    dl = await get_daily_log(db, user.id)
    if dl.steal_count >= DAILY_STEAL_LIMIT:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"今日偷花已达上限({DAILY_STEAL_LIMIT}次)",
                            back_href="/friends", back_text="返回好友")
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
    # 收益衰减：前3次满额，4-6次半额，7-10次仅花无奖励
    exp_g, coin_g = steal_reward(dl.steal_count)
    dl.steal_count += 1
    # 事件上报：被偷提醒
    await events.emit(db, user.id, MODULE_KEY, "interact_notify",
                      {"to_id": p.user_id, "title": "被偷花",
                       "content": f"{user.nickname} 偷了你的 {seed.name}（{bloom.name if bloom else ''}）"})
    st_thief = await get_state(db, user.id)
    await add_exp(db, st_thief, exp_g)
    st_thief.coins += coin_g
    await log.record(db, user.id, MODULE_KEY, "steal_flower",
                     f"{pot_id}:exp{exp_g}:coin{coin_g}:daily{dl.steal_count}")
    await db.commit()
    extra = f" | 经验+{exp_g} 金币+{coin_g}" if (exp_g or coin_g) else "（今日偷花奖励已衰减为0）"
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"偷到{bloom.name if bloom else seed.name}×1{extra}（今日{dl.steal_count}/{DAILY_STEAL_LIMIT}）",
                        back_href=f"/games/garden/visit/{p.user_id}", back_text="继续逛")


@router.post("/help/{pot_id}/{action}")
async def help_friend(pot_id: int, action: str, request: Request, db: AsyncSession = Depends(get_db)):
    """帮好友操作（浇水/除草/除虫），日限 + 双方奖励"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if action not in ACTION_NAMES:
        return await render(request, "result.html", db, user=user, ok=False, msg="未知操作",
                            back_href="/friends", back_text="返回好友")
    # 日限校验
    dl = await get_daily_log(db, user.id)
    if dl.help_count >= DAILY_HELP_LIMIT:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"今日帮忙已达上限({DAILY_HELP_LIMIT}次)",
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
    dl.help_count += 1
    st = await get_state(db, user.id)
    await add_exp(db, st, 2)  # 帮忙少量经验
    st.coins += 5
    # 事件上报：帮好友 + 通知主人
    await events.emit(db, user.id, MODULE_KEY, "interact_notify",
                      {"to_id": p.user_id, "title": "好友帮忙",
                       "content": f"{user.nickname} 帮你{ACTION_NAMES[action]}了{seed.name}"})
    await log.record(db, user.id, MODULE_KEY, "help_friend",
                     f"{pot_id}:{action}:daily{dl.help_count}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"帮好友{ACTION_NAMES[action]}完成！经验+2 金币+5（今日{dl.help_count}/{DAILY_HELP_LIMIT}）",
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
    cap = item_level_cap(st.level)
    seeds = (await db.execute(select(models.GardenSeed))).scalars().all()
    shop_list = []
    for s in seeds:
        if "shop" in s.obtain_sources:
            n = await goods.count_item(db, user.id, s.seed_item_key, MODULE_KEY)
            shop_list.append({"seed": s, "have": n,
                              "locked_level": st.level < s.min_level or s.item_level > cap})
    return await render(request, "garden/shop.html", db, user=user, st=st, shop_list=shop_list,
                        item_cap=cap, title=magician_title(st.level)[0])


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
    if seed.item_level > item_level_cap(st.level):
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"花种Lv{seed.item_level}超过你当前可使用上限Lv{item_level_cap(st.level)}",
                            back_href="/games/garden/shop", back_text="返回商店")
    # 价格随物品等级递增（普通 Lv1→20, Lv2→40；稀有翻倍）
    base = seed.item_level * 20
    price = base if seed.rarity == "普通" else base * 2
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


# ============================================================
# v0.1.3：订单交易系统（spec 经济主引擎 / 主要回收池）
# 产出 → 订单交付 → 金币/经验回收，闭环 harvest 的消费路径
# ============================================================
def _gen_order_requirements(db_blooms: list, st_level: int, order_type: str) -> list[dict]:
    """生成订单需求：从可用花朵池抽取 1-3 种，每种 1-3 个，附带品质要求"""
    if not db_blooms:
        return []
    n_items = random.randint(1, min(3, len(db_blooms)))
    chosen = random.sample(db_blooms, min(n_items, len(db_blooms)))
    reqs = []
    for bloom in chosen:
        qty = random.randint(ORDER_QTY_RANGE[0], ORDER_QTY_RANGE[1])
        # 限时单/加价单更可能要求高品质
        if order_type == "limited":
            q_pool = ["N", "G", "R", "E"]
        elif order_type == "premium":
            q_pool = ["N", "G", "R"]
        else:
            q_pool = ["N", "G"]
        quality = random.choice(q_pool)
        v = item_value_coin(bloom.item_level, bloom.rarity, base_sell=bloom.sell_price)
        reqs.append({"item_key": bloom.item_key, "name": bloom.name,
                     "qty": qty, "quality": quality, "value_coin": v})
    return reqs


def _calc_order_reward(reqs: list[dict], order_type: str, st_level: int, has_deadline: bool) -> tuple[int, int]:
    """计算订单奖励 (R_coin, R_exp) —— spec 公式"""
    if not reqs:
        return 0, 0
    v_req = sum(r["qty"] * r["value_coin"] * Q_VALUE_MUL[r["quality"]] for r in reqs)
    urgency = ORDER_URGENCY_MUL.get(order_type, 1.0) * (1.1 if has_deadline else 1.0)
    difficulty = max(ORDER_DIFFICULTY_MUL[r["quality"]] for r in reqs)
    r_coin = int(v_req * ORDER_MARGIN.get(order_type, 1.15) * urgency * difficulty)
    r_exp = int((r_coin ** ORDER_EXP_P) * order_exp_scale(st_level))
    return max(1, r_coin), max(1, r_exp)


async def _ensure_orders(db: AsyncSession, user_id: int, st: models.GardenState):
    """保证玩家有足够订单（首次进入/每日补充）"""
    res = await db.execute(select(models.GardenOrder).where(
        models.GardenOrder.user_id == user_id, models.GardenOrder.delivered.is_(False)))
    active = list(res.scalars().all())
    # 清理过期限时单
    now = datetime.utcnow()
    cleaned = False
    for o in active:
        if o.expire_at and o.expire_at < now:
            o.delivered = True  # 标记过期（不发放奖励）
            cleaned = True
    if cleaned:
        active = [o for o in active if not o.delivered]
    if len(active) >= ORDER_ACTIVE_MAX:
        return active
    # 需要补充：从玩家已点亮花谱的花朵中抽取需求池
    col_res = await db.execute(select(models.GardenCollection).where(
        models.GardenCollection.user_id == user_id))
    lit_keys = [c.entry_key for c in col_res.scalars().all()]
    bloom_keys = []
    for ek in lit_keys:
        entry = await db.get(models.GardenAlbumEntry, ek)
        if entry:
            bloom_keys.append(entry.bloom_key)
    db_blooms = []
    for bk in bloom_keys:
        b = await db.get(models.GardenBloom, bk)
        if b:
            db_blooms.append(b)
    # 若玩家花谱空（新手），用 Lv1 野花保底
    if not db_blooms:
        b = await db.get(models.GardenBloom, "bloom_wild_w")
        if b:
            db_blooms = [b]
    target = ORDER_DAILY_BASE + random.randint(0, ORDER_DAILY_RAND)
    to_add = max(0, min(target, ORDER_ACTIVE_MAX) - len(active))
    for _ in range(to_add):
        r = random.random()
        if r < 0.15:
            otype = "limited"
        elif r < 0.45:
            otype = "premium"
        else:
            otype = "normal"
        reqs = _gen_order_requirements(db_blooms, st.level, otype)
        if not reqs:
            continue
        has_dl = otype == "limited"
        r_coin, r_exp = _calc_order_reward(reqs, otype, st.level, has_dl)
        expire = (now + timedelta(hours=8)) if has_dl else None
        db.add(models.GardenOrder(user_id=user_id, order_type=otype,
                                  requirements=json.dumps(reqs, ensure_ascii=False),
                                  reward_coin=r_coin, reward_exp=r_exp,
                                  reward_token=5 if otype == "limited" else 0,
                                  expire_at=expire))
    await db.flush()
    res = await db.execute(select(models.GardenOrder).where(
        models.GardenOrder.user_id == user_id, models.GardenOrder.delivered.is_(False),
        (models.GardenOrder.expire_at.is_(None)) | (models.GardenOrder.expire_at > now)))
    return list(res.scalars().all())


@router.get("/orders")
async def orders_page(request: Request, db: AsyncSession = Depends(get_db)):
    """订单板：普通单/加价单/限时单"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    active = await _ensure_orders(db, user.id, st)
    await db.commit()  # v0.1.3：持久化新生成的订单（_ensure_orders 只 flush）
    # 计算每个订单的可交付状态
    order_infos = []
    for o in active:
        reqs = json.loads(o.requirements)
        can_deliver = True
        for r in reqs:
            cnt = await goods.count_item(db, user.id, r["item_key"], MODULE_KEY)
            if cnt < r["qty"]:
                can_deliver = False
                break
        remain = ""
        if o.expire_at:
            secs = int((o.expire_at - datetime.utcnow()).total_seconds())
            remain = f"{secs//3600}h{(secs%3600)//60}m" if secs > 0 else "已过期"
        order_infos.append({"order": o, "reqs": reqs, "can_deliver": can_deliver, "remain": remain})
    dl = await get_daily_log(db, user.id)
    free_left = max(0, ORDER_FREE_REROLL - dl.order_reroll_paid)
    title, tier_range = magician_title(st.level)
    return await render(request, "garden/orders.html", db, user=user, st=st,
                        order_infos=order_infos, free_left=free_left,
                        title=title, tier_range=tier_range)


@router.post("/orders/deliver/{order_id}")
async def order_deliver(order_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """交付订单：扣除材料 → 发放金币/经验/代币 → 记录历史"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    o = await db.get(models.GardenOrder, order_id)
    if not o or o.user_id != user.id or o.delivered:
        return await render(request, "result.html", db, user=user, ok=False, msg="订单无效",
                            back_href="/games/garden/orders", back_text="返回订单板")
    if o.expire_at and o.expire_at < datetime.utcnow():
        o.delivered = True
        await db.commit()
        return await render(request, "result.html", db, user=user, ok=False, msg="订单已过期",
                            back_href="/games/garden/orders", back_text="返回订单板")
    reqs = json.loads(o.requirements)
    # 校验材料
    for r in reqs:
        cnt = await goods.count_item(db, user.id, r["item_key"], MODULE_KEY)
        if cnt < r["qty"]:
            return await render(request, "result.html", db, user=user, ok=False,
                                msg=f"材料不足：{r['name']} 需要 {r['qty']} 个",
                                back_href="/games/garden/orders", back_text="返回订单板")
    # 扣除材料
    for r in reqs:
        await goods.remove_item(db, user.id, r["item_key"], MODULE_KEY, r["qty"])
    # 发放奖励
    st.coins += o.reward_coin
    await add_exp(db, st, o.reward_exp)
    o.delivered = True
    db.add(models.GardenOrderLog(user_id=user.id, order_type=o.order_type,
                                 coin_gain=o.reward_coin, exp_gain=o.reward_exp,
                                 token_gain=o.reward_token))
    await db.commit()
    await events.emit(db, user.id, MODULE_KEY, "ranking",
                      {"metric": "order_coin", "score": o.reward_coin, "period": "total"})
    await log.record(db, user.id, MODULE_KEY, "order_deliver", f"{o.id}:{o.order_type}:{o.reward_coin}")
    msg = f"订单交付成功！金币+{o.reward_coin} 经验+{o.reward_exp}"
    if o.reward_token:
        msg += f" 活动代币+{o.reward_token}"
    return await render(request, "result.html", db, user=user, ok=True, msg=msg,
                        back_href="/games/garden/orders", back_text="返回订单板")


@router.post("/orders/reroll")
async def orders_reroll(request: Request, db: AsyncSession = Depends(get_db)):
    """刷新订单板：免费次数用完后付费递增"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    dl = await get_daily_log(db, user.id)
    # 清空当前未交付订单
    res = await db.execute(select(models.GardenOrder).where(
        models.GardenOrder.user_id == user.id, models.GardenOrder.delivered.is_(False)))
    for o in res.scalars().all():
        o.delivered = True
    # 计算刷新成本
    if dl.order_reroll_paid < ORDER_FREE_REROLL:
        cost = 0
    else:
        cost = int(ORDER_REROLL_BASE * (ORDER_REROLL_RATIO ** (dl.order_reroll_paid - ORDER_FREE_REROLL)))
    if st.coins < cost:
        await db.rollback()
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"花园金币不足（刷新需{cost}）",
                            back_href="/games/garden/orders", back_text="返回订单板")
    st.coins -= cost
    dl.order_reroll_paid += 1
    await db.commit()
    await _ensure_orders(db, user.id, st)
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "order_reroll", f"cost{cost}")
    return RedirectResponse("/games/garden/orders", status_code=303)


@router.get("/orders/history")
async def orders_history(request: Request, db: AsyncSession = Depends(get_db)):
    """订单交付历史（统计 + 任务追踪）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    res = await db.execute(select(models.GardenOrderLog).where(
        models.GardenOrderLog.user_id == user.id).order_by(models.GardenOrderLog.delivered_at.desc()).limit(20))
    logs = list(res.scalars().all())
    total_coin = sum(l.coin_gain for l in logs)
    total_exp = sum(l.exp_gain for l in logs)
    st = await get_state(db, user.id)
    return await render(request, "garden/order_history.html", db, user=user, st=st,
                        logs=logs, total_coin=total_coin, total_exp=total_exp)

