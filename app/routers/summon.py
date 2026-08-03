"""召唤之王模块（v0.0.5）

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

router = APIRouter(prefix="/games/summon")
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
    gained = int(elapsed // 300)  # 每5分钟1点
    if gained > 0:
        st.energy = min(D.ENERGY_CAP, st.energy + gained)
        st.energy_updated_at = now


def reset_daily(st: models.SummonState):
    """日限重置"""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if st.daily_log_date != today:
        st.daily_log_date = today
        st.captures_today = 0


async def get_team(db: AsyncSession, user_id: int) -> list[models.SummonPet]:
    """获取出战队伍（按槽位排序）"""
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
    """幻兽加经验（沿用召唤师经验表），返回是否升级"""
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
            # 升级重算属性
            stats = D.roll_pet_stats(pet.species_id, pet.level, pet.growth_stars)
            pet.hp, pet.atk_phy, pet.atk_mag = stats["hp"], stats["atk_phy"], stats["atk_mag"]
            pet.def_phy, pet.def_mag, pet.spd = stats["def_phy"], stats["def_mag"], stats["spd"]
        else:
            break
    return leveled


def race_coef(atk_race: str, def_race: str) -> float:
    """种族克制系数"""
    if D.RACE_COUNTER.get(atk_race) == def_race:
        return 1.0 + D.RACE_BONUS_ADV
    if D.RACE_COUNTER.get(def_race) == atk_race:
        return 1.0 + D.RACE_BONUS_DISADV
    return 1.0


def calc_damage(atk_phy: int, atk_mag: int, def_phy: int, def_mag: int,
                skill_coef: float, atk_race: str, def_race: str,
                school: str, crit: float) -> tuple[int, bool]:
    """计算单次伤害（物伤/法伤二选一），返回(伤害, 是否暴击)"""
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
    """自动回合战斗结算
    team: 玩家幻兽列表（带 species 信息）
    enemies: 野生幻兽列表（dict，含 species_id/属性/info/skills）
    返回 {win, rounds, log}
    """
    # 构建战斗单位
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
        # 按速度排序行动
        alive = [u for u in units if u["alive"]]
        if not any(u["is_player"] for u in alive):
            return {"win": False, "rounds": rnd, "log": battle_log}
        if not any(not u["is_player"] for u in alive):
            return {"win": True, "rounds": rnd, "log": battle_log}
        alive.sort(key=lambda u: u["spd"], reverse=True)
        for u in alive:
            if not u["alive"]:
                continue
            # 选目标：敌方活着的随机一个
            foes = [x for x in units if x["alive"] and x["is_player"] != u["is_player"]]
            if not foes:
                break
            target = random.choice(foes)
            # 选技能：优先主动攻击技能
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
    # 超过回合数：比剩余总血量
    p_hp = sum(u["hp"] for u in units if u["is_player"] and u["alive"])
    e_hp = sum(u["hp"] for u in units if not u["is_player"] and u["alive"])
    return {"win": p_hp >= e_hp, "rounds": max_rounds, "log": battle_log}


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
    # 仓库球数
    ball_n = await goods.count_item(db, user.id, "IT_BALL_N", MODULE_KEY)
    ball_s = await goods.count_item(db, user.id, "IT_BALL_S", MODULE_KEY)
    ball_u = await goods.count_item(db, user.id, "IT_BALL_U", MODULE_KEY)
    pet_count = (await db.execute(select(func.count(models.SummonPet.id)).where(
        models.SummonPet.user_id == user.id))).scalar() or 0
    # 解锁预告
    next_unlock = None
    for lv in sorted(D.LEVEL_UNLOCKS.keys()):
        if lv > st.level:
            next_unlock = (lv, D.LEVEL_UNLOCKS[lv])
            break
    return await render(request, "summon/home.html", db, user=user, st=st,
                        team=team, team_cap=team_cap,
                        ball_n=ball_n, ball_s=ball_s, ball_u=ball_u,
                        pet_count=pet_count, exp_need=D.exp_needed(st.level),
                        soul_slots=D.soul_slots_for_level(st.level),
                        next_unlock=next_unlock)


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
    is_elite = stage_no % 5 == 0  # 每5关精英
    cost = D.COST_STAGE_ELITE if is_elite else D.COST_STAGE_NORMAL
    # 预览遭遇
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
    # 生成敌人
    enemy_count = 2 if is_elite else random.randint(1, 2)
    enemies = [D.roll_wild_pet(st.current_map) for _ in range(enemy_count)]
    # 战斗结算
    result = auto_battle(team, enemies)
    battle_log = result["log"][-12:]  # 只展示后12条
    # 奖励
    coin_reward = 0
    exp_reward = 0
    captured_pet = None
    if result["win"]:
        tier_num = int(st.current_map[1])
        coin_reward = (40 + tier_num * 20) * enemy_count + (50 if is_elite else 0)
        exp_reward = (15 + tier_num * 8) * enemy_count + (20 if is_elite else 0)
        st.coins += coin_reward
        leveled = add_summon_exp(st, exp_reward)
        # 幻兽经验
        for pet in team:
            add_pet_exp(pet, exp_reward)
        st.stage_cleared += 1
        # 通关一段
        if st.stage_cleared >= D.STAGES_PER_TIER:
            st.stage_cleared = 0
            next_tier_num = int(st.current_map[1]) + 1
            if next_tier_num <= D.TIER_COUNT:
                st.current_map = f"T{next_tier_num}"
        await events.emit(db, user.id, MODULE_KEY, "ranking",
                          {"metric": "level", "score": st.level})
        await log.record(db, user.id, MODULE_KEY, "battle_win",
                         f"{st.current_map}:{stage_no}:coin{coin_reward}:exp{exp_reward}")
        await db.commit()
        return await render(request, "summon/battle.html", db, user=user, ok=True,
                            msg=f"战斗胜利！金币+{coin_reward} 经验+{exp_reward}" + (" 召唤师升级！" if leveled else ""),
                            result=result, battle_log=battle_log, enemies=enemies,
                            coin_reward=coin_reward, exp_reward=exp_reward, leveled=leveled,
                            st=st, stage_no=stage_no, is_elite=is_elite,
                            exp_need=D.exp_needed(st.level),
                            back_href="/games/summon/stage", back_text="继续挑战")
    else:
        # 失败也给少量经验
        exp_reward = 5
        add_summon_exp(st, exp_reward)
        await log.record(db, user.id, MODULE_KEY, "battle_loss", f"{st.current_map}:{stage_no}")
        await db.commit()
        return await render(request, "summon/battle.html", db, user=user, ok=False,
                            msg=f"战斗失败…获得安慰经验+{exp_reward}",
                            result=result, battle_log=battle_log, enemies=enemies,
                            coin_reward=0, exp_reward=exp_reward, leveled=False,
                            st=st, stage_no=stage_no, is_elite=is_elite,
                            exp_need=D.exp_needed(st.level),
                            back_href="/games/summon/stage", back_text="重新挑战")


# ============================================================
# 路由：抓捕
# ============================================================
@router.post("/stage/capture")
async def stage_capture(request: Request, db: AsyncSession = Depends(get_db)):
    """在关卡尝试抓捕一只野生幻兽"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    if st.captures_today >= D.CAPTURE_DAILY_LIMIT:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"今日抓捕已达上限({D.CAPTURE_DAILY_LIMIT})",
                            back_href="/games/summon/stage", back_text="返回关卡")
    # 生成野生
    wild = D.roll_wild_pet(st.current_map)
    info = wild["info"]
    # 抓捕成功率 = 球倍率 × (1 - 等级差惩罚) × 稀有度难度
    ball_key = request.headers.get("x-ball", "IT_BALL_N")
    # 优先消耗超级→强力→普通
    for bk in ["IT_BALL_U", "IT_BALL_S", "IT_BALL_N"]:
        if await goods.count_item(db, user.id, bk, MODULE_KEY) > 0:
            ball_key = bk
            break
    has = await goods.count_item(db, user.id, ball_key, MODULE_KEY)
    if has <= 0:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="没有捕捉球，先去商店购买", back_href="/games/summon/shop", back_text="去商店")
    await goods.remove_item(db, user.id, ball_key, MODULE_KEY, 1)
    mul = D.BALL_MULTIPLIER.get(ball_key, 1.0)
    rarity_diff = {"N": 0.0, "R": 0.1, "E": 0.25, "L": 0.45}[info["rarity"]]
    base_rate = 0.6 * mul - rarity_diff
    base_rate = max(0.1, min(0.95, base_rate))
    success = random.random() < base_rate
    st.captures_today += 1
    if success:
        pet = models.SummonPet(
            user_id=user.id, species_id=wild["species_id"],
            nickname=info["name"], level=wild["level"], exp=0,
            hp=wild["hp"], atk_phy=wild["atk_phy"], atk_mag=wild["atk_mag"],
            def_phy=wild["def_phy"], def_mag=wild["def_mag"], spd=wild["spd"],
            crit=wild["crit"], growth_stars=wild["growth_stars"],
            skills=json.dumps(wild["skills"]), team_slot=-1,
        )
        db.add(pet)
        await log.record(db, user.id, MODULE_KEY, "capture",
                         f"{wild['species_id']}:{info['name']}:ball{ball_key}")
        await db.commit()
        return await render(request, "result.html", db, user=user, ok=True,
                            msg=f"抓捕成功！{info['name']}(Lv{wild['level']}) 已加入幻兽仓库",
                            back_href="/games/summon/pets", back_text="查看幻兽")
    else:
        await log.record(db, user.id, MODULE_KEY, "capture_fail",
                         f"{wild['species_id']}:{info['name']}:ball{ball_key}")
        await db.commit()
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"抓捕失败…{info['name']}逃跑了（成功率{int(base_rate*100)}%）",
                            back_href="/games/summon/stage", back_text="返回关卡")


# ============================================================
# 路由：幻兽列表 + 详情 + 上阵
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
        pets.append({"pet": p, "info": info, "skills": skills})
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
    skill_ids = json.loads(pet.skills or "[]")
    skills = [D.skill_info(s, 1) for s in skill_ids]
    team_cap = await get_team_capacity(st.level)
    return await render(request, "summon/pet_detail.html", db, user=user, st=st,
                        pet=pet, info=info, skills=skills, team_cap=team_cap,
                        exp_need=D.exp_needed(pet.level))


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
        # 下阵
        pet.team_slot = -1
    else:
        # 上阵：检查空位
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
    """放生幻兽（不得放生上阵中的）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    pet = await db.get(models.SummonPet, pet_id)
    if not pet or pet.user_id != user.id:
        return RedirectResponse("/games/summon/pets", status_code=303)
    if pet.team_slot >= 0:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="上阵中的幻兽不能放生，先下阵", back_href="/games/summon/pets", back_text="返回列表")
    # 放生返还少量铜钱
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


# ============================================================
# 路由：商店
# ============================================================
@router.get("/shop")
async def shop_view(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    # 按商店分组
    shop_names = {"shop_general": "通用商店", "shop_cash": "元宝商店"}
    grouped = {}
    for s in D.SHOP:
        shop_key, iid, cur, price, limit = s
        item_info = D.ITEMS.get(iid, (iid, "", "", 0))
        grouped.setdefault(shop_key, []).append({
            "iid": iid, "name": item_info[0], "type": item_info[1],
            "desc": item_info[2], "cur": cur, "price": price, "limit": limit,
            "cur_name": {"coins": "铜钱", "gems": "元宝"}.get(cur, cur),
            "affordable": (cur == "coins" and st.coins >= price) or (cur == "gems" and st.gems >= price),
        })
    shop_list = [{"shop_key": k, "shop_name": shop_names.get(k, k), "goods": v}
                 for k, v in grouped.items()]
    return await render(request, "summon/shop.html", db, user=user, st=st, shop_list=shop_list)


@router.post("/shop/buy/{item_id}")
async def shop_buy(item_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_daily(st)
    # 查找商品
    entry = None
    for s in D.SHOP:
        if s[1] == item_id:
            entry = s
            break
    if not entry:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="商品不存在", back_href="/games/summon/shop", back_text="返回商店")
    _, iid, cur, price, _ = entry
    if cur == "coins":
        if st.coins < price:
            return await render(request, "result.html", db, user=user, ok=False,
                                msg=f"铜钱不足（{st.coins}/{price}）", back_href="/games/summon/shop", back_text="返回商店")
        st.coins -= price
    elif cur == "gems":
        if st.gems < price:
            return await render(request, "result.html", db, user=user, ok=False,
                                msg=f"元宝不足（{st.gems}/{price}）", back_href="/games/summon/shop", back_text="返回商店")
        st.gems -= price
    await goods.add_item(db, user.id, iid, MODULE_KEY, 1)
    await log.record(db, user.id, MODULE_KEY, "shop_buy", f"{iid}:{price}{cur}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"购买成功：{D.ITEMS.get(iid, (iid,))[0]} ×1",
                        back_href="/games/summon/shop", back_text="返回商店")


# ============================================================
# 路由：图鉴
# ============================================================
@router.get("/album")
async def album_view(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    # 已捕获物种
    res = await db.execute(select(models.SummonPet.species_id).where(
        models.SummonPet.user_id == user.id).distinct())
    owned = {r[0] for r in res.all()}
    # 按段位分组
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
