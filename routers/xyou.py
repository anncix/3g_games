"""幻想西游模块（v0.2.3，qqgames 最小实现）

老味道点：五门派 / 200级转职 / 装备强化 / 副本挑战 / 宠物捕捉 / 修炼挂机
核心循环：修炼/副本 → 获得经验银两 → 转职升级换装 → 学技能 → 挑战更高副本 → 继续养成

本路由为 qqgames 最小实现：认证走 get_current_user，银两/金豆映射到
Wallet.silver_coin / Wallet.premium_coin（用 change_currency），模板渲染走
templates/xyou/*.html。
"""
import json
import random
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from models.database import get_db
from models.models import (
    User, XyouState, XyouSkill, XyouUserSkill, XyouEquip, XyouUserEquip,
    XyouDungeon, XyouPet, XyouUserPet, XyouScene, ItemXyou,
)
from utils.auth import get_current_user
from utils.common import change_currency
from routers import xyou_data as XY

router = APIRouter(prefix="/games/xyou", tags=["xyou"])
templates = Jinja2Templates(directory="templates")

MODULE_KEY = "xyou"
SILVER_CURRENCY = "silver_coin"  # 银两 -> 钱包 silver_coin
GOLD_BEAN_CURRENCY = "premium_coin"  # 金豆 -> 钱包 premium_coin

# 修炼基础收益（每小时）
CULTIVATE_EXP_PER_HOUR = 500
CULTIVATE_SILVER_PER_HOUR = 200
CULTIVATE_MAX_HOURS = 4


# ============================================================
# 辅助函数
# ============================================================
def get_state(db: Session, user_id: int) -> XyouState:
    st = db.query(XyouState).filter(XyouState.user_id == user_id).first()
    if not st:
        st = XyouState(user_id=user_id)
        db.add(st)
        db.commit()
        db.refresh(st)
    return st


def calc_player_power(st: XyouState) -> int:
    """简易战力：由属性 + 等级估算"""
    return int(st.hp * 0.2 + st.mp * 0.1 + st.atk * 2 + st.defense * 1.5
               + st.speed * 1.5 + st.lingli * 1.5 + st.level * 8)


def add_exp(st: XyouState, amount: int) -> bool:
    """加经验，按门派每级属性增量自动升级。
    spec：转职节点锁经验，需先完成转职任务才能继续升级。"""
    if XY.is_promotion_locked(st.level):
        return False
    if st.level >= XY.MAX_LEVEL:
        st.exp = 0
        return False
    st.exp += amount
    leveled = False
    while st.level < XY.MAX_LEVEL:
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
            if XY.is_promotion_locked(st.level):
                st.exp = 0
                break
        else:
            break
    return leveled


def add_silver(db: Session, user_id: int, st: XyouState, amount: int, remark: str = ""):
    """银两变动：同步状态 + 钱包 silver_coin（走 change_currency 记流水）"""
    st.silver += amount
    change_currency(user_id, SILVER_CURRENCY, amount, MODULE_KEY, remark=remark, db=db)


def _has_any_skill(db: Session, user_id: int) -> bool:
    return db.query(XyouUserSkill).filter(XyouUserSkill.user_id == user_id).first() is not None


def _is_fresh(db: Session, st: XyouState) -> bool:
    """未转职：1级0经验且未学任何技能"""
    return st.level == 1 and st.exp == 0 and not st.sect_key and not _has_any_skill(db, st.user_id)


def _learned_skills(db: Session, user_id: int) -> dict:
    return {s.skill_key: s.level for s in db.query(XyouUserSkill).filter(
        XyouUserSkill.user_id == user_id).all()}


def _def_map(db: Session) -> dict:
    return {e.key: e for e in db.query(XyouEquip).all()}


def _require_user(request: Request, db: Session):
    return get_current_user(request, db)


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
    exp_need = XY.exp_needed(st.level)
    promotion_locked = XY.is_promotion_locked(st.level)
    now = datetime.utcnow()
    cultivate_ready = bool(st.cultivate_end_at and now >= st.cultivate_end_at)
    scene = db.query(XyouScene).filter(XyouScene.key == st.current_scene).first()
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
    db.commit()
    return templates.TemplateResponse("xyou/home.html", {
        "request": request, "user": user, "st": st, "power": power,
        "exp_need": exp_need, "need_create": need_create, "scene_name": scene_name,
        "cultivate_ready": cultivate_ready, "promotion_locked": promotion_locked,
        "sect_name": XY.SECT_NAMES.get(st.sect_key, "未转职"),
        "silver": st.silver, "todo": todo,
    })


# ============================================================
# 门派选择（创建角色）
# ============================================================
@router.get("/create", response_class=HTMLResponse)
async def create_page(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    db.commit()
    return templates.TemplateResponse("xyou/create.html", {
        "request": request, "user": user, "st": st,
        "sects": XY.SECTS, "base_attrs": XY.SECT_BASE_ATTRS,
        "sect_weapon": XY.SECT_WEAPON,
    })


@router.post("/create", response_class=HTMLResponse)
async def create_submit(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    form = await request.form()
    sect_key = (form.get("sect_key") or "").strip()
    if sect_key not in XY.SECT_BASE_ATTRS:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": "门派选择非法",
            "back_href": "/games/xyou/create", "back_text": "返回"})
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
    db.commit()
    return RedirectResponse(url="/games/xyou", status_code=303)


# ============================================================
# 场景系统（世界地图）
# ============================================================
@router.get("/scenes", response_class=HTMLResponse)
async def scenes_page(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    current = db.query(XyouScene).filter(XyouScene.key == st.current_scene).first()
    exits = []
    if current:
        try:
            for ek in json.loads(current.exits or "[]"):
                s = db.query(XyouScene).filter(XyouScene.key == ek).first()
                if s:
                    exits.append(s)
        except Exception:
            pass
    all_scenes = db.query(XyouScene).order_by(XyouScene.level_min).all()
    db.commit()
    return templates.TemplateResponse("xyou/scenes.html", {
        "request": request, "user": user, "st": st, "current": current,
        "exits": exits, "all_scenes": all_scenes,
    })


@router.post("/scene/move/{scene_key}", response_class=HTMLResponse)
async def scene_move(scene_key: str, request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    target = db.query(XyouScene).filter(XyouScene.key == scene_key).first()
    if not target:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": "场景不存在",
            "back_href": "/games/xyou/scenes", "back_text": "返回"})
    current = db.query(XyouScene).filter(XyouScene.key == st.current_scene).first()
    if current:
        try:
            if scene_key not in json.loads(current.exits or "[]"):
                return templates.TemplateResponse("xyou/result.html", {
                    "request": request, "user": user, "ok": False, "msg": "该场景不在出口列表，无法直达",
                    "back_href": "/games/xyou/scenes", "back_text": "返回"})
        except Exception:
            pass
    if st.level < target.level_min:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": f"等级不足，需{target.level_min}级",
            "back_href": "/games/xyou/scenes", "back_text": "返回"})
    st.current_scene = scene_key
    db.commit()
    return RedirectResponse(url="/games/xyou/scenes", status_code=303)


# ============================================================
# 技能系统
# ============================================================
@router.get("/skills", response_class=HTMLResponse)
async def skills_page(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    if not st.sect_key:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": "请先选择门派",
            "back_href": "/games/xyou/create", "back_text": "前往选择"})
    learned = _learned_skills(db, user.id)
    skills = db.query(XyouSkill).filter(
        XyouSkill.sect_key == st.sect_key).order_by(XyouSkill.unlock_level).all()
    skill_list = []
    for sk in skills:
        skill_list.append({
            "key": sk.key, "name": sk.name, "skill_type": sk.skill_type,
            "unlock_level": sk.unlock_level, "cost_silver": sk.cost_silver,
            "cost_mp": sk.cost_mp, "effect": sk.effect,
            "level": learned.get(sk.key, 0),
            "can_learn": st.level >= sk.unlock_level and sk.key not in learned,
        })
    db.commit()
    return templates.TemplateResponse("xyou/skills.html", {
        "request": request, "user": user, "st": st, "skill_list": skill_list,
        "sect_name": XY.SECT_NAMES.get(st.sect_key, st.sect_key),
        "silver": st.silver, "exp_need": XY.exp_needed(st.level),
    })


@router.post("/skills/learn/{skill_key}", response_class=HTMLResponse)
async def skill_learn(skill_key: str, request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    if not st.sect_key:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": "请先选择门派",
            "back_href": "/games/xyou/create", "back_text": "前往选择"})
    sk = db.query(XyouSkill).filter(XyouSkill.key == skill_key).first()
    if not sk or sk.sect_key != st.sect_key:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": "技能不存在或不属于你的门派",
            "back_href": "/games/xyou/skills", "back_text": "返回技能"})
    if st.level < sk.unlock_level:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": f"等级不足，需{sk.unlock_level}级",
            "back_href": "/games/xyou/skills", "back_text": "返回技能"})
    learned = _learned_skills(db, user.id)
    if skill_key in learned:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": "已学习该技能",
            "back_href": "/games/xyou/skills", "back_text": "返回技能"})
    if st.silver < sk.cost_silver:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": f"银两不足（需{sk.cost_silver}）",
            "back_href": "/games/xyou/skills", "back_text": "返回技能"})
    add_silver(db, user.id, st, -sk.cost_silver, remark=f"learn skill {skill_key}")
    db.add(XyouUserSkill(user_id=user.id, skill_key=skill_key, level=1))
    db.commit()
    return templates.TemplateResponse("xyou/result.html", {
        "request": request, "user": user, "ok": True, "msg": f"学会《{sk.name}》",
        "back_href": "/games/xyou/skills", "back_text": "返回技能"})


# ============================================================
# 装备系统
# ============================================================
@router.get("/equip", response_class=HTMLResponse)
async def equip_page(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    all_equips = db.query(XyouUserEquip).filter(
        XyouUserEquip.user_id == user.id).order_by(XyouUserEquip.id.desc()).all()
    equipped = [e for e in all_equips if e.worn]
    bag_equips = [e for e in all_equips if not e.worn]
    slot_map = {s: None for s in XY.EQUIP_SLOTS}
    for e in equipped:
        slot_map[e.slot] = e
    # 商店列表（按等级/品质）
    shop_list = db.query(XyouEquip).order_by(
        XyouEquip.level_req, XyouEquip.quality).all()
    shop_list = [e for e in shop_list if not e.sect_req or e.sect_req == st.sect_key][:40]
    def_map = _def_map(db)
    power = calc_player_power(st)
    db.commit()
    return templates.TemplateResponse("xyou/equip.html", {
        "request": request, "user": user, "st": st, "slot_map": slot_map,
        "bag_equips": bag_equips, "def_map": def_map, "shop_list": shop_list,
        "power": power, "slots": XY.EQUIP_SLOTS, "silver": st.silver,
    })


@router.post("/equip/buy/{equip_key}", response_class=HTMLResponse)
async def equip_buy(equip_key: str, request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    e = db.query(XyouEquip).filter(XyouEquip.key == equip_key).first()
    if not e:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": "商品不存在",
            "back_href": "/games/xyou/equip", "back_text": "返回装备"})
    if e.sect_req and e.sect_req != st.sect_key:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": "门派不符，无法购买",
            "back_href": "/games/xyou/equip", "back_text": "返回装备"})
    if st.level < e.level_req:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": f"等级不足，需{e.level_req}级",
            "back_href": "/games/xyou/equip", "back_text": "返回装备"})
    if st.silver < e.price:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": f"银两不足（需{e.price}）",
            "back_href": "/games/xyou/equip", "back_text": "返回装备"})
    add_silver(db, user.id, st, -e.price, remark=f"buy equip {equip_key}")
    db.add(XyouUserEquip(user_id=user.id, equip_key=equip_key, slot=e.slot, worn=False))
    db.commit()
    return templates.TemplateResponse("xyou/result.html", {
        "request": request, "user": user, "ok": True, "msg": f"购得《{e.name}》",
        "back_href": "/games/xyou/equip", "back_text": "返回装备"})


@router.post("/equip/wear/{user_equip_id}", response_class=HTMLResponse)
async def equip_wear(user_equip_id: int, request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    e = db.query(XyouUserEquip).filter(XyouUserEquip.id == user_equip_id).first()
    if not e or e.user_id != user.id:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": "装备不存在",
            "back_href": "/games/xyou/equip", "back_text": "返回装备"})
    for old in db.query(XyouUserEquip).filter(
            XyouUserEquip.user_id == user.id,
            XyouUserEquip.slot == e.slot,
            XyouUserEquip.worn == True).all():
        old.worn = False
    e.worn = True
    db.commit()
    return templates.TemplateResponse("xyou/result.html", {
        "request": request, "user": user, "ok": True, "msg": f"已穿戴 {e.slot} 部位装备",
        "back_href": "/games/xyou/equip", "back_text": "返回装备"})


@router.post("/equip/takeoff/{user_equip_id}", response_class=HTMLResponse)
async def equip_takeoff(user_equip_id: int, request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    e = db.query(XyouUserEquip).filter(XyouUserEquip.id == user_equip_id).first()
    if not e or e.user_id != user.id:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": "装备不存在",
            "back_href": "/games/xyou/equip", "back_text": "返回装备"})
    e.worn = False
    db.commit()
    return templates.TemplateResponse("xyou/result.html", {
        "request": request, "user": user, "ok": True, "msg": "已卸下",
        "back_href": "/games/xyou/equip", "back_text": "返回装备"})


# ============================================================
# 副本系统
# ============================================================
@router.get("/dungeons", response_class=HTMLResponse)
async def dungeons_page(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    all_dg = db.query(XyouDungeon).order_by(XyouDungeon.level_min).all()
    scene_keys = {d.scene for d in all_dg}
    scenes = {}
    for sk in scene_keys:
        s = db.query(XyouScene).filter(XyouScene.key == sk).first()
        scenes[sk] = s.name if s else sk
    db.commit()
    return templates.TemplateResponse("xyou/dungeons.html", {
        "request": request, "user": user, "st": st, "dungeon_list": all_dg,
        "scenes": scenes,
    })


@router.post("/dungeon/{dungeon_key}", response_class=HTMLResponse)
async def dungeon_challenge(dungeon_key: str, request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    if not st.sect_key:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": "请先选择门派",
            "back_href": "/games/xyou/create", "back_text": "前往选择"})
    dg = db.query(XyouDungeon).filter(XyouDungeon.key == dungeon_key).first()
    if not dg:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": "副本不存在",
            "back_href": "/games/xyou/dungeons", "back_text": "返回副本"})
    if st.level < dg.level_min:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": f"等级不足，需{dg.level_min}级",
            "back_href": "/games/xyou/dungeons", "back_text": "返回副本"})
    my_power = calc_player_power(st)
    diff_mult = 1.5 if dg.difficulty == "困难" else 1.0
    enemy_power = int((dg.level_max * 30 + dg.reward_exp // 10) * diff_mult)
    prob = 0.5 + (my_power - enemy_power) / max(my_power + enemy_power, 1)
    prob = max(0.1, min(0.9, prob))
    win = random.random() < prob
    if win:
        add_silver(db, user.id, st, dg.reward_silver, remark=f"dungeon win {dungeon_key}")
        leveled = add_exp(st, dg.reward_exp)
        db.commit()
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": True, "msg":
                f"挑战《{dg.name}》胜利！经验+{dg.reward_exp}，银两+{dg.reward_silver}"
                f"{'，升级了！' if leveled else ''}",
            "back_href": "/games/xyou/dungeons", "back_text": "返回副本"})
    db.commit()
    return templates.TemplateResponse("xyou/result.html", {
        "request": request, "user": user, "ok": False, "msg": f"挑战《{dg.name}》失败，再接再厉",
        "back_href": "/games/xyou/dungeons", "back_text": "返回副本"})


# ============================================================
# 修炼挂机系统
# ============================================================
@router.get("/cultivate", response_class=HTMLResponse)
async def cultivate_page(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    if not st.sect_key:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": "请先选择门派",
            "back_href": "/games/xyou/create", "back_text": "前往选择"})
    now = datetime.utcnow()
    in_progress = bool(st.cultivate_end_at and now < st.cultivate_end_at)
    ready = bool(st.cultivate_end_at and now >= st.cultivate_end_at)
    remain = int((st.cultivate_end_at - now).total_seconds()) if in_progress else 0
    db.commit()
    return templates.TemplateResponse("xyou/cultivate.html", {
        "request": request, "user": user, "st": st, "in_progress": in_progress,
        "ready": ready, "remain": remain,
        "exp_per_hour": CULTIVATE_EXP_PER_HOUR,
        "silver_per_hour": CULTIVATE_SILVER_PER_HOUR,
        "max_hours": CULTIVATE_MAX_HOURS,
    })


@router.post("/cultivate/start", response_class=HTMLResponse)
async def cultivate_start(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    if not st.sect_key:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": "请先选择门派",
            "back_href": "/games/xyou/create", "back_text": "前往选择"})
    now = datetime.utcnow()
    if st.cultivate_end_at and now < st.cultivate_end_at:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": "修炼进行中，请等待结束",
            "back_href": "/games/xyou/cultivate", "back_text": "返回修炼"})
    st.cultivate_end_at = now + timedelta(hours=CULTIVATE_MAX_HOURS)
    db.commit()
    return templates.TemplateResponse("xyou/result.html", {
        "request": request, "user": user, "ok": True,
        "msg": f"开始修炼，{CULTIVATE_MAX_HOURS}小时后可领取收益",
        "back_href": "/games/xyou/cultivate", "back_text": "返回修炼"})


@router.post("/cultivate/claim", response_class=HTMLResponse)
async def cultivate_claim(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    now = datetime.utcnow()
    if not st.cultivate_end_at or now < st.cultivate_end_at:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": "修炼尚未结束，暂不可领取",
            "back_href": "/games/xyou/cultivate", "back_text": "返回修炼"})
    exp_yield = CULTIVATE_EXP_PER_HOUR * CULTIVATE_MAX_HOURS
    silver_yield = CULTIVATE_SILVER_PER_HOUR * CULTIVATE_MAX_HOURS
    leveled = add_exp(st, exp_yield)
    add_silver(db, user.id, st, silver_yield, remark="cultivate claim")
    st.cultivate_end_at = None
    db.commit()
    return templates.TemplateResponse("xyou/result.html", {
        "request": request, "user": user, "ok": True,
        "msg": f"领取修炼收益：经验+{exp_yield}，银两+{silver_yield}"
               f"{'，升级了！' if leveled else ''}",
        "back_href": "/games/xyou/cultivate", "back_text": "返回修炼"})


# ============================================================
# 宠物系统
# ============================================================
@router.get("/pet", response_class=HTMLResponse)
async def pet_page(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    my_pets = []
    pet_def_map = {}
    for up in db.query(XyouUserPet).filter(
            XyouUserPet.user_id == user.id).order_by(XyouUserPet.id.desc()).all():
        pd = db.query(XyouPet).filter(XyouPet.key == up.pet_key).first()
        pet_def_map[up.pet_key] = pd
        my_pets.append({"user_pet": up, "pet_def": pd})
    # 图鉴（未拥有的宠物）
    have_keys = {up.pet_key for up in my_pets}
    catalog = [p for p in db.query(XyouPet).order_by(XyouPet.level_req).all()
               if p.key not in have_keys]
    db.commit()
    return templates.TemplateResponse("xyou/pet.html", {
        "request": request, "user": user, "st": st, "my_pets": my_pets,
        "pet_def_map": pet_def_map, "catalog": catalog, "max_pets": 8,
    })


@router.post("/pet/capture/{pet_key}", response_class=HTMLResponse)
async def pet_capture(pet_key: str, request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    pd = db.query(XyouPet).filter(XyouPet.key == pet_key).first()
    if not pd:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": "宠物不存在",
            "back_href": "/games/xyou/pet", "back_text": "返回宠物"})
    if st.level < pd.level_req:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": f"等级不足，需{pd.level_req}级",
            "back_href": "/games/xyou/pet", "back_text": "返回宠物"})
    count = db.query(XyouUserPet).filter(XyouUserPet.user_id == user.id).count()
    if count >= 8:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": "宠物已满（最多 8 只）",
            "back_href": "/games/xyou/pet", "back_text": "返回宠物"})
    if random.random() > pd.capture_rate:
        db.commit()
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": f"捕捉《{pd.name}》失败，再接再厉",
            "back_href": "/games/xyou/pet", "back_text": "返回宠物"})
    db.add(XyouUserPet(user_id=user.id, pet_key=pd.key, nickname=pd.name, level=1))
    db.commit()
    return templates.TemplateResponse("xyou/result.html", {
        "request": request, "user": user, "ok": True, "msg": f"成功捕捉《{pd.name}》！",
        "back_href": "/games/xyou/pet", "back_text": "返回宠物"})


@router.post("/pet/set_battle/{user_pet_id}", response_class=HTMLResponse)
async def pet_set_battle(user_pet_id: int, request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    up = db.query(XyouUserPet).filter(XyouUserPet.id == user_pet_id).first()
    if not up or up.user_id != user.id:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": "宠物不存在",
            "back_href": "/games/xyou/pet", "back_text": "返回宠物"})
    for op in db.query(XyouUserPet).filter(
            XyouUserPet.user_id == user.id, XyouUserPet.in_battle == True).all():
        op.in_battle = False
    up.in_battle = True
    db.commit()
    return templates.TemplateResponse("xyou/result.html", {
        "request": request, "user": user, "ok": True, "msg": "已设置出战",
        "back_href": "/games/xyou/pet", "back_text": "返回宠物"})


# ============================================================
# 药品商店
# ============================================================
@router.get("/medicines", response_class=HTMLResponse)
async def medicines_page(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    potions = db.query(ItemXyou).filter(
        ItemXyou.module_key == MODULE_KEY,
        ItemXyou.type == "prop",
    ).order_by(ItemXyou.sell_price).all()
    db.commit()
    return templates.TemplateResponse("xyou/medicines.html", {
        "request": request, "user": user, "st": st, "potions": potions,
        "silver": st.silver,
    })


@router.post("/medicine/buy/{item_key}", response_class=HTMLResponse)
async def medicine_buy(item_key: str, request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    item = db.query(ItemXyou).filter(ItemXyou.key == item_key).first()
    if not item or item.module_key != MODULE_KEY:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": "物品不存在",
            "back_href": "/games/xyou/medicines", "back_text": "返回药品"})
    if item.sell_price <= 0:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": "该物品不可购买",
            "back_href": "/games/xyou/medicines", "back_text": "返回药品"})
    if st.silver < item.sell_price:
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": f"银两不足（需{item.sell_price}）",
            "back_href": "/games/xyou/medicines", "back_text": "返回药品"})
    add_silver(db, user.id, st, -item.sell_price, remark=f"buy medicine {item_key}")
    db.commit()
    return templates.TemplateResponse("xyou/result.html", {
        "request": request, "user": user, "ok": True, "msg": f"购得《{item.name}》",
        "back_href": "/games/xyou/medicines", "back_text": "返回药品"})


# ============================================================
# 转职系统（spec：9/59/109/139/169/189 多段转职）
# ============================================================
@router.get("/promote", response_class=HTMLResponse)
async def promote_page(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    promo = XY.PROMOTION_QUESTS.get(st.level)
    db.commit()
    return templates.TemplateResponse("xyou/promote.html", {
        "request": request, "user": user, "st": st, "promo": promo, "level": st.level,
    })


@router.post("/promote/complete", response_class=HTMLResponse)
async def promote_complete(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    st = get_state(db, user.id)
    if not XY.is_promotion_locked(st.level):
        return templates.TemplateResponse("xyou/result.html", {
            "request": request, "user": user, "ok": False, "msg": "当前等级无需转职",
            "back_href": "/games/xyou", "back_text": "返回首页"})
    promo = XY.PROMOTION_QUESTS.get(st.level, {})
    st.level += 1
    reward_exp = promo.get("reward_exp", 0)
    leveled = False
    if reward_exp:
        leveled = add_exp(st, reward_exp)
    db.commit()
    return templates.TemplateResponse("xyou/result.html", {
        "request": request, "user": user, "ok": True,
        "msg": f"转职成功！等级提升至 {st.level} 级"
               f"{f'，获得 {reward_exp} 经验' if reward_exp else ''}"
               f"{'，升级了！' if leveled else ''}",
        "back_href": "/games/xyou", "back_text": "返回首页"})