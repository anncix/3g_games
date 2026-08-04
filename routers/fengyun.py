"""风云三国模块（v0.1.9，精简版）

老味道点：三职业 / 三阵营 / 技能装备 / 副本挑战 / 军团社交 / 演武挂机
核心循环：演武/副本 → 获得经验银两 → 升级换装 → 学技能 → 挑战更高副本 → 继续养成

本路由为 qqgames 最小实现：认证走 get_current_user，银两映射到 Wallet.silver_coin
（用 change_currency），模板渲染走 templates/fengyun/*.html。
"""
import random
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from models.database import get_db
from models.models import (
    User, FengyunState, FengyunSkill, FengyunUserSkill, FengyunEquip,
    FengyunUserEquip, FengyunDungeon, FengyunLegion, FengyunLegionMember,
    FengyunTitle, FengyunAchievement, FengyunCity,
)
from utils.auth import get_current_user
from utils.common import change_currency
from routers import fengyun_data as FY

router = APIRouter(prefix="/games/fengyun", tags=["fengyun"])
templates = Jinja2Templates(directory="templates")

MODULE_KEY = "fengyun"
SILVER_CURRENCY = "silver_coin"  # 风云银两映射到钱包 silver_coin

# 演武基础收益（每小时）
TRAINING_EXP_PER_HOUR = 300
TRAINING_SILVER_PER_HOUR = 150

# 阵营默认主城
FACTION_CITY = {"wei": "xuchang_z", "shu": "chengdu", "wu": "jianye"}


# ============================================================
# 辅助函数
# ============================================================
def get_state(db: Session, user_id: int) -> FengyunState:
    st = db.query(FengyunState).filter(FengyunState.user_id == user_id).first()
    if not st:
        st = FengyunState(user_id=user_id)
        db.add(st)
        db.commit()
        db.refresh(st)
    return st


def calc_player_power(st: FengyunState) -> int:
    """简易战力：由属性 + 等级估算"""
    return int(st.hp * 0.2 + st.mp * 0.1 + st.atk * 2 + st.defense * 1.5
               + st.dodge * 1.5 + st.crit * 1.5 + st.level * 5)


def add_exp(st: FengyunState, amount: int) -> bool:
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


def get_silver(db: Session, st: FengyunState) -> int:
    """读取当前银两（以玩家状态为准）"""
    return st.silver


def add_silver(db: Session, user_id: int, st: FengyunState, amount: int, remark: str = ""):
    """银两变动：同步状态 + 钱包 silver_coin（走 change_currency 记流水）"""
    st.silver += amount
    change_currency(user_id, SILVER_CURRENCY, amount, MODULE_KEY, remark=remark, db=db)


def _has_any_skill(db: Session, user_id: int) -> bool:
    return db.query(FengyunUserSkill).filter(FengyunUserSkill.user_id == user_id).first() is not None


def _is_fresh(db: Session, st: FengyunState) -> bool:
    """未选择职业：1级0经验且未学任何技能"""
    return st.level == 1 and st.exp == 0 and not _has_any_skill(db, st.user_id)


def _learned_skills(db: Session, user_id: int) -> dict:
    return {s.skill_key: s.level for s in db.query(FengyunUserSkill).filter(
        FengyunUserSkill.user_id == user_id).all()}


def _def_map(db: Session) -> dict:
    return {e.key: e for e in db.query(FengyunEquip).all()}


def _require_user(request: Request, db: Session):
    user = get_current_user(request, db)
    if not user:
        return None
    return user


# ============================================================
# 首页
# ============================================================
@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    need_create = _is_fresh(db, st)
    power = calc_player_power(st)
    exp_need = FY.exp_needed(st.level)
    now = datetime.utcnow()
    training_ready = bool(st.training_end_at and now >= st.training_end_at)
    city = db.query(FengyunCity).filter(FengyunCity.key == st.current_city).first()
    city_name = city.name if city else st.current_city
    todo = []
    if need_create:
        todo.append(("请先选择职业与阵营", "前往创建", "/games/fengyun/create"))
    if training_ready:
        todo.append(("演武收益待领取", "前往演武", "/games/fengyun/training"))
    db.commit()
    return templates.TemplateResponse("fengyun/home.html", {
        "request": request, "user": user, "st": st, "power": power,
        "exp_need": exp_need, "need_create": need_create, "city_name": city_name,
        "training_ready": training_ready,
        "class_name": FY.CLASS_NAMES.get(st.class_key, st.class_key),
        "faction_name": FY.FACTION_NAMES.get(st.faction, st.faction),
        "silver": get_silver(db, st), "todo": todo,
    })


# ============================================================
# 职业与阵营选择
# ============================================================
@router.get("/create", response_class=HTMLResponse)
async def create_page(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    db.commit()
    return templates.TemplateResponse("fengyun/create.html", {
        "request": request, "user": user, "st": st,
        "classes": FY.CLASSES, "factions": FY.FACTIONS,
        "base_attrs": FY.CLASS_BASE_ATTRS,
    })


@router.post("/create", response_class=HTMLResponse)
async def create_submit(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    form = await request.form()
    class_key = (form.get("class_key") or "").strip()
    faction = (form.get("faction") or "").strip()
    if class_key not in FY.CLASS_BASE_ATTRS:
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False, "msg": "职业选择非法",
            "back_href": "/games/fengyun/create", "back_text": "返回"})
    if faction not in FY.FACTION_NAMES:
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False, "msg": "阵营选择非法",
            "back_href": "/games/fengyun/create", "back_text": "返回"})
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
    st.silver = 1000
    st.current_city = FACTION_CITY.get(faction, "chengdu")
    db.commit()
    return RedirectResponse(url="/games/fengyun", status_code=303)


# ============================================================
# 城市系统
# ============================================================
@router.get("/cities", response_class=HTMLResponse)
async def cities_page(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    cities = db.query(FengyunCity).order_by(FengyunCity.faction, FengyunCity.key).all()
    db.commit()
    return templates.TemplateResponse("fengyun/cities.html", {
        "request": request, "user": user, "st": st, "cities": cities,
        "faction_names": FY.FACTION_NAMES,
    })


# ============================================================
# 技能系统
# ============================================================
@router.get("/skills", response_class=HTMLResponse)
async def skills_page(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    learned = _learned_skills(db, user.id)
    skills = db.query(FengyunSkill).filter(
        FengyunSkill.class_key == st.class_key).order_by(FengyunSkill.unlock_level).all()
    skill_list = []
    for sk in skills:
        skill_list.append({
            "key": sk.key, "name": sk.name, "skill_type": sk.skill_type,
            "unlock_level": sk.unlock_level, "cost_silver": sk.cost_silver,
            "cost_exp": sk.cost_exp, "effect": sk.effect,
            "level": learned.get(sk.key, 0),
            "can_learn": st.level >= sk.unlock_level and sk.key not in learned,
        })
    db.commit()
    return templates.TemplateResponse("fengyun/skills.html", {
        "request": request, "user": user, "st": st, "skill_list": skill_list,
        "class_name": FY.CLASS_NAMES.get(st.class_key, st.class_key),
        "silver": get_silver(db, st), "exp_need": FY.exp_needed(st.level),
    })


@router.post("/skills/learn/{skill_key}", response_class=HTMLResponse)
async def skill_learn(skill_key: str, request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    sk = db.query(FengyunSkill).filter(FengyunSkill.key == skill_key).first()
    if not sk or sk.class_key != st.class_key:
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False, "msg": "技能不存在或不属于你的职业",
            "back_href": "/games/fengyun/skills", "back_text": "返回技能"})
    if st.level < sk.unlock_level:
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False, "msg": f"等级不足，需{sk.unlock_level}级",
            "back_href": "/games/fengyun/skills", "back_text": "返回技能"})
    learned = _learned_skills(db, user.id)
    if skill_key in learned:
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False, "msg": "已学习该技能",
            "back_href": "/games/fengyun/skills", "back_text": "返回技能"})
    if st.silver < sk.cost_silver:
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False, "msg": f"银两不足（需{sk.cost_silver}）",
            "back_href": "/games/fengyun/skills", "back_text": "返回技能"})
    if st.exp < sk.cost_exp:
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False, "msg": f"经验不足（需{sk.cost_exp}）",
            "back_href": "/games/fengyun/skills", "back_text": "返回技能"})
    add_silver(db, user.id, st, -sk.cost_silver, remark=f"learn skill {skill_key}")
    st.exp -= sk.cost_exp
    db.add(FengyunUserSkill(user_id=user.id, skill_key=skill_key, level=1))
    db.commit()
    return templates.TemplateResponse("fengyun/result.html", {
        "request": request, "user": user, "ok": True, "msg": f"学会《{sk.name}》",
        "back_href": "/games/fengyun/skills", "back_text": "返回技能"})


# ============================================================
# 装备系统
# ============================================================
@router.get("/equip", response_class=HTMLResponse)
async def equip_page(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    all_equips = db.query(FengyunUserEquip).filter(
        FengyunUserEquip.user_id == user.id).order_by(FengyunUserEquip.id.desc()).all()
    equipped = [e for e in all_equips if e.equipped]
    bag_equips = [e for e in all_equips if not e.equipped]
    slot_map = {s: None for s in FY.EQUIP_SLOTS}
    for e in equipped:
        slot_map[e.slot] = e
    # 商店列表（按等级/品质）
    shop_list = db.query(FengyunEquip).order_by(
        FengyunEquip.level_req, FengyunEquip.quality).all()
    shop_list = [e for e in shop_list if not e.class_req or e.class_req == st.class_key][:40]
    def_map = _def_map(db)
    power = calc_player_power(st)
    db.commit()
    return templates.TemplateResponse("fengyun/equip.html", {
        "request": request, "user": user, "st": st, "slot_map": slot_map,
        "bag_equips": bag_equips, "def_map": def_map, "shop_list": shop_list,
        "power": power, "slots": FY.EQUIP_SLOTS, "silver": get_silver(db, st),
    })


@router.post("/equip/buy/{equip_key}", response_class=HTMLResponse)
async def equip_buy(equip_key: str, request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    e = db.query(FengyunEquip).filter(FengyunEquip.key == equip_key).first()
    if not e:
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False, "msg": "商品不存在",
            "back_href": "/games/fengyun/equip", "back_text": "返回装备"})
    if e.class_req and e.class_req != st.class_key:
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False, "msg": "职业不符，无法购买",
            "back_href": "/games/fengyun/equip", "back_text": "返回装备"})
    if st.level < e.level_req:
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False, "msg": f"等级不足，需{e.level_req}级",
            "back_href": "/games/fengyun/equip", "back_text": "返回装备"})
    if st.silver < e.price:
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False, "msg": f"银两不足（需{e.price}）",
            "back_href": "/games/fengyun/equip", "back_text": "返回装备"})
    add_silver(db, user.id, st, -e.price, remark=f"buy equip {equip_key}")
    db.add(FengyunUserEquip(user_id=user.id, equip_key=equip_key, slot=e.slot, equipped=False))
    db.commit()
    return templates.TemplateResponse("fengyun/result.html", {
        "request": request, "user": user, "ok": True, "msg": f"购得《{e.name}》",
        "back_href": "/games/fengyun/equip", "back_text": "返回装备"})


@router.post("/equip/wear/{user_equip_id}", response_class=HTMLResponse)
async def equip_wear(user_equip_id: int, request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    e = db.query(FengyunUserEquip).filter(FengyunUserEquip.id == user_equip_id).first()
    if not e or e.user_id != user.id:
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False, "msg": "装备不存在",
            "back_href": "/games/fengyun/equip", "back_text": "返回装备"})
    for old in db.query(FengyunUserEquip).filter(
            FengyunUserEquip.user_id == user.id,
            FengyunUserEquip.slot == e.slot,
            FengyunUserEquip.equipped == True).all():
        old.equipped = False
    e.equipped = True
    db.commit()
    return templates.TemplateResponse("fengyun/result.html", {
        "request": request, "user": user, "ok": True, "msg": f"已穿戴 {e.slot} 部位装备",
        "back_href": "/games/fengyun/equip", "back_text": "返回装备"})


@router.post("/equip/takeoff/{user_equip_id}", response_class=HTMLResponse)
async def equip_takeoff(user_equip_id: int, request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    e = db.query(FengyunUserEquip).filter(FengyunUserEquip.id == user_equip_id).first()
    if not e or e.user_id != user.id:
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False, "msg": "装备不存在",
            "back_href": "/games/fengyun/equip", "back_text": "返回装备"})
    e.equipped = False
    db.commit()
    return templates.TemplateResponse("fengyun/result.html", {
        "request": request, "user": user, "ok": True, "msg": "已卸下",
        "back_href": "/games/fengyun/equip", "back_text": "返回装备"})


# ============================================================
# 副本系统
# ============================================================
@router.get("/dungeons", response_class=HTMLResponse)
async def dungeons_page(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    all_dg = db.query(FengyunDungeon).order_by(FengyunDungeon.level_min).all()
    dungeon_list = [d for d in all_dg if d.faction == "all" or d.faction == st.faction]
    city_keys = {d.city for d in dungeon_list}
    cities = {}
    for ck in city_keys:
        c = db.query(FengyunCity).filter(FengyunCity.key == ck).first()
        cities[ck] = c.name if c else ck
    db.commit()
    return templates.TemplateResponse("fengyun/dungeons.html", {
        "request": request, "user": user, "st": st, "dungeon_list": dungeon_list,
        "cities": cities, "faction_name": FY.FACTION_NAMES.get(st.faction, st.faction),
    })


@router.post("/dungeon/{dungeon_key}", response_class=HTMLResponse)
async def dungeon_challenge(dungeon_key: str, request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    dg = db.query(FengyunDungeon).filter(FengyunDungeon.key == dungeon_key).first()
    if not dg:
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False, "msg": "副本不存在",
            "back_href": "/games/fengyun/dungeons", "back_text": "返回副本"})
    if dg.faction != "all" and dg.faction != st.faction:
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False, "msg": "阵营不符，无法挑战",
            "back_href": "/games/fengyun/dungeons", "back_text": "返回副本"})
    if st.level < dg.level_min:
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False, "msg": f"等级不足，需{dg.level_min}级",
            "back_href": "/games/fengyun/dungeons", "back_text": "返回副本"})
    my_power = calc_player_power(st)
    enemy_power = dg.level_max * 30 + dg.reward_exp // 10
    prob = 0.5 + (my_power - enemy_power) / max(my_power + enemy_power, 1)
    prob = max(0.1, min(0.9, prob))
    win = random.random() < prob
    if win:
        add_silver(db, user.id, st, dg.reward_silver, remark=f"dungeon win {dungeon_key}")
        leveled = add_exp(st, dg.reward_exp)
        db.commit()
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": True, "msg":
                f"挑战《{dg.name}》胜利！经验+{dg.reward_exp}，银两+{dg.reward_silver}"
                f"{'，升级了！' if leveled else ''}",
            "back_href": "/games/fengyun/dungeons", "back_text": "返回副本"})
    db.commit()
    return templates.TemplateResponse("fengyun/result.html", {
        "request": request, "user": user, "ok": False, "msg": f"挑战《{dg.name}》失败，再接再厉",
        "back_href": "/games/fengyun/dungeons", "back_text": "返回副本"})


# ============================================================
# 演武系统
# ============================================================
@router.get("/training", response_class=HTMLResponse)
async def training_page(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
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
    db.commit()
    return templates.TemplateResponse("fengyun/training.html", {
        "request": request, "user": user, "st": st, "ready": ready,
        "seconds_left": seconds_left, "is_monday": is_monday,
        "exp_yield": exp_yield, "silver_yield": silver_yield,
        "max_hours": FY.TRAINING_MAX_HOURS,
    })


@router.post("/training/start", response_class=HTMLResponse)
async def training_start(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    now = datetime.utcnow()
    if st.training_end_at and now < st.training_end_at:
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False, "msg": "演武进行中，请等待结束",
            "back_href": "/games/fengyun/training", "back_text": "返回演武"})
    st.training_end_at = now + timedelta(hours=FY.TRAINING_MAX_HOURS)
    db.commit()
    return templates.TemplateResponse("fengyun/result.html", {
        "request": request, "user": user, "ok": True,
        "msg": f"开始演武，{FY.TRAINING_MAX_HOURS}小时后可领取收益",
        "back_href": "/games/fengyun/training", "back_text": "返回演武"})


@router.post("/training/claim", response_class=HTMLResponse)
async def training_claim(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    now = datetime.utcnow()
    if not st.training_end_at or now < st.training_end_at:
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False, "msg": "演武尚未结束，暂不可领取",
            "back_href": "/games/fengyun/training", "back_text": "返回演武"})
    is_monday = now.weekday() == 0
    exp_yield = TRAINING_EXP_PER_HOUR * FY.TRAINING_MAX_HOURS
    silver_yield = TRAINING_SILVER_PER_HOUR * FY.TRAINING_MAX_HOURS
    bonus = ""
    if is_monday:
        exp_yield *= FY.TRAINING_MONDAY_MULT
        bonus = "（周一10倍经验加成）"
    leveled = add_exp(st, exp_yield)
    add_silver(db, user.id, st, silver_yield, remark="training claim")
    st.training_end_at = None
    db.commit()
    return templates.TemplateResponse("fengyun/result.html", {
        "request": request, "user": user, "ok": True,
        "msg": f"领取演武收益：经验+{exp_yield}，银两+{silver_yield}{bonus}"
               f"{'，升级了！' if leveled else ''}",
        "back_href": "/games/fengyun/training", "back_text": "返回演武"})


# ============================================================
# 军团系统
# ============================================================
def _my_legion_member(db: Session, user_id: int):
    return db.query(FengyunLegionMember).filter(FengyunLegionMember.user_id == user_id).first()


@router.get("/legion", response_class=HTMLResponse)
async def legion_page(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    my_member = _my_legion_member(db, user.id)
    my_legion = None
    members = []
    if my_member:
        my_legion = db.query(FengyunLegion).filter(FengyunLegion.id == my_member.legion_id).first()
        if my_legion:
            for m in db.query(FengyunLegionMember).filter(FengyunLegionMember.legion_id == my_legion.id).all():
                mu = db.query(User).filter(User.id == m.user_id).first()
                ms = db.query(FengyunState).filter(FengyunState.user_id == m.user_id).first()
                members.append({"member": m, "user": mu, "state": ms})
    legion_list = db.query(FengyunLegion).limit(10).all()
    db.commit()
    return templates.TemplateResponse("fengyun/legion.html", {
        "request": request, "user": user, "st": st, "my_legion": my_legion,
        "my_member": my_member, "members": members, "legion_list": legion_list,
        "levels": FY.LEGION_LEVELS, "require": FY.LEGION_CREATE_REQUIRE,
        "silver": get_silver(db, st),
    })


@router.post("/legion/create", response_class=HTMLResponse)
async def legion_create(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    if _my_legion_member(db, user.id):
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False, "msg": "已加入军团，无法创建",
            "back_href": "/games/fengyun/legion", "back_text": "返回军团"})
    form = await request.form()
    name = (form.get("name") or "").strip()
    if not name or len(name) > 16:
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False, "msg": "军团名非法（1-16字）",
            "back_href": "/games/fengyun/legion", "back_text": "返回军团"})
    if st.level < FY.LEGION_CREATE_REQUIRE["leader_level"]:
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False,
            "msg": f"等级不足，需{FY.LEGION_CREATE_REQUIRE['leader_level']}级",
            "back_href": "/games/fengyun/legion", "back_text": "返回军团"})
    if st.silver < FY.LEGION_CREATE_REQUIRE["cost_silver"]:
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False,
            "msg": f"银两不足（需{FY.LEGION_CREATE_REQUIRE['cost_silver']}）",
            "back_href": "/games/fengyun/legion", "back_text": "返回军团"})
    exists = db.query(FengyunLegion).filter(FengyunLegion.name == name).first()
    if exists:
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False, "msg": "军团名已存在",
            "back_href": "/games/fengyun/legion", "back_text": "返回军团"})
    add_silver(db, user.id, st, -FY.LEGION_CREATE_REQUIRE["cost_silver"], remark="legion create")
    g = FengyunLegion(name=name, leader_id=user.id, level=1)
    db.add(g)
    db.flush()
    db.add(FengyunLegionMember(legion_id=g.id, user_id=user.id))
    db.commit()
    return templates.TemplateResponse("fengyun/result.html", {
        "request": request, "user": user, "ok": True, "msg": f"创建军团《{name}》成功！",
        "back_href": "/games/fengyun/legion", "back_text": "返回军团"})


@router.post("/legion/join/{legion_id}", response_class=HTMLResponse)
async def legion_join(legion_id: int, request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    if _my_legion_member(db, user.id):
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False, "msg": "已加入军团",
            "back_href": "/games/fengyun/legion", "back_text": "返回军团"})
    g = db.query(FengyunLegion).filter(FengyunLegion.id == legion_id).first()
    if not g:
        return templates.TemplateResponse("fengyun/result.html", {
            "request": request, "user": user, "ok": False, "msg": "军团不存在",
            "back_href": "/games/fengyun/legion", "back_text": "返回军团"})
    db.add(FengyunLegionMember(legion_id=legion_id, user_id=user.id))
    db.commit()
    return templates.TemplateResponse("fengyun/result.html", {
        "request": request, "user": user, "ok": True, "msg": f"加入军团《{g.name}》！",
        "back_href": "/games/fengyun/legion", "back_text": "返回军团"})


# ============================================================
# 称号 / 成就
# ============================================================
@router.get("/titles", response_class=HTMLResponse)
async def titles_page(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    all_titles = db.query(FengyunTitle).order_by(
        FengyunTitle.title_type, FengyunTitle.grade).all()
    grouped = {"prefix": [], "suffix": [], "pair": []}
    for t in all_titles:
        grouped.setdefault(t.title_type, []).append(t)
    db.commit()
    return templates.TemplateResponse("fengyun/titles.html", {
        "request": request, "user": user, "st": st, "grouped": grouped,
        "pair_rules": FY.TITLE_PAIR_RULES,
    })


@router.get("/achievements", response_class=HTMLResponse)
async def achievements_page(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    all_achv = db.query(FengyunAchievement).order_by(
        FengyunAchievement.difficulty, FengyunAchievement.category).all()
    grouped = {}
    for a in all_achv:
        grouped.setdefault(a.difficulty, []).append(a)
    db.commit()
    return templates.TemplateResponse("fengyun/achievements.html", {
        "request": request, "user": user, "st": st, "grouped": grouped,
    })