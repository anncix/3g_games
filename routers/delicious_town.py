"""美味小镇完整玩法（v0.3.1 怀旧版完整设计规范 · 同步 SQLAlchemy 移植版）

双主轴：餐厅星级(规模) + 菜谱等级(内容)
核心循环：拿食材 → 做菜/备菜 → 上桌营业 → 顾客消费 → 获得金币/经验/熟练度
        → 升菜等/升餐厅星级 → 去好友家补缺口或互动 → 回店继续经营

定版规则（保留老味道，做轻保护）：
- 开局金币 10000，模块等级 Lv1-80
- 顾客周期 180 秒/波；1 名服务员服务 3 桌
- 油壶初始 3000，可扩到 8000（档位：3000→4000→5000→5500→6000→7000→8000）
- 1 星起出现 10% 挑剔客，每升 1 星 +10%（上限 5 星 40%）
- 菜谱 6 级 × 3 品质（普通/极品/金牌），品质只升售价不升经验
- 翻柜日限 15 次，同好友日限 3 次 + 10 分钟冷却 + 收益衰减(100/70/40/0%)
- 蟑螂：日限 2 次，封 1 桌，15 分钟自动消失，单餐厅上限 3 只
- 服务员：雇好友 12 小时，500 金币，金币+3%/满意度+2%/速度-5%制作时间
- 经验公式：need(L→L+1) = 120 + 80*L

v0.1.1 新增：
- 油壶 8 档
- 赛厨系统：厨具 5 类 + 技能点 40 + 3 评委 + 厨力综合分
- 厨艺大赛：4 赛区 + 报名 + 结算
- 菜系 8 大 + 综合街映射（展示用）
- 万能食材替代（缺 1 个可用同级别万能食材替代）

v0.1.2 新增：
- 外卖订单系统（每日 3 单大额奖励，送餐）
"""
import json
import random
import time
from datetime import datetime, timedelta, date

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from models.database import get_db
from models.models import (
    User, TownProfile, TownRecipe, TownUserRecipe, TownIngredient, TownWaiter,
    TownFacility, TownCockroach, TownDailyLog, TownChefSkill, TownChefTool,
    TownMatchLog, TownContestEntry, TownFlipLog, ItemTown, Notification, InventoryItem,
)
from utils.auth import get_current_user
from utils.i18n import t
from utils.common import add_item, remove_item

router = APIRouter(prefix="/delicious_town", tags=["delicious_town"])
templates = Jinja2Templates(directory="templates")
MODULE_KEY = "town"

# ============================================================
# 定版配置
# ============================================================
CUSTOMER_CYCLE = 180          # 顾客周期（秒）
TABLES_PER_WAITER = 3         # 1 名服务员服务 3 桌
FLIP_DAILY_LIMIT = 15         # 翻柜日限
FLIP_PER_FRIEND_LIMIT = 3     # 同好友日限
FLIP_COOLDOWN = 600           # 10 分钟
ROACH_DAILY_LIMIT = 2         # 蟑螂日限
ROACH_COOLDOWN = 1800         # 30 分钟
ROACH_MAX_PER_RESTAURANT = 3  # 单餐厅上限
ROACH_DURATION = 900          # 15 分钟
WAITER_DURATION = 12 * 3600   # 12 小时
WAITER_HIRE_COST = 500
OIL_IDLE_PER_TABLE = 2        # 每有效桌每周期待机耗油 2

MAIN_QUESTS = [
    (1, "开业大吉", 1, "完成第一道菜（蛋炒饭）", "经验+50、金币+200"),
    (2, "食材采购", 5, "翻橱柜5次获得食材", "经验+120、菜谱碎片×2"),
    (3, "菜谱升级", 10, "解锁并制作2级菜（红烧肉）", "经验+300、金币+500"),
    (4, "油壶扩容", 15, "油壶升级到5000", "经验+200、特殊调料×1"),
    (5, "蟑螂来袭", 20, "处理3次蟑螂事件", "经验+250、金币+300"),
    (6, "雇佣帮手", 25, "雇佣1名服务员", "经验+180、金币+500"),
    (7, "厨艺大赛", 40, "报名参加厨艺大赛", "经验+1000、菜谱碎片×5"),
    (8, "金牌餐厅", 60, "餐厅升到5星", "经验+5000、特殊调料×3、金牌食材资格"),
]


def exp_needed(level: int) -> int:
    return 120 + 80 * level


# 菜谱级别表 (recipe_level, unlock_level, base_price, base_exp, cook_seconds, base_oil)
RECIPE_LEVEL_TABLE = {
    1: (1, 18, 2, 30, 8),
    2: (10, 36, 4, 45, 12),
    3: (20, 68, 7, 60, 18),
    4: (35, 118, 11, 90, 26),
    5: (50, 198, 16, 120, 36),
    6: (65, 320, 24, 180, 50),
}

QUALITY_PRICE_COEF = {"普通": 1.00, "极品": 1.25, "金牌": 1.55}
QUALITY_EXP_COEF = {"普通": 1.00, "极品": 1.00, "金牌": 1.00}

# 菜谱升级需求表
# (recipe_level, 极品熟练度, 极品金币, 极品材料数, 金牌熟练度, 金牌金币, 金牌材料数, 金牌特殊调料数)
RECIPE_UPGRADE_TABLE = {
    1: (20, 300, 4, 60, 1000, 10, 1),
    2: (25, 600, 6, 70, 2000, 12, 1),
    3: (30, 1200, 8, 80, 4000, 14, 2),
    4: (35, 2400, 10, 90, 8000, 16, 2),
    5: (40, 4800, 12, 100, 16000, 18, 3),
    6: (50, 9600, 14, 120, 32000, 20, 3),
}

# 星级效果表 (stars, apply_level, table_cap, waiter_total, cabinet_cap, facility_slots, picky_pct, rare_pct, revenue_coef)
STAR_TABLE = {
    0: (1, 3, 1, 24, 2, 0, 0, 1.00),
    1: (10, 6, 2, 30, 3, 10, 0, 1.05),
    2: (20, 9, 3, 36, 4, 20, 2, 1.10),
    3: (35, 12, 4, 42, 5, 30, 4, 1.15),
    4: (50, 15, 5, 48, 6, 35, 8, 1.20),
    5: (70, 18, 6, 54, 7, 40, 12, 1.25),
}

# 申星条件表 (stars, level, 普通菜数, 极品菜数, 金牌菜数, 累计营业, 累计收入)
STAR_APPLY_TABLE = {
    1: (10, 5, 0, 0, 100, 5000),
    2: (20, 15, 0, 0, 300, 30000),
    3: (35, 30, 15, 0, 800, 120000),
    4: (50, 0, 75, 10, 2000, 500000),
    5: (70, 0, 180, 45, 5000, 2000000),
}

# 油壶容量表（8 档）
OIL_POT_TABLE = [
    (3000, 0),
    (4000, 10000),
    (5000, 25000),
    (5500, 40000),
    (6000, 80000),
    (7000, 120000),
    (8000, 180000),
]

OIL_PACK_TABLE = {
    "small": (300, 60),
    "medium": (1000, 180),
    "large": (3000, 480),
}

CUSTOMER_TYPES = {
    "normal": (1.00, 1.00, "从上架菜里随机点单"),
    "picky": (1.25, 1.20, "指定一道菜，没有就走"),
    "rare": (1.60, 1.40, "指定高阶菜，没有就走"),
}

FACILITY_TABLE = {
    "trophy": ("小镇食神奖杯(铜)", 5000, 24, "每位顾客经验+1"),
    "poster": ("小C宣传海报", 1000, 24, "每位顾客金币+1"),
    "fresh_cabinet": ("防翻保鲜柜", 3000, 24, "被翻概率-50%"),
    "oil_stove": ("省油灶台", 4000, 24, "做菜耗油-10%"),
    "sanitizer": ("卫生香氛", 2500, 24, "蟑螂出现率-50%"),
}

FLIP_DECAY = [1.00, 0.70, 0.40, 0.00]

CUISINE_STREETS = {
    "湘菜": "湖南街", "粤菜": "广东街", "川菜": "四川街", "闽菜": "福建街",
    "徽菜": "安徽街", "鲁菜": "山东街", "浙菜": "浙江街", "苏菜": "江苏街",
    "综合": "综合一街 / 综合二街",
}

CHEF_TOOLS = {
    "spade": ("厨具·铲", 10, 2000),
    "knife": ("厨具·刀", 10, 2000),
    "pot": ("厨具·锅", 10, 2000),
    "flavor": ("厨具·味", 10, 2000),
    "mind": ("厨具·意", 10, 2000),
}
CHEF_TOOL_SLOTS = ["spade", "knife", "pot", "flavor", "mind"]

SKILL_TOTAL_POINTS = 40
SKILL_KEYS = ["huohou", "daogong", "chuyi", "tiaowei"]
SKILL_NAMES = {"huohou": "火候", "daogong": "刀功", "chuyi": "厨艺", "tiaowei": "调味"}

CONTEST_ZONES = {
    "junior": ("初级区", 40, 49),
    "middle": ("中级区", 50, 59),
    "senior": ("高级区", 60, 69),
    "super": ("超级区", 70, 999),
}
CONTEST_SIGNUP_COST = 20
CONTEST_SIGNUP_HOUR = (8, 23)

MATCH_DAILY_LIMIT = 10
MATCH_WIN_COIN = 200
MATCH_WIN_EXP = 30
MATCH_LOSE_COIN = 50

SEAT_COVER_TABLE = [
    (11, 15, 5, 0, 0), (16, 20, 15, 0, 0), (21, 25, 30, 0, 0),
    (26, 30, 60, 0, 0), (31, 35, 0, 30, 0), (36, 40, 0, 50, 0),
    (41, 45, 0, 75, 0), (46, 50, 0, 105, 0), (51, 55, 0, 140, 0),
    (56, 60, 0, 180, 0), (61, 65, 0, 215, 10), (66, 70, 0, 255, 25),
    (71, 75, 0, 275, 45), (76, 80, 0, 305, 70), (81, 85, 0, 275, 100),
    (86, 90, 0, 240, 135), (91, 999, 0, 210, 165),
]

GOLD_INGREDIENT_REPLACE = {
    "猪肉": "山黑猪肉", "鸡蛋": "草鸡蛋", "辣椒": "宝庆朝天椒",
    "干辣椒": "宝庆朝天椒", "大葱": "章丘大葱", "花椒": "韩城花椒",
    "豆瓣酱": "郫县豆瓣", "火腿": "金华火腿", "鲤鱼": "黄河鲤鱼",
    "鲈鱼": "松江鲈鱼", "鸡肉": "三黄鸡肉", "牛肉": "雪花牛肉",
    "茶叶": "西湖龙井", "对虾": "渤海对虾", "醋": "山西老陈醋",
    "鸭肉": "连城白鸭", "蛇肉": "永州蕲蛇", "鱼翅": "神秘九天翅",
    "鲍鱼": "神秘九孔鲍", "猪肚": "神秘黄金肚", "虫草": "神秘高山虫",
    "十三香": "神秘龙涎香", "燕窝": "神秘金丝盏", "蘑菇": "神秘金蟾菇",
    "香菇": "神秘金蟾菇", "五香料": "番红花粉",
}

WILD_INGREDIENTS = {
    1: ("town_wild_ing_1", "1级万能食材"),
    2: ("town_wild_ing_2", "2级万能食材"),
    3: ("town_wild_ing_3", "3级万能食材"),
    4: ("town_wild_ing_4", "4级万能食材"),
    5: ("town_wild_ing_5", "5级万能食材"),
    6: ("town_wild_ing_6", "6级万能食材"),
}

# 食材级别映射（用于万能食材替代判定）
ING_LEVEL_BY_PREFIX = {
    "town_ing_lv1": 1, "town_ing_lv2": 2, "town_ing_lv3": 3,
    "town_ing_lv4": 4, "town_ing_lv5": 5, "town_ing_lv6": 6,
}

DELIVERY_DAILY_LIMIT = 10
DELIVERY_ORDER_COUNT = 3
DELIVERY_DEADLINE = 24 * 3600


# ============================================================
# 工具函数
# ============================================================
def get_state(db: Session, user: User) -> TownProfile:
    """获取/创建餐厅状态"""
    town = user.town
    if not town:
        town = TownProfile(
            user_id=user.id,
            last_service_at=datetime.utcnow() - timedelta(seconds=CUSTOMER_CYCLE),
            last_oil_drain=datetime.utcnow() - timedelta(seconds=CUSTOMER_CYCLE),
        )
        db.add(town)
        db.flush()
    # 清理过期服务员/蟑螂/设施
    now = datetime.utcnow()
    db.query(TownWaiter).filter(
        TownWaiter.user_id == user.id, TownWaiter.expire_at < now).delete()
    db.query(TownCockroach).filter(
        TownCockroach.user_id == user.id, TownCockroach.expire_at < now).delete()
    db.query(TownFacility).filter(
        TownFacility.user_id == user.id, TownFacility.expire_at < now).delete()
    return town


def get_daily_log(db: Session, user_id: int) -> TownDailyLog:
    today = date.today().isoformat()
    dl = db.query(TownDailyLog).filter(
        TownDailyLog.user_id == user_id, TownDailyLog.date == today).first()
    if not dl:
        dl = TownDailyLog(user_id=user_id, date=today)
        db.add(dl)
        db.flush()
    return dl


def get_recipe_progress(db: Session, town: TownProfile, recipe_id: int) -> TownUserRecipe:
    p = db.query(TownUserRecipe).filter(
        TownUserRecipe.town_id == town.id,
        TownUserRecipe.recipe_id == recipe_id).first()
    if not p:
        p = TownUserRecipe(town_id=town.id, user_id=town.user_id, recipe_id=recipe_id)
        db.add(p)
        db.flush()
    return p


def add_exp(town: TownProfile, amount: int):
    town.restaurant_exp += amount
    while town.restaurant_exp >= exp_needed(town.restaurant_level):
        town.restaurant_exp -= exp_needed(town.restaurant_level)
        town.restaurant_level += 1


def star_info(stars: int) -> tuple:
    return STAR_TABLE.get(stars, STAR_TABLE[0])[1:]


def can_apply_star(stars, level, normal_cnt, fine_cnt, gold_cnt,
                   total_service, total_revenue) -> (bool, str):
    if stars >= 5:
        return False, "已达最高星级"
    target = STAR_APPLY_TABLE.get(stars + 1)
    if not target:
        return False, "无可升星级"
    req_level, req_normal, req_fine, req_gold, req_service, req_revenue = target
    if level < req_level:
        return False, f"需要等级 Lv{req_level}"
    if req_normal and normal_cnt < req_normal:
        return False, f"需学会 {req_normal} 道普通菜"
    if req_fine and fine_cnt < req_fine:
        return False, f"需学会 {req_fine} 道极品菜"
    if req_gold and gold_cnt < req_gold:
        return False, f"需学会 {req_gold} 道金牌菜"
    if total_service < req_service:
        return False, f"需累计营业 {req_service} 次（当前{total_service}）"
    if total_revenue < req_revenue:
        return False, f"需累计收入 {req_revenue}（当前{total_revenue}）"
    return True, ""


def count_learned_by_quality(db, town: TownProfile) -> (int, int, int):
    normal = fine = gold = 0
    for p in db.query(TownUserRecipe).filter(TownUserRecipe.town_id == town.id).all():
        if p.quality_level == "普通":
            normal += 1
        elif p.quality_level == "极品":
            fine += 1
        elif p.quality_level == "金牌":
            gold += 1
    return normal, fine, gold


def get_active_waiters(db, user_id: int):
    now = datetime.utcnow()
    return db.query(TownWaiter).filter(
        TownWaiter.user_id == user_id, TownWaiter.expire_at > now).all()


def get_active_cockroaches(db, user_id: int):
    now = datetime.utcnow()
    return db.query(TownCockroach).filter(
        TownCockroach.user_id == user_id, TownCockroach.expire_at > now).all()


def get_active_facilities(db, user_id: int):
    now = datetime.utcnow()
    return db.query(TownFacility).filter(
        TownFacility.user_id == user_id, TownFacility.expire_at > now).all()


def calc_serving_tables(table_count, waiter_count, roach_count) -> int:
    serviceable = waiter_count * TABLES_PER_WAITER
    unblocked = max(0, table_count - roach_count)
    return min(table_count, serviceable, unblocked)


def get_chef_skill(db, user_id: int) -> TownChefSkill:
    sk = db.query(TownChefSkill).filter(TownChefSkill.user_id == user_id).first()
    if not sk:
        sk = TownChefSkill(user_id=user_id)
        db.add(sk)
        db.flush()
    return sk


def chef_power(town, learned_count, gold_count, tools, sk) -> int:
    tool_score = sum(t.level * 15 for t in tools if t.equipped)
    skill_total = sk.huohou + sk.daogong + sk.chuyi + sk.tiaowei
    power = (town.restaurant_level * 10 + town.star_level * 200 + learned_count * 5
             + gold_count * 20 + tool_score + skill_total * 8)
    return power


def judge_score(power, skill_points, judge_focus) -> int:
    base = power // 10 + random.randint(5, 20)
    focus_bonus = skill_points.get(judge_focus, 0) * 3
    return base + focus_bonus


def contest_zone(level: int):
    for k, (_, lo, hi) in CONTEST_ZONES.items():
        if lo <= level <= hi:
            return k
    return None


def ing_level_of(item_key: str) -> int:
    for prefix, lv in ING_LEVEL_BY_PREFIX.items():
        if item_key.startswith(prefix):
            return lv
    return 1


def check_wild_substitute(db, user_id, missing_key) -> (bool, str, int):
    lv = ing_level_of(missing_key)
    wild_key, _ = WILD_INGREDIENTS.get(lv, ("", ""))
    if not wild_key:
        return False, "", 0
    have = count_ingredient(db, user_id, wild_key)
    return (have > 0, wild_key, lv) if have > 0 else (False, "", 0)


def today_str() -> str:
    return date.today().isoformat()


def count_ingredient(db, user_id, code) -> int:
    row = db.query(TownIngredient).filter(
        TownIngredient.user_id == user_id, TownIngredient.ingredient_code == code).first()
    return row.quantity if row else 0


def add_ingredient(db, town, user_id, code, qty):
    row = db.query(TownIngredient).filter(
        TownIngredient.user_id == user_id, TownIngredient.ingredient_code == code).first()
    if row:
        row.quantity += qty
    else:
        item = db.query(ItemTown).filter(ItemTown.key == code).first()
        db.add(TownIngredient(town_id=town.id, user_id=user_id,
                              ingredient_code=code,
                              ingredient_name=item.name if item else code,
                              quantity=qty))
    db.flush()


def remove_ingredient(db, user_id, code, qty) -> bool:
    row = db.query(TownIngredient).filter(
        TownIngredient.user_id == user_id, TownIngredient.ingredient_code == code).first()
    if not row or row.quantity < qty:
        return False
    row.quantity -= qty
    if row.quantity <= 0:
        db.delete(row)
    return True


def count_dish(db, user_id, code) -> int:
    return db.query(InventoryItem).filter(
        InventoryItem.user_id == user_id, InventoryItem.module_key == MODULE_KEY,
        InventoryItem.item_code == code).scalar() is not None and \
        (db.query(InventoryItem).filter(
            InventoryItem.user_id == user_id, InventoryItem.module_key == MODULE_KEY,
            InventoryItem.item_code == code).first().quantity or 0)


def _drain_oil_idle(db, town: TownProfile):
    now = datetime.utcnow()
    elapsed = (now - town.last_oil_drain).total_seconds()
    if elapsed < 60:
        return
    cycles = int(elapsed // 180)
    if cycles <= 0:
        return
    drain = cycles * OIL_IDLE_PER_TABLE * max(1, town.seats)
    town.oil_amount = max(0, town.oil_amount - drain)
    town.last_oil_drain = now


def _upgrade_preview(recipe, p) -> dict:
    if p.quality_level == "普通":
        prof_need, gold_need, mat_need, _, _, _, _ = RECIPE_UPGRADE_TABLE.get(recipe.recipe_level, (0, 0, 0, 0, 0, 0, 0))
        return {"target": "极品", "proficiency_need": prof_need, "proficiency_have": p.proficiency,
                "gold_need": gold_need, "mat_need": mat_need, "mat_key": "town_dish_fragment"}
    elif p.quality_level == "极品":
        _, _, _, prof_need, gold_need, mat_need, special_need = RECIPE_UPGRADE_TABLE.get(recipe.recipe_level, (0, 0, 0, 0, 0, 0, 0))
        return {"target": "金牌", "proficiency_need": prof_need, "proficiency_have": p.proficiency,
                "gold_need": gold_need, "mat_need": mat_need, "mat_key": "town_dish_fragment",
                "special_need": special_need, "special_key": "town_special_condiment"}
    return {}


def _gen_delivery_orders(learned: list) -> list:
    orders = []
    pool = learned[:] if learned else []
    for _ in range(DELIVERY_ORDER_COUNT):
        if not pool:
            break
        r = random.choice(pool)
        qty = random.randint(1, 3)
        orders.append({
            "dish_key": r.recipe_code,
            "qty": qty,
            "reward_exp": r.recipe_level * 100 * qty,
            "reward_gold": r.recipe_level * 50 * qty,
            "deadline_ts": int(time.time()) + DELIVERY_DEADLINE,
            "done": False,
        })
    return orders


def _fmt_remain(sec) -> str:
    if sec <= 0:
        return "已过期"
    h = sec // 3600
    m = (sec % 3600) // 60
    if h > 0:
        return f"{h}小时{m}分"
    return f"{m}分"


def get_common_context(request: Request, db: Session):
    user = get_current_user(request, db)
    if not user:
        return None
    lang = user.language or "zh"
    theme = user.theme or "light"
    unread_count = db.query(Notification).filter(
        Notification.user_id == user.id, Notification.is_read == False).count()
    return {
        "request": request,
        "user": user,
        "lang": lang,
        "theme": theme,
        "_": lambda key: t(key, lang),
        "unread_count": unread_count,
        "now": datetime.utcnow(),
    }


def render_result(request, db, user, ok, msg, back_href="/delicious_town", back_text="返回"):
    ctx = get_common_context(request, db)
    ctx.update({"ok": ok, "msg": msg, "back_href": back_href, "back_text": back_text})
    return templates.TemplateResponse("delicious_town/result.html", ctx)


# ============================================================
# 模块首页
# ============================================================
@router.get("", response_class=HTMLResponse)
def town_home(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    _drain_oil_idle(db, town)
    db.commit()
    cooking_recipe = None
    cook_remain = 0
    if town.cooking_recipe:
        cooking_recipe = db.query(TownRecipe).filter(
            TownRecipe.recipe_code == town.cooking_recipe).first()
        if cooking_recipe:
            cook_remain = max(0, int(cooking_recipe.cook_seconds -
                                     (datetime.utcnow() - town.cooking_started_at).total_seconds()))
    waiters = get_active_waiters(db, user.id)
    roaches = get_active_cockroaches(db, user.id)
    facilities = get_active_facilities(db, user.id)
    table_cap, waiter_total, cabinet_cap, facility_slots, picky_pct, rare_pct, revenue_coef = star_info(town.star_level)
    serving_tables = calc_serving_tables(town.seats, len(waiters) + 1, len(roaches))
    can_service = town.oil_amount > 0 and serving_tables > 0
    todo = []
    if town.oil_amount < town.oil_cap * 0.15:
        todo.append(("缺油告急", "red", "/delicious_town/oil", "去添油"))
    if cooking_recipe and cook_remain == 0:
        todo.append((f"{cooking_recipe.name}已出锅", "green", "/delicious_town", "收菜"))
    if not todo:
        todo.append(("暂无待办，去做菜吧", "muted", "/delicious_town/recipes", "去菜谱"))
    oil_pct = int(town.oil_amount / town.oil_cap * 100) if town.oil_cap > 0 else 0
    ctx.update({
        "st": town, "town": town, "cooking_recipe": cooking_recipe, "cook_remain": cook_remain,
        "todo": todo, "waiters": waiters, "roaches": roaches, "facilities": facilities,
        "table_cap": table_cap, "waiter_total": waiter_total, "cabinet_cap": cabinet_cap,
        "facility_slots": facility_slots, "picky_pct": picky_pct, "rare_pct": rare_pct,
        "revenue_coef": revenue_coef, "serving_tables": serving_tables,
        "can_service": can_service, "oil_pct": oil_pct, "exp_need": exp_needed(town.restaurant_level),
    })
    return templates.TemplateResponse("delicious_town/home.html", ctx)


# ============================================================
# 菜谱系统
# ============================================================
@router.get("/recipes", response_class=HTMLResponse)
def recipes_list(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    recipes = db.query(TownRecipe).order_by(TownRecipe.recipe_level).all()
    info = []
    for r in recipes:
        p = get_recipe_progress(db, town, r.id)
        ing = json.loads(r.ingredient_json) if r.ingredient_json else {}
        ings = []
        enough = True
        for k, n in ing.items():
            cnt = count_ingredient(db, user.id, k)
            item = db.query(ItemTown).filter(ItemTown.key == k).first()
            ings.append({"key": k, "name": item.name if item else k, "need": n, "have": cnt})
            if cnt < n:
                enough = False
        upgrade = None
        if p.quality_level != "金牌":
            upgrade = _upgrade_preview(r, p)
        info.append({"r": r, "p": p, "ings": ings, "enough": enough,
                     "locked_level": town.restaurant_level < r.level_required, "upgrade": upgrade})
    db.commit()
    ctx.update({"info": info, "st": town, "exp_need": exp_needed(town.restaurant_level)})
    return templates.TemplateResponse("delicious_town/recipes.html", ctx)


@router.get("/recipe/{recipe_id}", response_class=HTMLResponse)
def recipe_detail(recipe_id: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    r = db.query(TownRecipe).filter(TownRecipe.id == recipe_id).first()
    if not r:
        return render_result(request, db, user, False, "菜谱不存在", "/delicious_town/recipes", "返回菜谱")
    p = get_recipe_progress(db, town, r.id)
    ing = json.loads(r.ingredient_json) if r.ingredient_json else {}
    ings = []
    for k, n in ing.items():
        cnt = count_ingredient(db, user.id, k)
        item = db.query(ItemTown).filter(ItemTown.key == k).first()
        ings.append({"key": k, "name": item.name if item else k, "need": n, "have": cnt})
    upgrade = _upgrade_preview(r, p) if p.quality_level != "金牌" else None
    db.commit()
    ctx.update({"r": r, "p": p, "ings": ings, "upgrade": upgrade, "st": town,
                "exp_need": exp_needed(town.restaurant_level)})
    return templates.TemplateResponse("delicious_town/recipe_detail.html", ctx)


@router.post("/learn/{recipe_id}")
def learn_recipe(recipe_id: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    r = db.query(TownRecipe).filter(TownRecipe.id == recipe_id).first()
    if not r:
        return render_result(request, db, user, False, "菜谱不存在", "/delicious_town/recipes", "返回菜谱")
    p = get_recipe_progress(db, town, r.id)
    if p.quality_level != "普通" or recipe_already_has_level(db, town, r):
        if p.quality_level != "普通":
            return render_result(request, db, user, False, "已学会该菜谱", f"/delicious_town/recipe/{r.id}", "返回")
    if town.restaurant_level < r.level_required:
        return render_result(request, db, user, False,
                             f"需要等级 Lv{r.level_required}（当前 Lv{town.restaurant_level}）",
                             f"/delicious_town/recipe/{r.id}", "返回")
    cost = 50 * r.recipe_level
    if town.gold < cost:
        return render_result(request, db, user, False, f"金币不足（需 {cost}）", f"/delicious_town/recipe/{r.id}", "返回")
    town.gold -= cost
    p.quality_level = "普通"
    learn_exp = 5 * r.recipe_level
    add_exp(town, learn_exp)
    db.commit()
    return render_result(request, db, user, True, f"学会 {r.name}！金币-{cost} 经验+{learn_exp}",
                         "/delicious_town/recipes", "返回菜谱")


def recipe_already_has_level(db, town, recipe):
    # 若无 explicit 字段，用 quality_level != 未学 标识（普通=已学）
    return False


@router.post("/cook/{recipe_id}")
def cook(recipe_id: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth_login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    if town.cooking_recipe:
        return render_result(request, db, user, False, "正在烹饪中，先完成当前的", "/delicious_town", "返回")
    r = db.query(TownRecipe).filter(TownRecipe.id == recipe_id).first()
    if not r:
        return render_result(request, db, user, False, "菜谱不存在", "/delicious_town/recipes", "返回菜谱")
    p = get_recipe_progress(db, town, r.id)
    if p.quality_level != "普通" and quality_not_learned(p):
        return render_result(request, db, user, False, "未学会该菜谱", f"/delicious_town/recipe/{r.id}", "返回")
    oil_cost = r.oil_cost
    facilities = get_active_facilities(db, user.id)
    if any(f.facility_key == "oil_stove" for f in facilities):
        oil_cost = int(oil_cost * 0.9)
    if town.oil_amount < oil_cost:
        return render_result(request, db, user, False, f"油量不足（需 {oil_cost}）", "/delicious_town/oil", "去添油")
    ing = json.loads(r.ingredient_json) if r.ingredient_json else {}
    missing = []
    for k, n in ing.items():
        have = count_ingredient(db, user.id, k)
        if have < n:
            missing.append((k, n, have))
    wild_used = []
    if missing:
        if len(missing) == 1:
            mk, mn, mh = missing[0]
            shortage = mn - mh
            if shortage == 1:
                can_sub, wild_key, wild_lv = check_wild_substitute(db, user.id, mk)
                if can_sub:
                    wild_used.append((wild_key, wild_lv, mk))
                else:
                    item = db.query(ItemTown).filter(ItemTown.key == mk).first()
                    return render_result(request, db, user, False,
                                         f"食材不足：{item.name if item else mk}（缺1个，可用{wild_lv}级万能食材替代）",
                                         f"/delicious_town/recipe/{r.id}", "返回")
            else:
                item = db.query(ItemTown).filter(ItemTown.key == mk).first()
                return render_result(request, db, user, False,
                                     f"食材不足：{item.name if item else mk}（缺{shortage}个，万能食材只能补1个）",
                                     f"/delicious_town/recipe/{r.id}", "返回")
        else:
            item = db.query(ItemTown).filter(ItemTown.key == missing[0][0]).first()
            return render_result(request, db, user, False,
                                 f"食材不足：{item.name if item else missing[0][0]} 等多种材料缺失",
                                 f"/delicious_town/recipe/{r.id}", "返回")
    for k, n in ing.items():
        have = count_ingredient(db, user.id, k)
        if have >= n:
            remove_ingredient(db, user.id, k, n)
        elif have > 0:
            remove_ingredient(db, user.id, k, have)
    for wild_key, _wild_lv, _mk in wild_used:
        remove_ingredient(db, user.id, wild_key, 1)
    town.oil_amount -= oil_cost
    town.cooking_recipe = r.recipe_code
    town.cooking_started_at = datetime.utcnow()
    db.commit()
    wild_text = f"（消耗{wild_used[0][1]}级万能食材×1）" if wild_used else ""
    return render_result(request, db, user, True,
                         f"开始烹饪 {r.name}，约 {r.cook_seconds} 秒（耗油 {oil_cost}）{wild_text}",
                         "/delicious_town", "返回首页")


def quality_not_learned(p):
    return p.quality_level == "未学"


@router.post("/finish")
def finish_cook(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    if not town.cooking_recipe:
        return render_result(request, db, user, False, "没有在烹饪", "/delicious_town", "返回")
    r = db.query(TownRecipe).filter(TownRecipe.recipe_code == town.cooking_recipe).first()
    if not r or (datetime.utcnow() - town.cooking_started_at).total_seconds() < r.cook_seconds:
        return render_result(request, db, user, False, "还没烹饪完成", "/delicious_town", "返回")
    if r.output_item_key:
        item = db.query(ItemTown).filter(ItemTown.key == r.output_item_key).first()
        add_item(user.id, MODULE_KEY, r.output_item_key, item.name if item else r.output_item_key,
                 1, "dish", "common", "🍽️", db=db)
    p = get_recipe_progress(db, town, r.id)
    if p.quality_level == "普通" or p.quality_level in ("极品", "金牌"):
        p.proficiency += 1
    craft_exp = 2
    add_exp(town, craft_exp)
    town.dishes_served += 1
    town.cooking_recipe = ""
    town.cooking_started_at = None
    db.commit()
    return render_result(request, db, user, True, f"完成 {r.name}×1，熟练度+1，经验+{craft_exp}",
                         "/delicious_town", "返回首页")


@router.post("/upgrade/{recipe_id}")
def upgrade_recipe(recipe_id: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    r = db.query(TownRecipe).filter(TownRecipe.id == recipe_id).first()
    if not r:
        return render_result(request, db, user, False, "菜谱不存在", "/delicious_town/recipes", "返回")
    p = get_recipe_progress(db, town, r.id)
    if p.quality_level not in ("普通", "极品"):
        return render_result(request, db, user, False, "未学会该菜谱", f"/delicious_town/recipe/{r.id}", "返回")
    if p.quality_level == "金牌":
        return render_result(request, db, user, False, "已达最高品质", f"/delicious_town/recipe/{r.id}", "返回")
    if p.quality_level == "普通":
        prof_need, gold_need, mat_need, _, _, _, _ = RECIPE_UPGRADE_TABLE.get(r.recipe_level, (0, 0, 0, 0, 0, 0, 0))
        target = "极品"
        special_key = None
        special_need = 0
    else:
        _, _, _, prof_need, gold_need, mat_need, special_need = RECIPE_UPGRADE_TABLE.get(r.recipe_level, (0, 0, 0, 0, 0, 0, 0))
        target = "金牌"
        special_key = "town_special_condiment"
    mat_key = "town_dish_fragment"
    if p.proficiency < prof_need:
        return render_result(request, db, user, False, f"熟练度不足（需 {prof_need}，当前 {p.proficiency}）",
                             f"/delicious_town/recipe/{r.id}", "返回")
    if town.gold < gold_need:
        return render_result(request, db, user, False, f"金币不足（需 {gold_need}）", f"/delicious_town/recipe/{r.id}", "返回")
    if count_ingredient(db, user.id, mat_key) < mat_need:
        return render_result(request, db, user, False, f"菜谱碎片不足（需 {mat_need}）", f"/delicious_town/recipe/{r.id}", "返回")
    if special_key and count_ingredient(db, user.id, special_key) < special_need:
        return render_result(request, db, user, False, f"特殊调料不足（需 {special_need}）", f"/delicious_town/recipe/{r.id}", "返回")
    town.gold -= gold_need
    remove_ingredient(db, user.id, mat_key, mat_need)
    if special_key:
        remove_ingredient(db, user.id, special_key, special_need)
    p.quality_level = target
    db.commit()
    return render_result(request, db, user, True,
                         f"{r.name} 升级为 {target}！售价系数 {QUALITY_PRICE_COEF[target]}x",
                         f"/delicious_town/recipe/{r.id}", "返回")


@router.post("/shelf/{recipe_id}")
def toggle_shelf(recipe_id: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    r = db.query(TownRecipe).filter(TownRecipe.id == recipe_id).first()
    if not r:
        return render_result(request, db, user, False, "菜谱不存在", "/delicious_town/recipes", "返回菜谱")
    p = get_recipe_progress(db, town, r.id)
    if p.quality_level not in ("普通", "极品", "金牌"):
        return render_result(request, db, user, False, "未学会该菜谱", f"/delicious_town/recipe/{r.id}", "返回")
    p.on_shelf = not p.on_shelf
    db.commit()
    return RedirectResponse(url=f"/delicious_town/recipe/{r.id}", status_code=302)


# ============================================================
# 营业系统（顾客消费）
# ============================================================
@router.post("/serve")
def serve_customers(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    elapsed = (datetime.utcnow() - town.last_service_at).total_seconds()
    if elapsed < CUSTOMER_CYCLE:
        remain = int(CUSTOMER_CYCLE - elapsed)
        return render_result(request, db, user, False, f"顾客还没到（剩余 {remain} 秒）", "/delicious_town", "返回")
    waiters = get_active_waiters(db, user.id)
    roaches = get_active_cockroaches(db, user.id)
    serving_tables = calc_serving_tables(town.seats, len(waiters) + 1, len(roaches))
    if town.oil_amount <= 0:
        return render_result(request, db, user, False, "油量为 0，无法营业", "/delicious_town/oil", "去添油")
    if serving_tables <= 0:
        return render_result(request, db, user, False, "无可用桌位（被蟑螂封锁或服务员不足）", "/delicious_town", "返回")
    shelf_recs = db.query(TownUserRecipe).filter(
        TownUserRecipe.town_id == town.id, TownUserRecipe.on_shelf == True).all()
    shelf = []
    for p in shelf_recs:
        r = db.query(TownRecipe).filter(TownRecipe.id == p.recipe_id).first()
        if r:
            shelf.append((r, p))
    if not shelf:
        return render_result(request, db, user, False, "无上架菜，先去菜谱上架", "/delicious_town/recipes", "去菜谱")
    _, _, _, _, picky_pct, rare_pct, revenue_coef = star_info(town.star_level)
    facilities = get_active_facilities(db, user.id)
    coin_bonus = 1.0 + 0.03 * len(waiters)
    satisfaction_bonus = 1.0 + 0.02 * len(waiters)
    total_coin = 0
    total_exp = 0
    customer_log = []
    for _ in range(serving_tables):
        rnd = random.random() * 100
        if rnd < rare_pct:
            ctype = "rare"
        elif rnd < rare_pct + picky_pct:
            ctype = "picky"
        else:
            ctype = "normal"
        coin_coef, exp_coef, _ = CUSTOMER_TYPES[ctype]
        if ctype == "normal":
            r, p = random.choice(shelf)
        else:
            sorted_shelf = sorted(shelf, key=lambda x: x[0].recipe_level, reverse=True)
            r, p = sorted_shelf[0] if sorted_shelf else random.choice(shelf)
        price = int(r.gold_income * QUALITY_PRICE_COEF.get(p.quality_level, 1.0) * coin_coef * revenue_coef)
        exp = int(r.exp_income * exp_coef)
        if any(f.facility_key == "trophy" for f in facilities):
            exp += 1
        if any(f.facility_key == "poster" for f in facilities):
            price += 1
        total_coin += int(price * coin_bonus)
        total_exp += int(exp * satisfaction_bonus)
        customer_log.append({"type": ctype, "dish": r.name, "coin": int(price * coin_bonus), "exp": int(exp * satisfaction_bonus)})
    town.gold += total_coin
    town.total_revenue += total_coin
    town.total_service += 1
    town.fame += serving_tables
    add_exp(town, total_exp)
    town.last_service_at = datetime.utcnow()
    db.commit()
    return render_result(request, db, user, True,
                         f"营业结算：{serving_tables} 桌 | 金币+{total_coin} | 经验+{total_exp}",
                         "/delicious_town", "返回首页")


# ============================================================
# 油量系统
# ============================================================
@router.get("/oil", response_class=HTMLResponse)
def oil_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    oil_pct = int(town.oil_amount / town.oil_cap * 100) if town.oil_cap > 0 else 0
    pot_index = next((i for i, (cap, _) in enumerate(OIL_POT_TABLE) if cap == town.oil_cap), 0)
    next_pot = OIL_POT_TABLE[pot_index + 1] if pot_index + 1 < len(OIL_POT_TABLE) else None
    ctx.update({"st": town, "oil_pct": oil_pct, "pot_index": pot_index, "next_pot": next_pot,
                "oil_packs": OIL_PACK_TABLE, "exp_need": exp_needed(town.restaurant_level)})
    return templates.TemplateResponse("delicious_town/oil.html", ctx)


@router.post("/oil/buy/{pack_key}")
def buy_oil_pack(pack_key: str, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    pack = OIL_PACK_TABLE.get(pack_key)
    if not pack:
        return render_result(request, db, user, False, "补油包不存在", "/delicious_town/oil", "返回")
    oil_gain, price = pack
    if town.gold < price:
        return render_result(request, db, user, False, f"金币不足（需 {price}）", "/delicious_town/oil", "返回")
    town.gold -= price
    town.oil_amount = min(town.oil_cap, town.oil_amount + oil_gain)
    db.commit()
    return render_result(request, db, user, True,
                         f"购买补油包，油量 +{oil_gain}（当前 {town.oil_amount}/{town.oil_cap}）",
                         "/delicious_town/oil", "返回")


@router.post("/oil/expand")
def expand_oil_pot(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    pot_index = next((i for i, (cap, _) in enumerate(OIL_POT_TABLE) if cap == town.oil_cap), 0)
    if pot_index + 1 >= len(OIL_POT_TABLE):
        return render_result(request, db, user, False, "油壶已达最高档", "/delicious_town/oil", "返回")
    next_cap, cost = OIL_POT_TABLE[pot_index + 1]
    if town.gold < cost:
        return render_result(request, db, user, False, f"金币不足（需 {cost}）", "/delicious_town/oil", "返回")
    town.gold -= cost
    town.oil_cap = next_cap
    db.commit()
    return render_result(request, db, user, True, f"油壶扩容至 {next_cap}！", "/delicious_town/oil", "返回")


# ============================================================
# 餐厅升星
# ============================================================
@router.get("/star", response_class=HTMLResponse)
def star_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    normal, fine, gold_count = count_learned_by_quality(db, town)
    can_apply, apply_msg = can_apply_star(town.star_level, town.restaurant_level, normal, fine, gold_count,
                                          town.total_service, town.total_revenue)
    next_star = town.star_level + 1 if town.star_level < 5 else None
    next_req = STAR_APPLY_TABLE.get(next_star) if next_star else None
    next_effect = STAR_TABLE.get(next_star) if next_star else None
    ctx.update({"st": town, "normal": normal, "fine": fine, "gold": gold_count,
                "can_apply": can_apply, "apply_msg": apply_msg,
                "next_star": next_star, "next_req": next_req, "next_effect": next_effect,
                "exp_need": exp_needed(town.restaurant_level)})
    return templates.TemplateResponse("delicious_town/star.html", ctx)


@router.post("/star/apply")
def apply_star(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    normal, fine, gold_count = count_learned_by_quality(db, town)
    can_apply, apply_msg = can_apply_star(town.star_level, town.restaurant_level, normal, fine, gold_count,
                                          town.total_service, town.total_revenue)
    if not can_apply:
        return render_result(request, db, user, False, f"不满足升星条件：{apply_msg}", "/delicious_town/star", "返回")
    town.star_level += 1
    star_exp = 80 * town.star_level
    add_exp(town, star_exp)
    db.commit()
    return render_result(request, db, user, True, f"餐厅升至 {town.star_level} 星！经验+{star_exp}",
                         "/delicious_town", "返回首页")


# ============================================================
# 服务员系统
# ============================================================
@router.get("/waiter", response_class=HTMLResponse)
def waiter_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    waiters = get_active_waiters(db, user.id)
    _, waiter_total, _, _, _, _, _ = star_info(town.star_level)
    waiter_info = []
    for w in waiters:
        friend = db.query(User).filter(User.id == w.friend_user_id).first()
        remain = max(0, int((w.expire_at - datetime.utcnow()).total_seconds()))
        waiter_info.append({"waiter": w, "friend": friend, "remain": remain})
    hired_ids = {w.friend_user_id for w in waiters}
    hireable = []
    for f in user.friends:
        if f.id not in hired_ids:
            hireable.append(f)
    ctx.update({"st": town, "waiter_info": waiter_info, "waiter_total": waiter_total,
                "hireable": hireable, "exp_need": exp_needed(town.restaurant_level)})
    return templates.TemplateResponse("delicious_town/waiter.html", ctx)


@router.post("/waiter/hire/{uid}")
def hire_waiter(uid: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    if uid == user.id:
        return render_result(request, db, user, False, "不能雇自己", "/delicious_town/waiter", "返回")
    waiters = get_active_waiters(db, user.id)
    _, waiter_total, _, _, _, _, _ = star_info(town.star_level)
    if len(waiters) + 1 >= waiter_total:
        return render_result(request, db, user, False, f"服务员位已满（{waiter_total}）", "/delicious_town/waiter", "返回")
    if any(w.friend_user_id == uid for w in waiters):
        return render_result(request, db, user, False, "已雇佣该好友", "/delicious_town/waiter", "返回")
    if town.gold < WAITER_HIRE_COST:
        return render_result(request, db, user, False, f"金币不足（需 {WAITER_HIRE_COST}）", "/delicious_town/waiter", "返回")
    friend = db.query(User).filter(User.id == uid).first()
    if not friend:
        return render_result(request, db, user, False, "好友不存在", "/delicious_town/waiter", "返回")
    town.gold -= WAITER_HIRE_COST
    bonus_type = random.choice(["coins", "satisfaction", "speed"])
    db.add(TownWaiter(town_id=town.id, user_id=user.id, friend_user_id=uid,
                      friend_nickname=friend.nickname, bonus_type=bonus_type,
                      expire_at=datetime.utcnow() + timedelta(seconds=WAITER_DURATION)))
    db.commit()
    return render_result(request, db, user, True, f"雇佣成功！加成类型：{bonus_type}（12 小时）",
                         "/delicious_town/waiter", "返回")


@router.post("/waiter/fire/{waiter_id}")
def fire_waiter(waiter_id: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    w = db.query(TownWaiter).filter(TownWaiter.id == waiter_id, TownWaiter.user_id == user.id).first()
    if not w:
        return render_result(request, db, user, False, "服务员不存在", "/delicious_town/waiter", "返回")
    name = w.friend_nickname or "未知"
    db.delete(w)
    db.commit()
    return render_result(request, db, user, True, f"已解雇服务员 {name}", "/delicious_town/waiter", "返回")


# ============================================================
# 设施系统
# ============================================================
@router.get("/facility", response_class=HTMLResponse)
def facility_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    active = get_active_facilities(db, user.id)
    active_keys = {f.facility_key for f in active}
    _, _, _, facility_slots, _, _, _ = star_info(town.star_level)
    facility_info = []
    for k, (name, price, hours, effect) in FACILITY_TABLE.items():
        remain = 0
        if k in active_keys:
            f = next(x for x in active if x.facility_key == k)
            remain = max(0, int((f.expire_at - datetime.utcnow()).total_seconds()))
        facility_info.append({"key": k, "name": name, "price": price, "hours": hours,
                              "effect": effect, "active": k in active_keys, "remain": remain})
    ctx.update({"st": town, "facility_info": facility_info, "facility_slots": facility_slots,
                "active_count": len(active), "exp_need": exp_needed(town.restaurant_level)})
    return templates.TemplateResponse("delicious_town/facility.html", ctx)


@router.post("/facility/buy/{facility_key}")
def buy_facility(facility_key: str, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    if facility_key not in FACILITY_TABLE:
        return render_result(request, db, user, False, "设施不存在", "/delicious_town/facility", "返回")
    name, price, hours, effect = FACILITY_TABLE[facility_key]
    active = get_active_facilities(db, user.id)
    _, _, _, facility_slots, _, _, _ = star_info(town.star_level)
    if any(f.facility_key == facility_key for f in active):
        return render_result(request, db, user, False, f"{name} 已生效中", "/delicious_town/facility", "返回")
    if len(active) >= facility_slots:
        return render_result(request, db, user, False, f"设施位已满（{facility_slots}）", "/delicious_town/facility", "返回")
    if town.gold < price:
        return render_result(request, db, user, False, f"金币不足（需 {price}）", "/delicious_town/facility", "返回")
    town.gold -= price
    db.add(TownFacility(user_id=user.id, facility_key=facility_key,
                        expire_at=datetime.utcnow() + timedelta(hours=hours)))
    db.commit()
    return render_result(request, db, user, True, f"购买 {name}，生效 {hours} 小时",
                         "/delicious_town/facility", "返回")


# ============================================================
# 翻橱柜系统（怀旧核心互动）
# ============================================================
@router.get("/visit/{uid}", response_class=HTMLResponse)
def visit_town(uid: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    host = db.query(User).filter(User.id == uid).first()
    if not host:
        return render_result(request, db, user, False, "对方不存在", "/home/friends", "返回好友")
    get_state(db, host)
    town = user.town
    host_town = host.town
    items = []
    for inv in db.query(TownIngredient).filter(
            TownIngredient.user_id == uid, TownIngredient.quantity > 0).all():
        locked = inv.locked
        items.append({"inv": inv, "item": inv, "locked": locked, "qty": inv.quantity})
    dl = get_daily_log(db, user.id)
    today = date.today().isoformat()
    flip_logs = db.query(TownFlipLog).filter(
        TownFlipLog.thief_id == user.id, TownFlipLog.host_id == uid,
        TownFlipLog.created_at >= datetime.strptime(today, "%Y-%m-%d")).all()
    flip_count_today = len(flip_logs)
    last_flip = flip_logs[-1] if flip_logs else None
    cooldown_remain = 0
    if last_flip:
        cooldown_remain = max(0, int(FLIP_COOLDOWN - (datetime.utcnow() - last_flip.created_at).total_seconds()))
    host_facilities = get_active_facilities(db, uid)
    has_fresh_cabinet = any(f.facility_key == "fresh_cabinet" for f in host_facilities)
    ctx.update({"host": host, "host_st": host_town, "items": items, "dl": dl,
                "flip_count_today": flip_count_today, "cooldown_remain": cooldown_remain,
                "has_fresh_cabinet": has_fresh_cabinet, "flip_daily_limit": FLIP_DAILY_LIMIT,
                "flip_per_friend_limit": FLIP_PER_FRIEND_LIMIT})
    return templates.TemplateResponse("delicious_town/visit.html", ctx)


@router.post("/raid/{uid}/{item_key}")
def raid(uid: int, item_key: str, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    if uid == user.id:
        return render_result(request, db, user, False, "不能翻自己的", "/home/friends", "返回好友")
    dl = get_daily_log(db, user.id)
    if dl.flip_total >= FLIP_DAILY_LIMIT:
        return render_result(request, db, user, False, f"今日翻柜已达上限({FLIP_DAILY_LIMIT}次)", "/home/friends", "返回好友")
    today = date.today().isoformat()
    flip_logs = db.query(TownFlipLog).filter(
        TownFlipLog.thief_id == user.id, TownFlipLog.host_id == uid,
        TownFlipLog.created_at >= datetime.strptime(today, "%Y-%m-%d")).all()
    flip_count_today = len(flip_logs)
    if flip_count_today >= FLIP_PER_FRIEND_LIMIT:
        return render_result(request, db, user, False, f"对该好友今日已翻 {FLIP_PER_FRIEND_LIMIT} 次",
                             f"/delicious_town/visit/{uid}", "返回")
    if flip_logs:
        last_flip = flip_logs[-1]
        cooldown_remain = max(0, int(FLIP_COOLDOWN - (datetime.utcnow() - last_flip.created_at).total_seconds()))
        if cooldown_remain > 0:
            return render_result(request, db, user, False, f"冷却中（剩余 {cooldown_remain} 秒）",
                                 f"/delicious_town/visit/{uid}", "返回")
    host_facilities = get_active_facilities(db, uid)
    if any(f.facility_key == "fresh_cabinet" for f in host_facilities):
        if random.random() < 0.5:
            return render_result(request, db, user, False, "防翻保鲜柜生效，没翻到", f"/delicious_town/visit/{uid}", "继续翻")
    if not remove_ingredient(db, uid, item_key, 1):
        return render_result(request, db, user, False, "对方没有这种食材了", f"/delicious_town/visit/{uid}", "返回")
    extra = 0
    host_inv_qty = count_ingredient(db, uid, item_key)
    if host_inv_qty >= 10 and random.random() < 0.2:
        extra += 1
    if host_inv_qty >= 30 and random.random() < 0.1:
        extra += 1
    total_get = 1 + extra
    town = user.town or get_state(db, user)
    add_ingredient(db, town, user.id, item_key, total_get)
    decay_idx = min(flip_count_today, len(FLIP_DECAY) - 1)
    decay = FLIP_DECAY[decay_idx]
    flip_exp = int(1 * decay)
    add_exp(town, flip_exp)
    host_town = get_state(db, db.query(User).filter(User.id == uid).first())
    host_town.gold += 1
    host_town.fame += 1
    dl.flip_total += 1
    db.add(TownFlipLog(thief_id=user.id, host_id=uid, item_key=item_key,
                       times_today=flip_count_today + 1))
    item = db.query(ItemTown).filter(ItemTown.key == item_key).first()
    db.commit()
    extra_text = f"（大堆叠额外+{extra}）" if extra > 0 else ""
    decay_text = f"（衰减至 {int(decay*100)}%）" if decay < 1.0 else ""
    return render_result(request, db, user, True,
                         f"翻到 {item.name if item else item_key} ×{total_get}{extra_text} 经验+{flip_exp}{decay_text}",
                         f"/delicious_town/visit/{uid}", "继续翻")


# ============================================================
# 蟑螂与恶作剧
# ============================================================
@router.post("/roach/throw/{uid}")
def throw_roach(uid: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    if uid == user.id:
        return render_result(request, db, user, False, "不能丢自己", "/home/friends", "返回好友")
    dl = get_daily_log(db, user.id)
    if dl.roach_throw >= ROACH_DAILY_LIMIT:
        return render_result(request, db, user, False, f"今日丢蟑螂已达上限({ROACH_DAILY_LIMIT}次)", "/home/friends", "返回好友")
    today = date.today().isoformat()
    last_roach = db.query(TownCockroach).filter(
        TownCockroach.thrower_id == user.id, TownCockroach.user_id == uid,
        TownCockroach.created_at >= datetime.strptime(today, "%Y-%m-%d")
    ).order_by(TownCockroach.created_at.desc()).first()
    if last_roach:
        cooldown_remain = max(0, int(ROACH_COOLDOWN - (datetime.utcnow() - last_roach.created_at).total_seconds()))
        if cooldown_remain > 0:
            return render_result(request, db, user, False, f"对该好友冷却中（剩余 {cooldown_remain} 秒）",
                                 f"/delicious_town/visit/{uid}", "返回")
    existing = get_active_cockroaches(db, uid)
    if len(existing) >= ROACH_MAX_PER_RESTAURANT:
        return render_result(request, db, user, False, "对方餐厅蟑螂已满", f"/delicious_town/visit/{uid}", "返回")
    host_facilities = get_active_facilities(db, uid)
    if any(f.facility_key == "sanitizer" for f in host_facilities):
        if random.random() < 0.5:
            return render_result(request, db, user, False, "卫生香氛生效，蟑螂被驱散", f"/delicious_town/visit/{uid}", "返回")
    db.add(TownCockroach(user_id=uid, thrower_id=user.id,
                         expire_at=datetime.utcnow() + timedelta(seconds=ROACH_DURATION)))
    dl.roach_throw += 1
    db.commit()
    return render_result(request, db, user, True, "丢出蟑螂！对方 1 桌被封锁 15 分钟",
                         f"/delicious_town/visit/{uid}", "返回")


@router.post("/roach/clean")
def clean_roach(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    roaches = get_active_cockroaches(db, user.id)
    if not roaches:
        return render_result(request, db, user, False, "没有蟑螂", "/delicious_town", "返回")
    for r in roaches:
        db.delete(r)
    add_exp(town, 2 * len(roaches))
    db.commit()
    return render_result(request, db, user, True, f"清理 {len(roaches)} 只蟑螂，经验+{2*len(roaches)}",
                         "/delicious_town", "返回")


@router.post("/roach/clean/{uid}")
def help_clean_roach(uid: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    if uid == user.id:
        return render_result(request, db, user, False, "用清理自己的入口", f"/delicious_town/visit/{uid}", "返回")
    roaches = get_active_cockroaches(db, uid)
    if not roaches:
        return render_result(request, db, user, False, "对方没有蟑螂", f"/delicious_town/visit/{uid}", "返回")
    for r in roaches:
        db.delete(r)
    town = get_state(db, user)
    add_exp(town, 3)
    host_town = get_state(db, db.query(User).filter(User.id == uid).first())
    host_town.fame += 1
    db.commit()
    return render_result(request, db, user, True, f"帮好友清理 {len(roaches)} 只蟑螂，经验+3",
                         f"/delicious_town/visit/{uid}", "返回")


# ============================================================
# 赛厨 / 厨具 / 技能点 / 厨艺大赛
# ============================================================
@router.get("/chef", response_class=HTMLResponse)
def chef_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    tools = db.query(TownChefTool).filter(TownChefTool.user_id == user.id).all()
    sk = get_chef_skill(db, user.id)
    normal, fine, gold = count_learned_by_quality(db, town)
    learned_total = normal + fine + gold
    power = chef_power(town, learned_total, gold, tools, sk)
    skill_allocated = sk.huohou + sk.daogong + sk.chuyi + sk.tiaowei
    skill_remain = SKILL_TOTAL_POINTS - skill_allocated
    recent = db.query(TownMatchLog).filter(
        TownMatchLog.attacker_id == user.id).order_by(TownMatchLog.created_at.desc()).limit(5).all()
    entry = db.query(TownContestEntry).filter(
        TownContestEntry.user_id == user.id, TownContestEntry.signup_date == today_str()).first()
    zone = contest_zone(town.restaurant_level)
    db.commit()
    ctx.update({"st": town, "tools": tools, "sk": sk, "power": power, "skill_remain": skill_remain,
                "skill_total": SKILL_TOTAL_POINTS, "skill_names": SKILL_NAMES, "chef_tools_cfg": CHEF_TOOLS,
                "cuisine_streets": CUISINE_STREETS, "match_used": 0, "match_limit": MATCH_DAILY_LIMIT,
                "recent": recent, "entry": entry, "zone": zone, "contest_zones": CONTEST_ZONES,
                "exp_need": exp_needed(town.restaurant_level)})
    return templates.TemplateResponse("delicious_town/chef.html", ctx)


@router.post("/chef/skill_alloc/{skill_key}")
def chef_skill_alloc(skill_key: str, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    if skill_key not in SKILL_KEYS:
        return render_result(request, db, user, False, "技能非法", "/delicious_town/chef", "返回")
    sk = get_chef_skill(db, user.id)
    allocated = sk.huohou + sk.daogong + sk.chuyi + sk.tiaowei
    if allocated >= SKILL_TOTAL_POINTS:
        return render_result(request, db, user, False, f"技能点已分配完（{SKILL_TOTAL_POINTS}点）", "/delicious_town/chef", "返回")
    setattr(sk, skill_key, getattr(sk, skill_key) + 1)
    db.commit()
    return render_result(request, db, user, True,
                         f"{SKILL_NAMES[skill_key]} +1（剩余 {SKILL_TOTAL_POINTS - allocated - 1} 点）",
                         "/delicious_town/chef", "返回赛厨中心")


@router.post("/chef/skill_reset")
def chef_skill_reset(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    reset_cost = 2000
    if town.gold < reset_cost:
        return render_result(request, db, user, False, f"金币不足（需 {reset_cost}）", "/delicious_town/chef", "返回")
    sk = get_chef_skill(db, user.id)
    sk.huohou = sk.daogong = sk.chuyi = sk.tiaowei = 0
    town.gold -= reset_cost
    db.commit()
    return render_result(request, db, user, True, f"技能点已重置（消耗 {reset_cost} 金币）", "/delicious_town/chef", "返回赛厨中心")


@router.post("/chef/tool_buy/{tool_key}")
def chef_tool_buy(tool_key: str, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    if tool_key not in CHEF_TOOLS:
        return render_result(request, db, user, False, "厨具不存在", "/delicious_town/chef", "返回")
    town = get_state(db, user)
    name, _, price = CHEF_TOOLS[tool_key]
    existing = db.query(TownChefTool).filter(
        TownChefTool.user_id == user.id, TownChefTool.tool_key == tool_key).first()
    if existing:
        return render_result(request, db, user, False, f"已拥有{name}", "/delicious_town/chef", "返回")
    if town.gold < price:
        return render_result(request, db, user, False, f"金币不足（需 {price}）", "/delicious_town/chef", "返回")
    town.gold -= price
    db.add(TownChefTool(user_id=user.id, tool_key=tool_key, level=1, equipped=True))
    db.commit()
    return render_result(request, db, user, True, f"购买 {name}（1级），已自动装备", "/delicious_town/chef", "返回赛厨中心")


@router.get("/match", response_class=HTMLResponse)
def match_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    tools = db.query(TownChefTool).filter(TownChefTool.user_id == user.id).all()
    sk = get_chef_skill(db, user.id)
    normal, fine, gold = count_learned_by_quality(db, town)
    learned_total = normal + fine + gold
    power = chef_power(town, learned_total, gold, tools, sk)
    candidates = []
    for f in user.friends:
        ft = get_state(db, f)
        ftools = db.query(TownChefTool).filter(TownChefTool.user_id == f.id).all()
        fsk = get_chef_skill(db, f.id)
        fn, ffi, fg = count_learned_by_quality(db, ft)
        fpower = chef_power(ft, fn + ffi + fg, fg, ftools, fsk)
        candidates.append({"user": f, "power": fpower, "level": ft.restaurant_level})
    recent = db.query(TownMatchLog).filter(
        TownMatchLog.attacker_id == user.id).order_by(TownMatchLog.created_at.desc()).limit(10).all()
    db.commit()
    ctx.update({"st": town, "power": power, "candidates": candidates, "recent": recent,
                "match_limit": MATCH_DAILY_LIMIT, "skill_names": SKILL_NAMES})
    return templates.TemplateResponse("delicious_town/match.html", ctx)


@router.post("/match/challenge/{uid}")
def match_challenge(uid: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    if uid == user.id:
        return render_result(request, db, user, False, "不能挑战自己", "/delicious_town/match", "返回")
    defender = db.query(User).filter(User.id == uid).first()
    if not defender:
        return render_result(request, db, user, False, "对手不存在", "/delicious_town/match", "返回")
    st_a = get_state(db, user)
    st_d = get_state(db, defender)
    tools_a = db.query(TownChefTool).filter(TownChefTool.user_id == user.id).all()
    tools_d = db.query(TownChefTool).filter(TownChefTool.user_id == uid).all()
    sk_a = get_chef_skill(db, user.id)
    sk_d = get_chef_skill(db, uid)
    a_n, a_fi, a_g = count_learned_by_quality(db, st_a)
    d_n, d_fi, d_g = count_learned_by_quality(db, st_d)
    power_a = chef_power(st_a, a_n + a_fi + a_g, a_g, tools_a, sk_a)
    power_d = chef_power(st_d, d_n + d_fi + d_g, d_g, tools_d, sk_d)
    judges = random.sample(SKILL_KEYS, 3) if len(SKILL_KEYS) >= 3 else SKILL_KEYS[:]
    a_skill = {"huohou": sk_a.huohou, "daogong": sk_a.daogong, "chuyi": sk_a.chuyi, "tiaowei": sk_a.tiaowei}
    d_skill = {"huohou": sk_d.huohou, "daogong": sk_d.daogong, "chuyi": sk_d.chuyi, "tiaowei": sk_d.tiaowei}
    judge_detail = []
    a_total = d_total = 0
    for jf in judges:
        a_s = judge_score(power_a, a_skill, jf)
        d_s = judge_score(power_d, d_skill, jf)
        a_total += a_s
        d_total += d_s
        judge_detail.append({"focus": SKILL_NAMES[jf], "a_score": a_s, "d_score": d_s})
    if a_total > d_total:
        winner_id = user.id
        result = "win"
    else:
        winner_id = uid
        result = "lose"
    if winner_id == user.id:
        st_a.gold += MATCH_WIN_COIN
        add_exp(st_a, MATCH_WIN_EXP)
        msg = f"赛厨胜利！总分 {a_total}:{d_total}，金币+{MATCH_WIN_COIN} 经验+{MATCH_WIN_EXP}"
    else:
        st_a.gold += MATCH_LOSE_COIN
        msg = f"赛厨失利。总分 {a_total}:{d_total}（平局或分低，被挑战方胜），安慰金币+{MATCH_LOSE_COIN}"
    db.add(TownMatchLog(attacker_id=user.id, defender_id=uid, attacker_score=a_total,
                        defender_score=d_total, winner_id=winner_id,
                        detail=json.dumps(judge_detail, ensure_ascii=False)))
    db.commit()
    ctx = get_common_context(request, db)
    ctx.update({"ok": True, "msg": msg, "a_total": a_total, "d_total": d_total,
                "winner_id": winner_id, "judge_detail": judge_detail, "defender": defender,
                "back_href": "/delicious_town/match", "back_text": "继续赛厨"})
    return templates.TemplateResponse("delicious_town/match_result.html", ctx)


@router.get("/contest", response_class=HTMLResponse)
def contest_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    today = today_str()
    zone = contest_zone(town.restaurant_level)
    entry = db.query(TownContestEntry).filter(
        TownContestEntry.user_id == user.id, TownContestEntry.signup_date == today).first()
    now_hour = datetime.utcnow().hour
    signup_open = CONTEST_SIGNUP_HOUR[0] <= now_hour < CONTEST_SIGNUP_HOUR[1]
    history = db.query(TownContestEntry).filter(
        TownContestEntry.user_id == user.id).order_by(TownContestEntry.created_at.desc()).limit(10).all()
    db.commit()
    ctx.update({"st": town, "zone": zone, "entry": entry, "signup_open": signup_open,
                "signup_cost": CONTEST_SIGNUP_COST, "contest_zones": CONTEST_ZONES,
                "history": history, "exp_need": exp_needed(town.restaurant_level)})
    return templates.TemplateResponse("delicious_town/contest.html", ctx)


@router.post("/contest/signup")
def contest_signup(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    zone = contest_zone(town.restaurant_level)
    if not zone:
        return render_result(request, db, user, False, "等级不足，需 Lv40+ 才能参加厨艺大赛", "/delicious_town/contest", "返回")
    now_hour = datetime.utcnow().hour
    if not (CONTEST_SIGNUP_HOUR[0] <= now_hour < CONTEST_SIGNUP_HOUR[1]):
        return render_result(request, db, user, False,
                             f"报名时段为每日 {CONTEST_SIGNUP_HOUR[0]}-{CONTEST_SIGNUP_HOUR[1]} 时",
                             "/delicious_town/contest", "返回")
    today = today_str()
    existing = db.query(TownContestEntry).filter(
        TownContestEntry.user_id == user.id, TownContestEntry.signup_date == today).first()
    if existing:
        return render_result(request, db, user, False, "今日已报名", "/delicious_town/contest", "返回")
    cost = CONTEST_SIGNUP_COST * 10
    if town.gold < cost:
        return render_result(request, db, user, False, f"金币不足（需 {cost}，折算自 {CONTEST_SIGNUP_COST} 体力）",
                             "/delicious_town/contest", "返回")
    town.gold -= cost
    db.add(TownContestEntry(user_id=user.id, zone=zone, signup_date=today))
    db.commit()
    zone_name = CONTEST_ZONES[zone][0]
    return render_result(request, db, user, True,
                         f"报名成功！赛区：{zone_name}（{today}），23 时后系统匹配，次日 8 时前公布",
                         "/delicious_town/contest", "返回大赛")


@router.post("/contest/settle")
def contest_settle(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    today = today_str()
    entry = db.query(TownContestEntry).filter(
        TownContestEntry.user_id == user.id, TownContestEntry.signup_date == today).first()
    if not entry:
        return render_result(request, db, user, False, "今日未报名", "/delicious_town/contest", "返回")
    if entry.matched:
        return render_result(request, db, user, False,
                             f"今日已结算：{'胜' if entry.result == 'win' else '负'}",
                             "/delicious_town/contest", "返回")
    others = db.query(TownContestEntry).filter(
        TownContestEntry.zone == entry.zone, TownContestEntry.signup_date == today,
        TownContestEntry.user_id != user.id, TownContestEntry.matched == False).all()
    if others:
        opp_entry = random.choice(others)
        opp_id = opp_entry.user_id
        opp_st = get_state(db, db.query(User).filter(User.id == opp_id).first())
        opp_tools = db.query(TownChefTool).filter(TownChefTool.user_id == opp_id).all()
        opp_sk = get_chef_skill(db, opp_id)
        opp_fu = db.query(User).filter(User.id == opp_id).first()
        opp_n, opp_fi, opp_g = count_learned_by_quality(db, opp_st)
        opp_power = chef_power(opp_st, opp_n + opp_fi + opp_g, opp_g, opp_tools, opp_sk)
        opp_name = opp_fu.nickname if opp_fu else "对手"
    else:
        zone_name, lo, hi = CONTEST_ZONES[entry.zone]
        npc_level = random.randint(max(lo, town.restaurant_level - 3), min(hi, town.restaurant_level + 3))
        opp_power = npc_level * 12 + random.randint(50, 150)
        opp_id = 0
        opp_name = f"{zone_name}NPC厨师(Lv{npc_level})"
    tools = db.query(TownChefTool).filter(TownChefTool.user_id == user.id).all()
    sk = get_chef_skill(db, user.id)
    a_n, a_fi, a_g = count_learned_by_quality(db, town)
    power = chef_power(town, a_n + a_fi + a_g, a_g, tools, sk)
    a_score = power + random.randint(0, 200)
    d_score = opp_power + random.randint(0, 200)
    if a_score >= d_score:
        entry.result = "win"
        entry.reward_coin = 500
        town.gold += 500
        msg = f"厨艺大赛胜利！击败 {opp_name}（{a_score}:{d_score}），奖励金币+500"
    else:
        entry.result = "lose"
        entry.reward_coin = 100
        town.gold += 100
        msg = f"厨艺大赛失利。负于 {opp_name}（{a_score}:{d_score}），安慰金币+100"
    entry.matched = True
    entry.opponent_id = opp_id
    db.commit()
    return render_result(request, db, user, True, msg, "/delicious_town/contest", "返回大赛")


# ============================================================
# 外卖订单系统（送餐）
# ============================================================
@router.get("/delivery", response_class=HTMLResponse)
def delivery_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    today = today_str()
    counters = json.loads(town.extra_json) if hasattr(town, "extra_json") and getattr(town, "extra_json", None) else {}
    if counters.get("date") != today or not counters.get("delivery_orders"):
        learned = []
        for p in db.query(TownUserRecipe).filter(TownUserRecipe.town_id == town.id).all():
            r = db.query(TownRecipe).filter(TownRecipe.id == p.recipe_id).first()
            if r:
                learned.append(r)
        counters["date"] = today
        counters["delivery_orders"] = _gen_delivery_orders(learned)
        counters["delivery_done"] = 0
        town.extra_json = json.dumps(counters, ensure_ascii=False)
        db.commit()
    orders = counters.get("delivery_orders", [])
    done_today = counters.get("delivery_done", 0)
    now_ts = int(time.time())
    order_info = []
    for idx, o in enumerate(orders):
        dish_key = o.get("dish_key") or ""
        r = db.query(TownRecipe).filter(TownRecipe.recipe_code == dish_key).first()
        dish_name = r.name if r else (dish_key or "未知")
        output_key = r.output_item_key if r else ""
        have = count_dish(db, user.id, output_key) if output_key else 0
        qty = int(o.get("qty", 0))
        remain = max(0, int(o.get("deadline_ts", 0)) - now_ts)
        expired = remain <= 0
        done = bool(o.get("done"))
        can_complete = (not done and not expired and have >= qty and done_today < DELIVERY_DAILY_LIMIT)
        order_info.append({"idx": idx, "dish_name": dish_name, "qty": qty, "have": have,
                           "reward_exp": int(o.get("reward_exp", 0)),
                           "reward_gold": int(o.get("reward_gold", 0)),
                           "remain": _fmt_remain(remain), "remain_sec": remain,
                           "expired": expired, "done": done, "can_complete": can_complete})
    ctx.update({"st": town, "order_info": order_info, "done_today": done_today,
                "delivery_limit": DELIVERY_DAILY_LIMIT, "exp_need": exp_needed(town.restaurant_level)})
    return templates.TemplateResponse("delicious_town/delivery.html", ctx)


@router.post("/delivery/complete/{order_index}")
def delivery_complete(order_index: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    counters = json.loads(town.extra_json) if getattr(town, "extra_json", None) else {}
    orders = counters.get("delivery_orders", [])
    if order_index < 0 or order_index >= len(orders):
        return render_result(request, db, user, False, "订单不存在", "/delicious_town/delivery", "返回外卖")
    o = orders[order_index]
    if o.get("done"):
        return render_result(request, db, user, False, "该订单已完成", "/delicious_town/delivery", "返回外卖")
    if int(time.time()) >= int(o.get("deadline_ts", 0)):
        return render_result(request, db, user, False, "订单已过期", "/delicious_town/delivery", "返回外卖")
    done_today = int(counters.get("delivery_done", 0))
    if done_today >= DELIVERY_DAILY_LIMIT:
        return render_result(request, db, user, False, f"今日外卖完成已达上限({DELIVERY_DAILY_LIMIT}单)",
                             "/delicious_town/delivery", "返回外卖")
    r = db.query(TownRecipe).filter(TownRecipe.recipe_code == o.get("dish_key", "")).first()
    if not r:
        return render_result(request, db, user, False, "菜谱不存在", "/delicious_town/delivery", "返回外卖")
    qty = int(o.get("qty", 0))
    if not r.output_item_key:
        return render_result(request, db, user, False, "该菜无成品", "/delicious_town/delivery", "返回外卖")
    if count_dish(db, user.id, r.output_item_key) < qty:
        have = count_dish(db, user.id, r.output_item_key)
        return render_result(request, db, user, False, f"{r.name} 数量不足（需 {qty}，当前 {have}）",
                             "/delicious_town/delivery", "返回外卖")
    if not remove_item(user.id, MODULE_KEY, r.output_item_key, qty, db=db):
        return render_result(request, db, user, False, "扣除菜品失败", "/delicious_town/delivery", "返回外卖")
    reward_exp = int(o.get("reward_exp", 0))
    reward_gold = int(o.get("reward_gold", 0))
    town.gold += reward_gold
    town.total_revenue += reward_gold
    add_exp(town, reward_exp)
    o["done"] = True
    o["reward_exp"] = 0
    o["reward_gold"] = 0
    counters["delivery_done"] = done_today + 1
    town.extra_json = json.dumps(counters, ensure_ascii=False)
    db.commit()
    return render_result(request, db, user, True,
                         f"完成外卖订单：{r.name}×{qty} | 经验+{reward_exp} 金币+{reward_gold}",
                         "/delicious_town/delivery", "返回外卖")


# ============================================================
# 规则 & 主线任务
# ============================================================
@router.get("/rules", response_class=HTMLResponse)
def rules(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    return templates.TemplateResponse("delicious_town/rules.html", ctx)


@router.get("/mainquests", response_class=HTMLResponse)
def mainquests_list(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    town = get_state(db, user)
    ctx.update({"st": town, "quests": MAIN_QUESTS})
    return templates.TemplateResponse("delicious_town/mainquests.html", ctx)