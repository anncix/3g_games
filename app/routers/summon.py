"""召唤之王模块（v0.0.7 全量配表定版）

老味道点：图鉴收集 / 抓捕幻兽 / 回合战斗 / 种族克制 / 段位推进 / 组队成长
核心循环：进地图 → 刷关卡(遭遇战) → 抓捕幻兽 → 组队 → 升级 → 解锁高段位
"""
import json
import random
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from ..platform import goods, events, log
from .views import render
from . import summon_data as D

router = APIRouter(prefix="/games/summon", tags=["召唤之王"])
MODULE_KEY = "summon"


# ============================================================
# 辅助函数
# ============================================================
async def get_state(db: AsyncSession, user_id: int) -> models.SummonState:
    st = await db.get(models.SummonState, user_id)
    if not st:
        st = models.SummonState(user_id=user_id, last_battle_at=datetime.utcnow() - timedelta(seconds=9999))
        db.add(st)
        await db.commit()
        await db.refresh(st)
    return st


async def refresh_energy(st: models.SummonState):
    """按时间恢复活力（每5分钟+1，上限120）"""
    now = datetime.utcnow()
    elapsed = (now - st.energy_updated_at).total_seconds()
    gained = int(elapsed // 300)
    if gained > 0:
        st.energy = min(D.ENERGY_CAP, st.energy + gained)
        st.energy_updated_at = now


def reset_daily(st: models.SummonState):
    """日限重置：抓捕次数 / 日常计数 / 日常任务 / 保底保留"""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if st.daily_log_date != today:
        st.daily_log_date = today
        st.captures_today = 0
        st.daily_counters = "{}"
        st.daily_tasks = "{}"


def get_json(st: models.SummonState, field: str) -> dict:
    """安全读取 JSON 字段"""
    try:
        return json.loads(getattr(st, field) or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def set_json(st: models.SummonState, field: str, data: dict):
    setattr(st, field, json.dumps(data, ensure_ascii=False))


def incr_daily_counter(st: models.SummonState, metric: str, amount: int = 1):
    """增加今日计数器"""
    counters = get_json(st, "daily_counters")
    counters[metric] = counters.get(metric, 0) + amount
    set_json(st, "daily_counters", counters)


def get_daily_counter(st: models.SummonState, metric: str) -> int:
    return get_json(st, "daily_counters").get(metric, 0)


def get_pity(st: models.SummonState, rarity: str) -> int:
    return get_json(st, "capture_pity").get(rarity, 0)


def set_pity(st: models.SummonState, rarity: str, fails: int):
    pity = get_json(st, "capture_pity")
    pity[rarity] = fails
    set_json(st, "capture_pity", pity)


async def get_team(db: AsyncSession, user_id: int) -> list[models.SummonPet]:
    res = await db.execute(
        select(models.SummonPet).where(
            models.SummonPet.user_id == user_id,
            models.SummonPet.team_slot >= 0,
        ).order_by(models.SummonPet.team_slot))
    return list(res.scalars().all())


async def get_team_capacity(level: int) -> int:
    return 4 if level >= D.TEAM_SIZE_UNLOCK_4 else D.TEAM_SIZE_DEFAULT


def add_summon_exp(st: models.SummonState, amount: int) -> bool:
    """召唤师加经验，返回是否升级"""
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
            leveled = True
        else:
            break
    return leveled


def add_pet_exp(pet: models.SummonPet, amount: int) -> bool:
    """幻兽加经验（沿用召唤师经验表），升级重算属性（保留资质）"""
    if pet.level >= D.MAX_LEVEL:
        pet.exp = 0
        return False
    pet.exp += amount
    leveled = False
    while pet.level < D.MAX_LEVEL:
        need = D.exp_needed(pet.level)
        if pet.exp >= need:
            pet.exp -= need
            pet.level += 1
            leveled = True
        else:
            break
    if leveled:
        aptitudes = {}
        try:
            aptitudes = json.loads(pet.aptitudes or "{}")
        except (json.JSONDecodeError, TypeError):
            pass
        stats = D.roll_pet_stats(pet.species_id, pet.level, pet.growth_stars,
                                 aptitudes if aptitudes else None)
        pet.hp, pet.atk_phy, pet.atk_mag = stats["hp"], stats["atk_phy"], stats["atk_mag"]
        pet.def_phy, pet.def_mag, pet.spd = stats["def_phy"], stats["def_mag"], stats["spd"]
    return leveled


def race_coef(atk_race: str, def_race: str) -> float:
    if D.RACE_COUNTER.get(atk_race) == def_race:
        return D.RACE_COEF_ADV
    if D.RACE_COUNTER.get(def_race) == atk_race:
        return D.RACE_COEF_DISADV
    return D.RACE_COEF_NEUTRAL


def calc_damage(atk_phy: int, atk_mag: int, def_phy: int, def_mag: int,
                skill_coef: float, atk_race: str, def_race: str,
                school: str, crit: float) -> tuple[int, bool]:
    if school == "MAG":
        raw = atk_mag * skill_coef - def_mag
    else:
        raw = atk_phy * skill_coef - def_phy
    raw *= race_coef(atk_race, def_race)
    raw = max(1, raw)
    is_crit = random.random() < crit
    if is_crit:
        raw *= D.CRIT_DMG
    return int(raw), is_crit


def auto_battle(team: list[models.SummonPet], enemies: list[dict],
                max_rounds: int = 12) -> dict:
    """自动回合战斗结算"""
    def make_unit(pet, is_player: bool):
        if is_player:
            info = D.pet_info(pet.species_id)
            return {"name": pet.nickname or info["name"], "race": info["race"],
                    "hp": pet.hp, "max_hp": pet.hp, "atk_phy": pet.atk_phy,
                    "atk_mag": pet.atk_mag, "def_phy": pet.def_phy, "def_mag": pet.def_mag,
                    "spd": pet.spd, "crit": pet.crit, "skills": json.loads(pet.skills or "[]"),
                    "is_player": True, "alive": True}
        else:
            info = pet["info"]
            return {"name": info["name"], "race": info["race"],
                    "hp": pet["hp"], "max_hp": pet["hp"], "atk_phy": pet["atk_phy"],
                    "atk_mag": pet["atk_mag"], "def_phy": pet["def_phy"], "def_mag": pet["def_mag"],
                    "spd": pet["spd"], "crit": pet.get("crit", D.CRIT_BASE),
                    "skills": pet.get("skills", []), "is_player": False, "alive": True}

    units = [make_unit(p, True) for p in team] + [make_unit(e, False) for e in enemies]
    battle_log = []
    for rnd in range(1, max_rounds + 1):
        alive = [u for u in units if u["alive"]]
        if not any(u["is_player"] for u in alive):
            return {"win": False, "rounds": rnd, "log": battle_log}
        if not any(not u["is_player"] for u in alive):
            return {"win": True, "rounds": rnd, "log": battle_log}
        alive.sort(key=lambda u: u["spd"], reverse=True)
        for u in alive:
            if not u["alive"]:
                continue
            foes = [x for x in units if x["alive"] and x["is_player"] != u["is_player"]]
            if not foes:
                break
            target = random.choice(foes)
            actives = [s for s in u["skills"] if D.SKILLS.get(s, ("", "passive"))[1] == "active"]
            if actives:
                sid = random.choice(actives)
                sname, stype, school, coef, cd, _ = D.SKILLS[sid]
            else:
                sname, school, coef = "普攻", "PHY", 1.0
            dmg, is_crit = calc_damage(u["atk_phy"], u["atk_mag"], target["def_phy"],
                                       target["def_mag"], coef, u["race"], target["race"],
                                       school, u["crit"])
            target["hp"] -= dmg
            if target["hp"] <= 0:
                target["hp"] = 0
                target["alive"] = False
            battle_log.append({
                "round": rnd, "attacker": u["name"], "target": target["name"],
                "skill": sname, "dmg": dmg, "crit": is_crit,
                "target_hp": target["hp"], "target_dead": not target["alive"],
            })
    p_hp = sum(u["hp"] for u in units if u["is_player"] and u["alive"])
    e_hp = sum(u["hp"] for u in units if not u["is_player"] and u["alive"])
    return {"win": p_hp >= e_hp, "rounds": max_rounds, "log": battle_log}


def grant_rewards(st: models.SummonState, db_items: list[tuple[str, int]],
                  user_id: int, db: AsyncSession) -> dict:
    """发放掉落奖励（CUR_* 进货币，其他进背包）
    返回 {currency_gains: {field: amt}, item_gains: [(id, qty)]}
    注：背包写入需异步，此处只返回结果，由调用方 await goods.add_item
    """
    cur_map = {
        "CUR_COIN": ("coins", "铜钱"), "CUR_GEM": ("gems", "元宝"),
        "CUR_PRESTIGE": ("prestige", "声望"), "CUR_ARENA": ("arena_coin", "擂台币"),
        "CUR_BF": ("bf_coin", "战场币"), "CUR_GUILD": ("guild_coin", "贡献"),
        "CUR_MENTOR": ("mentor_coin", "桃李值"), "CUR_ENERGY": ("energy", "活力"),
    }
    cur_gains = {}
    item_gains = []
    for iid, qty in db_items:
        if iid in cur_map:
            field, _ = cur_map[iid]
            setattr(st, field, getattr(st, field) + qty)
            cur_gains[field] = cur_gains.get(field, 0) + qty
        else:
            item_gains.append((iid, qty))
    return {"currency_gains": cur_gains, "item_gains": item_gains}


def format_drop_summary(rewards: dict) -> str:
    """格式化掉落摘要文本"""
    parts = []
    cur_names = {"coins": "铜钱", "gems": "元宝", "prestige": "声望",
                 "arena_coin": "擂台币", "bf_coin": "战场币",
                 "guild_coin": "贡献", "mentor_coin": "桃李值", "energy": "活力"}
    for field, amt in rewards["currency_gains"].items():
        parts.append(f"{cur_names.get(field, field)}+{amt}")
    for iid, qty in rewards["item_gains"]:
        name = D.ITEMS.get(iid, (iid,))[0]
        parts.append(f"{name}+{qty}")
    return " / ".join(parts) if parts else "无额外掉落"


# ============================================================
# 路由：模块首页
# ============================================================
@router.get("")
async def summon_home(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    await refresh_energy(st)
    reset_daily(st)
    await db.commit()
    team = await get_team(db, user.id)
    team_cap = await get_team_capacity(st.level)
    ball_n = await goods.count_item(db, user.id, "IT_BALL_N", MODULE_KEY)
    ball_s = await goods.count_item(db, user.id, "IT_BALL_S", MODULE_KEY)
    ball_u = await goods.count_item(db, user.id, "IT_BALL_U", MODULE_KEY)
    pet_count = (await db.execute(select(func.count(models.SummonPet.id)).where(
        models.SummonPet.user_id == user.id))).scalar() or 0
    next_unlock = None
    for lv in sorted(D.LEVEL_UNLOCKS.keys()):
        if lv > st.level:
            next_unlock = (lv, D.LEVEL_UNLOCKS[lv])
            break
    # 日常任务进度摘要
    claimed_tasks = get_json(st, "daily_tasks")
    claimable = 0
    for tid, name, open_lv, limit, metric, reward in D.DAILY_TASKS:
        if st.level < open_lv or metric not in D.IMPLEMENTED_METRICS:
            continue
        target = _task_target(tid)
        if target and get_daily_counter(st, metric) >= target and tid not in claimed_tasks:
            claimable += 1
    return await render(request, "summon/home.html", db, user=user, st=st,
                        team=team, team_cap=team_cap,
                        ball_n=ball_n, ball_s=ball_s, ball_u=ball_u,
                        pet_count=pet_count, exp_need=D.exp_needed(st.level),
                        soul_slots=D.soul_slots_for_level(st.level),
                        next_unlock=next_unlock, claimable=claimable)


def _task_target(task_id: str) -> int:
    """从任务名解析目标次数"""
    targets = {"D001": 10, "D002": 3, "D003": 2, "D004": 10, "D005": 3,
               "D006": 10, "D007": 3, "D008": 8, "D009": 3, "D010": 20,
               "D011": 1, "D012": 1}
    return targets.get(task_id, 0)


# ============================================================
# 路由：世界地图（段位列表）
# ============================================================
@router.get("/map")
async def summon_map(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    tiers = []
    for i in range(1, D.TIER_COUNT + 1):
        tier = f"T{i}"
        unlock_lv = D.TIER_UNLOCK_LEVEL[tier]
        pet_ids = D.pets_in_tier(tier)
        tiers.append({
            "tier": tier, "unlock_lv": unlock_lv,
            "unlocked": st.level >= unlock_lv,
            "current": st.current_map == tier,
            "pet_count": len(pet_ids),
            "sample": [D.pet_info(pid)["name"] for pid in pet_ids[:3]],
            "stages": D.STAGES_PER_TIER,
            "cleared": st.stage_cleared if st.current_map == tier else 0,
        })
    return await render(request, "summon/map.html", db, user=user, st=st, tiers=tiers)


@router.post("/map/select/{tier}")
async def select_map(tier: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if tier not in D.TIER_UNLOCK_LEVEL or st.level < D.TIER_UNLOCK_LEVEL[tier]:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"需 Lv{D.TIER_UNLOCK_LEVEL.get(tier, '?')} 解锁该段位",
                            back_href="/games/summon/map", back_text="返回地图")
    st.current_map = tier
    await db.commit()
    return RedirectResponse("/games/summon/stage", status_code=303)


# ============================================================
# 路由：关卡（遭遇战入口）
# ============================================================
@router.get("/stage")
async def stage_view(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    await refresh_energy(st)
    await db.commit()
    team = await get_team(db, user.id)
    tier = st.current_map
    stage_no = st.stage_cleared + 1
    is_elite = stage_no % 5 == 0
    cost = D.COST_STAGE_ELITE if is_elite else D.COST_STAGE_NORMAL
    enemy_count = 2 if is_elite else random.randint(1, 2)
    can_battle = st.energy >= cost and len(team) > 0
    return await render(request, "summon/stage.html", db, user=user, st=st,
                        tier=tier, stage_no=stage_no, is_elite=is_elite, cost=cost,
                        enemy_count=enemy_count, team=team, can_battle=can_battle,
                        exp_need=D.exp_needed(st.level))


@router.post("/stage/battle")
async def stage_battle(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    await refresh_energy(st)
    reset_daily(st)
    team = await get_team(db, user.id)
    if not team:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="队伍为空，先去幻兽列表上阵", back_href="/games/summon/pets", back_text="去幻兽")
    stage_no = st.stage_cleared + 1
    is_elite = stage_no % 5 == 0
    cost = D.COST_STAGE_ELITE if is_elite else D.COST_STAGE_NORMAL
    if st.energy < cost:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"活力不足（需{cost}，当前{st.energy}）",
                            back_href="/games/summon/stage", back_text="返回关卡")
    st.energy -= cost
    enemy_count = 2 if is_elite else random.randint(1, 2)
    enemies = [D.roll_wild_pet(st.current_map) for _ in range(enemy_count)]
    result = auto_battle(team, enemies)
    battle_log = result["log"][-12:]
    tier_num = int(st.current_map[1])
    if result["win"]:
        # 掉落表抽取
        drop_key = "elite" if is_elite else "normal"
        tier_mul = 1.0 + tier_num * 0.1
        drops = D.roll_drop(drop_key, tier_mul)
        rewards = grant_rewards(st, drops, user.id, db)
        # 召唤师经验
        exp_reward = (15 + tier_num * 8) * enemy_count + (20 if is_elite else 0)
        leveled = add_summon_exp(st, exp_reward)
        # 幻兽经验
        pet_xp_key = "stage_elite_win" if is_elite else "stage_normal_win"
        pet_xp = D.PET_XP_SOURCES[pet_xp_key]
        for pet in team:
            add_pet_exp(pet, pet_xp)
        st.stage_cleared += 1
        if st.stage_cleared >= D.STAGES_PER_TIER:
            st.stage_cleared = 0
            next_tier_num = int(st.current_map[1]) + 1
            if next_tier_num <= D.TIER_COUNT:
                st.current_map = f"T{next_tier_num}"
        # 日常计数
        incr_daily_counter(st, pet_xp_key)
        # 发放背包物品
        for iid, qty in rewards["item_gains"]:
            await goods.add_item(db, user.id, iid, MODULE_KEY, qty)
        await events.emit(db, user.id, MODULE_KEY, "ranking",
                          {"metric": "level", "score": st.level})
        drop_text = format_drop_summary(rewards)
        await log.record(db, user.id, MODULE_KEY, "battle_win",
                         f"{st.current_map}:{stage_no}:exp{exp_reward}:{drop_text}")
        await db.commit()
        msg = f"战斗胜利！经验+{exp_reward}"
        if rewards["currency_gains"].get("coins"):
            msg += f" 铜钱+{rewards['currency_gains']['coins']}"
        if leveled:
            msg += " 召唤师升级！"
        return await render(request, "summon/battle.html", db, user=user, ok=True,
                            msg=msg, result=result, battle_log=battle_log, enemies=enemies,
                            rewards=rewards, drop_text=drop_text, exp_reward=exp_reward, leveled=leveled,
                            st=st, stage_no=stage_no, is_elite=is_elite,
                            exp_need=D.exp_needed(st.level),
                            back_href="/games/summon/stage", back_text="继续挑战")
    else:
        exp_reward = 5
        add_summon_exp(st, exp_reward)
        await log.record(db, user.id, MODULE_KEY, "battle_loss", f"{st.current_map}:{stage_no}")
        await db.commit()
        return await render(request, "summon/battle.html", db, user=user, ok=False,
                            msg=f"战斗失败…获得安慰经验+{exp_reward}",
                            result=result, battle_log=battle_log, enemies=enemies,
                            rewards={"currency_gains": {}, "item_gains": []},
                            drop_text="无掉落", exp_reward=exp_reward, leveled=False,
                            st=st, stage_no=stage_no, is_elite=is_elite,
                            exp_need=D.exp_needed(st.level),
                            back_href="/games/summon/stage", back_text="重新挑战")


# ============================================================
# 路由：副本（每日试炼，使用 DROP_DUNGEON）
# ============================================================
@router.get("/dungeon")
async def dungeon_view(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    await refresh_energy(st)
    reset_daily(st)
    await db.commit()
    done_today = get_daily_counter(st, "dungeon_win")
    team = await get_team(db, user.id)
    can_battle = (st.energy >= D.COST_DUNGEON and len(team) > 0
                  and done_today < D.DAILY_LIMITS["trial_each"])
    return await render(request, "summon/dungeon.html", db, user=user, st=st,
                        team=team, cost=D.COST_DUNGEON,
                        done_today=done_today, limit=D.DAILY_LIMITS["trial_each"],
                        can_battle=can_battle, exp_need=D.exp_needed(st.level))


@router.post("/dungeon/battle")
async def dungeon_battle(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    await refresh_energy(st)
    reset_daily(st)
    team = await get_team(db, user.id)
    if not team:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="队伍为空，先去幻兽列表上阵", back_href="/games/summon/pets", back_text="去幻兽")
    done_today = get_daily_counter(st, "dungeon_win")
    if done_today >= D.DAILY_LIMITS["trial_each"]:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"今日副本次数已达上限({D.DAILY_LIMITS['trial_each']})",
                            back_href="/games/summon/dungeon", back_text="返回副本")
    if st.energy < D.COST_DUNGEON:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"活力不足（需{D.COST_DUNGEON}，当前{st.energy}）",
                            back_href="/games/summon/dungeon", back_text="返回副本")
    st.energy -= D.COST_DUNGEON
    tier_num = int(st.current_map[1])
    enemy_count = random.randint(2, 3)
    enemies = [D.roll_wild_pet(st.current_map) for _ in range(enemy_count)]
    result = auto_battle(team, enemies)
    battle_log = result["log"][-12:]
    if result["win"]:
        tier_mul = 1.0 + tier_num * 0.15
        drops = D.roll_drop("dungeon", tier_mul)
        rewards = grant_rewards(st, drops, user.id, db)
        exp_reward = (20 + tier_num * 10) * enemy_count
        leveled = add_summon_exp(st, exp_reward)
        pet_xp = D.PET_XP_SOURCES["dungeon_win"]
        for pet in team:
            add_pet_exp(pet, pet_xp)
        incr_daily_counter(st, "dungeon_win")
        for iid, qty in rewards["item_gains"]:
            await goods.add_item(db, user.id, iid, MODULE_KEY, qty)
        drop_text = format_drop_summary(rewards)
        await log.record(db, user.id, MODULE_KEY, "dungeon_win",
                         f"{st.current_map}:exp{exp_reward}:{drop_text}")
        await db.commit()
        msg = f"副本通关！经验+{exp_reward}"
        if rewards["currency_gains"].get("coins"):
            msg += f" 铜钱+{rewards['currency_gains']['coins']}"
        if leveled:
            msg += " 召唤师升级！"
        return await render(request, "summon/battle.html", db, user=user, ok=True,
                            msg=msg, result=result, battle_log=battle_log, enemies=enemies,
                            rewards=rewards, drop_text=drop_text, exp_reward=exp_reward, leveled=leveled,
                            st=st, stage_no=0, is_elite=True,
                            exp_need=D.exp_needed(st.level),
                            back_href="/games/summon/dungeon", back_text="继续副本")
    else:
        exp_reward = 8
        add_summon_exp(st, exp_reward)
        await log.record(db, user.id, MODULE_KEY, "dungeon_loss", st.current_map)
        await db.commit()
        return await render(request, "summon/battle.html", db, user=user, ok=False,
                            msg=f"副本失败…获得安慰经验+{exp_reward}",
                            result=result, battle_log=battle_log, enemies=enemies,
                            rewards={"currency_gains": {}, "item_gains": []},
                            drop_text="无掉落", exp_reward=exp_reward, leveled=False,
                            st=st, stage_no=0, is_elite=True,
                            exp_need=D.exp_needed(st.level),
                            back_href="/games/summon/dungeon", back_text="重新挑战")


# ============================================================
# 路由：抓捕（v1.0 公式：基础率×球倍率 + 级差 + 保底）
# ============================================================
@router.post("/stage/capture")
async def stage_capture(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    if st.captures_today >= D.DAILY_LIMITS["capture"]:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"今日抓捕已达上限({D.DAILY_LIMITS['capture']})",
                            back_href="/games/summon/stage", back_text="返回关卡")
    wild = D.roll_wild_pet(st.current_map)
    info = wild["info"]
    # 选球：优先超级→强力→普通
    ball_key = "IT_BALL_N"
    for bk in ["IT_BALL_U", "IT_BALL_S", "IT_BALL_N"]:
        if await goods.count_item(db, user.id, bk, MODULE_KEY) > 0:
            ball_key = bk
            break
    has = await goods.count_item(db, user.id, ball_key, MODULE_KEY)
    if has <= 0:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="没有捕捉球，先去商店购买", back_href="/games/summon/shop", back_text="去商店")
    await goods.remove_item(db, user.id, ball_key, MODULE_KEY, 1)
    # v1.0 捕捉公式
    pity_fails = get_pity(st, info["rarity"])
    rate = D.capture_success_rate(info["rarity"], ball_key, st.level,
                                  wild["level"], pity_fails)
    success = random.random() < rate
    st.captures_today += 1
    if success:
        set_pity(st, info["rarity"], 0)
        apt_json = json.dumps(wild.get("aptitudes", {}), ensure_ascii=False)
        pet = models.SummonPet(
            user_id=user.id, species_id=wild["species_id"],
            nickname=info["name"], level=wild["level"], exp=0,
            hp=wild["hp"], atk_phy=wild["atk_phy"], atk_mag=wild["atk_mag"],
            def_phy=wild["def_phy"], def_mag=wild["def_mag"], spd=wild["spd"],
            crit=wild["crit"], growth_stars=wild["growth_stars"],
            aptitudes=apt_json,
            skills=json.dumps(wild["skills"]), team_slot=-1,
        )
        db.add(pet)
        incr_daily_counter(st, "capture_success")
        await log.record(db, user.id, MODULE_KEY, "capture",
                         f"{wild['species_id']}:{info['name']}:ball{ball_key}:rate{rate:.2f}")
        await db.commit()
        return await render(request, "result.html", db, user=user, ok=True,
                            msg=f"抓捕成功！{info['name']}(Lv{wild['level']} {wild['growth_stars']}★) 已加入仓库"
                                f"（成功率{int(rate*100)}%）",
                            back_href="/games/summon/pets", back_text="查看幻兽")
    else:
        set_pity(st, info["rarity"], pity_fails + 1)
        await log.record(db, user.id, MODULE_KEY, "capture_fail",
                         f"{wild['species_id']}:{info['name']}:ball{ball_key}:rate{rate:.2f}:pity{pity_fails+1}")
        await db.commit()
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"抓捕失败…{info['name']}逃跑了（成功率{int(rate*100)}%，保底累计{pity_fails+1}次）",
                            back_href="/games/summon/stage", back_text="返回关卡")


# ============================================================
# 路由：幻兽列表 + 详情 + 上阵 + 重生
# ============================================================
@router.get("/pets")
async def pet_list(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    res = await db.execute(select(models.SummonPet).where(
        models.SummonPet.user_id == user.id).order_by(models.SummonPet.team_slot,
                                                       models.SummonPet.captured_at.desc()))
    pets = []
    for p in res.scalars().all():
        info = D.pet_info(p.species_id)
        skills = [D.SKILLS.get(s, ("未知",))[0] for s in json.loads(p.skills or "[]")]
        apt = {}
        try:
            apt = json.loads(p.aptitudes or "{}")
        except (json.JSONDecodeError, TypeError):
            pass
        pets.append({"pet": p, "info": info, "skills": skills, "aptitudes": apt})
    team_cap = await get_team_capacity(st.level)
    in_team = sum(1 for p in pets if p["pet"].team_slot >= 0)
    return await render(request, "summon/pets.html", db, user=user, st=st,
                        pets=pets, team_cap=team_cap, in_team=in_team)


@router.get("/pet/{pet_id}")
async def pet_detail(pet_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    pet = await db.get(models.SummonPet, pet_id)
    if not pet or pet.user_id != user.id:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="幻兽不存在", back_href="/games/summon/pets", back_text="返回列表")
    info = D.pet_info(pet.species_id)
    spi = D.pet_skill_pool_info(pet.species_id)
    skill_ids = json.loads(pet.skills or "[]")
    skills = [D.skill_info(s, 1) for s in skill_ids]
    apt = {}
    try:
        apt = json.loads(pet.aptitudes or "{}")
    except (json.JSONDecodeError, TypeError):
        pass
    team_cap = await get_team_capacity(st.level)
    skill_slots = D.pet_skill_slots_for_level(pet.level)
    rebirth_count = await goods.count_item(db, user.id, D.REBIRTH["cost_item"], MODULE_KEY)
    return await render(request, "summon/pet_detail.html", db, user=user, st=st,
                        pet=pet, info=info, spi=spi, skills=skills, aptitudes=apt,
                        team_cap=team_cap, skill_slots=skill_slots,
                        rebirth_count=rebirth_count, exp_need=D.exp_needed(pet.level))


@router.post("/pet/{pet_id}/team")
async def pet_toggle_team(pet_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    pet = await db.get(models.SummonPet, pet_id)
    if not pet or pet.user_id != user.id:
        return RedirectResponse("/games/summon/pets", status_code=303)
    team_cap = await get_team_capacity(st.level)
    if pet.team_slot >= 0:
        pet.team_slot = -1
    else:
        team = await get_team(db, user.id)
        if len(team) >= team_cap:
            return await render(request, "result.html", db, user=user, ok=False,
                                msg=f"队伍已满（{team_cap}只）", back_href="/games/summon/pets", back_text="返回列表")
        used = {p.team_slot for p in team}
        for slot in range(team_cap):
            if slot not in used:
                pet.team_slot = slot
                break
    await db.commit()
    return RedirectResponse("/games/summon/pets", status_code=303)


@router.post("/pet/{pet_id}/release")
async def pet_release(pet_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    pet = await db.get(models.SummonPet, pet_id)
    if not pet or pet.user_id != user.id:
        return RedirectResponse("/games/summon/pets", status_code=303)
    if pet.team_slot >= 0:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="上阵中的幻兽不能放生，先下阵", back_href="/games/summon/pets", back_text="返回列表")
    st = await get_state(db, user.id)
    refund = 50 + pet.level * 10
    st.coins += refund
    info = D.pet_info(pet.species_id)
    await db.delete(pet)
    await log.record(db, user.id, MODULE_KEY, "release", f"{pet.species_id}:{info['name']}:{refund}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"已放生 {info['name']}，返还 {refund} 铜钱",
                        back_href="/games/summon/pets", back_text="返回列表")


@router.post("/pet/{pet_id}/rebirth")
async def pet_rebirth(pet_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """重生：消耗重生丹，重洗成长星/资质/技能（保留等级）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    pet = await db.get(models.SummonPet, pet_id)
    if not pet or pet.user_id != user.id:
        return RedirectResponse("/games/summon/pets", status_code=303)
    if await goods.count_item(db, user.id, D.REBIRTH["cost_item"], MODULE_KEY) <= 0:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="没有重生丹，先去商店购买", back_href="/games/summon/shop", back_text="去商店")
    await goods.remove_item(db, user.id, D.REBIRTH["cost_item"], MODULE_KEY, 1)
    old_stars = pet.growth_stars
    new_stars = random.choices([1, 2, 3, 4, 5], weights=[20, 25, 30, 15, 10])[0]
    pet.growth_stars = new_stars
    aptitudes = D.roll_aptitudes()
    pet.aptitudes = json.dumps(aptitudes, ensure_ascii=False)
    skills = D.roll_pet_skills(pet.species_id, pet.level)
    pet.skills = json.dumps(skills)
    stats = D.roll_pet_stats(pet.species_id, pet.level, new_stars, aptitudes)
    pet.hp, pet.atk_phy, pet.atk_mag = stats["hp"], stats["atk_phy"], stats["atk_mag"]
    pet.def_phy, pet.def_mag, pet.spd = stats["def_phy"], stats["def_mag"], stats["spd"]
    pet.crit = stats["crit"]
    info = D.pet_info(pet.species_id)
    await log.record(db, user.id, MODULE_KEY, "rebirth",
                     f"{pet.species_id}:{info['name']}:{old_stars}★→{new_stars}★")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"{info['name']} 重生完成！成长星 {old_stars}★→{new_stars}★，资质与技能已重洗",
                        back_href=f"/games/summon/pet/{pet_id}", back_text="查看详情")


# ============================================================
# 路由：商店（多货币）
# ============================================================
@router.get("/shop")
async def shop_view(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    grouped = {}
    for shop_key, slot, iid, cur, price, limit_d, limit_w, notes in D.SHOP:
        item_info = D.ITEMS.get(iid, (iid, "", "", 0))
        cur_field, cur_name = D.CURRENCY_FIELD.get(cur, (cur, cur))
        affordable = getattr(st, cur_field, 0) >= price
        grouped.setdefault(shop_key, []).append({
            "iid": iid, "name": item_info[0], "type": item_info[1],
            "desc": item_info[2], "cur": cur, "cur_name": cur_name,
            "price": price, "limit": limit_d, "affordable": affordable,
            "notes": notes,
        })
    shop_list = [{"shop_key": k, "shop_name": D.SHOP_NAMES.get(k, k), "goods": v}
                 for k, v in grouped.items()]
    return await render(request, "summon/shop.html", db, user=user, st=st, shop_list=shop_list)


@router.post("/shop/buy/{item_id}")
async def shop_buy(item_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    entry = None
    for s in D.SHOP:
        if s[2] == item_id:
            entry = s
            break
    if not entry:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="商品不存在", back_href="/games/summon/shop", back_text="返回商店")
    _, _, iid, cur, price, _, _, _ = entry
    cur_field, cur_name = D.CURRENCY_FIELD.get(cur, (cur, cur))
    balance = getattr(st, cur_field, 0)
    if balance < price:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"{cur_name}不足（{balance}/{price}）",
                            back_href="/games/summon/shop", back_text="返回商店")
    setattr(st, cur_field, balance - price)
    await goods.add_item(db, user.id, iid, MODULE_KEY, 1)
    await log.record(db, user.id, MODULE_KEY, "shop_buy", f"{iid}:{price}{cur_name}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"购买成功：{D.ITEMS.get(iid, (iid,))[0]} ×1（消耗{cur_name}{price}）",
                        back_href="/games/summon/shop", back_text="返回商店")


# ============================================================
# 路由：日常任务
# ============================================================
@router.get("/tasks")
async def tasks_view(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    await db.commit()
    claimed = get_json(st, "daily_tasks")
    tasks = []
    for tid, name, open_lv, limit, metric, reward_str in D.DAILY_TASKS:
        implemented = metric in D.IMPLEMENTED_METRICS
        locked = st.level < open_lv
        target = _task_target(tid)
        progress = get_daily_counter(st, metric) if implemented else 0
        is_claimable = (implemented and not locked and progress >= target and tid not in claimed)
        is_claimed = tid in claimed
        rewards = D.parse_reward(reward_str)
        reward_display = " / ".join(
            f"{D.ITEMS.get(iid, D.CURRENCIES.get(iid, (iid,)))[0]}+{q}" for iid, q in rewards)
        tasks.append({
            "tid": tid, "name": name, "open_lv": open_lv, "metric": metric,
            "target": target, "progress": min(progress, target) if implemented else 0,
            "locked": locked, "implemented": implemented,
            "claimable": is_claimable, "claimed": is_claimed,
            "reward_display": reward_display, "rewards": rewards,
        })
    return await render(request, "summon/tasks.html", db, user=user, st=st, tasks=tasks)


@router.post("/tasks/claim/{task_id}")
async def task_claim(task_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    claimed = get_json(st, "daily_tasks")
    if task_id in claimed:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="今日已领取该任务奖励", back_href="/games/summon/tasks", back_text="返回任务")
    task = None
    for tid, name, open_lv, limit, metric, reward_str in D.DAILY_TASKS:
        if tid == task_id:
            task = (tid, name, open_lv, limit, metric, reward_str)
            break
    if not task:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="任务不存在", back_href="/games/summon/tasks", back_text="返回任务")
    tid, name, open_lv, limit, metric, reward_str = task
    if st.level < open_lv:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"需 Lv{open_lv} 才能接取该任务", back_href="/games/summon/tasks", back_text="返回任务")
    if metric not in D.IMPLEMENTED_METRICS:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="该任务对应功能即将开放", back_href="/games/summon/tasks", back_text="返回任务")
    target = _task_target(tid)
    if get_daily_counter(st, metric) < target:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"任务未完成（{get_daily_counter(st, metric)}/{target}）",
                            back_href="/games/summon/tasks", back_text="返回任务")
    # 发放奖励
    rewards = D.parse_reward(reward_str)
    reward_items = [(iid, q) for iid, q in rewards]
    granted = grant_rewards(st, reward_items, user.id, db)
    for iid, qty in granted["item_gains"]:
        await goods.add_item(db, user.id, iid, MODULE_KEY, qty)
    claimed[task_id] = 1
    set_json(st, "daily_tasks", claimed)
    drop_text = format_drop_summary(granted)
    await log.record(db, user.id, MODULE_KEY, "task_claim", f"{task_id}:{drop_text}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"任务【{name}】奖励已领取：{drop_text}",
                        back_href="/games/summon/tasks", back_text="返回任务")


# ============================================================
# 路由：图鉴
# ============================================================
@router.get("/album")
async def album_view(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    res = await db.execute(select(models.SummonPet.species_id).where(
        models.SummonPet.user_id == user.id).distinct())
    owned = {r[0] for r in res.all()}
    album = {}
    for tier in [f"T{i}" for i in range(1, 9)]:
        album[tier] = []
        for pid in D.pets_in_tier(tier):
            info = D.pet_info(pid)
            album[tier].append({**info, "owned": pid in owned})
    owned_count = len(owned)
    return await render(request, "summon/album.html", db, user=user, st=st,
                        album=album, owned_count=owned_count, total_count=len(D.PETS))


# ============================================================
# 路由：规则
# ============================================================
@router.get("/rules")
async def rules_view(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return await render(request, "summon/rules.html", db, user=user)


# ============================================================
# 路由：战骨系统（BONE_PARTS / bone_upgrade_cost）
# ============================================================
@router.get("/bone")
async def bone_view(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    await db.commit()
    if st.level < 10:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"需 Lv10 解锁战骨系统",
                            back_href="/games/summon", back_text="返回首页")
    levels = get_json(st, "bone_levels")
    stone_n = await goods.count_item(db, user.id, "IT_STONE", MODULE_KEY)
    parts = []
    for key, (name, stats) in D.BONE_PARTS.items():
        lv = levels.get(key, 0)
        coin_cost, stone_cost = D.bone_upgrade_cost(lv)
        parts.append({"key": key, "name": name, "stats": stats, "level": lv,
                      "coin_cost": coin_cost, "stone_cost": stone_cost,
                      "affordable": st.coins >= coin_cost and stone_n >= stone_cost})
    return await render(request, "summon/bone.html", db, user=user, st=st,
                        parts=parts, stone_n=stone_n,
                        exp_need=D.exp_needed(st.level))


@router.post("/bone/upgrade/{part_key}")
async def bone_upgrade(part_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    if part_key not in D.BONE_PARTS:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="战骨部位不存在", back_href="/games/summon/bone", back_text="返回战骨")
    levels = get_json(st, "bone_levels")
    lv = levels.get(part_key, 0)
    coin_cost, stone_cost = D.bone_upgrade_cost(lv)
    if st.coins < coin_cost:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"铜钱不足（需{coin_cost}，当前{st.coins}）",
                            back_href="/games/summon/bone", back_text="返回战骨")
    if await goods.count_item(db, user.id, "IT_STONE", MODULE_KEY) < stone_cost:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"灵石不足（需{stone_cost}）",
                            back_href="/games/summon/bone", back_text="返回战骨")
    st.coins -= coin_cost
    await goods.remove_item(db, user.id, "IT_STONE", MODULE_KEY, stone_cost)
    levels[part_key] = lv + 1
    set_json(st, "bone_levels", levels)
    incr_daily_counter(st, "bone_upgrade")
    part_name = D.BONE_PARTS[part_key][0]
    await log.record(db, user.id, MODULE_KEY, "bone_upgrade",
                     f"{part_key}:{part_name}:{lv}->{lv+1}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"{part_name} 强化成功！Lv{lv}→Lv{lv+1}（消耗铜钱{coin_cost} 灵石{stone_cost}）",
                        back_href="/games/summon/bone", back_text="返回战骨")


# ============================================================
# 路由：魔魂系统（SOUL_RARITY / SOUL_HUNT / SOUL_XP / SOUL_FEED）
# ============================================================
@router.get("/soul")
async def soul_view(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    await db.commit()
    slot_count = D.soul_slots_for_level(st.level)
    if slot_count <= 0:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="需 Lv30 解锁魔魂系统",
                            back_href="/games/summon", back_text="返回首页")
    souls = json.loads(st.souls or "[]")
    # 补齐槽位展示（空槽显示 None）
    while len(souls) < slot_count:
        souls.append(None)
    charm_n = await goods.count_item(db, user.id, "IT_SOUL_CHARM", MODULE_KEY)
    hunters = []
    for i, (name, coin, charm, outputs) in enumerate(D.SOUL_HUNT):
        out_names = "、".join(D.SOUL_RARITY[o][0] for o in outputs)
        affordable = st.coins >= coin and charm_n >= charm
        hunters.append({"tier": i, "name": name, "coin": coin, "charm": charm,
                        "outputs": out_names, "affordable": affordable})
    return await render(request, "summon/soul.html", db, user=user, st=st,
                        souls=souls[:slot_count], slot_count=slot_count,
                        hunters=hunters, charm_n=charm_n,
                        soul_rarity=D.SOUL_RARITY,
                        exp_need=D.exp_needed(st.level))


@router.post("/soul/hunt/{hunter_tier}")
async def soul_hunt(hunter_tier: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    slot_count = D.soul_slots_for_level(st.level)
    if slot_count <= 0:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="需 Lv30 解锁魔魂系统",
                            back_href="/games/summon", back_text="返回首页")
    if hunter_tier < 0 or hunter_tier >= len(D.SOUL_HUNT):
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="猎魂师不存在", back_href="/games/summon/soul", back_text="返回魔魂")
    souls = json.loads(st.souls or "[]")
    while len(souls) < slot_count:
        souls.append(None)
    if all(s is not None for s in souls[:slot_count]):
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="魔魂槽已满，先吞噬或清理",
                            back_href="/games/summon/soul", back_text="返回魔魂")
    name, coin_cost, charm_cost, outputs = D.SOUL_HUNT[hunter_tier]
    if st.coins < coin_cost:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"铜钱不足（需{coin_cost}）",
                            back_href="/games/summon/soul", back_text="返回魔魂")
    if charm_cost > 0 and await goods.count_item(db, user.id, "IT_SOUL_CHARM", MODULE_KEY) < charm_cost:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"追魂法宝不足（需{charm_cost}）",
                            back_href="/games/summon/soul", back_text="返回魔魂")
    st.coins -= coin_cost
    if charm_cost > 0:
        await goods.remove_item(db, user.id, "IT_SOUL_CHARM", MODULE_KEY, charm_cost)
    rarity = random.choice(outputs)
    new_soul = {"rarity": rarity, "level": 1, "xp": 0}
    for i in range(slot_count):
        if souls[i] is None:
            souls[i] = new_soul
            break
    st.souls = json.dumps(souls, ensure_ascii=False)
    incr_daily_counter(st, "soul_hunt")
    rname = D.SOUL_RARITY[rarity][0]
    await log.record(db, user.id, MODULE_KEY, "soul_hunt",
                     f"{name}:{rarity}:{rname}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"猎魂师 {name} 成功召唤【{rname}】！（消耗铜钱{coin_cost}"
                            + (f" 追魂法宝{charm_cost}" if charm_cost else "") + "）",
                        back_href="/games/summon/soul", back_text="返回魔魂")


@router.post("/soul/feed/{slot_index}")
async def soul_feed(slot_index: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    slot_count = D.soul_slots_for_level(st.level)
    if slot_index < 0 or slot_index >= slot_count:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="槽位不存在", back_href="/games/summon/soul", back_text="返回魔魂")
    souls = json.loads(st.souls or "[]")
    while len(souls) < slot_count:
        souls.append(None)
    soul = souls[slot_index]
    if soul is None:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="该槽位无魔魂", back_href="/games/summon/soul", back_text="返回魔魂")
    # 吞噬材料：按从低到高消耗魂粉
    feed_order = ["IT_SOUL_POWDER_1", "IT_SOUL_POWDER_2", "IT_SOUL_POWDER_3", "IT_SOUL_POWDER_4"]
    feed_map = {"IT_SOUL_POWDER_1": ("YELLOW", 50), "IT_SOUL_POWDER_2": ("MYSTIC", 100),
                "IT_SOUL_POWDER_3": ("EARTH", 200), "IT_SOUL_POWDER_4": ("HEAVEN", 400)}
    gained_xp = 0
    used = []
    for iid in feed_order:
        have = await goods.count_item(db, user.id, iid, MODULE_KEY)
        if have > 0:
            await goods.remove_item(db, user.id, iid, MODULE_KEY, 1)
            _, xp = feed_map[iid]
            gained_xp += xp
            used.append(f"{D.ITEMS[iid][0]}×1(+{xp})")
            break
    if gained_xp == 0:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="没有魂粉材料（需 黄/玄/地/天 魂粉）",
                            back_href="/games/summon/soul", back_text="返回魔魂")
    soul["xp"] = soul.get("xp", 0) + gained_xp
    # 升级判定
    leveled = False
    while soul["level"] < 10:
        need = D.SOUL_XP.get((soul["level"], soul["level"] + 1), 0)
        if need == 0 or soul["xp"] < need:
            break
        soul["xp"] -= need
        soul["level"] += 1
        leveled = True
    souls[slot_index] = soul
    st.souls = json.dumps(souls, ensure_ascii=False)
    rname = D.SOUL_RARITY.get(soul["rarity"], ("?",))[0]
    await log.record(db, user.id, MODULE_KEY, "soul_feed",
                     f"slot{slot_index}:{rname}:xp+{gained_xp}:lv{soul['level']}")
    await db.commit()
    msg = f"【{rname}】吞噬获得魂力+{gained_xp}（{'、'.join(used)}）"
    if leveled:
        msg += f" 升级到 Lv{soul['level']}！"
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=msg, back_href="/games/summon/soul", back_text="返回魔魂")


# ============================================================
# 路由：战灵系统（SPIRIT_SLOTS / SPIRIT_QUALITY_WEIGHTS / SPIRIT_AFFIXES）
# ============================================================
def _roll_spirit() -> dict:
    """随机生成一个战灵（品质 + 3 词条）"""
    qualities = list(D.SPIRIT_QUALITY_WEIGHTS.keys())
    weights = [sum(D.SPIRIT_QUALITY_WEIGHTS[q]) for q in qualities]
    quality = random.choices(qualities, weights=weights)[0]
    affix_ids = random.sample(list(D.SPIRIT_AFFIXES.keys()), 3)
    affixes = []
    for aid in affix_ids:
        aname, atype, stat, lo, hi = D.SPIRIT_AFFIXES[aid]
        val = round(random.uniform(lo, hi), 3) if atype != "flat" else random.randint(lo, hi)
        affixes.append({"id": aid, "name": aname, "stat": stat, "value": val})
    return {"quality": quality, "affixes": affixes}


@router.get("/spirit")
async def spirit_view(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    await db.commit()
    if st.level < 35:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="需 Lv35 解锁战灵系统",
                            back_href="/games/summon", back_text="返回首页")
    spirits = json.loads(st.spirits or "[]")
    while len(spirits) < len(D.SPIRIT_SLOTS):
        spirits.append(None)
    dust_n = await goods.count_item(db, user.id, "IT_SPIRIT_DUST", MODULE_KEY)
    roll_no = get_daily_counter(st, "spirit_reroll") + 1
    coin_cost, dust_cost, is_free = D.spirit_reroll_cost(roll_no, 0)
    return await render(request, "summon/spirit.html", db, user=user, st=st,
                        spirits=spirits, slot_count=len(D.SPIRIT_SLOTS),
                        dust_n=dust_n, coin_cost=coin_cost, dust_cost=dust_cost,
                        is_free=is_free, roll_no=roll_no,
                        exp_need=D.exp_needed(st.level))


@router.post("/spirit/reroll")
async def spirit_reroll(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    form = await request.form()
    lock_count = 0
    try:
        lock_count = int(form.get("lock_count", "0") or "0")
    except (TypeError, ValueError):
        lock_count = 0
    lock_count = max(0, min(lock_count, len(D.SPIRIT_SLOTS)))
    roll_no = get_daily_counter(st, "spirit_reroll") + 1
    if roll_no > D.SPIRIT_REROLL_DAILY_CAP:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"今日洗炼次数已达上限({D.SPIRIT_REROLL_DAILY_CAP})",
                            back_href="/games/summon/spirit", back_text="返回战灵")
    coin_cost, dust_cost, is_free = D.spirit_reroll_cost(roll_no, lock_count)
    if not is_free:
        if st.coins < coin_cost:
            return await render(request, "result.html", db, user=user, ok=False,
                                msg=f"铜钱不足（需{coin_cost}）",
                                back_href="/games/summon/spirit", back_text="返回战灵")
        if dust_cost > 0 and await goods.count_item(db, user.id, "IT_SPIRIT_DUST", MODULE_KEY) < dust_cost:
            return await render(request, "result.html", db, user=user, ok=False,
                                msg=f"灵力不足（需{dust_cost}）",
                                back_href="/games/summon/spirit", back_text="返回战灵")
    spirits = json.loads(st.spirits or "[]")
    while len(spirits) < len(D.SPIRIT_SLOTS):
        spirits.append(None)
    # 重洗非锁定槽位
    new_spirits = []
    rerolled = []
    for i in range(len(D.SPIRIT_SLOTS)):
        if i < lock_count and spirits[i] is not None:
            new_spirits.append(spirits[i])
        else:
            sp = _roll_spirit()
            new_spirits.append(sp)
            rerolled.append(f"{D.SPIRIT_SLOTS[i+1]}({sp['quality']})")
    if not is_free:
        st.coins -= coin_cost
        if dust_cost > 0:
            await goods.remove_item(db, user.id, "IT_SPIRIT_DUST", MODULE_KEY, dust_cost)
    st.spirits = json.dumps(new_spirits, ensure_ascii=False)
    incr_daily_counter(st, "spirit_reroll")
    await log.record(db, user.id, MODULE_KEY, "spirit_reroll",
                     f"roll{roll_no}:lock{lock_count}:{'、'.join(rerolled)}")
    await db.commit()
    cost_text = "免费" if is_free else f"消耗铜钱{coin_cost}" + (f" 灵力{dust_cost}" if dust_cost else "")
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"战灵洗炼完成（{cost_text}）：{'、'.join(rerolled)}",
                        back_href="/games/summon/spirit", back_text="返回战灵")


# ============================================================
# 路由：擂台（ARENA）
# ============================================================
@router.get("/arena")
async def arena_view(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    await db.commit()
    if st.level < 10:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="需 Lv10 解锁擂台",
                            back_href="/games/summon", back_text="返回首页")
    done_today = get_daily_counter(st, "arena_battle")
    # 随机生成 3 个对手 NPC
    opponents = []
    for _ in range(3):
        tier = f"T{min(8, max(1, st.level // 10 or 1))}"
        wild = D.roll_wild_pet(tier)
        opponents.append(wild)
    team = await get_team(db, user.id)
    can_challenge = (done_today < D.ARENA["daily_free"] and len(team) > 0)
    return await render(request, "summon/arena.html", db, user=user, st=st,
                        done_today=done_today, limit=D.ARENA["daily_free"],
                        opponents=opponents, team=team, can_challenge=can_challenge,
                        arena=D.ARENA, exp_need=D.exp_needed(st.level))


@router.post("/arena/challenge")
async def arena_challenge(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    if st.level < 10:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="需 Lv10 解锁擂台", back_href="/games/summon", back_text="返回首页")
    done_today = get_daily_counter(st, "arena_battle")
    if done_today >= D.ARENA["daily_free"]:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"今日擂台次数已达上限({D.ARENA['daily_free']})",
                            back_href="/games/summon/arena", back_text="返回擂台")
    team = await get_team(db, user.id)
    if not team:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="队伍为空，先去幻兽列表上阵",
                            back_href="/games/summon/pets", back_text="去幻兽")
    tier = f"T{min(8, max(1, st.level // 10 or 1))}"
    enemies = [D.roll_wild_pet(tier)]
    result = auto_battle(team, enemies)
    battle_log = result["log"][-12:]
    incr_daily_counter(st, "arena_battle")
    if result["win"]:
        st.prestige += D.ARENA["win_prestige"]
        st.arena_coin += D.ARENA["win_arena_coin"]
        exp_reward = D.PET_XP_SOURCES["arena_win"]
        for pet in team:
            add_pet_exp(pet, exp_reward)
        await log.record(db, user.id, MODULE_KEY, "arena_win",
                         f"prestige+{D.ARENA['win_prestige']}:arena_coin+{D.ARENA['win_arena_coin']}")
        await db.commit()
        return await render(request, "summon/battle.html", db, user=user, ok=True,
                            msg=f"擂台胜利！声望+{D.ARENA['win_prestige']} 擂台币+{D.ARENA['win_arena_coin']}",
                            result=result, battle_log=battle_log, enemies=enemies,
                            rewards={"currency_gains": {"prestige": D.ARENA['win_prestige'],
                                                         "arena_coin": D.ARENA['win_arena_coin']},
                                     "item_gains": []},
                            drop_text=f"声望+{D.ARENA['win_prestige']} 擂台币+{D.ARENA['win_arena_coin']}",
                            exp_reward=exp_reward, leveled=False, st=st, stage_no=0, is_elite=False,
                            exp_need=D.exp_needed(st.level),
                            back_href="/games/summon/arena", back_text="继续挑战")
    else:
        loss_coin = min(st.arena_coin, D.ARENA["loss_arena_coin"])
        st.arena_coin -= loss_coin
        exp_reward = D.PET_XP_SOURCES["arena_loss"]
        for pet in team:
            add_pet_exp(pet, exp_reward)
        await log.record(db, user.id, MODULE_KEY, "arena_loss", f"arena_coin-{loss_coin}")
        await db.commit()
        return await render(request, "summon/battle.html", db, user=user, ok=False,
                            msg=f"擂台失利…擂台币-{loss_coin}",
                            result=result, battle_log=battle_log, enemies=enemies,
                            rewards={"currency_gains": {}, "item_gains": []},
                            drop_text="无掉落", exp_reward=exp_reward, leveled=False,
                            st=st, stage_no=0, is_elite=False,
                            exp_need=D.exp_needed(st.level),
                            back_href="/games/summon/arena", back_text="重新挑战")


# ============================================================
# 路由：战场（BATTLEFIELD）
# ============================================================
@router.get("/battlefield")
async def battlefield_view(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    await db.commit()
    if st.level < 40:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="需 Lv40 解锁战场",
                            back_href="/games/summon", back_text="返回首页")
    done_today = get_daily_counter(st, "battlefield_settle")
    team = await get_team(db, user.id)
    can_join = (done_today < D.BATTLEFIELD["daily_join_limit"] and len(team) > 0)
    return await render(request, "summon/battlefield.html", db, user=user, st=st,
                        done_today=done_today, limit=D.BATTLEFIELD["daily_join_limit"],
                        team=team, can_join=can_join, bf=D.BATTLEFIELD,
                        exp_need=D.exp_needed(st.level))


@router.post("/battlefield/join")
async def battlefield_join(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    if st.level < 40:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="需 Lv40 解锁战场", back_href="/games/summon", back_text="返回首页")
    done_today = get_daily_counter(st, "battlefield_settle")
    if done_today >= D.BATTLEFIELD["daily_join_limit"]:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"今日战场次数已达上限({D.BATTLEFIELD['daily_join_limit']})",
                            back_href="/games/summon/battlefield", back_text="返回战场")
    team = await get_team(db, user.id)
    if not team:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="队伍为空，先去幻兽列表上阵",
                            back_href="/games/summon/pets", back_text="去幻兽")
    tier = f"T{min(8, max(1, st.level // 10 or 1))}"
    enemy_count = random.randint(2, 3)
    enemies = [D.roll_wild_pet(tier) for _ in range(enemy_count)]
    result = auto_battle(team, enemies)
    battle_log = result["log"][-12:]
    incr_daily_counter(st, "battlefield_settle")
    if result["win"]:
        st.prestige += D.BATTLEFIELD["win_prestige"]
        st.bf_coin += D.BATTLEFIELD["win_bf_coin"]
        # 杀戮礼包掉落
        kill_drops = []
        for iid, weight, lo, hi in D.KILL_BOX_DROPS:
            if random.random() * 100 < weight:
                qty = random.randint(lo, hi)
                if qty > 0:
                    kill_drops.append((iid, qty))
        rewards = grant_rewards(st, kill_drops, user.id, db)
        for iid, qty in rewards["item_gains"]:
            await goods.add_item(db, user.id, iid, MODULE_KEY, qty)
        exp_reward = D.PET_XP_SOURCES["battlefield_settle"]
        for pet in team:
            add_pet_exp(pet, exp_reward)
        drop_text = format_drop_summary(rewards)
        await log.record(db, user.id, MODULE_KEY, "battlefield_win",
                         f"prestige+{D.BATTLEFIELD['win_prestige']}:bf_coin+{D.BATTLEFIELD['win_bf_coin']}:{drop_text}")
        await db.commit()
        msg = f"战场获胜！声望+{D.BATTLEFIELD['win_prestige']} 战场币+{D.BATTLEFIELD['win_bf_coin']} {drop_text}"
        return await render(request, "summon/battle.html", db, user=user, ok=True,
                            msg=msg, result=result, battle_log=battle_log, enemies=enemies,
                            rewards=rewards, drop_text=drop_text,
                            exp_reward=exp_reward, leveled=False, st=st, stage_no=0, is_elite=False,
                            exp_need=D.exp_needed(st.level),
                            back_href="/games/summon/battlefield", back_text="继续战场")
    else:
        loss_p = D.BATTLEFIELD["loss_prestige"]
        loss_b = min(st.bf_coin, D.BATTLEFIELD["loss_bf_coin"])
        st.prestige = max(0, st.prestige - loss_p)
        st.bf_coin -= loss_b
        exp_reward = 10
        for pet in team:
            add_pet_exp(pet, exp_reward)
        await log.record(db, user.id, MODULE_KEY, "battlefield_loss", f"bf_coin-{loss_b}")
        await db.commit()
        return await render(request, "summon/battle.html", db, user=user, ok=False,
                            msg=f"战场失利…战场币-{loss_b}",
                            result=result, battle_log=battle_log, enemies=enemies,
                            rewards={"currency_gains": {}, "item_gains": []},
                            drop_text="无掉落", exp_reward=exp_reward, leveled=False,
                            st=st, stage_no=0, is_elite=False,
                            exp_need=D.exp_needed(st.level),
                            back_href="/games/summon/battlefield", back_text="重新战场")


# ============================================================
# 路由：联盟（ALLIANCE_DONATION / ALLIANCE_SKILLS / ALLIANCE_STORAGE）
# ============================================================
@router.get("/alliance")
async def alliance_view(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    await db.commit()
    skill_levels = get_json(st, "alliance_skills")
    donate_list = []
    for iid, contrib in D.ALLIANCE_DONATION.items():
        have = await goods.count_item(db, user.id, iid, MODULE_KEY)
        donate_list.append({"iid": iid, "name": D.ITEMS[iid][0],
                            "contrib": contrib, "have": have})
    skills = []
    for sid, (name, max_lv, bonus, base, step) in D.ALLIANCE_SKILLS.items():
        cur_lv = skill_levels.get(sid, 0)
        cost, _, bonus_total = D.alliance_skill_cost(sid, cur_lv)
        skills.append({"sid": sid, "name": name, "max_lv": max_lv, "cur_lv": cur_lv,
                       "cost": cost, "bonus": bonus, "bonus_total": bonus_total,
                       "affordable": st.guild_coin >= cost, "maxed": cur_lv >= max_lv})
    return await render(request, "summon/alliance.html", db, user=user, st=st,
                        donate_list=donate_list, skills=skills,
                        storage=D.ALLIANCE_STORAGE, exp_need=D.exp_needed(st.level))


@router.post("/alliance/donate/{item_key}")
async def alliance_donate(item_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    if item_key not in D.ALLIANCE_DONATION:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="该物品不可捐献", back_href="/games/summon/alliance", back_text="返回联盟")
    contrib = D.ALLIANCE_DONATION[item_key]
    if await goods.count_item(db, user.id, item_key, MODULE_KEY) <= 0:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"{D.ITEMS[item_key][0]}数量不足",
                            back_href="/games/summon/alliance", back_text="返回联盟")
    await goods.remove_item(db, user.id, item_key, MODULE_KEY, 1)
    st.guild_coin += contrib
    incr_daily_counter(st, "guild_donate")
    await log.record(db, user.id, MODULE_KEY, "alliance_donate",
                     f"{item_key}:{D.ITEMS[item_key][0]}:contrib+{contrib}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"捐献 {D.ITEMS[item_key][0]} ×1，贡献+{contrib}（当前贡献 {st.guild_coin}）",
                        back_href="/games/summon/alliance", back_text="返回联盟")


@router.post("/alliance/skill/{skill_id}")
async def alliance_skill_upgrade(skill_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    if skill_id not in D.ALLIANCE_SKILLS:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="技能不存在", back_href="/games/summon/alliance", back_text="返回联盟")
    skill_levels = get_json(st, "alliance_skills")
    cur_lv = skill_levels.get(skill_id, 0)
    name, max_lv, bonus, base, step = D.ALLIANCE_SKILLS[skill_id]
    if cur_lv >= max_lv:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"{name}已满级", back_href="/games/summon/alliance", back_text="返回联盟")
    cost, _, _ = D.alliance_skill_cost(skill_id, cur_lv)
    if st.guild_coin < cost:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"贡献不足（需{cost}，当前{st.guild_coin}）",
                            back_href="/games/summon/alliance", back_text="返回联盟")
    st.guild_coin -= cost
    skill_levels[skill_id] = cur_lv + 1
    set_json(st, "alliance_skills", skill_levels)
    await log.record(db, user.id, MODULE_KEY, "alliance_skill",
                     f"{skill_id}:{name}:{cur_lv}->{cur_lv+1}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"{name} 升级成功！Lv{cur_lv}→Lv{cur_lv+1}（消耗贡献{cost}）",
                        back_href="/games/summon/alliance", back_text="返回联盟")


# ============================================================
# 路由：师徒（MASTER_APPRENTICE）
# ============================================================
@router.get("/mentor")
async def mentor_view(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    await db.commit()
    can_recruit = st.level >= D.MASTER_APPRENTICE["master_min_level"]
    return await render(request, "summon/mentor.html", db, user=user, st=st,
                        can_recruit=can_recruit, ma=D.MASTER_APPRENTICE,
                        exp_need=D.exp_needed(st.level))


@router.post("/mentor/recruit")
async def mentor_recruit(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    if st.level < D.MASTER_APPRENTICE["master_min_level"]:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"需 Lv{D.MASTER_APPRENTICE['master_min_level']} 才能收徒",
                            back_href="/games/summon", back_text="返回首页")
    st.mentor_count += 1
    # 收徒奖励：桃李值
    reward_mentor = 10
    st.mentor_coin += reward_mentor
    incr_daily_counter(st, "mentor_refill")
    await log.record(db, user.id, MODULE_KEY, "mentor_recruit",
                     f"apprentice#{st.mentor_count}:mentor_coin+{reward_mentor}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"成功收徒一名（第 {st.mentor_count} 位），桃李值+{reward_mentor}",
                        back_href="/games/summon/mentor", back_text="返回师徒")


# ============================================================
# 路由：通天塔 / 战灵塔（SPIRIT_TOWER_FLOORS）
# ============================================================
@router.get("/tower")
async def tower_view(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    await db.commit()
    floors = json.loads(st.tower_floors or '{"tongtian":0,"spirit":0}')
    tongtian_floor = floors.get("tongtian", 0)
    spirit_floor = floors.get("spirit", 0)
    team = await get_team(db, user.id)
    tongtian_maxed = tongtian_floor >= D.TONGTIAN_TOWER_FLOORS
    spirit_unlocked = st.level >= 35
    spirit_maxed = spirit_floor >= D.SPIRIT_TOWER_FLOORS
    can_climb_tongtian = (len(team) > 0 and not tongtian_maxed)
    can_climb_spirit = (spirit_unlocked and len(team) > 0 and not spirit_maxed)
    return await render(request, "summon/tower.html", db, user=user, st=st,
                        tongtian_floor=tongtian_floor, spirit_floor=spirit_floor,
                        tongtian_max=D.TONGTIAN_TOWER_FLOORS, spirit_max=D.SPIRIT_TOWER_FLOORS,
                        team=team, spirit_unlocked=spirit_unlocked,
                        can_climb_tongtian=can_climb_tongtian,
                        can_climb_spirit=can_climb_spirit,
                        exp_need=D.exp_needed(st.level))


@router.post("/tower/climb/{tower_type}")
async def tower_climb(tower_type: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    if tower_type not in ("tongtian", "spirit"):
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="塔类型不存在", back_href="/games/summon/tower", back_text="返回塔")
    if tower_type == "spirit" and st.level < 35:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="需 Lv35 解锁战灵塔",
                            back_href="/games/summon/tower", back_text="返回塔")
    floors = json.loads(st.tower_floors or '{"tongtian":0,"spirit":0}')
    cur_floor = floors.get(tower_type, 0)
    max_floor = D.TONGTIAN_TOWER_FLOORS if tower_type == "tongtian" else D.SPIRIT_TOWER_FLOORS
    if cur_floor >= max_floor:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="已登顶该塔", back_href="/games/summon/tower", back_text="返回塔")
    team = await get_team(db, user.id)
    if not team:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="队伍为空，先去幻兽列表上阵",
                            back_href="/games/summon/pets", back_text="去幻兽")
    # 敌人难度随层数提升
    tier = f"T{min(8, max(1, (cur_floor // 10) + 1))}"
    enemies = [D.roll_wild_pet(tier)]
    result = auto_battle(team, enemies)
    battle_log = result["log"][-12:]
    tower_name = "通天塔" if tower_type == "tongtian" else "战灵塔"
    metric = "tower_floor" if tower_type == "tongtian" else "spirit_tower_floor"
    if result["win"]:
        floors[tower_type] = cur_floor + 1
        st.tower_floors = json.dumps(floors, ensure_ascii=False)
        # 奖励
        reward_item = "IT_BURN_CRYSTAL" if tower_type == "tongtian" else "IT_SPIRIT_DUST"
        reward_qty = 3 + cur_floor // 5
        await goods.add_item(db, user.id, reward_item, MODULE_KEY, reward_qty)
        st.coins += 100 + cur_floor * 20
        exp_reward = D.PET_XP_SOURCES["tower_floor"]
        for pet in team:
            add_pet_exp(pet, exp_reward)
        incr_daily_counter(st, metric)
        await log.record(db, user.id, MODULE_KEY, "tower_climb",
                         f"{tower_type}:{cur_floor+1}:{reward_item}+{reward_qty}")
        await db.commit()
        return await render(request, "summon/battle.html", db, user=user, ok=True,
                            msg=f"{tower_name} 第{cur_floor+1}层通过！{D.ITEMS[reward_item][0]}+{reward_qty} 铜钱+{100+cur_floor*20}",
                            result=result, battle_log=battle_log, enemies=enemies,
                            rewards={"currency_gains": {"coins": 100+cur_floor*20},
                                     "item_gains": [(reward_item, reward_qty)]},
                            drop_text=f"{D.ITEMS[reward_item][0]}+{reward_qty} 铜钱+{100+cur_floor*20}",
                            exp_reward=exp_reward, leveled=False, st=st, stage_no=cur_floor+1,
                            is_elite=False, exp_need=D.exp_needed(st.level),
                            back_href="/games/summon/tower", back_text="继续登塔")
    else:
        exp_reward = 5
        for pet in team:
            add_pet_exp(pet, exp_reward)
        await log.record(db, user.id, MODULE_KEY, "tower_loss", f"{tower_type}:{cur_floor+1}")
        await db.commit()
        return await render(request, "summon/battle.html", db, user=user, ok=False,
                            msg=f"{tower_name} 第{cur_floor+1}层失败…获得安慰经验+{exp_reward}",
                            result=result, battle_log=battle_log, enemies=enemies,
                            rewards={"currency_gains": {}, "item_gains": []},
                            drop_text="无掉落", exp_reward=exp_reward, leveled=False,
                            st=st, stage_no=cur_floor+1, is_elite=False,
                            exp_need=D.exp_needed(st.level),
                            back_href="/games/summon/tower", back_text="重新挑战")


# ---------- v0.2.6 主线任务链 ----------
@router.get("/mainquests")
async def mainquests_list(request: Request, db: AsyncSession = Depends(get_db)):
    """列表页：8 条主线任务链（幻兽收集 + 战力推进）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    return await render(request, "summon/mainquests.html", db, user=user, st=st, quests=D.MAIN_QUESTS)
