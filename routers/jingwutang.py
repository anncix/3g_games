from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
import random
import json
from datetime import datetime

from models.database import get_db
from models.models import (
    User, JingwuRole, JingwuDungeon, JingwuEquipment, JingwuItem,
    JingwuSkill, JingwuUserSkill, JingwuPetTemplate, JingwuPet,
    JingwuTalisman, JingwuTitle, JingwuLevelExp,
    Notification, BattleLog, Wallet
)
from utils.auth import get_current_user
from utils.i18n import t
from utils.jingwutang import (
    init_jingwu_data, create_jingwu_character, calculate_stats, calculate_combat_power,
    apply_stats_to_role, recover_stamina, use_xianglu,
    start_training, stop_training, process_training, simulate_battle,
    allocate_point, get_training_time_remaining, get_training_progress,
    steal_exp, harass_target, treat_possession,
    learn_skill, toggle_skill_equip, get_equipped_skills,
    get_active_pet, toggle_pet_battle, toggle_pet_possess, buy_pet,
    equip_item, use_item, get_item_quantity,
    STAT_NAMES, TRAINING_TYPES, TITLE_CONFIGS, PET_TEMPLATES,
    PROFESSIONS, FABAO_LIST, DUNGEON_STAGES, TRANSFER_PATHS,
    EQUIPMENT_SLOTS, QUALITY_COLORS, POLARIS_STARS, DIVINE_EQUIPMENT_RECIPES,
)

router = APIRouter(prefix="/jingwutang", tags=["jingwutang"])
templates = Jinja2Templates(directory="templates")

# 确保基础数据已初始化
_data_inited = False


def _ensure_init(db: Session):
    global _data_inited
    if not _data_inited:
        init_jingwu_data(db)
        _data_inited = True


def get_common_context(request: Request, db: Session):
    _ensure_init(db)
    user = get_current_user(request, db)
    if not user:
        return None
    lang = user.language or "zh"
    theme = user.theme or "light"
    unread_count = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == False
    ).count()

    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
    gcoin = wallet.g_coin if wallet else 0

    ctx = {
        "request": request,
        "user": user,
        "lang": lang,
        "theme": theme,
        "_": lambda key: t(key, lang),
        "unread_count": unread_count,
        "now": datetime.utcnow(),
        "platform_gcoin": gcoin,
    }

    # 如果有角色，处理体力恢复和修炼进度
    if user.jw_role:
        role = user.jw_role
        recover_stamina(role)
        process_training(role, db)
        apply_stats_to_role(role)
        ctx["stats"] = calculate_stats(role)
    return ctx


def require_character(ctx, db: Session):
    if not ctx["user"].jw_role:
        return RedirectResponse(url="/jingwutang/create", status_code=302)
    return None


# ============================================================
# 1. 角色创建与首页
# ============================================================

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def jingwutang_home(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    redirect = require_character(ctx, db)
    if redirect:
        return redirect

    role = ctx["user"].jw_role
    stats = ctx["stats"]

    # 当前头衔
    current_title = None
    for tconfig in TITLE_CONFIGS:
        if role.level >= tconfig["req_level"]:
            current_title = tconfig

    # 修炼进度
    train_progress = get_training_progress(role)
    training_remaining = get_training_time_remaining(role)

    # 出战宠物
    active_pet = get_active_pet(role)

    # 已装备武器
    equipped_weapon = None
    for eq in role.equipments:
        if eq.is_equipped and eq.slot == "weapon":
            equipped_weapon = eq
            break

    # 今日胜率
    total_today = (role.wins_today or 0) + (role.losses_today or 0)
    win_rate = int((role.wins_today or 0) / total_today * 100) if total_today > 0 else 0

    # 技能池数量
    skill_pool_count = len(role.skill_pool or [])

    # 异常状态消息
    status_msg = None
    if role.train_status == 2:
        status_msg = "你气血不顺，修炼效率大降，请尽快治疗！"
    elif role.train_status == 3:
        status_msg = "⚠️ 你走火入魔了！1分钟内治疗可避免损失！"

    # 当前头衔
    title = current_title["name"] if current_title else "武林新丁"

    # 下一等级经验
    next_lvl_config = db.query(JingwuLevelExp).filter(JingwuLevelExp.level == role.level + 1).first()
    next_exp = next_lvl_config.exp_needed if next_lvl_config else role.exp * 2

    # 今日签到（简化：总是显示签到按钮）
    is_today_signed = False

    ctx.update({
        "role": role,
        "stats": stats,
        "title": title,
        "combat_power": calculate_combat_power(role),
        "next_exp": next_exp,
        "is_today_signed": is_today_signed,
        "current_title": current_title,
        "train_progress": train_progress,
        "training_remaining": training_remaining,
        "active_pet": active_pet,
        "equipped_weapon": equipped_weapon,
        "win_rate": win_rate,
        "skill_pool_count": skill_pool_count,
        "status_msg": status_msg,
        "stat_names": STAT_NAMES,
    })
    return templates.TemplateResponse("jingwutang/index.html", ctx)


@router.get("/create", response_class=HTMLResponse)
async def create_character_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    if ctx["user"].jw_role:
        return RedirectResponse(url="/jingwutang/", status_code=302)
    return templates.TemplateResponse("jingwutang/create.html", ctx)


@router.post("/create")
async def create_character_submit(
    request: Request,
    name: str = Form(...),
    gender: str = Form("male"),
    db: Session = Depends(get_db)
):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    if ctx["user"].jw_role:
        return RedirectResponse(url="/jingwutang/", status_code=302)
    if not name or len(name.strip()) < 1:
        ctx["error"] = "请输入角色名"
        return templates.TemplateResponse("jingwutang/create.html", ctx)
    create_jingwu_character(db, ctx["user"], name.strip(), gender)
    return RedirectResponse(url="/jingwutang/", status_code=302)


# ============================================================
# 2. 加点系统 /jingwutang/add_point
# ============================================================

@router.get("/add_point", response_class=HTMLResponse)
async def add_point_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect

    role = ctx["user"].jw_role
    stats = ctx["stats"]

    ctx.update({
        "role": role,
        "stats": stats,
        "stat_names": STAT_NAMES,
        "stat_detail": {
            "con": {"name": "体质", "icon": "❤️", "effect": "增加气血上限（+20/点）", "current": role.con_point},
            "int": {"name": "智力", "icon": "💧", "effect": "增加精气上限（+15/点）", "current": role.int_point},
            "str": {"name": "力量", "icon": "⚔️", "effect": "增加伤害（+3/点）", "current": role.str_point},
            "end": {"name": "耐力", "icon": "🛡️", "effect": "增加防御（+2/点）", "current": role.end_point},
            "agi": {"name": "敏捷", "icon": "💨", "effect": "增加速度/闪避（+2/点）", "current": role.agi_point},
        },
        "combat_power": role.combat_power,
    })
    return templates.TemplateResponse("jingwutang/add_point.html", ctx)


@router.post("/add_point")
async def do_add_point(
    request: Request,
    stat: str = Form(...),
    db: Session = Depends(get_db)
):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect

    success, msg = allocate_point(ctx["user"].jw_role, stat, db)
    return RedirectResponse(url="/jingwutang/add_point", status_code=302)


# 兼容旧的attributes路由
@router.get("/attributes", response_class=HTMLResponse)
async def attributes_redirect(request: Request, db: Session = Depends(get_db)):
    return RedirectResponse(url="/jingwutang/add_point", status_code=302)


@router.post("/attributes/allocate")
async def attributes_allocate(
    request: Request,
    stat: str = Form(...),
    db: Session = Depends(get_db)
):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect
    stat_map = {"con": "con", "str": "str", "mag": "int", "int": "int",
                "def": "end", "end": "end", "agi": "agi"}
    allocate_point(ctx["user"].jw_role, stat_map.get(stat, stat), db)
    return RedirectResponse(url="/jingwutang/add_point", status_code=302)


# ============================================================
# 3. 修炼系统 /jingwutang/training
# ============================================================

@router.get("/training", response_class=HTMLResponse)
async def training_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect

    role = ctx["user"].jw_role
    train_progress = get_training_progress(role)

    # 修炼中的好友（可吸星/骚扰）
    friends = []
    if ctx["user"].friends:
        for friend in ctx["user"].friends:
            if friend.jw_role and friend.jw_role.train_status == 1:
                friends.append({
                    "user": friend,
                    "role": friend.jw_role,
                    "progress": get_training_progress(friend.jw_role),
                })

    ctx.update({
        "role": role,
        "stats": ctx["stats"],
        "train_progress": train_progress,
        "training_remaining": get_training_time_remaining(role),
        "training_types": TRAINING_TYPES,
        "friends_training": friends[:10],
        "can_treat": role.train_status in (2, 3),
        "status_msg": None,
    })

    # 检查是否有刚结束的修炼奖励（通过query参数传递消息）
    msg = request.query_params.get("msg")
    if msg:
        ctx["status_msg"] = msg

    return templates.TemplateResponse("jingwutang/training.html", ctx)


@router.post("/training/start")
async def do_start_training(
    request: Request,
    training_type: str = Form("normal"),
    db: Session = Depends(get_db)
):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect

    success, msg = start_training(ctx["user"].jw_role, training_type)
    db.commit()
    return RedirectResponse(url="/jingwutang/training", status_code=302)


@router.get("/training/stop")
async def do_stop_training(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect

    success, msg = stop_training(ctx["user"].jw_role, db)
    return RedirectResponse(url="/jingwutang/training?msg=" + ("修炼完成！经验和技能点已领取" if success else "你没有在修炼"), status_code=302)


@router.get("/training/steal/{target_id}")
async def do_steal(request: Request, target_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect

    target = db.query(JingwuRole).filter(JingwuRole.id == target_id).first()
    if not target:
        return RedirectResponse(url="/jingwutang/training", status_code=302)

    success, msg = steal_exp(ctx["user"].jw_role, target, db)
    return RedirectResponse(url="/jingwutang/training?msg=" + msg, status_code=302)


@router.get("/training/harass/{target_id}")
async def do_harass(request: Request, target_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect

    target = db.query(JingwuRole).filter(JingwuRole.id == target_id).first()
    if not target:
        return RedirectResponse(url="/jingwutang/training", status_code=302)

    success, msg = harass_target(ctx["user"].jw_role, target, db)
    return RedirectResponse(url="/jingwutang/training?msg=" + msg, status_code=302)


@router.get("/training/treat")
async def do_treat(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect

    success, msg = treat_possession(ctx["user"].jw_role, db)
    return RedirectResponse(url="/jingwutang/training?msg=" + msg, status_code=302)


# ============================================================
# 4. 技能系统 /jingwutang/skills
# ============================================================

@router.get("/skills", response_class=HTMLResponse)
async def skills_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect

    role = ctx["user"].jw_role

    # 所有可学技能（商店）
    all_skills = db.query(JingwuSkill).order_by(JingwuSkill.req_level, JingwuSkill.price_sp).all()

    # 已学技能
    learned_ids = [us.skill_id for us in role.user_skills]
    equipped_ids = list(role.skill_pool or [])

    # 分类
    skills_by_type = {"attack": [], "control": [], "heal": [], "counter": [], "buff": [], "drain": []}
    for s in all_skills:
        skills_by_type.setdefault(s.skill_type, []).append({
            "skill": s,
            "learned": s.id in learned_ids,
            "equipped": s.id in equipped_ids,
            "can_learn": (role.level >= s.req_level and role.gcoin >= s.price_gcoin
                          and role.skill_points >= s.price_sp and s.id not in learned_ids),
        })

    # 已装配技能详情
    equipped_skills = []
    for us in role.user_skills:
        if us.is_equipped:
            equipped_skills.append(us)

    type_names = {
        "attack": "⚔️ 攻击技能",
        "control": "🔒 控制技能",
        "heal": "💚 回血技能",
        "counter": "🔔 反弹技能",
        "buff": "✨ 增益技能",
        "drain": "🌀 吸血技能",
    }

    ctx.update({
        "role": role,
        "stats": ctx["stats"],
        "skills_by_type": skills_by_type,
        "type_names": type_names,
        "equipped_skills": equipped_skills,
        "equipped_count": len(equipped_ids),
        "max_pool": 10,
        "learned_count": len(learned_ids),
    })
    return templates.TemplateResponse("jingwutang/skills.html", ctx)


@router.get("/skills/learn/{skill_id}")
async def do_learn_skill(request: Request, skill_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect

    learn_skill(ctx["user"].jw_role, skill_id, db)
    return RedirectResponse(url="/jingwutang/skills", status_code=302)


@router.get("/skills/toggle/{user_skill_id}")
async def do_toggle_skill(request: Request, user_skill_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect

    toggle_skill_equip(ctx["user"].jw_role, user_skill_id, db)
    return RedirectResponse(url="/jingwutang/skills", status_code=302)


# ============================================================
# 5. 比武系统 /jingwutang/arena
# ============================================================

@router.get("/arena", response_class=HTMLResponse)
async def arena_page(
    request: Request,
    friend_only: int = 0,
    db: Session = Depends(get_db)
):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect

    role = ctx["user"].jw_role

    # 匹配对手
    if friend_only and ctx["user"].friends:
        friend_ids = [f.id for f in ctx["user"].friends]
        opponents = db.query(JingwuRole).filter(
            JingwuRole.user_id.in_(friend_ids),
            JingwuRole.id != role.id,
        ).order_by(func.random()).limit(10).all()
    else:
        opponents = db.query(JingwuRole).filter(
            JingwuRole.user_id != ctx["user"].id,
            JingwuRole.level >= role.level - 5,
            JingwuRole.level <= role.level + 10
        ).order_by(func.random()).limit(10).all()

    if len(opponents) < 3:
        opponents = db.query(JingwuRole).filter(
            JingwuRole.user_id != ctx["user"].id
        ).order_by(func.random()).limit(10).all()

    # 组装对手数据
    opponent_data = []
    for opp in opponents:
        opp_stats = calculate_stats(opp)
        opp_pet = get_active_pet(opp)
        opponent_data.append({
            "role": opp,
            "stats": opp_stats,
            "combat_power": calculate_combat_power(opp),
            "active_pet": opp_pet,
            "title": next((t["name"] for t in TITLE_CONFIGS if opp.level >= t["req_level"]), "武林新丁"),
        })

    ctx.update({
        "role": role,
        "stats": ctx["stats"],
        "opponents": opponent_data,
        "friend_only": friend_only,
        "has_friends": len(ctx["user"].friends) > 0 if ctx["user"].friends else False,
        "can_battle": role.sp >= 10,
        "combat_power": role.combat_power,
    })
    return templates.TemplateResponse("jingwutang/arena.html", ctx)


@router.get("/battle/{opponent_id}")
async def battle(request: Request, opponent_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect

    attacker = ctx["user"].jw_role
    defender = db.query(JingwuRole).filter(JingwuRole.id == opponent_id).first()

    if not defender or defender.id == attacker.id:
        return RedirectResponse(url="/jingwutang/arena", status_code=302)

    if attacker.sp < 10:
        ctx["error"] = "体力不足！需要10点体力才能比武"
        return RedirectResponse(url="/jingwutang/arena", status_code=302)

    result = simulate_battle(attacker, defender, db)

    ctx.update({
        "role": attacker,
        "opponent": defender,
        "stats": calculate_stats(attacker),
        "opp_stats": calculate_stats(defender),
        "result": result,
        "battle_log": result["log_list"] if isinstance(result["log"], str) else result["log"].split("\n"),
        "is_win": result["winner"] == attacker,
    })
    return templates.TemplateResponse("jingwutang/battle.html", ctx)


@router.get("/refresh-opponents")
async def refresh_opponents(request: Request, db: Session = Depends(get_db)):
    return RedirectResponse(url="/jingwutang/arena", status_code=302)


# ============================================================
# 6. 闻香炉（体力恢复）
# ============================================================

@router.get("/xianglu", response_class=HTMLResponse)
async def xianglu_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect

    role = ctx["user"].jw_role
    msg = request.query_params.get("msg")

    # 获取帮派香炉信息
    gang = None
    xianglu = None
    my_fire = 0
    used_today = 0
    max_uses_per_day = 3
    restore_sp = 30 + role.xianglu_level * 10
    remaining_time = "香炉未点燃"
    can_add_fire = False
    can_wenxiang = role.sp < role.max_sp and used_today < max_uses_per_day

    if role.gang_id:
        from models.models import JingwuGang, JingwuGangMember
        gang = db.query(JingwuGang).filter(JingwuGang.id == role.gang_id).first()
        if gang:
            xianglu = gang  # 帮派就是香炉持有者
            # 简化：根据帮派灵气显示火量
            fire_count = min(10, max(0, gang.incense_energy // 100))
            my_fire = 0  # 简化
            can_add_fire = True
            restore_sp = 20 + fire_count * 3  # 火量越多恢复越多
            remaining_time = "正在燃烧"

    ctx.update({
        "role": role,
        "stats": ctx["stats"],
        "combat_power": role.combat_power,
        "xianglu": xianglu,
        "gang": gang,
        "my_fire": my_fire,
        "used_today": used_today,
        "max_uses_per_day": max_uses_per_day,
        "restore_sp": restore_sp,
        "remaining_time": remaining_time,
        "can_add_fire": can_add_fire,
        "can_wenxiang": can_wenxiang,
    })
    if msg:
        ctx["status_msg"] = msg
    return templates.TemplateResponse("jingwutang/xianglu.html", ctx)


@router.get("/xianglu/wenxiang")
async def do_wenxiang(request: Request, db: Session = Depends(get_db)):
    """闻香恢复体力"""
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect
    role = ctx["user"].jw_role
    success, msg = use_xianglu(role, db)
    return RedirectResponse(url="/jingwutang/xianglu?msg=" + msg, status_code=302)


@router.get("/xianglu/add_fire")
async def do_add_fire(request: Request, db: Session = Depends(get_db)):
    """给帮派香炉加火"""
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect
    role = ctx["user"].jw_role
    if role.gang_id:
        from models.models import JingwuGang
        gang = db.query(JingwuGang).filter(JingwuGang.id == role.gang_id).first()
        if gang:
            gang.incense_energy = min(gang.incense_max_energy, gang.incense_energy + 100)
            # 加火者恢复10体力
            role.sp = min(role.max_sp, role.sp + 10)
            db.commit()
            msg = "加火成功！恢复10点体力，帮派成员闻香效果提升"
        else:
            msg = "你还没有帮派"
    else:
        msg = "你还没有帮派"
    return RedirectResponse(url="/jingwutang/xianglu?msg=" + msg, status_code=302)


# ============================================================
# 7. 宠物系统 /jingwutang/pet
# ============================================================

@router.get("/pet", response_class=HTMLResponse)
async def pet_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect

    role = ctx["user"].jw_role
    pet_templates = db.query(JingwuPetTemplate).all()
    pet_tpl_data = []
    for pt in pet_templates:
        owned = any(p.pet_code == pt.pet_code for p in role.pets)
        pet_tpl_data.append({
            "template": pt,
            "owned": owned,
            "can_buy": role.gcoin >= pt.price_gcoin and not owned,
        })

    ctx.update({
        "role": role,
        "stats": ctx["stats"],
        "pets": role.pets,
        "pet_templates": pet_tpl_data,
        "active_pet": get_active_pet(role),
    })
    return templates.TemplateResponse("jingwutang/pet.html", ctx)


@router.get("/pet/buy/{pet_code}")
async def do_buy_pet(request: Request, pet_code: str, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect
    buy_pet(ctx["user"].jw_role, pet_code, db)
    return RedirectResponse(url="/jingwutang/pet", status_code=302)


@router.get("/pet/battle/{pet_id}")
async def do_pet_battle(request: Request, pet_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect
    toggle_pet_battle(ctx["user"].jw_role, pet_id, db)
    return RedirectResponse(url="/jingwutang/pet", status_code=302)


@router.get("/pet/possess/{pet_id}")
async def do_pet_possess(request: Request, pet_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect
    toggle_pet_possess(ctx["user"].jw_role, pet_id, db)
    return RedirectResponse(url="/jingwutang/pet", status_code=302)


# ============================================================
# 8. 帮派系统
# ============================================================

@router.get("/gang", response_class=HTMLResponse)
async def gang_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect

    role = ctx["user"].jw_role
    from models.models import JingwuGang, JingwuGangMember

    gang = None
    leader_name = ""
    member_count = 0
    is_leader = False
    my_gang_member = None

    if role.gang_id:
        gang = db.query(JingwuGang).filter(JingwuGang.id == role.gang_id).first()
        if gang:
            member_count = db.query(JingwuGangMember).filter(
                JingwuGangMember.gang_id == gang.id
            ).count()
            leader = db.query(JingwuRole).filter(JingwuRole.id == gang.leader_id).first()
            leader_name = leader.name if leader else "未知"
            is_leader = (gang.leader_id == role.id)
            my_gang_member = db.query(JingwuGangMember).filter(
                JingwuGangMember.gang_id == gang.id,
                JingwuGangMember.role_id == role.id
            ).first()

    # 帮派列表（未加入时显示）
    gangs = []
    if not gang:
        gangs = db.query(JingwuGang).filter(JingwuGang.status == 1).order_by(
            desc(JingwuGang.level), desc(JingwuGang.member_count)
        ).limit(20).all()
        for g in gangs:
            g.member_count = db.query(JingwuGangMember).filter(JingwuGangMember.gang_id == g.id).count()

    ctx.update({
        "role": role,
        "stats": ctx["stats"],
        "combat_power": role.combat_power,
        "gang": gang,
        "leader_name": leader_name,
        "member_count": member_count,
        "is_leader": is_leader,
        "gangs": gangs,
    })
    return templates.TemplateResponse("jingwutang/gang.html", ctx)


@router.get("/gang/join/{gang_id}")
async def gang_join(request: Request, gang_id: int, db: Session = Depends(get_db)):
    from models.models import JingwuGang, JingwuGangMember
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect
    role = ctx["user"].jw_role
    if role.gang_id:
        return RedirectResponse(url="/jingwutang/gang", status_code=302)
    gang = db.query(JingwuGang).filter(JingwuGang.id == gang_id, JingwuGang.status == 1).first()
    if not gang:
        return RedirectResponse(url="/jingwutang/gang", status_code=302)
    # 检查入帮费
    if role.gcoin < (gang.join_gcoin_fee or 0):
        return RedirectResponse(url="/jingwutang/gang?msg=G币不足", status_code=302)
    if role.level < (gang.join_level_required or 1):
        return RedirectResponse(url="/jingwutang/gang?msg=等级不足", status_code=302)
    role.gcoin -= (gang.join_gcoin_fee or 0)
    role.gang_id = gang.id
    db.add(JingwuGangMember(
        gang_id=gang.id, user_id=ctx["user"].id, role_id=role.id,
        role_name="member", nickname=role.name,
    ))
    gang.member_count = (gang.member_count or 1) + 1
    db.commit()
    return RedirectResponse(url="/jingwutang/gang", status_code=302)


@router.post("/gang/create")
async def gang_create(request: Request, name: str = Form(...), db: Session = Depends(get_db)):
    from models.models import JingwuGang, JingwuGangMember
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect
    role = ctx["user"].jw_role
    if role.gang_id:
        return RedirectResponse(url="/jingwutang/gang", status_code=302)
    if role.gcoin < 5000:
        return RedirectResponse(url="/jingwutang/gang?msg=G币不足", status_code=302)
    if not name or len(name.strip()) < 1 or len(name) > 12:
        return RedirectResponse(url="/jingwutang/gang?msg=帮派名称不合法", status_code=302)
    existing = db.query(JingwuGang).filter(JingwuGang.name == name.strip()).first()
    if existing:
        return RedirectResponse(url="/jingwutang/gang?msg=帮派名已存在", status_code=302)
    role.gcoin -= 5000
    gang = JingwuGang(
        name=name.strip(), leader_id=role.id, leader_name=role.name,
        member_count=1, level=1, funds=0, status=1,
    )
    db.add(gang)
    db.flush()
    role.gang_id = gang.id
    db.add(JingwuGangMember(
        gang_id=gang.id, user_id=ctx["user"].id, role_id=role.id,
        role_name="leader", nickname=role.name,
    ))
    db.commit()
    return RedirectResponse(url="/jingwutang/gang", status_code=302)


@router.get("/gang/leave")
async def gang_leave(request: Request, db: Session = Depends(get_db)):
    from models.models import JingwuGang, JingwuGangMember
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect
    role = ctx["user"].jw_role
    if not role.gang_id:
        return RedirectResponse(url="/jingwutang/gang", status_code=302)
    gang = db.query(JingwuGang).filter(JingwuGang.id == role.gang_id).first()
    if gang and gang.leader_id == role.id:
        return RedirectResponse(url="/jingwutang/gang?msg=帮主不能退出帮派，请先转让或解散", status_code=302)
    member = db.query(JingwuGangMember).filter(
        JingwuGangMember.gang_id == role.gang_id, JingwuGangMember.role_id == role.id
    ).first()
    if member:
        db.delete(member)
    role.gang_id = None
    if gang:
        gang.member_count = max(0, (gang.member_count or 1) - 1)
    db.commit()
    return RedirectResponse(url="/jingwutang/gang", status_code=302)


@router.get("/gang/disband")
async def gang_disband(request: Request, db: Session = Depends(get_db)):
    from models.models import JingwuGang, JingwuGangMember
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect
    role = ctx["user"].jw_role
    if not role.gang_id:
        return RedirectResponse(url="/jingwutang/gang", status_code=302)
    gang = db.query(JingwuGang).filter(JingwuGang.id == role.gang_id).first()
    if not gang or gang.leader_id != role.id:
        return RedirectResponse(url="/jingwutang/gang", status_code=302)
    # 解散：移除所有成员
    members = db.query(JingwuGangMember).filter(JingwuGangMember.gang_id == gang.id).all()
    for m in members:
        if m.role:
            m.role.gang_id = None
        db.delete(m)
    db.delete(gang)
    role.gang_id = None
    db.commit()
    return RedirectResponse(url="/jingwutang/gang", status_code=302)


# ============================================================
# 9. 装备/背包/锻造/法宝/武魂/北极星/副本（保留旧路由，兼容现有模板）
# ============================================================

@router.get("/inventory", response_class=HTMLResponse)
async def inventory(request: Request, category: str = "all", db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect
    role = ctx["user"].jw_role
    categories = ["equipment", "prop", "gem", "shenbing", "blueprint", "mold", "material", "other"]
    category_names = {
        "equipment": "装备", "prop": "道具", "gem": "宝石", "shenbing": "神兵",
        "blueprint": "图纸", "mold": "模具", "material": "材料", "other": "其他",
    }
    if category != "all":
        items = [i for i in role.items if i.item_type == category or i.category == category]
    else:
        items = list(role.items)
    ctx.update({
        "role": role, "items": items, "current_category": category,
        "categories": categories, "category_names": category_names,
        "total_items": len(list(role.items)), "max_items": 480,
    })
    return templates.TemplateResponse("jingwutang/inventory.html", ctx)


@router.get("/item/use/{item_id}")
async def do_use_item(request: Request, item_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect
    use_item(ctx["user"].jw_role, item_id, db)
    return RedirectResponse(url="/jingwutang/inventory", status_code=302)


@router.get("/equipment", response_class=HTMLResponse)
async def equipment_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect
    role = ctx["user"].jw_role
    equipped = {}
    unequipped = []
    for eq in role.equipments:
        if eq.is_equipped:
            equipped[eq.slot] = eq
        else:
            unequipped.append(eq)
    ctx.update({
        "role": role, "equipped": equipped, "unequipped": unequipped,
        "equipment_slots": EQUIPMENT_SLOTS, "quality_colors": QUALITY_COLORS,
        "stats": ctx["stats"],
    })
    return templates.TemplateResponse("jingwutang/equipment.html", ctx)


@router.get("/equipment/equip/{equip_id}")
async def do_equip(request: Request, equip_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect
    equip_item(ctx["user"].jw_role, equip_id, db)
    return RedirectResponse(url="/jingwutang/equipment", status_code=302)


@router.get("/forge", response_class=HTMLResponse)
async def forge_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect
    ctx.update({"role": ctx["user"].jw_role, "stats": ctx["stats"], "recipes": DIVINE_EQUIPMENT_RECIPES})
    return templates.TemplateResponse("jingwutang/forge.html", ctx)


@router.get("/fabao", response_class=HTMLResponse)
async def fabao_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect
    ctx.update({"role": ctx["user"].jw_role, "stats": ctx["stats"]})
    return templates.TemplateResponse("jingwutang/fabao.html", ctx)


@router.get("/wuhun", response_class=HTMLResponse)
async def wuhun_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect
    ctx.update({"role": ctx["user"].jw_role, "stats": ctx["stats"], "wuhun_data": []})
    return templates.TemplateResponse("jingwutang/wuhun.html", ctx)


@router.get("/polaris", response_class=HTMLResponse)
async def polaris_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect
    ctx.update({"role": ctx["user"].jw_role, "stats": ctx["stats"], "polaris_stars": POLARIS_STARS})
    return templates.TemplateResponse("jingwutang/polaris.html", ctx)


@router.get("/dungeon", response_class=HTMLResponse)
async def dungeon_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect
    role = ctx["user"].jw_role
    dungeon = db.query(JingwuDungeon).filter(JingwuDungeon.role_id == role.id).first()
    ctx.update({"role": role, "stats": ctx["stats"], "dungeon": dungeon, "stages": DUNGEON_STAGES})
    return templates.TemplateResponse("jingwutang/dungeon.html", ctx)


@router.get("/dungeon/fight/{stage_id}")
async def dungeon_fight(request: Request, stage_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect
    role = ctx["user"].jw_role
    dungeon = db.query(JingwuDungeon).filter(JingwuDungeon.role_id == role.id).first()
    stage = next((s for s in DUNGEON_STAGES if s["id"] == stage_id), None)
    if not stage or role.level < stage["level_req"]:
        return RedirectResponse(url="/jingwutang/dungeon", status_code=302)
    if dungeon and dungeon.daily_attempts <= 0:
        return RedirectResponse(url="/jingwutang/dungeon", status_code=302)

    if dungeon:
        dungeon.daily_attempts -= 1

    boss_role = JingwuRole(name=stage["boss"], level=stage["level_req"] + 5)
    boss_role.max_hp = 500 + stage["level_req"] * 100
    boss_role.hp = boss_role.max_hp
    boss_role.damage = 20 + stage["level_req"] * 3
    boss_role.base_damage = boss_role.damage
    boss_role.defense = 10 + stage["level_req"] * 2
    boss_role.base_defense = boss_role.defense
    boss_role.speed = 15 + stage["level_req"]
    boss_role.base_speed = boss_role.speed
    boss_role.base_dodge = 30
    boss_role.base_crit = 10
    boss_role.accuracy = 100
    boss_role.dodge = 30
    boss_role.crit = 10
    boss_role.crit_damage = 150
    boss_role.user = ctx["user"]
    boss_role.con_point = boss_role.int_point = boss_role.str_point = 0
    boss_role.end_point = boss_role.agi_point = 0
    boss_role.equipments = []
    boss_role.pets = []
    boss_role.skill_pool = []
    boss_role.user_skills = []

    result = simulate_battle(role, boss_role, db, is_dungeon=True)

    if result["winner"] == role and dungeon:
        dungeon.stage = min(dungeon.stage + 1, len(DUNGEON_STAGES))
    db.commit()

    ctx.update({
        "role": role, "stats": ctx["stats"], "stage": stage,
        "result": result, "battle_log": result.get("log_list", result["log"].split("\n") if isinstance(result["log"], str) else []),
    })
    return templates.TemplateResponse("jingwutang/dungeon_battle.html", ctx)


# ============================================================
# 10. 别名/便捷路由
# ============================================================

@router.get("/sign")
async def daily_sign(request: Request, db: Session = Depends(get_db)):
    """每日签到"""
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect
    role = ctx["user"].jw_role
    # 简单签到奖励
    role.gcoin = (role.gcoin or 0) + 100
    role.sp = min(role.max_sp, role.sp + 20)
    role.skill_points = (role.skill_points or 0) + 1
    db.commit()
    return RedirectResponse(url="/jingwutang/?msg=签到成功！获得100G币+20体力+1技能点", status_code=302)


@router.get("/shop")
async def shop_redirect(request: Request, db: Session = Depends(get_db)):
    return RedirectResponse(url="/jingwutang/polaris", status_code=302)


@router.get("/talisman")
async def talisman_redirect(request: Request, db: Session = Depends(get_db)):
    return RedirectResponse(url="/jingwutang/fabao", status_code=302)


@router.get("/rank", response_class=HTMLResponse)
async def rank_page(request: Request, db: Session = Depends(get_db)):
    """战力排行榜"""
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    redirect = require_character(ctx, db)
    if redirect:
        return redirect
    role = ctx["user"].jw_role
    # 获取战力排行前50
    top_roles = db.query(JingwuRole).order_by(desc(JingwuRole.combat_power)).limit(50).all()
    # 我的排名
    my_rank = db.query(JingwuRole).filter(JingwuRole.combat_power > role.combat_power).count() + 1
    rank_list = []
    for i, r in enumerate(top_roles):
        rank_list.append({
            "rank": i + 1,
            "role": r,
            "name": r.name,
            "level": r.level,
            "combat_power": r.combat_power,
            "is_me": r.id == role.id,
        })
    ctx.update({
        "role": role,
        "stats": ctx["stats"],
        "combat_power": role.combat_power,
        "rank_list": rank_list,
        "my_rank": my_rank,
    })
    return templates.TemplateResponse("jingwutang/rank.html", ctx)


@router.get("/create-role")
async def create_role_redirect(request: Request, db: Session = Depends(get_db)):
    return RedirectResponse(url="/jingwutang/create", status_code=302)
