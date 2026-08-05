"""魔法花园模块（v0.3.2 同步框架完整玩法移植自 v0.3.1 app/routers/garden.py）

完整玩法：种植/收获/淡水/除草/除虫/商店/买种子/图谱点亮/订单/合成工坊/装饰/兑换/任务链/好友互动。
框架约定：
- router = APIRouter(prefix="/magic_garden")
- 同步 SQLAlchemy Session；get_current_user 校验登录
- templates.TemplateResponse("magic_garden/xxx.html", ctx)，ctx 含 request/user/lang/theme/_/t
- 多币种使用 utils.common.change_currency（花园金币 -> Wallet.g_coin）
- 背包使用 utils.common.add_item/remove_item（module_key="garden"）

数据模型打通：seed 生成的完整数据（ItemGarden/GardenSeed/GardenBloom/GardenAlbumEntryFull/
GardenRecipe/GardenOrderTemplate）与玩法路由直接引用；玩家状态使用新增的
GardenState/GardenPot/GardenCollection/GardenCraftCredit/GardenOrder/GardenOrderLog/
GardenExchange/GardenDailyLog。
"""
import json
import random
import math
from datetime import datetime, date, timedelta

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from models.database import get_db
from models.models import (
    User, Wallet, InventoryItem, Notification,
    ItemGarden, GardenSeed, GardenBloom, GardenAlbumEntryFull,
    GardenRecipe, GardenOrderTemplate,
    GardenState, GardenPot, GardenCollection, GardenCraftCredit,
    GardenOrder, GardenOrderLog, GardenExchange, GardenDailyLog,
    GardenFriendAction,
)
from utils.auth import get_current_user
from utils.i18n import t
from utils.common import change_currency, add_notification, fire_event
from . import garden_data as D
from .garden_data import QUEST_CHAIN, QUEST_CHAIN_REWARD_CHARM

router = APIRouter(prefix="/magic_garden", tags=["魔法花园"])
templates = Jinja2Templates(directory="templates")
MODULE_KEY = "garden"

# 阶段名称（索引 1..stages）
STAGE_NAMES = {0: "已播种", 1: "发芽期", 2: "花苗期", 3: "花蕾期", 4: "成熟"}
ACTION_NAMES = {"water": "浇水", "weed": "除草", "debug": "除虫"}

# 魔法师称号体系（16 段位，每 5 级一段）
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

# 装饰物品目录（与 seed 注册的 garden_deco_* 物品一一对应）
DECO_CATALOG: dict = {
    "garden_deco_fountain": {"name": "花园喷泉", "env_score": 15, "set_key": "water",  "price": 200},
    "garden_deco_pond":     {"name": "池塘",     "env_score": 30, "set_key": "water",  "price": 320},
    "garden_deco_lamp":     {"name": "路灯",     "env_score": 8,  "set_key": "light",  "price": 80},
    "garden_deco_arch":     {"name": "花拱门",   "env_score": 20, "set_key": "light",  "price": 180},
    "garden_deco_bench":    {"name": "长椅",     "env_score": 6,  "set_key": "statue", "price": 60},
    "garden_deco_statue":   {"name": "雕塑",     "env_score": 25, "set_key": "statue", "price": 240},
    "garden_deco_fence":    {"name": "栅栏",     "env_score": 5,  "set_key": "",       "price": 40},
    "garden_deco_tree":     {"name": "景观树",   "env_score": 10, "set_key": "",       "price": 100},
    "garden_deco_birdcage": {"name": "鸟笼",     "env_score": 12, "set_key": "",       "price": 120},
    "garden_deco_windmill": {"name": "风车",     "env_score": 18, "set_key": "",       "price": 160},
}

# 装饰套装
DECO_SETS: dict = {
    "water":  {"name": "水景套装", "members": ["garden_deco_fountain", "garden_deco_pond"],     "bonus": 10},
    "light":  {"name": "灯饰套装", "members": ["garden_deco_lamp", "garden_deco_arch"],          "bonus": 15},
    "statue": {"name": "雕塑套装", "members": ["garden_deco_statue", "garden_deco_arch", "garden_deco_bench"], "bonus": 20},
}

# 品质系统
QUALITY_TIERS = ["N", "G", "R", "E", "L"]
Q_VALUE_MUL = {"N": 1.0, "G": 1.1, "R": 1.25, "E": 1.45, "L": 1.7}
QUALITY_WEIGHT_BASE = {"N": 70, "G": 20, "R": 7, "E": 2.5, "L": 0.5}
RARITY_MUL = {"普通": 1.0, "稀有": 1.8, "史诗": 2.6, "传说": 4.0}
V_TIME_K0, V_TIME_K1 = 8, 0.5

# 订单系统配置
ORDER_MARGIN = {"normal": 1.15, "premium": 1.45, "limited": 1.75}
ORDER_URGENCY_MUL = {"normal": 1.0, "premium": 1.0, "limited": 1.2}
ORDER_DIFFICULTY_MUL = {"N": 1.0, "G": 1.1, "R": 1.25, "E": 1.45, "L": 1.7}
ORDER_DAILY_BASE, ORDER_DAILY_RAND = 4, 2
ORDER_ACTIVE_MAX = 6
ORDER_FREE_REROLL = 2
ORDER_REROLL_BASE, ORDER_REROLL_RATIO = 50, 1.5
ORDER_EXP_P = 0.6
ORDER_QTY_RANGE = (1, 3)


# ============================================================
# 基础工具
# ============================================================
def magician_title(level: int):
    for lo, hi, name in MAGICIAN_TITLES:
        if lo <= level <= hi:
            return name, (lo, hi)
    return "见习魔法师", (1, 5)


def tier_index(level: int) -> int:
    return min(15, (level - 1) // 5)


def pot_count_for_level(level: int) -> int:
    return min(12, 4 + tier_index(level))


def craft_slots_for_level(level: int) -> int:
    if level >= 46:
        return 6
    if level >= 31:
        return 5
    if level >= 21:
        return 4
    if level >= 11:
        return 3
    return 2


def craft_seconds_for(target_level: int) -> int:
    return 30 + target_level * 60


def item_level_cap(player_level: int) -> int:
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


def exp_needed(level: int) -> int:
    return 120 + 80 * level


def calc_env_score(decorations: list) -> tuple:
    base_sum = sum(d.get("env_score", 0) for d in decorations)
    placed_keys = {d.get("item_key") for d in decorations}
    set_bonuses = []
    bonus_total = 0
    for set_key, sinfo in DECO_SETS.items():
        if all(m in placed_keys for m in sinfo["members"]):
            bonus_total += sinfo["bonus"]
            set_bonuses.append({"set_key": set_key, "name": sinfo["name"], "bonus": sinfo["bonus"]})
    return base_sum + bonus_total, base_sum, set_bonuses


def env_quality_mul(env_score: int) -> float:
    k, s = 0.3, 50.0
    return 1 + k * (1 - math.exp(-env_score / s))


def roll_quality(quality_buff: float = 0.0, env_score: int = 0) -> str:
    env_mul = 1 + 0.3 * (1 - math.exp(-env_score / 50.0))
    weights = {q: QUALITY_WEIGHT_BASE[q] * (1 + quality_buff) * env_mul for q in QUALITY_TIERS}
    return random.choices(QUALITY_TIERS, weights=[weights[q] for q in QUALITY_TIERS], k=1)[0]


def v_time_unit(level: int) -> float:
    return V_TIME_K0 + V_TIME_K1 * level


def crop_base_value(grow_seconds: int, level: int) -> float:
    return (grow_seconds / 3600.0) * v_time_unit(level)


def item_value_coin(item_level: int, rarity: str, grow_seconds: int = 0, base_sell: int = 0) -> int:
    if grow_seconds > 0:
        v = crop_base_value(grow_seconds, item_level) * RARITY_MUL.get(rarity, 1.0)
    else:
        v = max(base_sell, 1) * 4.0
    return max(1, int(v))


def order_exp_scale(level: int) -> float:
    return 1.0 + level * 0.05


# ============================================================
# 框架上下文与背包/金币助手
# ============================================================
def get_common_context(request: Request, db: Session):
    user = get_current_user(request, db)
    if not user:
        return None
    lang = user.language or "zh"
    theme = user.theme or "light"
    unread_count = db.query(Notification).filter(
        Notification.user_id == user.id, Notification.is_read == False
    ).count()
    return {
        "request": request,
        "user": user,
        "lang": lang,
        "theme": theme,
        "_": lambda key: t(key, lang),
        "t": lambda key: t(key, lang),
        "unread_count": unread_count,
        "now": datetime.utcnow(),
    }


def get_gold(db: Session, user_id: int) -> int:
    w = db.query(Wallet).filter(Wallet.user_id == user_id).first()
    return w.g_coin if w else 0


def add_gold(db: Session, user_id: int, amount: int, remark: str = ""):
    change_currency(user_id, "g_coin", amount, "garden", remark=remark, db=db)


def spend_gold(db: Session, user_id: int, amount: int, remark: str = "") -> bool:
    if get_gold(db, user_id) < amount:
        return False
    change_currency(user_id, "g_coin", -amount, "garden", remark=remark, db=db)
    return True


def count_item(db: Session, user_id: int, item_code: str, module: str = "garden") -> int:
    row = db.query(InventoryItem).filter(
        InventoryItem.user_id == user_id, InventoryItem.module_key == module,
        InventoryItem.item_code == item_code).first()
    return row.quantity if row else 0


def add_item(db: Session, user_id: int, item_code: str, item_name: str,
             qty: int = 1, item_type: str = "item"):
    from utils.common import add_item as _add_item
    _add_item(user_id, "garden", item_code, item_name, qty, item_type=item_type, db=db)


def remove_item(db: Session, user_id: int, item_code: str, qty: int = 1) -> bool:
    from utils.common import remove_item as _remove_item
    return _remove_item(user_id, "garden", item_code, qty, db=db)


def list_inventory(db: Session, user_id: int, module: str = "garden"):
    return db.query(InventoryItem).filter(
        InventoryItem.user_id == user_id, InventoryItem.module_key == module).all()


def get_item_by_key(db: Session, key: str):
    return db.query(ItemGarden).filter(ItemGarden.key == key).first()


# ============================================================
# 玩家花园状态
# ============================================================
def get_state(db: Session, user_id: int) -> GardenState:
    st = db.query(GardenState).filter(GardenState.user_id == user_id).first()
    if not st:
        st = GardenState(user_id=user_id)
        db.add(st)
        db.flush()
        for i in range(st.pot_count):
            db.add(GardenPot(user_id=user_id, slot=i))
        db.commit()
        db.refresh(st)
    # 自动按当前等级补齐花盆数（段位解锁）
    target = pot_count_for_level(st.level)
    if target > st.pot_count:
        for i in range(st.pot_count, target):
            exists = db.query(GardenPot).filter(
                GardenPot.user_id == user_id, GardenPot.slot == i).first()
            if not exists:
                db.add(GardenPot(user_id=user_id, slot=i))
        st.pot_count = target
        db.commit()
        db.refresh(st)
    # 自动按当前等级补齐工坊槽位数
    craft_target = craft_slots_for_level(st.level)
    if craft_target > st.craft_slots:
        st.craft_slots = craft_target
        db.commit()
        db.refresh(st)
    return st


def add_exp(db: Session, st: GardenState, amount: int):
    old_level = st.level
    st.exp += amount
    while st.exp >= exp_needed(st.level):
        st.exp -= exp_needed(st.level)
        st.level += 1
    if st.level > old_level:
        target = pot_count_for_level(st.level)
        if target > st.pot_count:
            for i in range(st.pot_count, target):
                exists = db.query(GardenPot).filter(
                    GardenPot.user_id == st.user_id, GardenPot.slot == i).first()
                if not exists:
                    db.add(GardenPot(user_id=st.user_id, slot=i))
            st.pot_count = target
        craft_target = craft_slots_for_level(st.level)
        if craft_target > st.craft_slots:
            st.craft_slots = craft_target


def get_daily_log(db: Session, user_id: int) -> GardenDailyLog:
    today = date.today().isoformat()
    dl = db.query(GardenDailyLog).filter(
        GardenDailyLog.user_id == user_id, GardenDailyLog.date == today).first()
    if not dl:
        dl = GardenDailyLog(user_id=user_id, date=today)
        db.add(dl)
        db.flush()
    return dl


def steal_reward(times_today: int) -> tuple:
    if times_today < 3:
        return 2, 5
    if times_today < 6:
        return 1, 2
    return 0, 0


# ============================================================
# 花盆阶段状态机
# ============================================================
def current_stage(pot: GardenPot, seed) -> int:
    if not pot.seed_key or not pot.planted_at or not seed:
        return -1
    elapsed = (datetime.utcnow() - pot.planted_at).total_seconds()
    if elapsed >= seed.grow_seconds:
        return seed.stages
    step = seed.grow_seconds / seed.stages
    return min(int(elapsed // step), seed.stages - 1)


def stage_label(stage: int) -> str:
    return STAGE_NAMES.get(stage, "未知")


def remain_seconds(pot: GardenPot, seed) -> int:
    if not pot.seed_key or not pot.planted_at or not seed:
        return 0
    return max(0, int(seed.grow_seconds - (datetime.utcnow() - pot.planted_at).total_seconds()))


def needed_action(seed, stage: int):
    if stage <= 0 or stage >= seed.stages:
        return None
    actions = json.loads(seed.stage_actions) if seed.stage_actions else {}
    return actions.get(str(stage))


def pot_action_status(pot: GardenPot, seed) -> dict:
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
# 合成队列 / 任务链 JSON（寄存在 GardenState.craft_queue）
# ============================================================
def _craft_data(st: GardenState) -> dict:
    if not st.craft_queue:
        return {"queue": [], "charm": 0, "quest_step": 1, "quest_flowers": {}, "quest_materials": {}}
    data = json.loads(st.craft_queue)
    if isinstance(data, list):
        data = {"queue": data, "charm": 0, "quest_step": 1, "quest_flowers": {}, "quest_materials": {}}
    data.setdefault("queue", [])
    data.setdefault("charm", 0)
    data.setdefault("quest_step", 1)
    data.setdefault("quest_flowers", {})
    data.setdefault("quest_materials", {})
    return data


def _craft_queue(st: GardenState) -> list:
    return _craft_data(st)["queue"]


def _set_craft_queue(st: GardenState, q: list):
    data = _craft_data(st)
    data["queue"] = q
    st.craft_queue = json.dumps(data, ensure_ascii=False)


def _craft_queue_view(st: GardenState, now: datetime) -> list:
    q = _craft_queue(st)
    view = []
    for item in q:
        started_at = datetime.fromisoformat(item["started_at"])
        finish_at = datetime.fromisoformat(item["finish_at"])
        total = max(1, (finish_at - started_at).total_seconds())
        elapsed = (now - started_at).total_seconds()
        progress = min(100, max(0, int(elapsed / total * 100)))
        remain = max(0, int((finish_at - now).total_seconds()))
        view.append({**item, "progress": progress, "remain": remain, "done": now >= finish_at})
    return view


# ============================================================
# 订单系统
# ============================================================
def _gen_order_requirements(db_blooms: list, st_level: int, order_type: str) -> list:
    if not db_blooms:
        return []
    n_items = random.randint(1, min(3, len(db_blooms)))
    chosen = random.sample(db_blooms, min(n_items, len(db_blooms)))
    reqs = []
    for bloom in chosen:
        qty = random.randint(ORDER_QTY_RANGE[0], ORDER_QTY_RANGE[1])
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


def _calc_order_reward(reqs: list, order_type: str, st_level: int, has_deadline: bool) -> tuple:
    if not reqs:
        return 0, 0
    v_req = sum(r["qty"] * r["value_coin"] * Q_VALUE_MUL[r["quality"]] for r in reqs)
    urgency = ORDER_URGENCY_MUL.get(order_type, 1.0) * (1.1 if has_deadline else 1.0)
    difficulty = max(ORDER_DIFFICULTY_MUL[r["quality"]] for r in reqs)
    r_coin = int(v_req * ORDER_MARGIN.get(order_type, 1.15) * urgency * difficulty)
    r_exp = int((r_coin ** ORDER_EXP_P) * order_exp_scale(st_level))
    return max(1, r_coin), max(1, r_exp)


def _ensure_orders(db: Session, user_id: int, st: GardenState):
    now = datetime.utcnow()
    active = db.query(GardenOrder).filter(
        GardenOrder.user_id == user_id, GardenOrder.delivered.is_(False)).all()
    cleaned = False
    for o in active:
        if o.expire_at and o.expire_at < now:
            o.delivered = True
            cleaned = True
    if cleaned:
        active = [o for o in active if not o.delivered]
    if len(active) >= ORDER_ACTIVE_MAX:
        return active
    templates_pool = db.query(GardenOrderTemplate).filter(
        GardenOrderTemplate.level_min <= st.level,
        GardenOrderTemplate.level_max >= st.level).all()
    target = ORDER_DAILY_BASE + random.randint(0, ORDER_DAILY_RAND)
    to_add = max(0, min(target, ORDER_ACTIVE_MAX) - len(active))
    for _ in range(to_add):
        if templates_pool:
            tpl = random.choices(templates_pool, weights=[t.weight for t in templates_pool], k=1)[0]
            otype = tpl.order_type
            reqs = json.loads(tpl.requirements)
        else:
            # 回退：玩家已点亮花谱的花朵池
            lit_keys = [c.entry_key for c in db.query(GardenCollection).filter(
                GardenCollection.user_id == user_id).all()]
            db_blooms = []
            for ek in lit_keys:
                entry = db.query(GardenAlbumEntryFull).filter(GardenAlbumEntryFull.key == ek).first()
                if entry:
                    b = db.query(GardenBloom).filter(GardenBloom.key == entry.bloom_key).first()
                    if b:
                        db_blooms.append(b)
            if not db_blooms:
                b = db.query(GardenBloom).filter(GardenBloom.key == "bloom_wild_w").first()
                if b:
                    db_blooms = [b]
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
        db.add(GardenOrder(user_id=user_id, order_type=otype,
                           requirements=json.dumps(reqs, ensure_ascii=False),
                           reward_coin=r_coin, reward_exp=r_exp,
                           reward_token=5 if otype == "limited" else 0,
                           expire_at=expire))
    db.flush()
    return db.query(GardenOrder).filter(
        GardenOrder.user_id == user_id, GardenOrder.delivered.is_(False),
        (GardenOrder.expire_at.is_(None)) | (GardenOrder.expire_at > now)).all()


# ============================================================
# 装饰系统
# ============================================================
def _decorations(st: GardenState) -> list:
    return json.loads(st.decorations) if st.decorations else []


def _save_env_score(db: Session, st: GardenState) -> tuple:
    decos = _decorations(st)
    total, base_sum, set_bonuses = calc_env_score(decos)
    st.env_score = total
    return total, base_sum, set_bonuses


# ============================================================
# 任务链
# ============================================================
def _quest_have(data: dict, name: str) -> int:
    return data["quest_materials"].get(name, 0) + data["quest_flowers"].get(name, 0)


def _quest_deduct(data: dict, name: str, need: int):
    from_mat = min(need, data["quest_materials"].get(name, 0))
    if from_mat > 0:
        data["quest_materials"][name] = data["quest_materials"].get(name, 0) - from_mat
    rest = need - from_mat
    if rest > 0:
        data["quest_flowers"][name] = data["quest_flowers"].get(name, 0) - rest


# ============================================================
# 首页 / 花圃
# ============================================================
@router.get("", response_class=None)
def garden_home(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    st = get_state(db, user.id)
    pots = db.query(GardenPot).filter(GardenPot.user_id == user.id).order_by(GardenPot.slot).all()
    pot_info = []
    todo_harvest = 0
    todo_action = 0
    for p in pots:
        seed = db.query(GardenSeed).filter(GardenSeed.key == p.seed_key).first() if p.seed_key else None
        ainfo = pot_action_status(p, seed) if seed else {"stage": -1, "stage_label": "空地", "remain": 0, "action": None, "action_done": True}
        if seed and ainfo["stage"] == seed.stages:
            todo_harvest += 1
        if ainfo.get("action") and not ainfo["action_done"]:
            todo_action += 1
        pot_info.append({"pot": p, "seed": seed, **ainfo})
    entries = db.query(GardenAlbumEntryFull).all()
    lit_keys = set()
    for c in db.query(GardenCollection).filter(GardenCollection.user_id == user.id).all():
        if c.lit:
            lit_keys.add(c.entry_key)
    lit_count = len(lit_keys)
    title, tier_range = magician_title(st.level)

    day_seed = int(datetime.utcnow().strftime("%Y%m%d"))
    weather_msg = D.WEATHER_MESSAGES[day_seed % len(D.WEATHER_MESSAGES)]
    cdata = _craft_data(st)
    quest_step = cdata.get("quest_step", 1)
    if quest_step > len(QUEST_CHAIN):
        spirit_done = len(QUEST_CHAIN) + 1
    else:
        spirit_done = quest_step - 1
    spirit_total = D.SPIRIT_BOOK_TOTAL
    atlas_total = len(entries)
    rarity_counts = {b: 0 for b in D.RARITY_BUCKETS}
    lit_entries = [e for e in entries if e.key in lit_keys]
    bloom_keys = [e.bloom_key for e in lit_entries if e.bloom_key]
    blooms_map = {}
    if bloom_keys:
        for b in db.query(GardenBloom).filter(GardenBloom.key.in_(bloom_keys)).all():
            blooms_map[b.key] = b
    for e in lit_entries:
        b = blooms_map.get(e.bloom_key)
        br = b.rarity if b else "普通"
        rarity_counts[D.RARITY_BUCKET_MAP.get(br, "普通")] += 1
    empty_pots = sum(1 for p in pots if not p.seed_key)
    planted_pots = len(pots) - empty_pots
    unread = db.query(Notification).filter(
        Notification.user_id == user.id, Notification.is_read == False).count()
    garden_name = f"{user.nickname or user.username}的花园"

    ctx.update({
        "st": st, "pots": pots, "pot_info": pot_info,
        "todo_harvest": todo_harvest, "todo_action": todo_action,
        "entries": entries, "lit_count": lit_count,
        "exp_need": exp_needed(st.level), "action_names": ACTION_NAMES,
        "title": title, "tier_range": tier_range,
        "item_cap": item_level_cap(st.level),
        "D": D, "weather_msg": weather_msg,
        "spirit_done": spirit_done, "spirit_total": spirit_total,
        "atlas_total": atlas_total, "rarity_counts": rarity_counts,
        "empty_pots": empty_pots, "planted_pots": planted_pots,
        "unread": unread, "garden_name": garden_name,
        "announce": D.ANNOUNCE, "board_msg": D.BOARD_MSG,
        "gold": get_gold(db, user.id),
    })
    return templates.TemplateResponse("magic_garden/home.html", ctx)


@router.get("/pots")
def pots_list(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    st = get_state(db, user.id)
    pots = db.query(GardenPot).filter(GardenPot.user_id == user.id).order_by(GardenPot.slot).all()
    pot_info = []
    for p in pots:
        seed = db.query(GardenSeed).filter(GardenSeed.key == p.seed_key).first() if p.seed_key else None
        ainfo = pot_action_status(p, seed) if seed else {"stage": -1, "stage_label": "空地", "remain": 0, "action": None, "action_done": True}
        pot_info.append({"pot": p, "seed": seed, **ainfo})
    ctx.update({"st": st, "pot_info": pot_info, "exp_need": exp_needed(st.level),
                "action_names": ACTION_NAMES, "title": magician_title(st.level)[0],
                "gold": get_gold(db, user.id)})
    return templates.TemplateResponse("magic_garden/pots.html", ctx)


@router.get("/pot/{slot}")
def pot_detail(slot: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    st = get_state(db, user.id)
    p = db.query(GardenPot).filter(GardenPot.user_id == user.id, GardenPot.slot == slot).first()
    if not p:
        raise HTTPException(404)
    seed = db.query(GardenSeed).filter(GardenSeed.key == p.seed_key).first() if p.seed_key else None
    ainfo = pot_action_status(p, seed) if seed else {"stage": -1, "stage_label": "空地", "remain": 0, "action": None, "action_done": True}
    plantable = []
    if not p.seed_key:
        all_seeds = db.query(GardenSeed).filter(GardenSeed.min_level <= st.level).all()
        for s in all_seeds:
            n = count_item(db, user.id, s.seed_item_key)
            if n > 0:
                plantable.append((s, n))
    ctx.update({"st": st, "pot": p, "seed": seed, "locked": False, "ainfo": ainfo,
                "plantable": plantable, "action_names": ACTION_NAMES,
                "exp_need": exp_needed(st.level), "gold": get_gold(db, user.id)})
    return templates.TemplateResponse("magic_garden/pot_detail.html", ctx)


# ============================================================
# 播种 / 阶段操作 / 收获 / 上锁
# ============================================================
@router.post("/plant/{slot}")
def plant(slot: int, seed_key: str = Form(...), request: Request = None,
          db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    st = get_state(db, user.id)
    seed = db.query(GardenSeed).filter(GardenSeed.key == seed_key).first()
    if not seed:
        return _result(ctx, ok=False, msg="花种不存在",
                       back_href=f"/magic_garden/pot/{slot}", back_text="返回花盆")
    if st.level < seed.min_level:
        return _result(ctx, ok=False, msg=f"需要花园等级 {seed.min_level} 才能种植{seed.name}",
                       back_href=f"/magic_garden/pot/{slot}", back_text="返回花盆")
    if seed.item_level > item_level_cap(st.level):
        return _result(ctx, ok=False,
                       msg=f"花种等级Lv{seed.item_level}超过你当前可使用上限Lv{item_level_cap(st.level)}",
                       back_href=f"/magic_garden/pot/{slot}", back_text="返回花盆")
    if not remove_item(db, user.id, seed.seed_item_key, 1):
        return _result(ctx, ok=False, msg="没有该花种",
                       back_href="/magic_garden/craft", back_text="去合成")
    p = db.query(GardenPot).filter(GardenPot.user_id == user.id, GardenPot.slot == slot).first()
    if not p:
        return _result(ctx, ok=False, msg="花盆不存在",
                       back_href="/magic_garden/pots", back_text="返回花圃")
    p.seed_key = seed_key
    p.planted_at = datetime.utcnow()
    p.watered = False
    p.weeded = False
    p.debugged = False
    add_exp(db, st, 2)
    db.commit()
    return _result(ctx, ok=True,
                   msg=f"种下{seed.name}，约{seed.grow_seconds}秒成熟。注意浇水/除草/除虫可提升产量！",
                   back_href=f"/magic_garden/pot/{slot}", back_text="返回花盆")


@router.post("/action/{slot}/{action}")
def stage_action(slot: int, action: str, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    if action not in ACTION_NAMES:
        return _result(ctx, ok=False, msg="未知操作",
                       back_href=f"/magic_garden/pot/{slot}", back_text="返回花盆")
    st = get_state(db, user.id)
    p = db.query(GardenPot).filter(GardenPot.user_id == user.id, GardenPot.slot == slot).first()
    if not p or not p.seed_key:
        return _result(ctx, ok=False, msg="花盆为空",
                       back_href=f"/magic_garden/pot/{slot}", back_text="返回花盆")
    seed = db.query(GardenSeed).filter(GardenSeed.key == p.seed_key).first()
    ainfo = pot_action_status(p, seed)
    needed = needed_action(seed, ainfo["stage"])
    if needed != action:
        return _result(ctx, ok=False,
                       msg=f"当前阶段({ainfo['stage_label']})不需要{ACTION_NAMES[action]}",
                       back_href=f"/magic_garden/pot/{slot}", back_text="返回花盆")
    if ainfo["action_done"]:
        return _result(ctx, ok=False, msg="本阶段已操作过",
                       back_href=f"/magic_garden/pot/{slot}", back_text="返回花盆")
    if action == "water":
        p.watered = True
    elif action == "weed":
        p.weeded = True
    elif action == "debug":
        p.debugged = True
    add_exp(db, st, 3)
    db.commit()
    return _result(ctx, ok=True, msg=f"{ACTION_NAMES[action]}完成！获得经验+3，产量与稀有度提升",
                   back_href=f"/magic_garden/pot/{slot}", back_text="返回花盆")


@router.post("/harvest/{slot}")
def harvest(slot: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    st = get_state(db, user.id)
    p = db.query(GardenPot).filter(GardenPot.user_id == user.id, GardenPot.slot == slot).first()
    if not p or not p.seed_key:
        return _result(ctx, ok=False, msg="花盆为空",
                       back_href="/magic_garden/pots", back_text="返回花圃")
    seed = db.query(GardenSeed).filter(GardenSeed.key == p.seed_key).first()
    stage = current_stage(p, seed)
    if stage < seed.stages:
        return _result(ctx, ok=False,
                       msg=f"还未成熟（当前：{stage_label(stage)}），剩余 {remain_seconds(p, seed)} 秒",
                       back_href=f"/magic_garden/pot/{slot}", back_text="返回花盆")
    actions_done = sum([p.watered, p.weeded, p.debugged])
    base_yield = random.randint(seed.yield_min, seed.yield_max)
    final_yield = base_yield + (1 if actions_done >= 2 else 0)
    blooms_map = json.loads(seed.possible_blooms)
    bloom_keys = list(blooms_map.keys())
    weights = list(blooms_map.values())
    results = []
    quality_results = []
    coins_gain = 0
    exp_gain = 0
    lit_entries = []
    for _ in range(final_yield):
        bk = random.choices(bloom_keys, weights=weights, k=1)[0]
        bloom = db.query(GardenBloom).filter(GardenBloom.key == bk).first()
        if not bloom:
            continue
        add_item(db, user.id, bloom.item_key, bloom.name, 1, item_type="flower")
        quality = roll_quality(0.0, st.env_score)
        coin_per = int(bloom.sell_price // 2 * Q_VALUE_MUL[quality])
        coins_gain += coin_per
        results.append(bloom)
        quality_results.append(quality)
        exp_gain += 3 + bloom.item_level * 2
        entry = db.query(GardenAlbumEntryFull).filter(GardenAlbumEntryFull.key == bloom.album_entry_key).first()
        if entry:
            existing = db.query(GardenCollection).filter(
                GardenCollection.user_id == user.id,
                GardenCollection.entry_key == entry.key).first()
            if not existing:
                db.add(GardenCollection(user_id=user.id, entry_key=entry.key, lit=True))
                lit_entries.append(entry)
                exp_gain += 15 + bloom.item_level * 5
                coins_gain += 20 + bloom.item_level * 5
    add_gold(db, user.id, coins_gain, "garden_harvest")
    add_exp(db, st, exp_gain)
    p.seed_key = ""
    p.planted_at = None
    p.watered = False
    p.weeded = False
    p.debugged = False
    db.commit()
    if lit_entries:
        fire_event(user.id, MODULE_KEY, "icon_light", {"icon_key": "icon_gardener"}, db=db)
    bloom_summary = {}
    for b, q in zip(results, quality_results):
        key = f"{b.name}({q})"
        bloom_summary[key] = bloom_summary.get(key, 0) + 1
    summary_text = "、".join(f"{n}×{c}" for n, c in bloom_summary.items())
    msg = f"收获{seed.name}：{summary_text} | 金币+{coins_gain} | 经验+{exp_gain}"
    if st.env_score > 0:
        msg += f" | 环境值{st.env_score}加成品质"
    if lit_entries:
        msg += f" | 点亮花谱：{'、'.join(e.name for e in lit_entries)}"
    ctx.update({"ok": True, "msg": msg, "results": results, "quality_results": quality_results,
                "bloom_summary": bloom_summary, "coins_gain": coins_gain, "exp_gain": exp_gain,
                "lit_entries": lit_entries, "seed": seed, "st": st,
                "back_href": "/magic_garden/pots", "back_text": "返回花圃",
                "gold": get_gold(db, user.id)})
    return templates.TemplateResponse("magic_garden/harvest_result.html", ctx)


@router.post("/lock/{slot}")
def toggle_lock(slot: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    return RedirectResponse(url=f"/magic_garden/pot/{slot}", status_code=302)


# ============================================================
# 花谱（图鉴内核）
# ============================================================
@router.get("/album")
def album(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    entries = db.query(GardenAlbumEntryFull).order_by(GardenAlbumEntryFull.series).all()
    lit_keys = set()
    for c in db.query(GardenCollection).filter(GardenCollection.user_id == user.id).all():
        if c.lit:
            lit_keys.add(c.entry_key)
    groups = {}
    for e in entries:
        groups.setdefault(e.series, []).append(e)
    ctx.update({"groups": groups, "lit_keys": lit_keys, "lit_count": len(lit_keys),
                "total": len(entries)})
    return templates.TemplateResponse("magic_garden/album.html", ctx)


@router.get("/album/{entry_key}")
def album_detail(entry_key: str, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    entry = db.query(GardenAlbumEntryFull).filter(GardenAlbumEntryFull.key == entry_key).first()
    if not entry:
        raise HTTPException(404)
    bloom = db.query(GardenBloom).filter(GardenBloom.key == entry.bloom_key).first()
    lit = db.query(GardenCollection).filter(
        GardenCollection.user_id == user.id, GardenCollection.entry_key == entry_key).first()
    is_lit = bool(lit and lit.lit)
    hold = count_item(db, user.id, bloom.item_key) if bloom else 0
    ctx.update({"entry": entry, "bloom": bloom, "is_lit": is_lit, "hold": hold})
    return templates.TemplateResponse("magic_garden/album_detail.html", ctx)


@router.post("/album/light/{entry_key}")
def album_light(entry_key: str, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    entry = db.query(GardenAlbumEntryFull).filter(GardenAlbumEntryFull.key == entry_key).first()
    if not entry:
        raise HTTPException(404)
    bloom = db.query(GardenBloom).filter(GardenBloom.key == entry.bloom_key).first()
    if not bloom:
        return _result(ctx, ok=False, msg="花谱数据异常",
                       back_href="/magic_garden/album", back_text="返回花谱")
    existing = db.query(GardenCollection).filter(
        GardenCollection.user_id == user.id, GardenCollection.entry_key == entry_key).first()
    if existing and existing.lit:
        return _result(ctx, ok=False, msg="该花谱已点亮",
                       back_href=f"/magic_garden/album/{entry_key}", back_text="返回")
    if count_item(db, user.id, bloom.item_key) < 1:
        return _result(ctx, ok=False, msg=f"未持有{bloom.name}，无法点亮",
                       back_href=f"/magic_garden/album/{entry_key}", back_text="返回")
    st = get_state(db, user.id)
    if existing:
        existing.lit = True
        existing.lit_at = datetime.utcnow()
    else:
        db.add(GardenCollection(user_id=user.id, entry_key=entry_key, lit=True))
    add_gold(db, user.id, 20, "garden_album_light")
    add_exp(db, st, 15)
    db.commit()
    fire_event(user.id, MODULE_KEY, "icon_light", {"icon_key": "icon_gardener"}, db=db)
    fire_event(user.id, MODULE_KEY, "achievement", {"key": "achv_flower_master", "delta": 1}, db=db)
    return _result(ctx, ok=True, msg=f"点亮花谱【{entry.name}】！金币+20 经验+15",
                   back_href="/magic_garden/album", back_text="返回花谱")


# ============================================================
# 合成工坊
# ============================================================
@router.get("/craft")
def craft_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    st = get_state(db, user.id)
    cap = item_level_cap(st.level)
    now = datetime.utcnow()
    queue_view = sorted(_craft_queue_view(st, now), key=lambda x: x.get("slot", 0))
    occupied_slots = {item["slot"] for item in queue_view}
    slots = []
    for i in range(st.craft_slots):
        item = next((x for x in queue_view if x["slot"] == i), None)
        slots.append({"slot": i, "busy": item is not None, "item": item})
    recipes = db.query(GardenRecipe).all()
    info = []
    for r in recipes:
        seed = db.query(GardenSeed).filter(GardenSeed.key == r.result_seed_key).first()
        mats = json.loads(r.materials)
        mat_info = []
        can = True
        for k, n in mats.items():
            item = get_item_by_key(db, k)
            cnt = count_item(db, user.id, k)
            mat_info.append({"key": k, "name": item.name if item else k, "need": n, "have": cnt})
            if cnt < n:
                can = False
        credit = db.query(GardenCraftCredit).filter(
            GardenCraftCredit.user_id == user.id, GardenCraftCredit.recipe_id == r.id).first()
        credits = credit.credits if credit else 0
        level_locked = seed and seed.item_level > cap
        craft_secs = craft_seconds_for(r.target_level)
        info.append({"recipe": r, "seed": seed, "mats": mat_info,
                     "can": can and not level_locked, "credits": credits,
                     "level_locked": level_locked, "craft_seconds": craft_secs})
    ctx.update({"st": st, "info": info, "item_cap": cap,
                "title": magician_title(st.level)[0], "slots": slots,
                "queue_view": queue_view, "free_slots": st.craft_slots - len(occupied_slots),
                "gold": get_gold(db, user.id)})
    return templates.TemplateResponse("magic_garden/craft.html", ctx)


def _start_craft(db: Session, request: Request, ctx: dict, user, st: GardenState,
                 recipe_id: int):
    r = db.query(GardenRecipe).filter(GardenRecipe.id == recipe_id).first()
    if not r:
        return _result(ctx, ok=False, msg="配方不存在",
                       back_href="/magic_garden/craft", back_text="返回合成")
    seed = db.query(GardenSeed).filter(GardenSeed.key == r.result_seed_key).first()
    if not seed:
        return _result(ctx, ok=False, msg="目标花种不存在",
                       back_href="/magic_garden/craft", back_text="返回合成")
    if seed.item_level > item_level_cap(st.level):
        return _result(ctx, ok=False,
                       msg=f"目标花种Lv{seed.item_level}超过你当前可使用上限Lv{item_level_cap(st.level)}",
                       back_href="/magic_garden/craft", back_text="返回合成")
    q = _craft_queue(st)
    occupied = {it["slot"] for it in q}
    free_slot = next((i for i in range(st.craft_slots) if i not in occupied), None)
    if free_slot is None:
        return _result(ctx, ok=False,
                       msg=f"工坊槽位已满（{st.craft_slots}/{st.craft_slots}），请先领取完成的合成",
                       back_href="/magic_garden/craft", back_text="返回合成")
    mats = json.loads(r.materials)
    for k, n in mats.items():
        if count_item(db, user.id, k) < n:
            item = get_item_by_key(db, k)
            return _result(ctx, ok=False, msg=f"材料不足：{item.name if item else k}",
                           back_href="/magic_garden/craft", back_text="返回合成")
    for k, n in mats.items():
        remove_item(db, user.id, k, n)
    now = datetime.utcnow()
    finish = now + timedelta(seconds=craft_seconds_for(r.target_level))
    q.append({
        "recipe_id": r.id, "recipe_name": r.name, "target_seed_key": r.result_seed_key,
        "target_seed_name": seed.name, "started_at": now.isoformat(),
        "finish_at": finish.isoformat(), "slot": free_slot,
    })
    _set_craft_queue(st, q)
    db.commit()
    return _result(ctx, ok=True,
                   msg=f"开始合成【{r.name}】！占用槽位 #{free_slot+1}，预计 {craft_seconds_for(r.target_level)} 秒后完成（Lv{r.target_level}）",
                   back_href="/magic_garden/craft", back_text="返回工坊")


@router.post("/craft/{recipe_id}")
def craft(recipe_id: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    st = get_state(db, user.id)
    return _start_craft(db, request, ctx, user, st, recipe_id)


@router.post("/craft/start/{recipe_id}")
def craft_start(recipe_id: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    st = get_state(db, user.id)
    return _start_craft(db, request, ctx, user, st, recipe_id)


@router.post("/craft/collect/{slot}")
def craft_collect(slot: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    st = get_state(db, user.id)
    q = _craft_queue(st)
    item = next((it for it in q if it.get("slot") == slot), None)
    if not item:
        return _result(ctx, ok=False, msg=f"槽位 #{slot+1} 没有进行中的合成",
                       back_href="/magic_garden/craft", back_text="返回工坊")
    finish_at = datetime.fromisoformat(item["finish_at"])
    now = datetime.utcnow()
    if now < finish_at:
        remain = int((finish_at - now).total_seconds())
        return _result(ctx, ok=False, msg=f"合成未完成，还需 {remain} 秒",
                       back_href="/magic_garden/craft", back_text="返回工坊")
    recipe_id = item["recipe_id"]
    r = db.query(GardenRecipe).filter(GardenRecipe.id == recipe_id).first()
    if not r:
        q = [it for it in q if it.get("slot") != slot]
        _set_craft_queue(st, q)
        db.commit()
        return _result(ctx, ok=False, msg="配方已失效，合成作废",
                       back_href="/magic_garden/craft", back_text="返回工坊")
    seed = db.query(GardenSeed).filter(GardenSeed.key == r.result_seed_key).first()
    credit = db.query(GardenCraftCredit).filter(
        GardenCraftCredit.user_id == user.id, GardenCraftCredit.recipe_id == r.id).first()
    if not credit:
        credit = GardenCraftCredit(user_id=user.id, recipe_id=r.id, credits=0)
        db.add(credit)
        db.flush()
    guaranteed = credit.credits + 1 >= r.fail_credit_threshold
    success = guaranteed or (random.randint(1, 100) <= r.success_rate)
    q = [it for it in q if it.get("slot") != slot]
    _set_craft_queue(st, q)
    if success:
        add_item(db, user.id, seed.seed_item_key, f"{seed.name}种子", r.result_qty, item_type="flower")
        credit.credits = 0
        craft_exp = 5 + r.target_level * 3
        add_exp(db, st, craft_exp)
        db.commit()
        msg = f"合成成功！获得{seed.name}种子×{r.result_qty}"
        if guaranteed:
            msg += "（保底触发）"
        msg += f" | 经验+{craft_exp}"
        return _result(ctx, ok=True, msg=msg,
                       back_href="/magic_garden/craft", back_text="返回工坊")
    else:
        credit.credits += 1
        db.commit()
        remain = r.fail_credit_threshold - credit.credits
        return _result(ctx, ok=False,
                       msg=f"合成失败…保底进度 {credit.credits}/{r.fail_credit_threshold}（再失败{remain}次必成）",
                       back_href="/magic_garden/craft", back_text="返回工坊")


# ============================================================
# 兑换中心
# ============================================================
@router.get("/exchange")
def exchange_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    exchanges = db.query(GardenExchange).all()
    info = []
    for ex in exchanges:
        seed = db.query(GardenSeed).filter(GardenSeed.key == ex.result_seed_key).first()
        mats = json.loads(ex.materials)
        mat_info = []
        can = True
        for k, n in mats.items():
            item = get_item_by_key(db, k)
            cnt = count_item(db, user.id, k)
            mat_info.append({"key": k, "name": item.name if item else k, "need": n, "have": cnt})
            if cnt < n:
                can = False
        info.append({"ex": ex, "seed": seed, "mats": mat_info, "can": can})
    ctx.update({"info": info, "gold": get_gold(db, user.id)})
    return templates.TemplateResponse("magic_garden/exchange.html", ctx)


@router.post("/exchange/{exchange_id}")
def do_exchange(exchange_id: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    ex = db.query(GardenExchange).filter(GardenExchange.id == exchange_id).first()
    if not ex:
        return _result(ctx, ok=False, msg="兑换不存在",
                       back_href="/magic_garden/exchange", back_text="返回兑换")
    seed = db.query(GardenSeed).filter(GardenSeed.key == ex.result_seed_key).first()
    if not seed:
        return _result(ctx, ok=False, msg="目标花种不存在",
                       back_href="/magic_garden/exchange", back_text="返回兑换")
    mats = json.loads(ex.materials)
    for k, n in mats.items():
        if count_item(db, user.id, k) < n:
            item = get_item_by_key(db, k)
            return _result(ctx, ok=False, msg=f"材料不足：{item.name if item else k}",
                           back_href="/magic_garden/exchange", back_text="返回兑换")
    for k, n in mats.items():
        remove_item(db, user.id, k, n)
    add_item(db, user.id, seed.seed_item_key, f"{seed.name}种子", ex.result_qty, item_type="flower")
    db.commit()
    return _result(ctx, ok=True, msg=f"兑换成功！获得{seed.name}种子×{ex.result_qty}",
                   back_href="/magic_garden/exchange", back_text="返回兑换")


# ============================================================
# 展示页
# ============================================================
@router.get("/showcase")
def showcase(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    st = get_state(db, user.id)
    entries = db.query(GardenAlbumEntryFull).all()
    lit_keys = set()
    lit_entries = []
    for c in db.query(GardenCollection).filter(
            GardenCollection.user_id == user.id).order_by(GardenCollection.lit_at.desc()).all():
        if c.lit:
            lit_keys.add(c.entry_key)
            e = db.query(GardenAlbumEntryFull).filter(GardenAlbumEntryFull.key == c.entry_key).first()
            if e:
                lit_entries.append(e)
    recent = lit_entries[:5]
    invs = list_inventory(db, user.id)
    rare_blooms = []
    for inv in invs:
        if inv.item_type == "flower" and inv.quantity > 0:
            bloom = db.query(GardenBloom).filter(GardenBloom.item_key == inv.item_code).first()
            if bloom and bloom.rarity in ("稀有", "传说"):
                rare_blooms.append({"bloom": bloom, "item": bloom, "qty": inv.quantity})
    ctx.update({"st": st, "lit_count": len(lit_keys), "total": len(entries),
                "recent": recent, "rare_blooms": rare_blooms,
                "gold": get_gold(db, user.id)})
    return templates.TemplateResponse("magic_garden/showcase.html", ctx)


# ============================================================
# 好友互动：偷花 / 帮忙 / 送花 / 访问
# ============================================================
def _already_stolen(db: Session, thief_id: int, pot_id: int) -> bool:
    return db.query(GardenFriendAction).filter(
        GardenFriendAction.actor_user_id == thief_id,
        GardenFriendAction.action_type == "steal",
        GardenFriendAction.flower_code == str(pot_id)).first() is not None


@router.get("/visit/{uid}")
def visit_garden(uid: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    host = db.query(User).filter(User.id == uid).first()
    if not host:
        raise HTTPException(404)
    pots = db.query(GardenPot).filter(GardenPot.user_id == uid).order_by(GardenPot.slot).all()
    pot_info = []
    for p in pots:
        seed = db.query(GardenSeed).filter(GardenSeed.key == p.seed_key).first() if p.seed_key else None
        ainfo = pot_action_status(p, seed) if seed else {"stage": -1, "stage_label": "空地", "remain": 0, "action": None, "action_done": True}
        mature = seed and ainfo["stage"] == seed.stages
        already_stolen = _already_stolen(db, user.id, p.id)
        can_help = seed and ainfo.get("action") and not ainfo["action_done"] and not mature
        pot_info.append({"pot": p, "seed": seed, "mature": mature,
                         "already_stolen": already_stolen, "can_help": can_help, "ainfo": ainfo})
    my_flowers = []
    for inv in list_inventory(db, user.id):
        if inv.item_type == "flower" and inv.quantity > 0:
            my_flowers.append((inv, inv.quantity))
    ctx.update({"host": host, "pot_info": pot_info, "my_flowers": my_flowers,
                "action_names": ACTION_NAMES})
    return templates.TemplateResponse("magic_garden/visit.html", ctx)


@router.post("/steal/{pot_id}")
def steal_flower(pot_id: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    dl = get_daily_log(db, user.id)
    if dl.steal_count >= DAILY_STEAL_LIMIT:
        return _result(ctx, ok=False, msg=f"今日偷花已达上限({DAILY_STEAL_LIMIT}次)",
                       back_href="/home/friends", back_text="返回好友")
    p = db.query(GardenPot).filter(GardenPot.id == pot_id).first()
    if not p or p.user_id == user.id:
        return _result(ctx, ok=False, msg="不能偷自己的",
                       back_href="/magic_garden", back_text="返回")
    if _already_stolen(db, user.id, p.id):
        return _result(ctx, ok=False, msg="已偷过这盆",
                       back_href=f"/magic_garden/visit/{p.user_id}", back_text="返回")
    seed = db.query(GardenSeed).filter(GardenSeed.key == p.seed_key).first() if p.seed_key else None
    if not seed or current_stage(p, seed) < seed.stages:
        return _result(ctx, ok=False, msg="还没成熟",
                       back_href=f"/magic_garden/visit/{p.user_id}", back_text="返回")
    blooms_map = json.loads(seed.possible_blooms)
    bloom_keys = list(blooms_map.keys())
    weights = list(blooms_map.values())
    bk = random.choices(bloom_keys, weights=weights, k=1)[0]
    bloom = db.query(GardenBloom).filter(GardenBloom.key == bk).first()
    if bloom:
        add_item(db, user.id, bloom.item_key, bloom.name, 1, item_type="flower")
    p.seed_key = ""
    p.planted_at = None
    p.watered = False
    p.weeded = False
    p.debugged = False
    exp_g, coin_g = steal_reward(dl.steal_count)
    dl.steal_count += 1
    db.add(GardenFriendAction(actor_user_id=user.id, target_user_id=p.user_id,
                              action_type="steal", flower_code=str(p.id)))
    add_notification(p.user_id, "interact", f"{user.nickname or user.username} 偷了你的 {seed.name}",
                     f"{user.nickname or user.username} 偷了你的 {seed.name}（{bloom.name if bloom else ''}）",
                     MODULE_KEY, db=db)
    st = get_state(db, user.id)
    add_exp(db, st, exp_g)
    add_gold(db, user.id, coin_g, "garden_steal")
    db.commit()
    extra = f" | 经验+{exp_g} 金币+{coin_g}" if (exp_g or coin_g) else "（今日偷花奖励已衰减为0）"
    return _result(ctx, ok=True,
                   msg=f"偷到{bloom.name if bloom else seed.name}×1{extra}（今日{dl.steal_count}/{DAILY_STEAL_LIMIT}）",
                   back_href=f"/magic_garden/visit/{p.user_id}", back_text="继续逛")


@router.post("/help/{pot_id}/{action}")
def help_friend(pot_id: int, action: str, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    if action not in ACTION_NAMES:
        return _result(ctx, ok=False, msg="未知操作",
                       back_href="/home/friends", back_text="返回好友")
    dl = get_daily_log(db, user.id)
    if dl.help_count >= DAILY_HELP_LIMIT:
        return _result(ctx, ok=False, msg=f"今日帮忙已达上限({DAILY_HELP_LIMIT}次)",
                       back_href="/home/friends", back_text="返回好友")
    p = db.query(GardenPot).filter(GardenPot.id == pot_id).first()
    if not p or p.user_id == user.id:
        return _result(ctx, ok=False, msg="不能帮自己",
                       back_href="/home/friends", back_text="返回好友")
    seed = db.query(GardenSeed).filter(GardenSeed.key == p.seed_key).first() if p.seed_key else None
    if not seed:
        return _result(ctx, ok=False, msg="花盆为空",
                       back_href=f"/magic_garden/visit/{p.user_id}", back_text="返回")
    ainfo = pot_action_status(p, seed)
    needed = needed_action(seed, ainfo["stage"])
    if needed != action or ainfo["action_done"]:
        return _result(ctx, ok=False, msg="当前阶段不需要此操作或已完成",
                       back_href=f"/magic_garden/visit/{p.user_id}", back_text="返回")
    if action == "water":
        p.watered = True
    elif action == "weed":
        p.weeded = True
    elif action == "debug":
        p.debugged = True
    dl.help_count += 1
    st = get_state(db, user.id)
    add_exp(db, st, 2)
    add_gold(db, user.id, 5, "garden_help")
    add_notification(p.user_id, "interact", "好友帮忙",
                     f"{user.nickname or user.username} 帮你{ACTION_NAMES[action]}了{seed.name}",
                     MODULE_KEY, db=db)
    db.commit()
    return _result(ctx, ok=True,
                   msg=f"帮好友{ACTION_NAMES[action]}完成！经验+2 金币+5（今日{dl.help_count}/{DAILY_HELP_LIMIT}）",
                   back_href=f"/magic_garden/visit/{p.user_id}", back_text="继续逛")


@router.post("/gift/{uid}/{item_key}")
def gift_flower(uid: int, item_key: str, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    if not remove_item(db, user.id, item_key, 1):
        return _result(ctx, ok=False, msg="你没有这朵花",
                       back_href=f"/magic_garden/visit/{uid}", back_text="返回")
    item = get_item_by_key(db, item_key)
    add_item(db, uid, item_key, item.name if item else item_key, 1, item_type="flower")
    add_notification(uid, "interact", "收到鲜花",
                     f"{user.nickname or user.username} 送给你 {item.name if item else item_key} ×1",
                     MODULE_KEY, db=db)
    db.commit()
    return _result(ctx, ok=True, msg=f"送出{item.name if item else item_key}×1",
                   back_href=f"/magic_garden/visit/{uid}", back_text="返回")


# ============================================================
# 商店 / 规则
# ============================================================
@router.get("/shop")
def garden_shop(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    st = get_state(db, user.id)
    cap = item_level_cap(st.level)
    seeds = db.query(GardenSeed).all()
    shop_list = []
    for s in seeds:
        if "shop" in s.obtain_sources:
            n = count_item(db, user.id, s.seed_item_key)
            shop_list.append({"seed": s, "have": n,
                              "locked_level": st.level < s.min_level or s.item_level > cap})
    ctx.update({"st": st, "shop_list": shop_list, "item_cap": cap,
                "title": magician_title(st.level)[0], "gold": get_gold(db, user.id)})
    return templates.TemplateResponse("magic_garden/shop.html", ctx)


@router.post("/shop/buy/{seed_key}")
def shop_buy(seed_key: str, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    st = get_state(db, user.id)
    seed = db.query(GardenSeed).filter(GardenSeed.key == seed_key).first()
    if not seed or "shop" not in seed.obtain_sources:
        return _result(ctx, ok=False, msg="该花种不可购买",
                       back_href="/magic_garden/shop", back_text="返回商店")
    if st.level < seed.min_level:
        return _result(ctx, ok=False, msg=f"需要花园等级 {seed.min_level}",
                       back_href="/magic_garden/shop", back_text="返回商店")
    if seed.item_level > item_level_cap(st.level):
        return _result(ctx, ok=False,
                       msg=f"花种Lv{seed.item_level}超过你当前可使用上限Lv{item_level_cap(st.level)}",
                       back_href="/magic_garden/shop", back_text="返回商店")
    base = seed.item_level * 20
    price = base if seed.rarity == "普通" else base * 2
    if not spend_gold(db, user.id, price, "garden_shop_buy"):
        return _result(ctx, ok=False, msg=f"金币不足（需{price}）",
                       back_href="/magic_garden/shop", back_text="返回商店")
    add_item(db, user.id, seed.seed_item_key, f"{seed.name}种子", 1, item_type="flower")
    db.commit()
    return _result(ctx, ok=True, msg=f"购买{seed.name}种子×1（花费{price}金币）",
                   back_href="/magic_garden/shop", back_text="返回商店")


@router.get("/rules")
def rules(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    return templates.TemplateResponse("magic_garden/rules.html", ctx)


# ============================================================
# 装饰系统
# ============================================================
@router.get("/deco")
def deco_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    st = get_state(db, user.id)
    total, base_sum, set_bonuses = _save_env_score(db, st)
    db.commit()
    db.refresh(st)
    decos = _decorations(st)
    placed_keys = {d["item_key"] for d in decos}
    set_status = []
    for set_key, sinfo in DECO_SETS.items():
        placed_members = [m for m in sinfo["members"] if m in placed_keys]
        active = len(placed_members) == len(sinfo["members"])
        member_names = [DECO_CATALOG[m]["name"] if m in DECO_CATALOG else m for m in sinfo["members"]]
        set_status.append({"set_key": set_key, "name": sinfo["name"],
                           "member_names": member_names, "bonus": sinfo["bonus"],
                           "placed_count": len(placed_members),
                           "total_count": len(sinfo["members"]), "active": active})
    shop = []
    for key, info in DECO_CATALOG.items():
        cnt = count_item(db, user.id, key)
        shop.append({"key": key, "name": info["name"], "env_score": info["env_score"],
                     "set_key": info["set_key"], "price": info["price"], "have": cnt,
                     "placed": key in placed_keys})
    mul = env_quality_mul(total)
    set_bonus_total = sum(s["bonus"] for s in set_bonuses)
    title, tier_range = magician_title(st.level)
    ctx.update({"st": st, "decos": decos, "env_total": total, "env_base": base_sum,
                "set_bonus_total": set_bonus_total, "set_bonuses": set_bonuses,
                "set_status": set_status, "shop": shop, "env_mul": mul,
                "title": title, "tier_range": tier_range,
                "gold": get_gold(db, user.id)})
    return templates.TemplateResponse("magic_garden/deco.html", ctx)


@router.post("/deco/buy/{deco_key}")
def deco_buy(deco_key: str, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    info = DECO_CATALOG.get(deco_key)
    if not info:
        return _result(ctx, ok=False, msg="装饰不存在",
                       back_href="/magic_garden/deco", back_text="返回装饰")
    if not spend_gold(db, user.id, info["price"], "garden_deco_buy"):
        return _result(ctx, ok=False, msg=f"金币不足（需{info['price']}）",
                       back_href="/magic_garden/deco", back_text="返回装饰")
    add_item(db, user.id, deco_key, info["name"], 1, item_type="decoration")
    db.commit()
    return _result(ctx, ok=True, msg=f"购买{info['name']}×1（花费{info['price']}金币）",
                   back_href="/magic_garden/deco", back_text="返回装饰")


@router.post("/deco/place/{deco_key}")
def deco_place(deco_key: str, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    info = DECO_CATALOG.get(deco_key)
    if not info:
        return _result(ctx, ok=False, msg="装饰不存在",
                       back_href="/magic_garden/deco", back_text="返回装饰")
    st = get_state(db, user.id)
    decos = _decorations(st)
    if any(d["item_key"] == deco_key for d in decos):
        return _result(ctx, ok=False, msg=f"{info['name']}已放置在花园中",
                       back_href="/magic_garden/deco", back_text="返回装饰")
    if not remove_item(db, user.id, deco_key, 1):
        return _result(ctx, ok=False, msg=f"背包中没有{info['name']}（先去商店购买）",
                       back_href="/magic_garden/deco", back_text="返回装饰")
    decos.append({"item_key": deco_key, "name": info["name"],
                  "env_score": info["env_score"], "set_key": info["set_key"]})
    st.decorations = json.dumps(decos, ensure_ascii=False)
    total, base_sum, set_bonuses = _save_env_score(db, st)
    db.commit()
    msg = f"放置{info['name']}，环境值+{info['env_score']}（当前 {total}）"
    if set_bonuses:
        msg += f" | 激活套装：{'、'.join(s['name'] for s in set_bonuses)}"
    return _result(ctx, ok=True, msg=msg,
                   back_href="/magic_garden/deco", back_text="返回装饰")


@router.post("/deco/remove/{deco_key}")
def deco_remove(deco_key: str, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    info = DECO_CATALOG.get(deco_key)
    if not info:
        return _result(ctx, ok=False, msg="装饰不存在",
                       back_href="/magic_garden/deco", back_text="返回装饰")
    st = get_state(db, user.id)
    decos = _decorations(st)
    target = next((d for d in decos if d["item_key"] == deco_key), None)
    if not target:
        return _result(ctx, ok=False, msg=f"{info['name']}未放置在花园中",
                       back_href="/magic_garden/deco", back_text="返回装饰")
    decos = [d for d in decos if d["item_key"] != deco_key]
    st.decorations = json.dumps(decos, ensure_ascii=False)
    total, base_sum, set_bonuses = _save_env_score(db, st)
    add_item(db, user.id, deco_key, info["name"], 1, item_type="decoration")
    db.commit()
    return _result(ctx, ok=True, msg=f"撤下{info['name']}，环境值降至 {total}",
                   back_href="/magic_garden/deco", back_text="返回装饰")


# ============================================================
# 订单系统
# ============================================================
@router.get("/orders")
def orders_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    st = get_state(db, user.id)
    active = _ensure_orders(db, user.id, st)
    db.commit()
    order_infos = []
    for o in active:
        reqs = json.loads(o.requirements)
        can_deliver = True
        for r in reqs:
            cnt = count_item(db, user.id, r["item_key"])
            if cnt < r["qty"]:
                can_deliver = False
                break
        remain = ""
        if o.expire_at:
            secs = int((o.expire_at - datetime.utcnow()).total_seconds())
            remain = f"{secs//3600}h{(secs%3600)//60}m" if secs > 0 else "已过期"
        order_infos.append({"order": o, "reqs": reqs, "can_deliver": can_deliver, "remain": remain})
    dl = get_daily_log(db, user.id)
    free_left = max(0, ORDER_FREE_REROLL - dl.order_reroll_paid)
    title, tier_range = magician_title(st.level)
    ctx.update({"st": st, "order_infos": order_infos, "free_left": free_left,
                "title": title, "tier_range": tier_range,
                "gold": get_gold(db, user.id)})
    return templates.TemplateResponse("magic_garden/orders.html", ctx)


@router.post("/orders/deliver/{order_id}")
def order_deliver(order_id: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    st = get_state(db, user.id)
    o = db.query(GardenOrder).filter(GardenOrder.id == order_id).first()
    if not o or o.user_id != user.id or o.delivered:
        return _result(ctx, ok=False, msg="订单无效",
                       back_href="/magic_garden/orders", back_text="返回订单板")
    if o.expire_at and o.expire_at < datetime.utcnow():
        o.delivered = True
        db.commit()
        return _result(ctx, ok=False, msg="订单已过期",
                       back_href="/magic_garden/orders", back_text="返回订单板")
    reqs = json.loads(o.requirements)
    for r in reqs:
        cnt = count_item(db, user.id, r["item_key"])
        if cnt < r["qty"]:
            return _result(ctx, ok=False, msg=f"材料不足：{r['name']} 需要 {r['qty']} 个",
                           back_href="/magic_garden/orders", back_text="返回订单板")
    for r in reqs:
        remove_item(db, user.id, r["item_key"], r["qty"])
    add_gold(db, user.id, o.reward_coin, "garden_order")
    add_exp(db, st, o.reward_exp)
    o.delivered = True
    db.add(GardenOrderLog(user_id=user.id, order_type=o.order_type,
                          coin_gain=o.reward_coin, exp_gain=o.reward_exp,
                          token_gain=o.reward_token))
    db.commit()
    fire_event(user.id, MODULE_KEY, "ranking",
               {"metric": "order_coin", "score": o.reward_coin, "period": "total"}, db=db)
    msg = f"订单交付成功！金币+{o.reward_coin} 经验+{o.reward_exp}"
    if o.reward_token:
        msg += f" 活动代币+{o.reward_token}"
    return _result(ctx, ok=True, msg=msg,
                   back_href="/magic_garden/orders", back_text="返回订单板")


@router.post("/orders/reroll")
def orders_reroll(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    st = get_state(db, user.id)
    dl = get_daily_log(db, user.id)
    for o in db.query(GardenOrder).filter(
            GardenOrder.user_id == user.id, GardenOrder.delivered.is_(False)).all():
        o.delivered = True
    if dl.order_reroll_paid < ORDER_FREE_REROLL:
        cost = 0
    else:
        cost = int(ORDER_REROLL_BASE * (ORDER_REROLL_RATIO ** (dl.order_reroll_paid - ORDER_FREE_REROLL)))
    if not spend_gold(db, user.id, cost, "garden_order_reroll"):
        db.rollback()
        return _result(ctx, ok=False, msg=f"金币不足（刷新需{cost}）",
                       back_href="/magic_garden/orders", back_text="返回订单板")
    dl.order_reroll_paid += 1
    db.commit()
    _ensure_orders(db, user.id, st)
    db.commit()
    return RedirectResponse(url="/magic_garden/orders", status_code=302)


@router.get("/orders/history")
def orders_history(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    logs = db.query(GardenOrderLog).filter(
        GardenOrderLog.user_id == user.id).order_by(
        GardenOrderLog.delivered_at.desc()).limit(20).all()
    total_coin = sum(l.coin_gain for l in logs)
    total_exp = sum(l.exp_gain for l in logs)
    st = get_state(db, user.id)
    ctx.update({"st": st, "logs": logs, "total_coin": total_coin, "total_exp": total_exp,
                "gold": get_gold(db, user.id)})
    return templates.TemplateResponse("magic_garden/order_history.html", ctx)


# ============================================================
# 魔法任务链（7 步）
# ============================================================
@router.get("/quest")
def quest_home(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    st = get_state(db, user.id)
    data = _craft_data(st)
    quest_step = data["quest_step"]
    charm = data["charm"]
    completed = quest_step > len(QUEST_CHAIN)
    current = QUEST_CHAIN[quest_step - 1] if 1 <= quest_step <= len(QUEST_CHAIN) else None
    ctx.update({"st": st, "steps": QUEST_CHAIN, "current": current, "quest_step": quest_step,
                "charm": charm, "completed": completed,
                "quest_flowers": data["quest_flowers"], "quest_materials": data["quest_materials"],
                "reward_charm": QUEST_CHAIN_REWARD_CHARM,
                "title": magician_title(st.level)[0], "exp_need": exp_needed(st.level),
                "gold": get_gold(db, user.id)})
    return templates.TemplateResponse("magic_garden/quest.html", ctx)


@router.post("/quest/explore")
def quest_explore(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    st = get_state(db, user.id)
    data = _craft_data(st)
    if data["quest_step"] != 1:
        return _result(ctx, ok=False, msg="当前步骤无法探索好友花园",
                       back_href="/magic_garden/quest", back_text="返回任务")
    if random.random() < 0.5:
        data["quest_step"] = 2
        data["charm"] += QUEST_CHAIN_REWARD_CHARM[1]
        st.craft_queue = json.dumps(data, ensure_ascii=False)
        db.commit()
        return _result(ctx, ok=True, msg="找到神秘魔杖！魅力+60，解锁【绿野精灵】任务",
                       back_href="/magic_garden/quest", back_text="返回任务")
    st.craft_queue = json.dumps(data, ensure_ascii=False)
    db.commit()
    return _result(ctx, ok=False, msg="未发现魔杖，再试试",
                   back_href="/magic_garden/quest", back_text="返回任务")


@router.post("/quest/synthesize")
def quest_synthesize(step: int = Form(...), request: Request = None,
                     db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    st = get_state(db, user.id)
    if step < 2 or step > len(QUEST_CHAIN):
        return _result(ctx, ok=False, msg="无效的任务步骤",
                       back_href="/magic_garden/quest", back_text="返回任务")
    data = _craft_data(st)
    if data["quest_step"] != step:
        return _result(ctx, ok=False, msg="当前步骤不匹配，请按顺序完成",
                       back_href="/magic_garden/quest", back_text="返回任务")
    _s, name, skill_req, materials, success_rate, max_yield, _charm, exp, _hours, reward_text = QUEST_CHAIN[step - 1]
    if st.level < skill_req:
        return _result(ctx, ok=False, msg=f"需要花园等级 {skill_req} 才能进行【{name}】任务",
                       back_href="/magic_garden/quest", back_text="返回任务")
    for mname, mneed in materials.items():
        if _quest_have(data, mname) < mneed:
            return _result(ctx, ok=False, msg=f"材料不足：{mname} 需要 {mneed} 个",
                           back_href="/magic_garden/quest", back_text="返回任务")
    for mname, mneed in materials.items():
        _quest_deduct(data, mname, mneed)
    if random.random() < success_rate:
        data["quest_flowers"][name] = data["quest_flowers"].get(name, 0) + max_yield
        data["charm"] += QUEST_CHAIN_REWARD_CHARM[step]
        data["quest_step"] = step + 1
        st.craft_queue = json.dumps(data, ensure_ascii=False)
        add_exp(db, st, exp)
        db.commit()
        msg = (f"种植成功！收获【{name}】×{max_yield} | 魅力+{QUEST_CHAIN_REWARD_CHARM[step]}"
               f" | 经验+{exp} | {reward_text}")
        if step == len(QUEST_CHAIN):
            msg = (f"【五彩之翼】合成成功！收获×{max_yield} | 魅力+{QUEST_CHAIN_REWARD_CHARM[step]}"
                   f" | 经验+{exp} | 荣获「暗香使者」称号！任务链全部完成")
        return _result(ctx, ok=True, msg=msg,
                       back_href="/magic_garden/quest", back_text="返回任务")
    st.craft_queue = json.dumps(data, ensure_ascii=False)
    db.commit()
    return _result(ctx, ok=False, msg="种植失败，材料已消耗",
                   back_href="/magic_garden/quest", back_text="返回任务")


# ============================================================
# 通用结果页
# ============================================================
def _result(ctx: dict, ok: bool, msg: str, back_href: str, back_text: str):
    ctx.update({"ok": ok, "msg": msg, "back_href": back_href, "back_text": back_text})
    return templates.TemplateResponse("magic_garden/result.html", ctx)