"""幻想西游模块（v0.2.2）

老味道点：五门派 / 200级转职 / 装备强化 / 副本挑战 / 宠物捕捉 / 修炼挂机
核心循环：修炼/副本 → 获得经验银两 → 转职升级换装 → 学技能 → 挑战更高副本 → 继续养成

口径：怀旧 / 旧逻辑 / WAP 层级页 / 可复刻落地。
排行/商城/背包/消息 走平台公共系统（events.emit 上报 + 链接跳转）。
"""
import json
import random
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from ..platform import goods, events, log
from .views import render
from . import xyou_data as XY

router = APIRouter(prefix="/games/xyou", tags=["幻想西游"])
MODULE_KEY = "xyou"

# 修炼基础收益（每小时）
CULTIVATE_EXP_PER_HOUR = 500
CULTIVATE_SILVER_PER_HOUR = 200
CULTIVATE_MAX_HOURS = 4


# ============================================================
# 辅助函数
# ============================================================
async def get_state(db: AsyncSession, user_id: int) -> models.XyouState:
    st = await db.get(models.XyouState, user_id)
    if not st:
        st = models.XyouState(user_id=user_id)
        db.add(st)
        await db.commit()
        await db.refresh(st)
    return st


def calc_player_power(st: models.XyouState) -> int:
    """简易战力"""
    return int(st.hp * 0.2 + st.mp * 0.1 + st.atk * 2 + st.defense * 1.5
               + st.speed * 1.5 + st.lingli * 1.5 + st.level * 8)


def add_exp(st: models.XyouState, amount: int) -> bool:
    """加经验，按门派每级属性增量自动升级。
    spec：转职节点锁经验，需先完成转职任务才能继续升级。"""
    # 转职锁：等级处于转职节点时，不再吃经验
    if XY.is_promotion_locked(st.level):
        return False
    if st.level >= XY.MAX_LEVEL:
        st.exp = 0
        return False
    st.exp += amount
    leveled = False
    while st.level < XY.MAX_LEVEL:
        # 即将升到下一级前，检查下一级是否是转职节点
        next_level = st.level + 1
        need = XY.exp_needed(st.level)
        if need <= 0:
            break
        if st.exp >= need:
            st.exp -= need
            st.level = next_level
            per = XY.SECT_PER_LEVEL.get(st.sect_key, {})
            st.hp += per.get("hp", 0)
            st.mp += per.get("mp", 0)
            st.atk += per.get("atk", 0)
            st.defense += per.get("defense", 0)
            st.speed += per.get("speed", 0)
            st.lingli += per.get("lingli", 0)
            leveled = True
            # 升到转职节点后，锁经验，等待玩家做转职任务
            if XY.is_promotion_locked(st.level):
                st.exp = 0
                break
        else:
            break
    return leveled


async def _has_any_skill(db: AsyncSession, user_id: int) -> bool:
    res = await db.execute(select(models.XyouUserSkill).where(
        models.XyouUserSkill.user_id == user_id).limit(1))
    return res.scalar_one_or_none() is not None


async def _is_fresh(db: AsyncSession, st: models.XyouState) -> bool:
    """未转职：1级0经验且未学任何技能"""
    return st.level == 1 and st.exp == 0 and not st.sect_key and not await _has_any_skill(db, st.user_id)


async def _learned_skills(db: AsyncSession, user_id: int) -> dict:
    res = await db.execute(select(models.XyouUserSkill).where(
        models.XyouUserSkill.user_id == user_id))
    return {s.skill_key: s.level for s in res.scalars().all()}


async def _equip_def_map(db: AsyncSession) -> dict:
    """{equip_key: XyouEquip}"""
    res = await db.execute(select(models.XyouEquip))
    return {e.key: e for e in res.scalars().all()}


async def _notify_milestones(db: AsyncSession, user_id: int, st: models.XyouState):
    """等级里程碑上报平台：10级点亮图标"""
    if st.level >= 10:
        await events.emit(db, user_id, MODULE_KEY, "icon_light", {"icon_key": "icon_xyou"})


def _daily_counters(st: models.XyouState) -> dict:
    try:
        return json.loads(st.daily_counters or "{}")
    except Exception:
        return {}


def _save_daily_counters(st: models.XyouState, data: dict):
    st.daily_counters = json.dumps(data, ensure_ascii=False)


def _today_key() -> str:
    return datetime.utcnow().strftime("%Y%m%d")


# ============================================================
# 首页
# ============================================================
@router.get("")
async def home(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    need_create = await _is_fresh(db, st)
    power = calc_player_power(st)
    exp_need = XY.exp_needed(st.level)
    promotion_locked = XY.is_promotion_locked(st.level)
    # 修炼待领
    now = datetime.utcnow()
    cultivate_ready = bool(st.cultivate_end_at and now >= st.cultivate_end_at)
    # 当前场景名
    scene = await db.get(models.XyouScene, st.current_scene)
    scene_name = scene.name if scene else st.current_scene
    todo = []
    if need_create:
        todo.append(("请先选择门派", "点击前往", "/games/xyou/create"))
    if cultivate_ready:
        todo.append(("修炼收益待领取", "前往修炼", "/games/xyou/cultivate"))
    if promotion_locked and not need_create:
        promo = XY.PROMOTION_QUESTS.get(st.level)
        if promo:
            todo.append((promo["name"], "完成转职", "/games/xyou/promote"))
    await db.commit()
    return await render(request, "xyou/home.html", db, user=user, st=st,
                        power=power, exp_need=exp_need, need_create=need_create,
                        scene_name=scene_name, cultivate_ready=cultivate_ready,
                        promotion_locked=promotion_locked,
                        sect_name=XY.SECT_NAMES.get(st.sect_key, "未转职"),
                        todo=todo)


# ============================================================
# 门派选择（创建角色）
# ============================================================
@router.get("/create")
async def create_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    await db.commit()
    return await render(request, "xyou/create.html", db, user=user, st=st,
                        sects=XY.SECTS, base_attrs=XY.SECT_BASE_ATTRS,
                        sect_weapon=XY.SECT_WEAPON)


@router.post("/create")
async def create_submit(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    form = await request.form()
    sect_key = (form.get("sect_key") or "").strip()
    if sect_key not in XY.SECT_BASE_ATTRS:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="门派选择非法", back_href="/games/xyou/create", back_text="返回")
    st.sect_key = sect_key
    base = XY.SECT_BASE_ATTRS[sect_key]
    st.hp = base["hp"]
    st.mp = base["mp"]
    st.atk = base["atk"]
    st.defense = base["defense"]
    st.speed = base["speed"]
    st.lingli = base["lingli"]
    st.level = 1
    st.exp = 0
    st.current_scene = "changan"
    await log.record(db, user.id, MODULE_KEY, "create", sect_key)
    await db.commit()
    return RedirectResponse("/games/xyou", status_code=303)


# ============================================================
# 技能系统
# ============================================================
@router.get("/skills")
async def skills_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if not st.sect_key:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="请先选择门派", back_href="/games/xyou/create", back_text="前往选择")
    learned = await _learned_skills(db, user.id)
    res = await db.execute(select(models.XyouSkill).where(
        models.XyouSkill.sect_key == st.sect_key).order_by(models.XyouSkill.unlock_level))
    skill_list = []
    for sk in res.scalars().all():
        skill_list.append({
            "key": sk.key, "name": sk.name, "skill_type": sk.skill_type,
            "unlock_level": sk.unlock_level, "cost_silver": sk.cost_silver,
            "cost_mp": sk.cost_mp, "effect": sk.effect,
            "level": learned.get(sk.key, 0),
            "can_learn": st.level >= sk.unlock_level and sk.key not in learned,
        })
    await db.commit()
    return await render(request, "xyou/skills.html", db, user=user, st=st,
                        skill_list=skill_list, learned=learned,
                        sect_name=XY.SECT_NAMES.get(st.sect_key, st.sect_key),
                        exp_need=XY.exp_needed(st.level))


@router.post("/skills/learn/{skill_key}")
async def skill_learn(skill_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if not st.sect_key:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="请先选择门派", back_href="/games/xyou/create", back_text="前往选择")
    sk = await db.get(models.XyouSkill, skill_key)
    if not sk or sk.sect_key != st.sect_key:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="技能不存在或不属于你的门派",
                            back_href="/games/xyou/skills", back_text="返回技能")
    if st.level < sk.unlock_level:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"等级不足，需{sk.unlock_level}级",
                            back_href="/games/xyou/skills", back_text="返回技能")
    learned = await _learned_skills(db, user.id)
    if skill_key in learned:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="已学习该技能", back_href="/games/xyou/skills", back_text="返回技能")
    if st.silver < sk.cost_silver:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"银两不足（需{sk.cost_silver}）",
                            back_href="/games/xyou/skills", back_text="返回技能")
    st.silver -= sk.cost_silver
    db.add(models.XyouUserSkill(user_id=user.id, skill_key=skill_key, level=1))
    await log.record(db, user.id, MODULE_KEY, "skill.learn", skill_key)
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"学会《{sk.name}》", back_href="/games/xyou/skills", back_text="返回技能")


# ============================================================
# 装备系统
# ============================================================
@router.get("/equip")
async def equip_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    res = await db.execute(select(models.XyouUserEquip).where(
        models.XyouUserEquip.user_id == user.id).order_by(models.XyouUserEquip.id.desc()))
    all_equips = list(res.scalars().all())
    equipped = [e for e in all_equips if e.worn]
    bag_equips = [e for e in all_equips if not e.worn]
    slot_map = {s: None for s in XY.EQUIP_SLOTS}
    for e in equipped:
        slot_map[e.slot] = e
    def_map = await _equip_def_map(db)
    power = calc_player_power(st)
    await db.commit()
    return await render(request, "xyou/equip.html", db, user=user, st=st,
                        slot_map=slot_map, bag_equips=bag_equips, def_map=def_map,
                        power=power, slots=XY.EQUIP_SLOTS)


@router.post("/equip/wear/{user_equip_id}")
async def equip_wear(user_equip_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    e = await db.get(models.XyouUserEquip, user_equip_id)
    if not e or e.user_id != user.id:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="装备不存在", back_href="/games/xyou/equip", back_text="返回")
    eq_def = await db.get(models.XyouEquip, e.equip_key)
    if eq_def:
        if eq_def.sect_req and eq_def.sect_req != (await get_state(db, user.id)).sect_key:
            return await render(request, "result.html", db, user=user, ok=False,
                                msg="门派不符，无法穿戴",
                                back_href="/games/xyou/equip", back_text="返回")
        if (await get_state(db, user.id)).level < eq_def.level_req:
            return await render(request, "result.html", db, user=user, ok=False,
                                msg=f"等级不足，需{eq_def.level_req}级",
                                back_href="/games/xyou/equip", back_text="返回")
    res = await db.execute(select(models.XyouUserEquip).where(
        models.XyouUserEquip.user_id == user.id,
        models.XyouUserEquip.slot == e.slot,
        models.XyouUserEquip.worn.is_(True)))
    for old in res.scalars().all():
        old.worn = False
    e.worn = True
    await log.record(db, user.id, MODULE_KEY, "equip.wear", f"{e.slot}:{e.id}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"已穿戴 {e.slot} 部位装备",
                        back_href="/games/xyou/equip", back_text="返回装备")


@router.post("/equip/takeoff/{user_equip_id}")
async def equip_takeoff(user_equip_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    e = await db.get(models.XyouUserEquip, user_equip_id)
    if not e or e.user_id != user.id:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="装备不存在", back_href="/games/xyou/equip", back_text="返回")
    e.worn = False
    await log.record(db, user.id, MODULE_KEY, "equip.takeoff", str(e.id))
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg="已卸下", back_href="/games/xyou/equip", back_text="返回装备")


# ============================================================
# 装备商店
# ============================================================
@router.get("/shop")
async def shop_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    res = await db.execute(select(models.XyouEquip).order_by(
        models.XyouEquip.level_req, models.XyouEquip.quality))
    shop_list = [e for e in res.scalars().all()
                 if not e.sect_req or e.sect_req == st.sect_key]
    await db.commit()
    return await render(request, "xyou/shop.html", db, user=user, st=st,
                        shop_list=shop_list)


@router.post("/shop/buy/{equip_key}")
async def shop_buy(equip_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    e = await db.get(models.XyouEquip, equip_key)
    if not e:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="商品不存在", back_href="/games/xyou/shop", back_text="返回商店")
    if e.sect_req and e.sect_req != st.sect_key:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="门派不符，无法购买",
                            back_href="/games/xyou/shop", back_text="返回商店")
    if st.level < e.level_req:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"等级不足，需{e.level_req}级",
                            back_href="/games/xyou/shop", back_text="返回商店")
    if st.silver < e.price:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"银两不足（需{e.price}）",
                            back_href="/games/xyou/shop", back_text="返回商店")
    st.silver -= e.price
    db.add(models.XyouUserEquip(user_id=user.id, equip_key=equip_key,
                                slot=e.slot, worn=False))
    await goods.add_item(db, user.id, equip_key, MODULE_KEY, 1)
    await log.record(db, user.id, MODULE_KEY, "shop.buy", equip_key)
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"购得《{e.name}》", back_href="/games/xyou/shop", back_text="返回商店")


# ============================================================
# 副本系统
# ============================================================
@router.get("/dungeons")
async def dungeons_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    res = await db.execute(select(models.XyouDungeon).order_by(models.XyouDungeon.level_min))
    all_dg = res.scalars().all()
    # 场景名映射
    scene_keys = {d.scene for d in all_dg}
    scenes = {}
    for sk in scene_keys:
        s = await db.get(models.XyouScene, sk)
        scenes[sk] = s.name if s else sk
    await db.commit()
    return await render(request, "xyou/dungeons.html", db, user=user, st=st,
                        dungeon_list=all_dg, scenes=scenes)


@router.post("/dungeon/{dungeon_key}")
async def dungeon_challenge(dungeon_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if not st.sect_key:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="请先选择门派", back_href="/games/xyou/create", back_text="前往选择")
    dg = await db.get(models.XyouDungeon, dungeon_key)
    if not dg:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="副本不存在", back_href="/games/xyou/dungeons", back_text="返回")
    if st.level < dg.level_min:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"等级不足，需{dg.level_min}级",
                            back_href="/games/xyou/dungeons", back_text="返回")
    # 简易战斗：按战力与副本等级估算胜率
    my_power = calc_player_power(st)
    diff_mult = 1.5 if dg.difficulty == "困难" else 1.0
    enemy_power = int((dg.level_max * 30 + dg.reward_exp // 10) * diff_mult)
    prob = 0.5 + (my_power - enemy_power) / max(my_power + enemy_power, 1)
    prob = max(0.1, min(0.9, prob))
    win = random.random() < prob
    if win:
        st.silver += dg.reward_silver
        leveled = add_exp(st, dg.reward_exp)
        # 副本掉落：按 drop_quality 随机装备
        drop_msg = ""
        res = await db.execute(select(models.XyouEquip).where(
            models.XyouEquip.quality == dg.drop_quality).limit(10))
        candidates = [e for e in res.scalars().all()
                      if (not e.sect_req or e.sect_req == st.sect_key)
                      and e.level_req <= st.level + 10]
        if candidates and random.random() < 0.6:
            drop = random.choice(candidates)
            db.add(models.XyouUserEquip(user_id=user.id, equip_key=drop.key,
                                        slot=drop.slot, worn=False))
            await goods.add_item(db, user.id, drop.key, MODULE_KEY, 1)
            drop_msg = f"，掉落《{drop.name}》"
        await _notify_milestones(db, user.id, st)
        await log.record(db, user.id, MODULE_KEY, "dungeon.win", dungeon_key)
        await db.commit()
        return await render(request, "result.html", db, user=user, ok=True,
                            msg=f"挑战《{dg.name}》胜利！经验+{dg.reward_exp}，银两+{dg.reward_silver}{drop_msg}"
                                f"{'，升级了！' if leveled else ''}",
                            back_href="/games/xyou/dungeons", back_text="返回副本")
    await log.record(db, user.id, MODULE_KEY, "dungeon.loss", dungeon_key)
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=False,
                        msg=f"挑战《{dg.name}》失败，再接再厉",
                        back_href="/games/xyou/dungeons", back_text="返回副本")


# ============================================================
# 修炼挂机系统
# ============================================================
@router.get("/cultivate")
async def cultivate_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if not st.sect_key:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="请先选择门派", back_href="/games/xyou/create", back_text="前往选择")
    now = datetime.utcnow()
    in_progress = bool(st.cultivate_end_at and now < st.cultivate_end_at)
    ready = bool(st.cultivate_end_at and now >= st.cultivate_end_at)
    remain = (st.cultivate_end_at - now).total_seconds() if in_progress else 0
    await db.commit()
    return await render(request, "xyou/cultivate.html", db, user=user, st=st,
                        in_progress=in_progress, ready=ready, remain=int(remain),
                        exp_per_hour=CULTIVATE_EXP_PER_HOUR,
                        silver_per_hour=CULTIVATE_SILVER_PER_HOUR,
                        max_hours=CULTIVATE_MAX_HOURS)


@router.post("/cultivate/start")
async def cultivate_start(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if not st.sect_key:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="请先选择门派", back_href="/games/xyou/create", back_text="前往选择")
    now = datetime.utcnow()
    if st.cultivate_end_at and now < st.cultivate_end_at:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="修炼进行中，请等待结束",
                            back_href="/games/xyou/cultivate", back_text="返回修炼")
    st.cultivate_end_at = now + timedelta(hours=CULTIVATE_MAX_HOURS)
    await log.record(db, user.id, MODULE_KEY, "cultivate.start", "")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"开始修炼，{CULTIVATE_MAX_HOURS}小时后可领取收益",
                        back_href="/games/xyou/cultivate", back_text="返回修炼")


@router.post("/cultivate/claim")
async def cultivate_claim(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    now = datetime.utcnow()
    if not st.cultivate_end_at or now < st.cultivate_end_at:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="修炼尚未结束，暂不可领取",
                            back_href="/games/xyou/cultivate", back_text="返回修炼")
    exp_yield = CULTIVATE_EXP_PER_HOUR * CULTIVATE_MAX_HOURS
    silver_yield = CULTIVATE_SILVER_PER_HOUR * CULTIVATE_MAX_HOURS
    leveled = add_exp(st, exp_yield)
    st.silver += silver_yield
    st.cultivate_end_at = None
    await _notify_milestones(db, user.id, st)
    await log.record(db, user.id, MODULE_KEY, "cultivate.claim", f"exp={exp_yield},silver={silver_yield}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"领取修炼收益：经验+{exp_yield}，银两+{silver_yield}"
                            f"{'，升级了！' if leveled else ''}",
                        back_href="/games/xyou/cultivate", back_text="返回修炼")


# ============================================================
# 转职系统（spec：9/59/109/139/169/189 多段转职）
# ============================================================
@router.get("/promote")
async def promote_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    promo = XY.PROMOTION_QUESTS.get(st.level)
    await db.commit()
    return await render(request, "xyou/promote.html", db, user=user, st=st,
                        promo=promo, level=st.level)


@router.post("/promote/complete")
async def promote_complete(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if not XY.is_promotion_locked(st.level):
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="当前等级无需转职", back_href="/games/xyou", back_text="返回首页")
    promo = XY.PROMOTION_QUESTS.get(st.level, {})
    # 转职完成：等级+1，给予经验奖励
    st.level += 1
    reward_exp = promo.get("reward_exp", 0)
    leveled = False
    if reward_exp:
        leveled = add_exp(st, reward_exp)
    await log.record(db, user.id, MODULE_KEY, "promote.complete", f"level={st.level}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"转职成功！等级提升至 {st.level} 级"
                            f"{f'，获得 {reward_exp} 经验' if reward_exp else ''}"
                            f"{'，升级了！' if leveled else ''}",
                        back_href="/games/xyou", back_text="返回首页")


# ============================================================
# 宠物系统
# ============================================================
@router.get("/pet")
async def pet_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    res = await db.execute(select(models.XyouUserPet).where(
        models.XyouUserPet.user_id == user.id).order_by(models.XyouUserPet.id.desc()))
    my_pets = []
    pet_def_map = {}
    for up in res.scalars().all():
        pd = await db.get(models.XyouPet, up.pet_key)
        pet_def_map[up.pet_key] = pd
        my_pets.append({"user_pet": up, "pet_def": pd})
    await db.commit()
    return await render(request, "xyou/pet.html", db, user=user, st=st,
                        my_pets=my_pets, max_pets=8)


@router.post("/pet/set_battle/{user_pet_id}")
async def pet_set_battle(user_pet_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """设置出战宠物（同时只能 1 只出战）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    up = await db.get(models.XyouUserPet, user_pet_id)
    if not up or up.user_id != user.id:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="宠物不存在", back_href="/games/xyou/pet", back_text="返回")
    # 清除其他宠物的出战状态
    res = await db.execute(select(models.XyouUserPet).where(
        models.XyouUserPet.user_id == user.id,
        models.XyouUserPet.in_battle.is_(True)))
    for op in res.scalars().all():
        op.in_battle = False
    up.in_battle = True
    await log.record(db, user.id, MODULE_KEY, "pet.battle", str(up.id))
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg="已设置出战", back_href="/games/xyou/pet", back_text="返回宠物")


@router.post("/pet/rest/{user_pet_id}")
async def pet_rest(user_pet_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """休息宠物"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    up = await db.get(models.XyouUserPet, user_pet_id)
    if not up or up.user_id != user.id:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="宠物不存在", back_href="/games/xyou/pet", back_text="返回")
    up.in_battle = False
    await log.record(db, user.id, MODULE_KEY, "pet.rest", str(up.id))
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg="宠物已休息", back_href="/games/xyou/pet", back_text="返回宠物")


# ============================================================
# 场景系统（世界地图）
# ============================================================
@router.get("/scenes")
async def scenes_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    current = await db.get(models.XyouScene, st.current_scene)
    exits = []
    if current:
        try:
            exit_keys = json.loads(current.exits or "[]")
            for ek in exit_keys:
                s = await db.get(models.XyouScene, ek)
                if s:
                    exits.append(s)
        except Exception:
            pass
    res = await db.execute(select(models.XyouScene).order_by(models.XyouScene.level_min))
    all_scenes = res.scalars().all()
    await db.commit()
    return await render(request, "xyou/scenes.html", db, user=user, st=st,
                        current=current, exits=exits, all_scenes=all_scenes)


@router.post("/scene/move/{scene_key}")
async def scene_move(scene_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """移动到相邻场景"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    target = await db.get(models.XyouScene, scene_key)
    if not target:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="场景不存在", back_href="/games/xyou/scenes", back_text="返回")
    current = await db.get(models.XyouScene, st.current_scene)
    if current:
        try:
            exit_keys = json.loads(current.exits or "[]")
            if scene_key not in exit_keys:
                return await render(request, "result.html", db, user=user, ok=False,
                                    msg="该场景不在出口列表，无法直达",
                                    back_href="/games/xyou/scenes", back_text="返回")
        except Exception:
            pass
    if st.level < target.level_min:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"等级不足，需{target.level_min}级",
                            back_href="/games/xyou/scenes", back_text="返回")
    st.current_scene = scene_key
    await log.record(db, user.id, MODULE_KEY, "scene.move", scene_key)
    await db.commit()
    return RedirectResponse("/games/xyou/scenes", status_code=303)


# ============================================================
# 战斗系统（场景内遇怪）
# ============================================================
@router.get("/battle")
async def battle_page(request: Request, db: AsyncSession = Depends(get_db)):
    """列出当前场景可战斗的怪物"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if not st.sect_key:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="请先选择门派", back_href="/games/xyou/create", back_text="前往选择")
    scene_monsters = [m for m in XY.MONSTERS if m[8] == st.current_scene]
    await db.commit()
    return await render(request, "xyou/battle.html", db, user=user, st=st,
                        monsters=scene_monsters)


@router.post("/battle/fight/{monster_key}")
async def battle_fight(monster_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """与怪物战斗（简易回合制）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if not st.sect_key:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="请先选择门派", back_href="/games/xyou/create", back_text="前往选择")
    # 日限 50 场
    counters = _daily_counters(st)
    today = _today_key()
    if counters.get(f"battle_{today}", 0) >= 50:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="今日战斗次数已用完（50/50）",
                            back_href="/games/xyou/battle", back_text="返回战斗")
    # 查找怪物
    monster = None
    for m in XY.MONSTERS:
        if m[0] == monster_key and m[8] == st.current_scene:
            monster = m
            break
    if not monster:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="怪物不存在或不在当前场景",
                            back_href="/games/xyou/battle", back_text="返回战斗")
    m_key, m_name, m_lvl, m_hp, m_atk, m_def, m_exp, m_silver, m_scene = monster
    # 战斗：按战力估算胜率
    my_power = calc_player_power(st)
    monster_power = m_hp * 0.2 + m_atk * 2 + m_def * 1.5 + m_lvl * 8
    prob = 0.5 + (my_power - monster_power) / max(my_power + monster_power, 1)
    prob = max(0.1, min(0.9, prob))
    win = random.random() < prob
    counters[f"battle_{today}"] = counters.get(f"battle_{today}", 0) + 1
    _save_daily_counters(st, counters)
    if win:
        st.silver += m_silver
        leveled = add_exp(st, m_exp)
        # 宠物获得 20% 经验
        res = await db.execute(select(models.XyouUserPet).where(
            models.XyouUserPet.user_id == user.id,
            models.XyouUserPet.in_battle.is_(True)))
        battle_pet = res.scalar_one_or_none()
        pet_msg = ""
        if battle_pet:
            pet_exp = XY.calc_pet_exp(m_exp)
            battle_pet.exp += pet_exp
            # 宠物升级（简化：每 1000 经验升 1 级，且不超人物等级）
            while battle_pet.exp >= 1000 and battle_pet.level < st.level:
                battle_pet.exp -= 1000
                battle_pet.level += 1
            pet_msg = f"，宠物获得 {pet_exp} 经验"
        await _notify_milestones(db, user.id, st)
        await log.record(db, user.id, MODULE_KEY, "battle.win", monster_key)
        await db.commit()
        return await render(request, "result.html", db, user=user, ok=True,
                            msg=f"击败《{m_name}》！经验+{m_exp}，银两+{m_silver}{pet_msg}"
                                f"{'，升级了！' if leveled else ''}",
                            back_href="/games/xyou/battle", back_text="继续战斗")
    await log.record(db, user.id, MODULE_KEY, "battle.loss", monster_key)
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=False,
                        msg=f"被《{m_name}》击败，再接再厉",
                        back_href="/games/xyou/battle", back_text="继续战斗")


# ============================================================
# 规则页
# ============================================================
@router.get("/rules")
async def rules(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return await render(request, "xyou/rules.html", db, user=user,
                        sects=XY.SECTS, max_level=XY.MAX_LEVEL,
                        promotion_levels=XY.PROMOTION_LEVELS)


# ============================================================
# v0.2.3 新增：高级材料图鉴页
# ============================================================
@router.get("/materials")
async def materials_page(request: Request, db: AsyncSession = Depends(get_db)):
    """高级升级材料图鉴 + 区域材料掉落表"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    res = await db.execute(select(models.XyouMaterial).order_by(models.XyouMaterial.key))
    material_list = res.scalars().all()
    await db.commit()
    return await render(request, "xyou/materials.html", db, user=user,
                        material_list=material_list,
                        region_materials=XY.REGION_MATERIALS,
                        gem_tiers=XY.GEM_TIERS)


# ============================================================
# v0.2.3 新增：长安城坐标查询页
# ============================================================
@router.get("/coords")
async def coords_page(request: Request, db: AsyncSession = Depends(get_db)):
    """长安城核心坐标 + 各区域进入方式"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    res = await db.execute(select(models.XyouCoord).where(
        models.XyouCoord.scene_key == "changan"
    ).order_by(models.XyouCoord.id))
    coord_list = res.scalars().all()
    await db.commit()
    return await render(request, "xyou/coords.html", db, user=user,
                        coord_list=coord_list,
                        region_entries=XY.REGION_ENTRIES)


# ============================================================
# v0.2.3 新增：自动战斗/挂机设置页
# ============================================================
@router.get("/autobattle")
async def autobattle_page(request: Request, db: AsyncSession = Depends(get_db)):
    """自动战斗/挂机系统参数 + 当前玩家设置"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    try:
        cur_settings = json.loads(st.auto_settings or "{}")
    except Exception:
        cur_settings = {}
    await db.commit()
    return await render(request, "xyou/autobattle.html", db, user=user, st=st,
                        auto_settings=XY.AUTO_BATTLE_SETTINGS,
                        hotkeys=XY.BATTLE_HOTKEYS_DEFAULT,
                        system_settings=XY.SYSTEM_SETTINGS,
                        cur_settings=cur_settings)


@router.post("/autobattle/save")
async def autobattle_save(request: Request, db: AsyncSession = Depends(get_db)):
    """保存自动战斗设置（HP/MP 阈值 / 自动遇敌 / 自动拾取等）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    form = await request.form()
    settings = {
        "auto_encounter": bool(form.get("auto_encounter")),
        "auto_attack": bool(form.get("auto_attack")),
        "hp_threshold": int(form.get("hp_threshold") or 30),
        "mp_threshold": int(form.get("mp_threshold") or 20),
        "auto_pickup": bool(form.get("auto_pickup")),
        "pet_auto_summon": bool(form.get("pet_auto_summon")),
    }
    st.auto_settings = json.dumps(settings, ensure_ascii=False)
    await log.record(db, user.id, MODULE_KEY, "autobattle.save", "")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg="自动战斗设置已保存",
                        back_href="/games/xyou/autobattle", back_text="返回设置")


# ============================================================
# v0.2.3 新增：升级路线推荐页
# ============================================================
@router.get("/roadmap")
async def roadmap_page(request: Request, db: AsyncSession = Depends(get_db)):
    """新手快速升级路线 + 经验获取渠道 + 等级卡点"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    await db.commit()
    return await render(request, "xyou/roadmap.html", db, user=user, st=st,
                        leveling_roadmap=XY.LEVELING_ROADMAP,
                        exp_sources=XY.EXP_SOURCES,
                        level_gates=XY.LEVEL_GATES,
                        mentor_reward_exp=XY.MENTOR_REWARD_EXP,
                        mentor_unlock_level=XY.MENTOR_UNLOCK_LEVEL,
                        mentor_level_req=XY.MENTOR_LEVEL_REQ)


# ============================================================
# v0.2.3 新增：副本 BOSS 详细页
# ============================================================
@router.get("/dungeon_bosses")
async def dungeon_bosses_page(request: Request, db: AsyncSession = Depends(get_db)):
    """副本 BOSS 详细掉落表（来源 zol.com.cn 全网检索）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    await db.commit()
    return await render(request, "xyou/dungeon_bosses.html", db, user=user,
                        dungeon_bosses=XY.DUNGEON_BOSSES,
                        task_types=XY.TASK_TYPES)
