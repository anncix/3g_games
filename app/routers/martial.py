"""精武堂模块（v0.1.0）

老味道点：人物养成 / 修炼挂机 / 加点流派 / 装备强化 / 比武对抗 / 帮派社交
核心循环：修炼/任务 → 获得经验资源 → 升级加点 → 换装强化 → 比武/挑战 → 继续养成

口径：怀旧 / 旧逻辑 / WAP 层级页 / 可复刻落地。
排行/商城/背包/消息 走平台公共系统（events.emit 上报 + 链接跳转）。
"""
import json
import random
from datetime import datetime, date

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from ..platform import goods, events, log
from .views import render
from . import martial_data as D

router = APIRouter(prefix="/games/martial")
MODULE_KEY = "martial"


# ============================================================
# 辅助函数
# ============================================================
async def get_state(db: AsyncSession, user_id: int) -> models.MartialState:
    st = await db.get(models.MartialState, user_id)
    if not st:
        st = models.MartialState(user_id=user_id)
        db.add(st)
        await db.commit()
        await db.refresh(st)
    return st


def reset_daily(st: models.MartialState):
    """日限重置：比武次数/日常计数/日常任务/活跃"""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if st.daily_log_date != today:
        st.daily_log_date = today
        st.daily_counters = "{}"
        st.daily_tasks = "{}"
        st.daily_activity = "{}"
        st.daily_activity_point = 0


def get_json(st: models.MartialState, field: str) -> dict:
    try:
        return json.loads(getattr(st, field) or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def set_json(st: models.MartialState, field: str, data: dict):
    setattr(st, field, json.dumps(data, ensure_ascii=False))


def incr_counter(st: models.MartialState, metric: str, amount: int = 1):
    counters = get_json(st, "daily_counters")
    counters[metric] = counters.get(metric, 0) + amount
    set_json(st, "daily_counters", counters)


def get_counter(st: models.MartialState, metric: str) -> int:
    return get_json(st, "daily_counters").get(metric, 0)


async def get_learned_skills(db: AsyncSession, user_id: int) -> dict:
    """返回 {skill_id: level}"""
    res = await db.execute(select(models.MartialSkill).where(
        models.MartialSkill.user_id == user_id))
    return {s.skill_id: s.level for s in res.scalars().all()}


async def get_equipped(db: AsyncSession, user_id: int) -> list[models.MartialEquip]:
    res = await db.execute(select(models.MartialEquip).where(
        models.MartialEquip.user_id == user_id, models.MartialEquip.equipped.is_(True)))
    return list(res.scalars().all())


async def get_all_equips(db: AsyncSession, user_id: int) -> list[models.MartialEquip]:
    res = await db.execute(select(models.MartialEquip).where(
        models.MartialEquip.user_id == user_id).order_by(models.MartialEquip.created_at.desc()))
    return list(res.scalars().all())


def compute_player(st: models.MartialState, equipped: list, learned: dict) -> dict:
    """计算玩家完整属性与战力"""
    attrs = {k: getattr(st, k) for k in D.ATTR_KEYS}
    equip_bonus = {}
    for e in equipped:
        for k, v in D.equip_total_stats(e).items():
            equip_bonus[k] = equip_bonus.get(k, 0) + v
    skill_bonus = {}
    for sid, lv in learned.items():
        if sid in D.SKILLS and D.SKILLS[sid][2] == "passive":
            for k, v in D.skill_passive_bonus(sid, lv).items():
                skill_bonus[k] = skill_bonus.get(k, 0) + v
    stats = D.calc_stats(st.level, attrs, equip_bonus, skill_bonus)
    skill_score = D.skill_total_score(learned)
    equip_score = D.equip_total_score(equipped)
    power = D.calc_power(stats, skill_score, equip_score)
    return {"attrs": attrs, "stats": stats, "power": power,
            "skill_score": skill_score, "equip_score": equip_score}


def add_exp(st: models.MartialState, amount: int) -> bool:
    """加经验，返回是否升级"""
    if st.level >= D.MAX_LEVEL:
        st.exp = 0
        return False
    st.exp += amount
    leveled = False
    while st.level < D.MAX_LEVEL:
        need = D.exp_needed(st.level)
        if st.exp >= need:
            st.exp -= need
            st.level += 1
            st.attr_points += D.ATTR_PER_LEVEL
            leveled = True
        else:
            break
    return leveled


def active_skill_of(learned: dict):
    """取已学最高阶主动技能"""
    for sid in ("SKM_04", "SKM_03", "SKM_02", "SKM_01"):
        if sid in learned:
            return (sid, learned[sid])
    return None


def task_progress(st: models.MartialState, target_type: str) -> int:
    """某日常任务当前进度"""
    return get_counter(st, target_type)


def task_claimed(st: models.MartialState, task_id: str) -> bool:
    return task_id in get_json(st, "daily_tasks")


def claim_task(st: models.MartialState, task_id: str):
    tasks = get_json(st, "daily_tasks")
    tasks[task_id] = 1
    set_json(st, "daily_tasks", tasks)


# ============================================================
# 首页
# ============================================================
@router.get("")
async def martial_home(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    equipped = await get_equipped(db, user.id)
    learned = await get_learned_skills(db, user.id)
    player = compute_player(st, equipped, learned)
    # 修炼可领收益
    now = datetime.utcnow()
    seconds = int((now - st.cultivate_started_at).total_seconds())
    exp_y, silver_y = D.cultivate_yield(seconds, st.cultivate_biguan)
    # 今日待办摘要
    todo = []
    if exp_y > 0 or silver_y > 0:
        todo.append(("修炼收益待领取", f"+{exp_y}经验 +{silver_y}银两", "/games/martial/cultivate"))
    if st.attr_points > 0:
        todo.append(("可分配属性点", f"{st.attr_points} 点", "/games/martial/attrs"))
    arena_used = get_counter(st, "pvp_arena_try")
    if arena_used < D.ARENA_DAILY_FREE:
        todo.append(("比武场", f"剩{D.ARENA_DAILY_FREE - arena_used}次", "/games/martial/arena"))
    pve_used = get_counter(st, "pve_normal_win")
    if pve_used < D.PVE_DAILY_ATTEMPT:
        todo.append(("挑战关卡", f"剩{D.PVE_DAILY_ATTEMPT - pve_used}次", "/games/martial/challenge"))
    # 日常任务可领数
    claimable = 0
    for tid, t in D.DAILY_TASKS.items():
        if task_claimed(st, tid):
            continue
        if st.level < t[1]:
            continue
        if task_progress(st, t[2]) >= t[3]:
            claimable += 1
    if claimable:
        todo.append(("日常任务", f"{claimable}个可领", "/games/martial/tasks"))
    await db.commit()
    return await render(request, "martial/home.html", db, user=user, st=st,
                        player=player, exp_y=exp_y, silver_y=silver_y, todo=todo,
                        claimable=claimable, exp_need=D.exp_needed(st.level))


# ============================================================
# 修炼系统
# ============================================================
@router.get("/cultivate")
async def cultivate_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    now = datetime.utcnow()
    seconds = int((now - st.cultivate_started_at).total_seconds())
    exp_y, silver_y = D.cultivate_yield(seconds, st.cultivate_biguan)
    biguan_used = get_counter(st, "cultivate_biguan")
    await db.commit()
    return await render(request, "martial/cultivate.html", db, user=user, st=st,
                        seconds=seconds, exp_y=exp_y, silver_y=silver_y,
                        biguan_used=biguan_used, exp_need=D.exp_needed(st.level))


@router.post("/cultivate/claim")
async def cultivate_claim(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    now = datetime.utcnow()
    seconds = int((now - st.cultivate_started_at).total_seconds())
    exp_y, silver_y = D.cultivate_yield(seconds, st.cultivate_biguan)
    if exp_y <= 0 and silver_y <= 0:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="暂无可领取的修炼收益", back_href="/games/martial/cultivate", back_text="返回")
    add_exp(st, exp_y)
    st.silver += silver_y
    st.cultivate_started_at = now
    incr_counter(st, "cultivate_claim")
    await log.record(db, user.id, MODULE_KEY, "cultivate.claim", f"exp={exp_y},silver={silver_y}")
    await events.emit(db, user.id, MODULE_KEY, "cultivate_claim", {"exp": exp_y, "silver": silver_y})
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"领取修炼收益：经验+{exp_y}，银两+{silver_y}",
                        back_href="/games/martial/cultivate", back_text="返回修炼")


@router.post("/cultivate/biguan")
async def cultivate_biguan(request: Request, db: AsyncSession = Depends(get_db)):
    """进入/切换闭关（消耗荣誉 + 次数限制）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    biguan_used = get_counter(st, "cultivate_biguan")
    if biguan_used >= D.BIGUAN_DAILY_LIMIT:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"今日闭关次数已用完（{D.BIGUAN_DAILY_LIMIT}次）",
                            back_href="/games/martial/cultivate", back_text="返回")
    if st.honor < D.BIGUAN_COST_HONOR:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"荣誉不足（需{D.BIGUAN_COST_HONOR}）",
                            back_href="/games/martial/cultivate", back_text="返回")
    st.honor -= D.BIGUAN_COST_HONOR
    st.cultivate_biguan = True
    st.cultivate_started_at = datetime.utcnow()
    incr_counter(st, "cultivate_biguan")
    await log.record(db, user.id, MODULE_KEY, "cultivate.biguan", "start")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"进入闭关修炼（经验×{D.BIGUAN_EXP_MUL}，银两×{D.BIGUAN_SILVER_MUL}）",
                        back_href="/games/martial/cultivate", back_text="返回修炼")


@router.post("/cultivate/normal")
async def cultivate_normal(request: Request, db: AsyncSession = Depends(get_db)):
    """切回普通修炼"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    st.cultivate_biguan = False
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg="已切换为普通修炼", back_href="/games/martial/cultivate", back_text="返回修炼")


# ============================================================
# 加点系统
# ============================================================
@router.get("/attrs")
async def attrs_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    equipped = await get_equipped(db, user.id)
    learned = await get_learned_skills(db, user.id)
    player = compute_player(st, equipped, learned)
    return await render(request, "martial/attrs.html", db, user=user, st=st,
                        player=player, exp_need=D.exp_needed(st.level))


@router.post("/attr/add/{attr}")
async def attr_add(attr: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if attr not in D.ATTR_KEYS:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="属性非法", back_href="/games/martial/attrs", back_text="返回")
    if st.attr_points <= 0:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="无可分配属性点", back_href="/games/martial/attrs", back_text="返回")
    setattr(st, attr, getattr(st, attr) + 1)
    st.attr_points -= 1
    incr_counter(st, "attr_add")
    await log.record(db, user.id, MODULE_KEY, "attr.add", f"{attr}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"{D.ATTR_NAMES[attr]}+1（剩余{st.attr_points}点）",
                        back_href="/games/martial/attrs", back_text="返回加点")


@router.post("/attr/reset")
async def attr_reset(request: Request, db: AsyncSession = Depends(get_db)):
    """洗点：消耗银两，归还全部已分配点数"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if st.silver < D.RESET_COST_SILVER:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"银两不足（需{D.RESET_COST_SILVER}）",
                            back_href="/games/martial/attrs", back_text="返回")
    allocated = sum(getattr(st, k) - 5 for k in D.ATTR_KEYS)
    if allocated <= 0:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="无已分配点数可洗", back_href="/games/martial/attrs", back_text="返回")
    st.silver -= D.RESET_COST_SILVER
    for k in D.ATTR_KEYS:
        setattr(st, k, 5)
    st.attr_points += allocated
    await log.record(db, user.id, MODULE_KEY, "attr.reset", f"refund={allocated}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"洗点成功，归还 {allocated} 点（消耗银两{D.RESET_COST_SILVER}）",
                        back_href="/games/martial/attrs", back_text="返回加点")


# ============================================================
# 技能系统
# ============================================================
@router.get("/skills")
async def skills_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    learned = await get_learned_skills(db, user.id)
    skill_list = []
    for sid, info in D.SKILLS.items():
        skill_list.append({
            "id": sid, "name": info[0], "school": info[1], "type": info[2],
            "coef": info[3], "unlock_level": info[4], "learn_cost": info[5],
            "upgrade_cost": info[6], "desc": info[7],
            "level": learned.get(sid, 0),
        })
    return await render(request, "martial/skills.html", db, user=user, st=st,
                        skill_list=skill_list, learned=learned, exp_need=D.exp_needed(st.level))


@router.post("/skill/learn/{sid}")
async def skill_learn(sid: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if sid not in D.SKILLS:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="技能不存在", back_href="/games/martial/skills", back_text="返回")
    info = D.SKILLS[sid]
    if st.level < info[4]:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"等级不足，需{info[4]}级", back_href="/games/martial/skills", back_text="返回")
    learned = await get_learned_skills(db, user.id)
    if sid in learned:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="已学习该技能", back_href="/games/martial/skills", back_text="返回")
    cost = info[5]
    if st.silver < cost:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"银两不足（需{cost}）", back_href="/games/martial/skills", back_text="返回")
    st.silver -= cost
    db.add(models.MartialSkill(user_id=user.id, skill_id=sid, level=1))
    await log.record(db, user.id, MODULE_KEY, "skill.learn", sid)
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"学会《{info[0]}》", back_href="/games/martial/skills", back_text="返回技能")


@router.post("/skill/upgrade/{sid}")
async def skill_upgrade(sid: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    res = await db.execute(select(models.MartialSkill).where(
        models.MartialSkill.user_id == user.id, models.MartialSkill.skill_id == sid))
    sk = res.scalar_one_or_none()
    if not sk:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="未学习该技能", back_href="/games/martial/skills", back_text="返回")
    if sk.level >= D.SKILL_MAX_LEVEL:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="技能已满级", back_href="/games/martial/skills", back_text="返回")
    info = D.SKILLS[sid]
    cost = info[6]
    if st.silver < cost:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"银两不足（需{cost}）", back_href="/games/martial/skills", back_text="返回")
    st.silver -= cost
    sk.level += 1
    await log.record(db, user.id, MODULE_KEY, "skill.upgrade", f"{sid}:{sk.level}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"《{info[0]}》升至 {sk.level} 级",
                        back_href="/games/martial/skills", back_text="返回技能")


# ============================================================
# 装备系统
# ============================================================
@router.get("/equip")
async def equip_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    all_equips = await get_all_equips(db, user.id)
    equipped = [e for e in all_equips if e.equipped]
    bag_equips = [e for e in all_equips if not e.equipped]
    # 按部位整理穿戴槽位
    slot_map = {s: None for s in D.EQUIP_SLOTS}
    for e in equipped:
        slot_map[e.slot] = e
    player = compute_player(st, equipped, await get_learned_skills(db, user.id))
    return await render(request, "martial/equip.html", db, user=user, st=st,
                        slot_map=slot_map, bag_equips=bag_equips, player=player,
                        slot_names=D.EQUIP_SLOT_NAMES, quality_names=D.EQUIP_QUALITY_NAMES,
                        exp_need=D.exp_needed(st.level))


@router.post("/equip/wear/{equip_id}")
async def equip_wear(equip_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    e = await db.get(models.MartialEquip, equip_id)
    if not e or e.user_id != user.id:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="装备不存在", back_href="/games/martial/equip", back_text="返回")
    # 卸下同部位已穿戴
    res = await db.execute(select(models.MartialEquip).where(
        models.MartialEquip.user_id == user.id,
        models.MartialEquip.slot == e.slot,
        models.MartialEquip.equipped.is_(True)))
    for old in res.scalars().all():
        old.equipped = False
    e.equipped = True
    await log.record(db, user.id, MODULE_KEY, "equip.wear", f"{e.slot}:{e.id}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"已穿戴 {D.EQUIP_SLOT_NAMES.get(e.slot, e.slot)}",
                        back_href="/games/martial/equip", back_text="返回装备")


@router.post("/equip/unequip/{equip_id}")
async def equip_unequip(equip_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    e = await db.get(models.MartialEquip, equip_id)
    if not e or e.user_id != user.id:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="装备不存在", back_href="/games/martial/equip", back_text="返回")
    e.equipped = False
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg="已卸下", back_href="/games/martial/equip", back_text="返回装备")


@router.post("/equip/strengthen/{equip_id}")
async def equip_strengthen(equip_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    e = await db.get(models.MartialEquip, equip_id)
    if not e or e.user_id != user.id:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="装备不存在", back_href="/games/martial/equip", back_text="返回")
    next_lv = e.strengthen + 1
    if next_lv > D.STRENGTHEN_MAX:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="已达强化上限", back_href="/games/martial/equip", back_text="返回")
    silver_cost, stone_cost, success_rate, _ = D.STRENGTHEN_TABLE[next_lv]
    if st.silver < silver_cost:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"银两不足（需{silver_cost}）", back_href="/games/martial/equip", back_text="返回")
    stone_have = await goods.count_item(db, user.id, "MT_STRENGTH_STONE", MODULE_KEY)
    if stone_have < stone_cost:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"强化石不足（需{stone_cost}）", back_href="/games/martial/equip", back_text="返回")
    st.silver -= silver_cost
    await goods.remove_item(db, user.id, "MT_STRENGTH_STONE", MODULE_KEY, stone_cost)
    incr_counter(st, "equip_strengthen")
    ok = random.random() < success_rate
    if ok:
        e.strengthen = next_lv
        msg = f"强化成功！+{next_lv}级"
    else:
        msg = f"强化失败（消耗已扣），成功率{int(success_rate*100)}%"
    await log.record(db, user.id, MODULE_KEY, "equip.strengthen", f"{e.id}:{next_lv}:{'ok' if ok else 'fail'}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=ok,
                        msg=msg, back_href="/games/martial/equip", back_text="返回装备")


@router.post("/equip/craft/{slot}")
async def equip_craft(slot: str, request: Request, db: AsyncSession = Depends(get_db)):
    """打造装备：消耗材料生成一件随机品质装备"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if slot not in D.EQUIP_SLOTS:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="部位非法", back_href="/games/martial/equip", back_text="返回")
    if st.level < 12:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="打造需12级开启", back_href="/games/martial/equip", back_text="返回")
    # 消耗：3 玄铁精华 + 500 银两
    need_iron = 3
    need_silver = 500
    iron_have = await goods.count_item(db, user.id, "MT_IRON_ESSENCE", MODULE_KEY)
    if iron_have < need_iron:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"玄铁精华不足（需{need_iron}）", back_href="/games/martial/equip", back_text="返回")
    if st.silver < need_silver:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"银两不足（需{need_silver}）", back_href="/games/martial/equip", back_text="返回")
    await goods.remove_item(db, user.id, "MT_IRON_ESSENCE", MODULE_KEY, need_iron)
    st.silver -= need_silver
    incr_counter(st, "equip_craft")
    # 随机品质（偏向低品质）
    quality = random.choices(D.EQUIP_QUALITIES, weights=[50, 30, 15, 4, 1])[0]
    stats = D.gen_equip_stats(slot, quality)
    e = models.MartialEquip(user_id=user.id, slot=slot, quality=quality, strengthen=0,
                            stats=json.dumps(stats), equipped=False)
    db.add(e)
    await log.record(db, user.id, MODULE_KEY, "equip.craft", f"{slot}:{quality}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"打造出 {D.EQUIP_QUALITY_NAMES[quality]}品质 {D.EQUIP_SLOT_NAMES[slot]}！",
                        back_href="/games/martial/equip", back_text="返回装备")


# ============================================================
# 比武场（PVP）
# ============================================================
@router.get("/arena")
async def arena_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    arena_used = get_counter(st, "pvp_arena_try")
    # 取若干其他玩家作为对手（按战力近似）
    other_states = (await db.execute(
        select(models.MartialState).where(models.MartialState.user_id != user.id).limit(8)
    )).scalars().all()
    opponents = []
    for os in other_states:
        oquipped = await get_equipped(db, os.user_id)
        olearned = await get_learned_skills(db, os.user_id)
        oplayer = compute_player(os, oquipped, olearned)
        ou = await db.get(models.User, os.user_id)
        opponents.append({"st": os, "user": ou, "player": oplayer})
    # 若无其他玩家，生成一个 NPC 对手
    if not opponents:
        npc = models.MartialState(user_id=0, level=max(1, st.level),
                                  arena_score=st.arena_score,
                                  strength=5, agility=5, physique=5, inner_power=5)
        npc_player = compute_player(npc, [], {})
        opponents.append({"st": npc, "user": None, "player": npc_player})
    await db.commit()
    return await render(request, "martial/arena.html", db, user=user, st=st,
                        opponents=opponents, arena_used=arena_used,
                        exp_need=D.exp_needed(st.level))


@router.post("/arena/challenge/{target_id}")
async def arena_challenge(target_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    arena_used = get_counter(st, "pvp_arena_try")
    if arena_used >= D.ARENA_DAILY_FREE:
        # 尝试用荣誉买额外次数
        if st.honor < D.ARENA_EXTRA_COST_HONOR:
            return await render(request, "result.html", db, user=user, ok=False,
                                msg=f"今日免费次数已用完，额外需{D.ARENA_EXTRA_COST_HONOR}荣誉",
                                back_href="/games/martial/arena", back_text="返回")
        st.honor -= D.ARENA_EXTRA_COST_HONOR
    # 获取对手
    if target_id == 0:
        target_st = models.MartialState(user_id=0, level=max(1, st.level),
                                        arena_score=st.arena_score,
                                        strength=5, agility=5, physique=5, inner_power=5)
        target_player = compute_player(target_st, [], {})
        target_user = None
    else:
        target_st = await db.get(models.MartialState, target_id)
        if not target_st:
            return await render(request, "result.html", db, user=user, ok=False,
                                msg="对手不存在", back_href="/games/martial/arena", back_text="返回")
        target_player = compute_player(target_st, await get_equipped(db, target_id),
                                       await get_learned_skills(db, target_id))
        target_user = await db.get(models.User, target_id)
    # 战斗
    equipped = await get_equipped(db, user.id)
    learned = await get_learned_skills(db, user.id)
    my_player = compute_player(st, equipped, learned)
    result = D.auto_battle(my_player["stats"], st.level, active_skill_of(learned),
                           target_player["stats"], target_st.level)
    incr_counter(st, "pvp_arena_try")
    if result["win"]:
        st.arena_score += D.ARENA_WIN_SCORE
        st.honor += D.ARENA_WIN_HONOR
        st.arena_wins += 1
        incr_counter(st, "pvp_arena_win")
        score_delta = D.ARENA_WIN_SCORE
        honor_gain = D.ARENA_WIN_HONOR
    else:
        st.arena_score = max(0, st.arena_score + D.ARENA_LOSS_SCORE)
        st.honor += D.ARENA_LOSS_HONOR
        score_delta = D.ARENA_LOSS_SCORE
        honor_gain = D.ARENA_LOSS_HONOR
    # 记录战报
    blog = models.MartialArenaLog(attacker_id=user.id, defender_id=target_id,
                                  win=result["win"], score_delta=score_delta,
                                  battle_log=json.dumps(result["log"][:30]))
    db.add(blog)
    # 对手若是真实玩家，扣其分
    if target_id != 0 and target_st:
        if result["win"]:
            target_st.arena_score = max(0, target_st.arena_score - D.ARENA_WIN_SCORE)
        else:
            target_st.arena_score += D.ARENA_WIN_SCORE // 2
        await events.emit(db, target_id, MODULE_KEY, "arena_attacked",
                          {"by": user.id, "win": result["win"]})
    await events.emit(db, user.id, MODULE_KEY, "pvp_result",
                      {"win": result["win"], "score_delta": score_delta})
    await log.record(db, user.id, MODULE_KEY, "pvp.challenge", f"{target_id}:{'win' if result['win'] else 'loss'}")
    await db.commit()
    tname = target_user.nickname if target_user else "武林新秀(NPC)"
    return await render(request, "martial/arena_result.html", db, user=user, st=st,
                        win=result["win"], tname=tname, battle_log=result["log"][:30],
                        score_delta=score_delta, honor_gain=honor_gain,
                        my_hp=result["atk_hp_left"], enemy_hp=result["def_hp_left"],
                        my_player=my_player, target_player=target_player)


# ============================================================
# PVE 挑战
# ============================================================
@router.get("/challenge")
async def challenge_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    pve_used = get_counter(st, "pve_normal_win")
    # 已通关记录
    res = await db.execute(select(models.MartialStageLog).where(
        models.MartialStageLog.user_id == user.id, models.MartialStageLog.cleared.is_(True)))
    cleared = {r.stage_id for r in res.scalars().all()}
    stages = []
    for sid, info in D.PVE_STAGES.items():
        stages.append({"id": sid, "name": info[0], "req_level": info[1],
                       "silver": info[3], "exp": info[4], "cleared": sid in cleared,
                       "can": st.level >= info[1]})
    await db.commit()
    return await render(request, "martial/challenge.html", db, user=user, st=st,
                        stages=stages, pve_used=pve_used, exp_need=D.exp_needed(st.level))


@router.post("/challenge/{stage_id}")
async def challenge_battle(stage_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    if stage_id not in D.PVE_STAGES:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="关卡不存在", back_href="/games/martial/challenge", back_text="返回")
    info = D.PVE_STAGES[stage_id]
    if st.level < info[1]:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"等级不足，需{info[1]}级", back_href="/games/martial/challenge", back_text="返回")
    pve_used = get_counter(st, "pve_normal_win")
    if pve_used >= D.PVE_DAILY_ATTEMPT:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"今日挑战次数已用完（{D.PVE_DAILY_ATTEMPT}次）",
                            back_href="/games/martial/challenge", back_text="返回")
    # 战斗
    equipped = await get_equipped(db, user.id)
    learned = await get_learned_skills(db, user.id)
    my_player = compute_player(st, equipped, learned)
    enemy_stats = D.make_enemy(stage_id, st.level)
    result = D.auto_battle(my_player["stats"], st.level, active_skill_of(learned),
                           enemy_stats, st.level)
    if result["win"]:
        st.silver += info[3]
        leveled = add_exp(st, info[4])
        incr_counter(st, "pve_normal_win")
        # 精英关（S03+）计 elite
        if info[1] >= 10:
            incr_counter(st, "pve_elite_win")
        # 高级关计 boss
        if info[1] >= 25:
            incr_counter(st, "boss_try")
        # 掉落
        drop_item, drop_qty, drop_rate = info[5], info[6], info[7]
        dropped = random.random() < drop_rate
        if dropped and drop_item:
            await goods.add_item(db, user.id, drop_item, MODULE_KEY, drop_qty)
        # 通关记录
        existing = (await db.execute(select(models.MartialStageLog).where(
            models.MartialStageLog.user_id == user.id,
            models.MartialStageLog.stage_id == stage_id))).scalar_one_or_none()
        if not existing:
            db.add(models.MartialStageLog(user_id=user.id, stage_id=stage_id, cleared=True))
        elif not existing.cleared:
            existing.cleared = True
        await log.record(db, user.id, MODULE_KEY, "pve.win", f"{stage_id}")
        await db.commit()
        return await render(request, "martial/challenge_result.html", db, user=user, st=st,
                            win=True, stage_name=info[0], silver=info[3], exp=info[4],
                            leveled=leveled, dropped=dropped, drop_item=drop_item,
                            drop_qty=drop_qty, battle_log=result["log"][:20],
                            my_hp=result["atk_hp_left"], enemy_hp=result["def_hp_left"])
    else:
        incr_counter(st, "pve_normal_win")
        await log.record(db, user.id, MODULE_KEY, "pve.loss", stage_id)
        await db.commit()
        return await render(request, "martial/challenge_result.html", db, user=user, st=st,
                            win=False, stage_name=info[0], silver=0, exp=0,
                            leveled=False, dropped=False, drop_item="", drop_qty=0,
                            battle_log=result["log"][:20],
                            my_hp=result["atk_hp_left"], enemy_hp=result["def_hp_left"])


# ============================================================
# 日常任务 + 活跃奖励
# ============================================================
@router.get("/tasks")
async def tasks_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    task_list = []
    for tid, t in D.DAILY_TASKS.items():
        progress = task_progress(st, t[2])
        task_list.append({
            "id": tid, "name": t[0], "open_level": t[1], "target": t[3],
            "progress": min(progress, t[3]), "silver": t[4], "exp": t[5],
            "item1": t[6], "qty1": t[7], "item2": t[8], "qty2": t[9],
            "point": t[10], "claimed": task_claimed(st, tid),
            "can_claim": st.level >= t[1] and progress >= t[3] and not task_claimed(st, tid),
        })
    activity_rewards = []
    claimed_activity = get_json(st, "daily_activity")
    for point, r in D.DAILY_ACTIVITY_REWARDS.items():
        activity_rewards.append({
            "point": point, "silver": r[0], "exp": r[1],
            "item1": r[2], "qty1": r[3], "item2": r[4], "qty2": r[5],
            "claimed": point in claimed_activity,
            "can_claim": st.daily_activity_point >= point and point not in claimed_activity,
        })
    await db.commit()
    return await render(request, "martial/tasks.html", db, user=user, st=st,
                        task_list=task_list, activity_rewards=activity_rewards,
                        exp_need=D.exp_needed(st.level))


@router.post("/tasks/claim/{tid}")
async def task_claim(tid: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    if tid not in D.DAILY_TASKS:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="任务不存在", back_href="/games/martial/tasks", back_text="返回")
    t = D.DAILY_TASKS[tid]
    if task_claimed(st, tid):
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="已领取过", back_href="/games/martial/tasks", back_text="返回")
    if st.level < t[1]:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"等级不足，需{t[1]}级", back_href="/games/martial/tasks", back_text="返回")
    if task_progress(st, t[2]) < t[3]:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="任务未完成", back_href="/games/martial/tasks", back_text="返回")
    # 发奖
    st.silver += t[4]
    leveled = add_exp(st, t[5])
    if t[6] and t[7]:
        await goods.add_item(db, user.id, t[6], MODULE_KEY, t[7])
    if t[8] and t[9]:
        await goods.add_item(db, user.id, t[8], MODULE_KEY, t[9])
    claim_task(st, tid)
    st.daily_activity_point += t[10]
    await log.record(db, user.id, MODULE_KEY, "task.claim", tid)
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"领取任务奖励：银两+{t[4]}，经验+{t[5]}{'，升级了！' if leveled else ''}",
                        back_href="/games/martial/tasks", back_text="返回任务")


@router.post("/activity/claim/{point}")
async def activity_claim(point: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    if point not in D.DAILY_ACTIVITY_REWARDS:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="档位不存在", back_href="/games/martial/tasks", back_text="返回")
    claimed_activity = get_json(st, "daily_activity")
    if point in claimed_activity:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="已领取过", back_href="/games/martial/tasks", back_text="返回")
    if st.daily_activity_point < point:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"活跃度不足（需{point}）", back_href="/games/martial/tasks", back_text="返回")
    r = D.DAILY_ACTIVITY_REWARDS[point]
    st.silver += r[0]
    leveled = add_exp(st, r[1])
    if r[2] and r[3]:
        await goods.add_item(db, user.id, r[2], MODULE_KEY, r[3])
    if r[4] and r[5]:
        await goods.add_item(db, user.id, r[4], MODULE_KEY, r[5])
    claimed_activity[point] = 1
    set_json(st, "daily_activity", claimed_activity)
    await log.record(db, user.id, MODULE_KEY, "activity.claim", str(point))
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"领取活跃奖励：银两+{r[0]}，经验+{r[1]}{'，升级了！' if leveled else ''}",
                        back_href="/games/martial/tasks", back_text="返回任务")


# ============================================================
# 帮派（门派）
# ============================================================
@router.get("/guild")
async def guild_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    my_guild = None
    members = []
    if st.guild_id:
        my_guild = await db.get(models.MartialGuild, st.guild_id)
        if my_guild:
            res = await db.execute(select(models.MartialGuildMember).where(
                models.MartialGuildMember.guild_id == my_guild.id))
            member_rows = res.scalars().all()
            for m in member_rows:
                mu = await db.get(models.User, m.user_id)
                ms = await db.get(models.MartialState, m.user_id)
                members.append({"member": m, "user": mu, "state": ms})
    # 推荐帮派列表
    res = await db.execute(select(models.MartialGuild).limit(10))
    guild_list = res.scalars().all()
    donate_used = get_counter(st, "guild_donate")
    await db.commit()
    return await render(request, "martial/guild.html", db, user=user, st=st,
                        my_guild=my_guild, members=members, guild_list=guild_list,
                        donate_used=donate_used, donate_limit=D.GUILD_DONATE_DAILY_LIMIT,
                        guild_shop=D.GUILD_SHOP, exp_need=D.exp_needed(st.level))


@router.post("/guild/create")
async def guild_create(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if st.guild_id:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="已加入帮派，无法创建", back_href="/games/martial/guild", back_text="返回")
    form = await request.form()
    name = (form.get("name") or "").strip()
    if not name or len(name) > 16:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="帮派名非法（1-16字）", back_href="/games/martial/guild", back_text="返回")
    if st.silver < D.GUILD_CREATE_COST_SILVER:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"银两不足（需{D.GUILD_CREATE_COST_SILVER}）",
                            back_href="/games/martial/guild", back_text="返回")
    exists = (await db.execute(select(models.MartialGuild).where(
        models.MartialGuild.name == name))).scalar_one_or_none()
    if exists:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="帮派名已存在", back_href="/games/martial/guild", back_text="返回")
    st.silver -= D.GUILD_CREATE_COST_SILVER
    g = models.MartialGuild(name=name, leader_id=user.id)
    db.add(g)
    await db.flush()
    db.add(models.MartialGuildMember(guild_id=g.id, user_id=user.id))
    st.guild_id = g.id
    await log.record(db, user.id, MODULE_KEY, "guild.create", f"{g.id}:{name}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"创建帮派《{name}》成功！",
                        back_href="/games/martial/guild", back_text="返回帮派")


@router.post("/guild/join/{guild_id}")
async def guild_join(guild_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if st.guild_id:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="已加入帮派", back_href="/games/martial/guild", back_text="返回")
    g = await db.get(models.MartialGuild, guild_id)
    if not g:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="帮派不存在", back_href="/games/martial/guild", back_text="返回")
    db.add(models.MartialGuildMember(guild_id=guild_id, user_id=user.id))
    st.guild_id = guild_id
    await log.record(db, user.id, MODULE_KEY, "guild.join", str(guild_id))
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"加入帮派《{g.name}》！",
                        back_href="/games/martial/guild", back_text="返回帮派")


@router.post("/guild/leave")
async def guild_leave(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if not st.guild_id:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="未加入帮派", back_href="/games/martial/guild", back_text="返回")
    g = await db.get(models.MartialGuild, st.guild_id)
    res = await db.execute(select(models.MartialGuildMember).where(
        models.MartialGuildMember.guild_id == st.guild_id,
        models.MartialGuildMember.user_id == user.id))
    m = res.scalar_one_or_none()
    if m:
        await db.delete(m)
    # 帮主退出则解散
    if g and g.leader_id == user.id:
        await db.delete(g)
        st.guild_id = 0
    else:
        st.guild_id = 0
    await log.record(db, user.id, MODULE_KEY, "guild.leave", "")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg="已退出帮派", back_href="/games/martial/guild", back_text="返回帮派")


@router.post("/guild/donate/{donate_key}")
async def guild_donate(donate_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    if not st.guild_id:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="未加入帮派", back_href="/games/martial/guild", back_text="返回")
    if donate_key not in D.GUILD_DONATE:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="捐献项非法", back_href="/games/martial/guild", back_text="返回")
    donate_used = get_counter(st, "guild_donate")
    if donate_used >= D.GUILD_DONATE_DAILY_LIMIT:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"今日捐献次数已用完（{D.GUILD_DONATE_DAILY_LIMIT}次）",
                            back_href="/games/martial/guild", back_text="返回")
    cost, contrib = D.GUILD_DONATE[donate_key]
    if donate_key.startswith("silver"):
        if st.silver < cost:
            return await render(request, "result.html", db, user=user, ok=False,
                                msg=f"银两不足（需{cost}）", back_href="/games/martial/guild", back_text="返回")
        st.silver -= cost
    else:  # honor
        if st.honor < cost:
            return await render(request, "result.html", db, user=user, ok=False,
                                msg=f"荣誉不足（需{cost}）", back_href="/games/martial/guild", back_text="返回")
        st.honor -= cost
    st.contribution += contrib
    res = await db.execute(select(models.MartialGuildMember).where(
        models.MartialGuildMember.guild_id == st.guild_id,
        models.MartialGuildMember.user_id == user.id))
    m = res.scalar_one_or_none()
    if m:
        m.contribution += contrib
    incr_counter(st, "guild_donate")
    incr_counter(st, "guild_task_finish")  # 捐献计入帮派任务完成
    await log.record(db, user.id, MODULE_KEY, "guild.donate", f"{donate_key}:{contrib}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"捐献成功，贡献+{contrib}",
                        back_href="/games/martial/guild", back_text="返回帮派")


@router.post("/guild/shop/{item_key}")
async def guild_shop_buy(item_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if not st.guild_id:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="未加入帮派", back_href="/games/martial/guild", back_text="返回")
    if item_key not in D.GUILD_SHOP:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="商品不存在", back_href="/games/martial/guild", back_text="返回")
    cost, _ = D.GUILD_SHOP[item_key]
    if st.contribution < cost:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"贡献不足（需{cost}）", back_href="/games/martial/guild", back_text="返回")
    st.contribution -= cost
    await goods.add_item(db, user.id, item_key, MODULE_KEY, 1)
    await log.record(db, user.id, MODULE_KEY, "guild.shop", item_key)
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"兑换成功：{item_key}", back_href="/games/martial/guild", back_text="返回帮派")


# ============================================================
# 规则页
# ============================================================
@router.get("/rules")
async def rules(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return await render(request, "martial/rules.html", db, user=user)
