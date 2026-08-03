"""风云三国模块（v0.1.9）

老味道点：三职业 / 三阵营 / 技能装备 / 副本挑战 / 军团社交 / 演武挂机 / 荣誉称号成就
核心循环：演武/副本 → 获得经验银两 → 升级换装 → 学技能 → 挑战更高副本 → 继续养成

口径：怀旧 / 旧逻辑 / WAP 层级页 / 可复刻落地。
排行/商城/背包/消息 走平台公共系统（events.emit 上报 + 链接跳转）。
"""
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
from . import fengyun_data as FY

router = APIRouter(prefix="/games/fengyun")
MODULE_KEY = "fengyun"

# 演武基础收益（每小时）
TRAINING_EXP_PER_HOUR = 300
TRAINING_SILVER_PER_HOUR = 150

# 阵营默认主城
FACTION_CITY = {"wei": "xuchang_z", "shu": "chengdu", "wu": "jianye"}


# ============================================================
# 辅助函数
# ============================================================
async def get_state(db: AsyncSession, user_id: int) -> models.FengyunState:
    st = await db.get(models.FengyunState, user_id)
    if not st:
        st = models.FengyunState(user_id=user_id)
        db.add(st)
        await db.commit()
        await db.refresh(st)
    return st


def calc_player_power(st: models.FengyunState) -> int:
    """简易战力：由属性 + 等级估算"""
    return int(st.hp * 0.2 + st.mp * 0.1 + st.atk * 2 + st.defense * 1.5
               + st.dodge * 1.5 + st.crit * 1.5 + st.level * 5)


def add_exp(st: models.FengyunState, amount: int) -> bool:
    """加经验，按职业每级属性增量自动升级，返回是否升级"""
    if st.level >= FY.MAX_LEVEL:
        st.exp = 0
        return False
    st.exp += amount
    leveled = False
    while st.level < FY.MAX_LEVEL:
        need = FY.exp_needed(st.level)
        if need <= 0:
            break
        if st.exp >= need:
            st.exp -= need
            st.level += 1
            per = FY.CLASS_PER_LEVEL.get(st.class_key, {})
            st.hp += per.get("hp", 0)
            st.mp += per.get("mp", 0)
            st.atk += per.get("atk", 0)
            st.defense += per.get("defense", 0)
            st.dodge += per.get("dodge", 0)
            st.crit += per.get("crit", 0)
            leveled = True
        else:
            break
    return leveled


async def _has_any_skill(db: AsyncSession, user_id: int) -> bool:
    res = await db.execute(select(models.FengyunUserSkill).where(
        models.FengyunUserSkill.user_id == user_id).limit(1))
    return res.scalar_one_or_none() is not None


async def _is_fresh(db: AsyncSession, st: models.FengyunState) -> bool:
    """未选择职业：1级0经验且未学任何技能"""
    return st.level == 1 and st.exp == 0 and not await _has_any_skill(db, st.user_id)


async def _learned_skills(db: AsyncSession, user_id: int) -> dict:
    res = await db.execute(select(models.FengyunUserSkill).where(
        models.FengyunUserSkill.user_id == user_id))
    return {s.skill_key: s.level for s in res.scalars().all()}


async def _equip_def_map(db: AsyncSession) -> dict:
    """{equip_key: FengyunEquip}"""
    res = await db.execute(select(models.FengyunEquip))
    return {e.key: e for e in res.scalars().all()}


async def _notify_milestones(db: AsyncSession, user_id: int, st: models.FengyunState):
    """等级里程碑上报平台：10级点亮图标，30级推进成就"""
    if st.level >= 10:
        await events.emit(db, user_id, MODULE_KEY, "icon_light", {"icon_key": "icon_fengyun"})
    if st.level >= 30:
        await events.emit(db, user_id, MODULE_KEY, "achievement",
                          {"key": "achv_fengyun_30", "absolute": True})


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
    exp_need = FY.exp_needed(st.level)
    # 演武待领
    now = datetime.utcnow()
    training_ready = bool(st.training_end_at and now >= st.training_end_at)
    # 当前城市名
    city = await db.get(models.FengyunCity, st.current_city)
    city_name = city.name if city else st.current_city
    todo = []
    if need_create:
        todo.append(("请先选择职业与阵营", "点击前往", "/games/fengyun/create"))
    if training_ready:
        todo.append(("演武收益待领取", "前往演武", "/games/fengyun/training"))
    await db.commit()
    return await render(request, "fengyun/home.html", db, user=user, st=st,
                        power=power, exp_need=exp_need, need_create=need_create,
                        city_name=city_name, training_ready=training_ready,
                        class_name=FY.CLASS_NAMES.get(st.class_key, st.class_key),
                        faction_name=FY.FACTION_NAMES.get(st.faction, st.faction),
                        todo=todo)


# ============================================================
# 职业与阵营选择
# ============================================================
@router.get("/create")
async def create_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    await db.commit()
    return await render(request, "fengyun/create.html", db, user=user, st=st,
                        classes=FY.CLASSES, factions=FY.FACTIONS,
                        base_attrs=FY.CLASS_BASE_ATTRS)


@router.post("/create")
async def create_submit(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    form = await request.form()
    class_key = (form.get("class_key") or "").strip()
    faction = (form.get("faction") or "").strip()
    if class_key not in FY.CLASS_BASE_ATTRS:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="职业选择非法", back_href="/games/fengyun/create", back_text="返回")
    if faction not in FY.FACTION_NAMES:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="阵营选择非法", back_href="/games/fengyun/create", back_text="返回")
    st.class_key = class_key
    st.faction = faction
    base = FY.CLASS_BASE_ATTRS[class_key]
    st.hp = base["hp"]
    st.mp = base["mp"]
    st.atk = base["atk"]
    st.defense = base["defense"]
    st.dodge = base["dodge"]
    st.crit = base["crit"]
    st.level = 1
    st.exp = 0
    st.current_city = FACTION_CITY.get(faction, "chengdu")
    await log.record(db, user.id, MODULE_KEY, "create", f"{class_key}/{faction}")
    await db.commit()
    return RedirectResponse("/games/fengyun", status_code=303)


# ============================================================
# 技能系统
# ============================================================
@router.get("/skills")
async def skills_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    learned = await _learned_skills(db, user.id)
    res = await db.execute(select(models.FengyunSkill).where(
        models.FengyunSkill.class_key == st.class_key).order_by(models.FengyunSkill.unlock_level))
    skill_list = []
    for sk in res.scalars().all():
        skill_list.append({
            "key": sk.key, "name": sk.name, "skill_type": sk.skill_type,
            "unlock_level": sk.unlock_level, "cost_silver": sk.cost_silver,
            "cost_exp": sk.cost_exp, "effect": sk.effect,
            "level": learned.get(sk.key, 0),
            "can_learn": st.level >= sk.unlock_level and sk.key not in learned,
        })
    await db.commit()
    return await render(request, "fengyun/skills.html", db, user=user, st=st,
                        skill_list=skill_list, learned=learned,
                        class_name=FY.CLASS_NAMES.get(st.class_key, st.class_key),
                        exp_need=FY.exp_needed(st.level))


@router.post("/skills/learn/{skill_key}")
async def skill_learn(skill_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    sk = await db.get(models.FengyunSkill, skill_key)
    if not sk or sk.class_key != st.class_key:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="技能不存在或不属于你的职业",
                            back_href="/games/fengyun/skills", back_text="返回技能")
    if st.level < sk.unlock_level:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"等级不足，需{sk.unlock_level}级",
                            back_href="/games/fengyun/skills", back_text="返回技能")
    learned = await _learned_skills(db, user.id)
    if skill_key in learned:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="已学习该技能", back_href="/games/fengyun/skills", back_text="返回技能")
    if st.silver < sk.cost_silver:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"银两不足（需{sk.cost_silver}）",
                            back_href="/games/fengyun/skills", back_text="返回技能")
    if st.exp < sk.cost_exp:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"经验不足（需{sk.cost_exp}）",
                            back_href="/games/fengyun/skills", back_text="返回技能")
    st.silver -= sk.cost_silver
    st.exp -= sk.cost_exp
    db.add(models.FengyunUserSkill(user_id=user.id, skill_key=skill_key, level=1))
    await log.record(db, user.id, MODULE_KEY, "skill.learn", skill_key)
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"学会《{sk.name}》", back_href="/games/fengyun/skills", back_text="返回技能")


# ============================================================
# 装备系统
# ============================================================
@router.get("/equip")
async def equip_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    res = await db.execute(select(models.FengyunUserEquip).where(
        models.FengyunUserEquip.user_id == user.id).order_by(models.FengyunUserEquip.id.desc()))
    all_equips = list(res.scalars().all())
    equipped = [e for e in all_equips if e.equipped]
    bag_equips = [e for e in all_equips if not e.equipped]
    slot_map = {s: None for s in FY.EQUIP_SLOTS}
    for e in equipped:
        slot_map[e.slot] = e
    def_map = await _equip_def_map(db)
    power = calc_player_power(st)
    await db.commit()
    return await render(request, "fengyun/equip.html", db, user=user, st=st,
                        slot_map=slot_map, bag_equips=bag_equips, def_map=def_map,
                        power=power, slots=FY.EQUIP_SLOTS)


@router.post("/equip/wear/{user_equip_id}")
async def equip_wear(user_equip_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    e = await db.get(models.FengyunUserEquip, user_equip_id)
    if not e or e.user_id != user.id:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="装备不存在", back_href="/games/fengyun/equip", back_text="返回")
    res = await db.execute(select(models.FengyunUserEquip).where(
        models.FengyunUserEquip.user_id == user.id,
        models.FengyunUserEquip.slot == e.slot,
        models.FengyunUserEquip.equipped.is_(True)))
    for old in res.scalars().all():
        old.equipped = False
    e.equipped = True
    await log.record(db, user.id, MODULE_KEY, "equip.wear", f"{e.slot}:{e.id}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"已穿戴 {e.slot} 部位装备",
                        back_href="/games/fengyun/equip", back_text="返回装备")


@router.post("/equip/takeoff/{user_equip_id}")
async def equip_takeoff(user_equip_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    e = await db.get(models.FengyunUserEquip, user_equip_id)
    if not e or e.user_id != user.id:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="装备不存在", back_href="/games/fengyun/equip", back_text="返回")
    e.equipped = False
    await log.record(db, user.id, MODULE_KEY, "equip.takeoff", str(e.id))
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg="已卸下", back_href="/games/fengyun/equip", back_text="返回装备")


# ============================================================
# 装备商店
# ============================================================
@router.get("/shop")
async def shop_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    res = await db.execute(select(models.FengyunEquip).order_by(
        models.FengyunEquip.level_req, models.FengyunEquip.quality))
    shop_list = [e for e in res.scalars().all()
                 if not e.class_req or e.class_req == st.class_key]
    await db.commit()
    return await render(request, "fengyun/shop.html", db, user=user, st=st,
                        shop_list=shop_list)


@router.post("/shop/buy/{equip_key}")
async def shop_buy(equip_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    e = await db.get(models.FengyunEquip, equip_key)
    if not e:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="商品不存在", back_href="/games/fengyun/shop", back_text="返回商店")
    if e.class_req and e.class_req != st.class_key:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="职业不符，无法购买",
                            back_href="/games/fengyun/shop", back_text="返回商店")
    if st.level < e.level_req:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"等级不足，需{e.level_req}级",
                            back_href="/games/fengyun/shop", back_text="返回商店")
    if st.silver < e.price:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"银两不足（需{e.price}）",
                            back_href="/games/fengyun/shop", back_text="返回商店")
    st.silver -= e.price
    db.add(models.FengyunUserEquip(user_id=user.id, equip_key=equip_key,
                                   slot=e.slot, equipped=False))
    await goods.add_item(db, user.id, equip_key, MODULE_KEY, 1)
    await log.record(db, user.id, MODULE_KEY, "shop.buy", equip_key)
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"购得《{e.name}》", back_href="/games/fengyun/shop", back_text="返回商店")


# ============================================================
# 副本系统
# ============================================================
@router.get("/dungeons")
async def dungeons_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    res = await db.execute(select(models.FengyunDungeon).order_by(models.FengyunDungeon.level_min))
    all_dg = res.scalars().all()
    dungeon_list = [d for d in all_dg if d.faction == "all" or d.faction == st.faction]
    # 城市名映射
    city_keys = {d.city for d in dungeon_list}
    cities = {}
    for ck in city_keys:
        c = await db.get(models.FengyunCity, ck)
        cities[ck] = c.name if c else ck
    await db.commit()
    return await render(request, "fengyun/dungeons.html", db, user=user, st=st,
                        dungeon_list=dungeon_list, cities=cities,
                        faction_name=FY.FACTION_NAMES.get(st.faction, st.faction))


@router.post("/dungeon/{dungeon_key}")
async def dungeon_challenge(dungeon_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    dg = await db.get(models.FengyunDungeon, dungeon_key)
    if not dg:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="副本不存在", back_href="/games/fengyun/dungeons", back_text="返回")
    if dg.faction != "all" and dg.faction != st.faction:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="阵营不符，无法挑战",
                            back_href="/games/fengyun/dungeons", back_text="返回")
    if st.level < dg.level_min:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"等级不足，需{dg.level_min}级",
                            back_href="/games/fengyun/dungeons", back_text="返回")
    # 简易战斗：按战力与副本等级估算胜率
    my_power = calc_player_power(st)
    enemy_power = dg.level_max * 30 + dg.reward_exp // 10
    prob = 0.5 + (my_power - enemy_power) / max(my_power + enemy_power, 1)
    prob = max(0.1, min(0.9, prob))
    win = random.random() < prob
    if win:
        st.silver += dg.reward_silver
        leveled = add_exp(st, dg.reward_exp)
        await _notify_milestones(db, user.id, st)
        await log.record(db, user.id, MODULE_KEY, "dungeon.win", dungeon_key)
        await db.commit()
        return await render(request, "result.html", db, user=user, ok=True,
                            msg=f"挑战《{dg.name}》胜利！经验+{dg.reward_exp}，银两+{dg.reward_silver}"
                                f"{'，升级了！' if leveled else ''}",
                            back_href="/games/fengyun/dungeons", back_text="返回副本")
    await log.record(db, user.id, MODULE_KEY, "dungeon.loss", dungeon_key)
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=False,
                        msg=f"挑战《{dg.name}》失败，再接再厉",
                        back_href="/games/fengyun/dungeons", back_text="返回副本")


# ============================================================
# 军团系统
# ============================================================
async def _my_legion_member(db: AsyncSession, user_id: int):
    res = await db.execute(select(models.FengyunLegionMember).where(
        models.FengyunLegionMember.user_id == user_id))
    return res.scalar_one_or_none()


@router.get("/legion")
async def legion_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    my_member = await _my_legion_member(db, user.id)
    my_legion = None
    members = []
    if my_member:
        my_legion = await db.get(models.FengyunLegion, my_member.legion_id)
        if my_legion:
            res = await db.execute(select(models.FengyunLegionMember).where(
                models.FengyunLegionMember.legion_id == my_legion.id))
            for m in res.scalars().all():
                mu = await db.get(models.User, m.user_id)
                ms = await db.get(models.FengyunState, m.user_id)
                members.append({"member": m, "user": mu, "state": ms})
    res = await db.execute(select(models.FengyunLegion).limit(10))
    legion_list = res.scalars().all()
    await db.commit()
    return await render(request, "fengyun/legion.html", db, user=user, st=st,
                        my_legion=my_legion, my_member=my_member, members=members,
                        legion_list=legion_list, levels=FY.LEGION_LEVELS,
                        require=FY.LEGION_CREATE_REQUIRE)


@router.post("/legion/create")
async def legion_create(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if await _my_legion_member(db, user.id):
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="已加入军团，无法创建",
                            back_href="/games/fengyun/legion", back_text="返回")
    form = await request.form()
    name = (form.get("name") or "").strip()
    if not name or len(name) > 16:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="军团名非法（1-16字）",
                            back_href="/games/fengyun/legion", back_text="返回")
    if st.level < FY.LEGION_CREATE_REQUIRE["leader_level"]:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"等级不足，需{FY.LEGION_CREATE_REQUIRE['leader_level']}级",
                            back_href="/games/fengyun/legion", back_text="返回")
    if st.silver < FY.LEGION_CREATE_REQUIRE["cost_silver"]:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"银两不足（需{FY.LEGION_CREATE_REQUIRE['cost_silver']}）",
                            back_href="/games/fengyun/legion", back_text="返回")
    exists = (await db.execute(select(models.FengyunLegion).where(
        models.FengyunLegion.name == name))).scalar_one_or_none()
    if exists:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="军团名已存在", back_href="/games/fengyun/legion", back_text="返回")
    st.silver -= FY.LEGION_CREATE_REQUIRE["cost_silver"]
    g = models.FengyunLegion(name=name, leader_id=user.id, level=1)
    db.add(g)
    await db.flush()
    db.add(models.FengyunLegionMember(legion_id=g.id, user_id=user.id))
    await log.record(db, user.id, MODULE_KEY, "legion.create", f"{g.id}:{name}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"创建军团《{name}》成功！",
                        back_href="/games/fengyun/legion", back_text="返回军团")


@router.post("/legion/join/{legion_id}")
async def legion_join(legion_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if await _my_legion_member(db, user.id):
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="已加入军团", back_href="/games/fengyun/legion", back_text="返回")
    g = await db.get(models.FengyunLegion, legion_id)
    if not g:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="军团不存在", back_href="/games/fengyun/legion", back_text="返回")
    db.add(models.FengyunLegionMember(legion_id=legion_id, user_id=user.id))
    await log.record(db, user.id, MODULE_KEY, "legion.join", str(legion_id))
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"加入军团《{g.name}》！",
                        back_href="/games/fengyun/legion", back_text="返回军团")


# ============================================================
# 称号
# ============================================================
@router.get("/titles")
async def titles_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    res = await db.execute(select(models.FengyunTitle).order_by(
        models.FengyunTitle.title_type, models.FengyunTitle.grade))
    all_titles = list(res.scalars().all())
    grouped = {"prefix": [], "suffix": [], "pair": []}
    for t in all_titles:
        grouped.setdefault(t.title_type, []).append(t)
    await db.commit()
    return await render(request, "fengyun/titles.html", db, user=user, st=st,
                        grouped=grouped, pair_rules=FY.TITLE_PAIR_RULES)


# ============================================================
# 成就
# ============================================================
@router.get("/achievements")
async def achievements_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    res = await db.execute(select(models.FengyunAchievement).order_by(
        models.FengyunAchievement.difficulty, models.FengyunAchievement.category))
    all_achv = list(res.scalars().all())
    grouped = {}
    for a in all_achv:
        grouped.setdefault(a.difficulty, []).append(a)
    await db.commit()
    return await render(request, "fengyun/achievements.html", db, user=user, st=st,
                        grouped=grouped)


# ============================================================
# 演武系统
# ============================================================
@router.get("/training")
async def training_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    now = datetime.utcnow()
    seconds_left = 0
    ready = False
    if st.training_end_at:
        if now >= st.training_end_at:
            ready = True
        else:
            seconds_left = int((st.training_end_at - now).total_seconds())
    is_monday = now.weekday() == 0
    exp_yield = TRAINING_EXP_PER_HOUR * FY.TRAINING_MAX_HOURS
    silver_yield = TRAINING_SILVER_PER_HOUR * FY.TRAINING_MAX_HOURS
    if is_monday:
        exp_yield *= FY.TRAINING_MONDAY_MULT
    await db.commit()
    return await render(request, "fengyun/training.html", db, user=user, st=st,
                        ready=ready, seconds_left=seconds_left, is_monday=is_monday,
                        exp_yield=exp_yield, silver_yield=silver_yield,
                        max_hours=FY.TRAINING_MAX_HOURS)


@router.post("/training/start")
async def training_start(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    now = datetime.utcnow()
    if st.training_end_at and now < st.training_end_at:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="演武进行中，请等待结束",
                            back_href="/games/fengyun/training", back_text="返回演武")
    st.training_end_at = now + timedelta(hours=FY.TRAINING_MAX_HOURS)
    await log.record(db, user.id, MODULE_KEY, "training.start", "")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"开始演武，{FY.TRAINING_MAX_HOURS}小时后可领取收益",
                        back_href="/games/fengyun/training", back_text="返回演武")


@router.post("/training/claim")
async def training_claim(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    now = datetime.utcnow()
    if not st.training_end_at or now < st.training_end_at:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="演武尚未结束，暂不可领取",
                            back_href="/games/fengyun/training", back_text="返回演武")
    is_monday = now.weekday() == 0
    exp_yield = TRAINING_EXP_PER_HOUR * FY.TRAINING_MAX_HOURS
    silver_yield = TRAINING_SILVER_PER_HOUR * FY.TRAINING_MAX_HOURS
    bonus = ""
    if is_monday:
        exp_yield *= FY.TRAINING_MONDAY_MULT
        bonus = "（周一10倍经验加成）"
    leveled = add_exp(st, exp_yield)
    st.silver += silver_yield
    st.training_end_at = None
    await _notify_milestones(db, user.id, st)
    await log.record(db, user.id, MODULE_KEY, "training.claim", f"exp={exp_yield},silver={silver_yield}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"领取演武收益：经验+{exp_yield}，银两+{silver_yield}{bonus}"
                            f"{'，升级了！' if leveled else ''}",
                        back_href="/games/fengyun/training", back_text="返回演武")


# ============================================================
# 规则页
# ============================================================
@router.get("/rules")
async def rules(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return await render(request, "fengyun/rules.html", db, user=user)
