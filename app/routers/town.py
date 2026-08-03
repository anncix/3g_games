"""美味小镇模块（v0.1.1 怀旧版完整设计规范）

双主轴：餐厅星级(规模) + 菜谱等级(内容)
核心循环：拿食材 → 做菜/备菜 → 上桌营业 → 顾客消费 → 获得金币/经验/熟练度
        → 升菜等/升餐厅星级 → 去好友家补缺口或互动 → 回店继续经营

定版规则（保留老味道，做轻保护）：
- 开局金币 10000，模块等级 Lv1-80
- 顾客周期 180 秒/波；1 名服务员服务 3 桌
- 油壶初始 3000，可扩到 9000（8 档：3000→4000→5000→5500→6000→7000→8000→9000）
- 1 星起出现 10% 挑剔客，每升 1 星 +10%（上限 5 星 40%）
- 菜谱 6 级 × 3 品质（普通/极品/金牌），品质只升售价不升经验
- 翻柜日限 15 次，同好友日限 3 次 + 10 分钟冷却 + 收益衰减(100/70/40/0%)
- 蟑螂：日限 2 次，封 1 桌，15 分钟自动消失，单餐厅上限 3 只
- 服务员：雇好友 12 小时，500 金币，金币+3%/满意度+2%/速度-5%制作时间
- 经验公式：need(L→L+1) = 120 + 80*L（与平台方案A统一）

v0.1.1 新增（对齐《QQ家园美味小镇页面结构与数值资料汇总》）：
- 油壶 8 档（补 5500/9000 凭证）
- 赛厨系统：厨具 5 类(铲/刀/锅/味/意) + 技能点 40 + 3 评委 + 厨力综合分
- 厨艺大赛：4 赛区(40-49/50-59/60-69/70+) + 报名 20 体力 + 8-23 时报名 + 23 时匹配
- 菜系 8 大 + 综合街映射（展示用）
- 万能食材（缺 1 个可用同级别万能食材替代）
- 上座率经验表 / 金牌食材替换映射（展示用，[unverified] 标注）
"""
import json
import random
from datetime import datetime, timedelta, date

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from ..platform import goods, events, locks, friends as fsvc, log
from .views import render

router = APIRouter(prefix="/games/town")
MODULE_KEY = "town"

# ============================================================
# 定版配置（方案C 完整定版数值）
# ============================================================
# 顾客周期
CUSTOMER_CYCLE = 180  # 秒
# 服务员效率
TABLES_PER_WAITER = 3
# 翻柜限制
FLIP_DAILY_LIMIT = 15
FLIP_PER_FRIEND_LIMIT = 3
FLIP_COOLDOWN = 600  # 10 分钟
# 蟑螂
ROACH_DAILY_LIMIT = 2
ROACH_COOLDOWN = 1800  # 30 分钟
ROACH_MAX_PER_RESTAURANT = 3
ROACH_DURATION = 900  # 15 分钟
# 服务员
WAITER_DURATION = 12 * 3600  # 12 小时
WAITER_HIRE_COST = 500
# 油量自然消耗（每有效桌每周期待机耗油 2）
OIL_IDLE_PER_TABLE = 2
# 经验公式（与平台方案A统一）
def exp_needed(level: int) -> int:
    return 120 + 80 * level

# 菜谱级别表（6 级菜）
# (recipe_level, unlock_level, base_price, base_exp, cook_seconds, base_oil)
RECIPE_LEVEL_TABLE = {
    1: (1, 18, 2, 30, 8),
    2: (10, 36, 4, 45, 12),
    3: (20, 68, 7, 60, 18),
    4: (35, 118, 11, 90, 26),
    5: (50, 198, 16, 120, 36),
    6: (65, 320, 24, 180, 50),
}

# 品质系数（售价升，经验不升）
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

# 星级效果表
# (stars, apply_level, table_cap, waiter_total, cabinet_cap, facility_slots, picky_pct, rare_pct, revenue_coef)
STAR_TABLE = {
    0: (1, 3, 1, 24, 2, 0, 0, 1.00),
    1: (10, 6, 2, 30, 3, 10, 0, 1.05),
    2: (20, 9, 3, 36, 4, 20, 2, 1.10),
    3: (35, 12, 4, 42, 5, 30, 4, 1.15),
    4: (50, 15, 5, 48, 6, 35, 8, 1.20),
    5: (70, 18, 6, 54, 7, 40, 12, 1.25),
}

# 申星条件表
# (stars, level, 普通菜数, 极品菜数, 金牌菜数, 累计营业, 累计收入)
STAR_APPLY_TABLE = {
    1: (10, 5, 0, 0, 100, 5000),
    2: (20, 15, 0, 0, 300, 30000),
    3: (35, 30, 15, 0, 800, 120000),
    4: (50, 0, 75, 10, 2000, 500000),
    5: (70, 0, 180, 45, 5000, 2000000),
}

# 油壶容量表（v0.1.1：8 档，对齐 spec 口径）
# spec 原档：3000默认 / 4000初级金币 / 5000中级积分 / 5500高级(上)元宝
#           6000高级(下)元宝 / 7000黄金(上)元宝 / 8000黄金(下)元宝 / 9000白金(上)活动
# 本平台只有金币单一货币，统一折算为金币成本（积分/元宝/活动按兑换价值折算）
OIL_POT_TABLE = [
    (3000, 0),         # 初始
    (4000, 10000),     # 初级油壶凭证（金币商城）
    (5000, 25000),     # 中级油壶凭证（积分兑换折算）
    (5500, 40000),     # 高级油壶凭证(上)（元宝折算）
    (6000, 80000),     # 高级油壶凭证(下)（元宝折算）
    (7000, 120000),    # 黄金油壶凭证(上)（元宝折算）
    (8000, 180000),    # 黄金油壶凭证(下)（元宝折算）
    (9000, 280000),    # 白金油壶凭证(上)（活动折算）
]

# 补油包
OIL_PACK_TABLE = {
    "small": (300, 60),
    "medium": (1000, 180),
    "large": (3000, 480),
}

# 顾客类型
# (type, coin_coef, exp_coef, rule)
CUSTOMER_TYPES = {
    "normal": (1.00, 1.00, "从上架菜里随机点单"),
    "picky": (1.25, 1.20, "指定一道菜，没有就走"),
    "rare": (1.60, 1.40, "指定高阶菜，没有就走"),
}

# 设施表
FACILITY_TABLE = {
    "trophy": ("小镇食神奖杯(铜)", 5000, 24, "每位顾客经验+1"),
    "poster": ("小C宣传海报", 1000, 24, "每位顾客金币+1"),
    "fresh_cabinet": ("防翻保鲜柜", 3000, 24, "被翻概率-50%"),
    "oil_stove": ("省油灶台", 4000, 24, "做菜耗油-10%"),
    "sanitizer": ("卫生香氛", 2500, 24, "蟑螂出现率-50%"),
}

# 翻柜收益衰减
FLIP_DECAY = [1.00, 0.70, 0.40, 0.00]


# ============================================================
# v0.1.1 新增配置（对齐《美味小镇页面结构与数值资料汇总》）
# ============================================================
# 菜系 8 大 + 综合街映射（spec 原文口径，展示用）
CUISINE_STREETS = {
    "湘菜": "湖南街", "粤菜": "广东街", "川菜": "四川街", "闽菜": "福建街",
    "徽菜": "安徽街", "鲁菜": "山东街", "浙菜": "浙江街", "苏菜": "江苏街",
    "综合": "综合一街 / 综合二街",
}

# 厨具 5 类（spec：[铲]/[刀]/[锅]/[味]/[意]，每类只能装配对应厨具）
# (key, name, base_power, price)
CHEF_TOOLS = {
    "spade":  ("厨具·铲", 10, 2000),
    "knife":  ("厨具·刀", 10, 2000),
    "pot":    ("厨具·锅", 10, 2000),
    "flavor": ("厨具·味", 10, 2000),
    "mind":   ("厨具·意", 10, 2000),
}
CHEF_TOOL_SLOTS = ["spade", "knife", "pot", "flavor", "mind"]

# 技能点（spec：40 点示例分配 15 火候/9 刀功/8 厨艺/8 调味）
SKILL_TOTAL_POINTS = 40
SKILL_KEYS = ["huohou", "daogong", "chuyi", "tiaowei"]
SKILL_NAMES = {"huohou": "火候", "daogong": "刀功", "chuyi": "厨艺", "tiaowei": "调味"}

# 赛区划分（spec：初级40-49/中级50-59/高级60-69/超级70+）
CONTEST_ZONES = {
    "junior":  ("初级区", 40, 49),
    "middle":  ("中级区", 50, 59),
    "senior":  ("高级区", 60, 69),
    "super":   ("超级区", 70, 999),
}
CONTEST_SIGNUP_COST = 20      # 报名消耗体力（spec）
CONTEST_SIGNUP_HOUR = (8, 23)  # 报名时段 8-23 时（spec）

# 赛厨参数
MATCH_DAILY_LIMIT = 10        # 每日主动赛厨次数
MATCH_WIN_COIN = 200          # 胜利金币奖励
MATCH_WIN_EXP = 30            # 胜利经验
MATCH_LOSE_COIN = 50          # 失败安慰金币

# 上座率经验表（spec 标注 [unverified]，作为菜品覆盖建议）
# (等级段起, 等级段止, 普通菜数, 极品菜数, 金牌菜数)
SEAT_COVER_TABLE = [
    (11, 15, 5, 0, 0),
    (16, 20, 15, 0, 0),
    (21, 25, 30, 0, 0),
    (26, 30, 60, 0, 0),
    (31, 35, 0, 30, 0),
    (36, 40, 0, 50, 0),
    (41, 45, 0, 75, 0),
    (46, 50, 0, 105, 0),
    (51, 55, 0, 140, 0),
    (56, 60, 0, 180, 0),
    (61, 65, 0, 215, 10),
    (66, 70, 0, 255, 25),
    (71, 75, 0, 275, 45),
    (76, 80, 0, 305, 70),
    (81, 85, 0, 275, 100),
    (86, 90, 0, 240, 135),
    (91, 999, 0, 210, 165),
]

# 金牌食材替换映射（spec：升金牌时部分食材会替换）
# base_ingredient_name -> upgrade_ingredient_name
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

# 万能食材（spec：缺 1 个可用对应级别万能食材补齐）
# (级别, item_key, name)
WILD_INGREDIENTS = {
    1: ("town_wild_ing_1", "1级万能食材"),
    2: ("town_wild_ing_2", "2级万能食材"),
    3: ("town_wild_ing_3", "3级万能食材"),
    4: ("town_wild_ing_4", "4级万能食材"),
    5: ("town_wild_ing_5", "5级万能食材"),
    6: ("town_wild_ing_6", "6级万能食材"),
}

# 食材级别（用于万能食材替代判定，按 item_key 前缀映射）
# key 前缀 → 级别
ING_LEVEL_BY_PREFIX = {
    "town_ing_rice": 1, "town_ing_egg": 1, "town_ing_veg": 1,
    "town_ing_meat": 2, "town_ing_tofu": 2, "town_ing_noodle": 2,
    "town_ing_chicken": 3, "town_ing_fish": 3, "town_ing_mushroom": 3,
    "town_ing_beef": 4, "town_ing_shrimp": 4,
    "town_ing_crab": 5, "town_ing_truffle": 5,
    "town_ing_abalone": 6, "town_ing_mystery": 6,
}


# ============================================================
# 工具函数
# ============================================================
async def get_state(db: AsyncSession, user_id: int) -> models.TownState:
    """获取/创建餐厅状态（自动按等级补齐桌位）"""
    st = await db.get(models.TownState, user_id)
    if not st:
        # 新餐厅：last_service_at 设为过去时间，允许首次营业
        st = models.TownState(user_id=user_id,
                              last_service_at=datetime.utcnow() - timedelta(seconds=CUSTOMER_CYCLE),
                              last_oil_drain=datetime.utcnow() - timedelta(seconds=CUSTOMER_CYCLE))
        db.add(st)
        await db.commit()
        await db.refresh(st)
    # 清理过期服务员/蟑螂/设施
    now = datetime.utcnow()
    await db.execute(delete(models.TownWaiter).where(
        models.TownWaiter.user_id == user_id, models.TownWaiter.expire_at < now))
    await db.execute(delete(models.TownCockroach).where(
        models.TownCockroach.user_id == user_id, models.TownCockroach.expire_at < now))
    await db.execute(delete(models.TownFacility).where(
        models.TownFacility.user_id == user_id, models.TownFacility.expire_at < now))
    await db.commit()
    return st


async def get_daily_log(db: AsyncSession, user_id: int) -> models.TownDailyLog:
    """获取/创建今日日限计数"""
    today = date.today().isoformat()
    res = await db.execute(select(models.TownDailyLog).where(
        models.TownDailyLog.user_id == user_id, models.TownDailyLog.date == today))
    dl = res.scalar_one_or_none()
    if not dl:
        dl = models.TownDailyLog(user_id=user_id, date=today)
        db.add(dl)
        await db.flush()
    return dl


async def get_recipe_progress(db: AsyncSession, user_id: int, recipe_key: str) -> models.TownRecipeProgress:
    """获取/创建菜谱进度"""
    res = await db.execute(select(models.TownRecipeProgress).where(
        models.TownRecipeProgress.user_id == user_id,
        models.TownRecipeProgress.recipe_key == recipe_key))
    p = res.scalar_one_or_none()
    if not p:
        p = models.TownRecipeProgress(user_id=user_id, recipe_key=recipe_key)
        db.add(p)
        await db.flush()
    return p


async def add_exp(db: AsyncSession, st: models.TownState, amount: int):
    """加经验并处理升级"""
    st.exp += amount
    while st.exp >= exp_needed(st.level):
        st.exp -= exp_needed(st.level)
        st.level += 1


def star_info(stars: int) -> tuple:
    """返回星级效果 (table_cap, waiter_total, cabinet_cap, facility_slots, picky_pct, rare_pct, revenue_coef)"""
    return STAR_TABLE.get(stars, STAR_TABLE[0])[1:]


def can_apply_star(stars: int, level: int, normal_cnt: int, fine_cnt: int, gold_cnt: int,
                   total_service: int, total_revenue: int) -> tuple[bool, str]:
    """检查是否满足升星条件"""
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


async def count_learned_by_quality(db: AsyncSession, user_id: int) -> tuple[int, int, int]:
    """统计已学菜谱按品质计数 (普通, 极品, 金牌)"""
    res = await db.execute(select(models.TownRecipeProgress).where(
        models.TownRecipeProgress.user_id == user_id,
        models.TownRecipeProgress.learned.is_(True)))
    normal = fine = gold = 0
    for p in res.scalars().all():
        if p.quality == "普通":
            normal += 1
        elif p.quality == "极品":
            fine += 1
        elif p.quality == "金牌":
            gold += 1
    return normal, fine, gold


async def get_active_waiters(db: AsyncSession, user_id: int) -> list[models.TownWaiter]:
    """获取当前生效的服务员"""
    now = datetime.utcnow()
    res = await db.execute(select(models.TownWaiter).where(
        models.TownWaiter.user_id == user_id, models.TownWaiter.expire_at > now))
    return list(res.scalars().all())


async def get_active_cockroaches(db: AsyncSession, user_id: int) -> list[models.TownCockroach]:
    """获取当前生效的蟑螂"""
    now = datetime.utcnow()
    res = await db.execute(select(models.TownCockroach).where(
        models.TownCockroach.user_id == user_id, models.TownCockroach.expire_at > now))
    return list(res.scalars().all())


async def get_active_facilities(db: AsyncSession, user_id: int) -> list[models.TownFacility]:
    """获取当前生效的设施"""
    now = datetime.utcnow()
    res = await db.execute(select(models.TownFacility).where(
        models.TownFacility.user_id == user_id, models.TownFacility.expire_at > now))
    return list(res.scalars().all())


def calc_serving_tables(table_count: int, waiter_count: int, roach_count: int) -> int:
    """计算实际可来客桌数 = min(已摆桌, 可服务桌, 未被蟑螂封锁桌)"""
    serviceable = waiter_count * TABLES_PER_WAITER
    unblocked = max(0, table_count - roach_count)
    return min(table_count, serviceable, unblocked)


# ============================================================
# v0.1.1：赛厨 / 厨力 / 万能食材 工具函数
# ============================================================
async def get_chef_skill(db: AsyncSession, user_id: int) -> models.TownChefSkill:
    """获取/创建技能点记录"""
    sk = await db.get(models.TownChefSkill, user_id)
    if not sk:
        sk = models.TownChefSkill(user_id=user_id)
        db.add(sk)
        await db.flush()
    return sk


async def get_chef_tools(db: AsyncSession, user_id: int) -> list[models.TownChefTool]:
    """获取玩家全部厨具"""
    res = await db.execute(select(models.TownChefTool).where(
        models.TownChefTool.user_id == user_id))
    return list(res.scalars().all())


async def get_equipped_tools(db: AsyncSession, user_id: int) -> list[models.TownChefTool]:
    """获取已装备厨具"""
    res = await db.execute(select(models.TownChefTool).where(
        models.TownChefTool.user_id == user_id, models.TownChefTool.equipped.is_(True)))
    return list(res.scalars().all())


def chef_power(st: models.TownState, learned_count: int, gold_count: int,
               tools: list[models.TownChefTool], sk: models.TownChefSkill) -> int:
    """计算综合厨力（spec：厨力越高胜率越高，从餐厅首页名片查看）

    厨力 = 等级×10 + 星级×200 + 已学菜×5 + 金牌菜×20
          + 装备厨具等级和×15 + 技能点总数×8
    """
    tool_score = sum(t.level * 15 for t in tools if t.equipped)
    skill_total = sk.huohou + sk.daogong + sk.chuyi + sk.tiaowei
    power = (st.level * 10 + st.stars * 200 + learned_count * 5
             + gold_count * 20 + tool_score + skill_total * 8)
    return power


def judge_score(power: int, skill_points: dict, judge_focus: str) -> int:
    """单评委打分（spec：3 评委各关注不同打分点）

    基础分 = 厨力 / 10 + 随机扰动
    评委关注点加成：火候/刀功/厨艺/调味 中某项 ×3
    """
    base = power // 10 + random.randint(5, 20)
    focus_bonus = skill_points.get(judge_focus, 0) * 3
    return base + focus_bonus


def contest_zone(level: int) -> str | None:
    """按等级返回赛区 key"""
    for k, (_, lo, hi) in CONTEST_ZONES.items():
        if lo <= level <= hi:
            return k
    return None


def ing_level_of(item_key: str) -> int:
    """食材级别（用于万能食材替代判定）"""
    return ING_LEVEL_BY_PREFIX.get(item_key, 1)


async def check_wild_substitute(db: AsyncSession, user_id: int, missing_key: str) -> tuple[bool, str, int]:
    """检查是否可用万能食材替代缺失食材

    spec：合成时只差 1 个食材，可用对应级别万能食材补齐
    返回 (能否替代, 万能食材item_key, 万能食材级别)
    """
    lv = ing_level_of(missing_key)
    wild_key, _ = WILD_INGREDIENTS.get(lv, ("", ""))
    if not wild_key:
        return False, "", 0
    have = await goods.count_item(db, user_id, wild_key, MODULE_KEY)
    return (have > 0, wild_key, lv) if have > 0 else (False, "", 0)


def today_str() -> str:
    return date.today().isoformat()


# ============================================================
# 模块首页
# ============================================================
@router.get("")
async def town_home(request: Request, db: AsyncSession = Depends(get_db)):
    """模块首页：餐厅概况 + 今日待办 + 快捷入口"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    # 油量自然消耗（待机耗油：每有效桌每周期待机耗油 2，按时间累计）
    await _drain_oil_idle(db, st)
    await db.commit()
    # 当前烹饪
    cooking_recipe = None
    cook_remain = 0
    if st.cooking_recipe:
        cooking_recipe = await db.get(models.TownRecipe, st.cooking_recipe)
        if cooking_recipe:
            cook_remain = max(0, int(cooking_recipe.cook_seconds - (datetime.utcnow() - st.cooking_started_at).total_seconds()))
    # 服务员/蟑螂/设施
    waiters = await get_active_waiters(db, user.id)
    roaches = await get_active_cockroaches(db, user.id)
    facilities = await get_active_facilities(db, user.id)
    table_cap, waiter_total, cabinet_cap, facility_slots, picky_pct, rare_pct, revenue_coef = star_info(st.stars)
    serving_tables = calc_serving_tables(st.table_count, len(waiters) + 1, len(roaches))
    # 可营业判定
    can_service = st.oil > 0 and serving_tables > 0
    # 待办
    todo = []
    if st.oil < st.oil_cap * 0.15:
        todo.append(("缺油告急", "red", "/games/town/oil", "去添油"))
    if cooking_recipe and cook_remain == 0:
        todo.append((f"{cooking_recipe.name}已出锅", "green", "/games/town", "收菜"))
    if not todo:
        todo.append(("暂无待办，去做菜吧", "muted", "/games/town/recipes", "去菜谱"))
    # 油量百分比
    oil_pct = int(st.oil / st.oil_cap * 100) if st.oil_cap > 0 else 0
    return await render(request, "town/home.html", db, user=user, st=st,
                        cooking_recipe=cooking_recipe, cook_remain=cook_remain,
                        todo=todo, waiters=waiters, roaches=roaches, facilities=facilities,
                        table_cap=table_cap, waiter_total=waiter_total,
                        cabinet_cap=cabinet_cap, facility_slots=facility_slots,
                        picky_pct=picky_pct, rare_pct=rare_pct, revenue_coef=revenue_coef,
                        serving_tables=serving_tables, can_service=can_service,
                        oil_pct=oil_pct, exp_need=exp_needed(st.level))


async def _drain_oil_idle(db: AsyncSession, st: models.TownState):
    """油量待机自然消耗：每个有效桌每周期待机耗油 2

    怀旧优化：不会因为离线一会儿就崩盘，按时间累计但保守
    """
    now = datetime.utcnow()
    elapsed = (now - st.last_oil_drain).total_seconds()
    if elapsed < 60:  # 不足 1 分钟不结算
        return
    # 按每 3 分钟消耗一个"有效桌待机耗油"单位（保守，避免离线崩盘）
    cycles = int(elapsed // 180)  # 顾客周期
    if cycles <= 0:
        return
    drain = cycles * OIL_IDLE_PER_TABLE * max(1, st.table_count)
    st.oil = max(0, st.oil - drain)
    st.last_oil_drain = now


# ============================================================
# 菜谱系统
# ============================================================
@router.get("/recipes")
async def recipes_list(request: Request, db: AsyncSession = Depends(get_db)):
    """菜谱列表：已学/未学/上架"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    recipes = (await db.execute(select(models.TownRecipe).order_by(models.TownRecipe.recipe_level))).scalars().all()
    info = []
    for r in recipes:
        p = await get_recipe_progress(db, user.id, r.key)
        ing = json.loads(r.ingredients)
        ings = []
        enough = True
        for k, n in ing.items():
            cnt = await goods.count_item(db, user.id, k, MODULE_KEY)
            item = await goods.get_item_by_key(db, k)
            ings.append({"key": k, "name": item.name if item else k, "need": n, "have": cnt})
            if cnt < n:
                enough = False
        # 升级材料需求预览
        upgrade_info = None
        if p.learned and p.quality != "金牌":
            upgrade_info = _upgrade_preview(r, p)
        info.append({"r": r, "p": p, "ings": ings, "enough": enough,
                     "locked_level": st.level < r.unlock_level, "upgrade": upgrade_info})
    return await render(request, "town/recipes.html", db, user=user, st=st, info=info,
                        exp_need=exp_needed(st.level))


def _upgrade_preview(recipe: models.TownRecipe, p: models.TownRecipeProgress) -> dict:
    """菜谱升级需求预览"""
    if p.quality == "普通":
        proficiency_need, gold_need, mat_need, _, _, _, _ = RECIPE_UPGRADE_TABLE.get(recipe.recipe_level, (0, 0, 0, 0, 0, 0, 0))
        return {"target": "极品", "proficiency_need": proficiency_need, "proficiency_have": p.proficiency,
                "gold_need": gold_need, "mat_need": mat_need, "mat_key": "town_dish_fragment"}
    elif p.quality == "极品":
        _, _, _, proficiency_need, gold_need, mat_need, special_need = RECIPE_UPGRADE_TABLE.get(recipe.recipe_level, (0, 0, 0, 0, 0, 0, 0))
        return {"target": "金牌", "proficiency_need": proficiency_need, "proficiency_have": p.proficiency,
                "gold_need": gold_need, "mat_need": mat_need, "mat_key": "town_dish_fragment",
                "special_need": special_need, "special_key": "town_special_condiment"}
    return {}


@router.get("/recipe/{key}")
async def recipe_detail(key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """菜谱详情"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    r = await db.get(models.TownRecipe, key)
    if not r:
        raise HTTPException(404)
    p = await get_recipe_progress(db, user.id, key)
    ing = json.loads(r.ingredients)
    ings = []
    for k, n in ing.items():
        cnt = await goods.count_item(db, user.id, k, MODULE_KEY)
        item = await goods.get_item_by_key(db, k)
        ings.append({"key": k, "name": item.name if item else k, "need": n, "have": cnt})
    upgrade_info = _upgrade_preview(r, p) if p.learned and p.quality != "金牌" else None
    # 升级材料持有量
    if upgrade_info:
        upgrade_info["mat_have"] = await goods.count_item(db, user.id, upgrade_info["mat_key"], MODULE_KEY)
        if "special_key" in upgrade_info:
            upgrade_info["special_have"] = await goods.count_item(db, user.id, upgrade_info["special_key"], MODULE_KEY)
    return await render(request, "town/recipe_detail.html", db, user=user, st=st, r=r, p=p, ings=ings,
                        upgrade=upgrade_info, exp_need=exp_needed(st.level))


@router.post("/learn/{key}")
async def learn_recipe(key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """学菜（消耗金币，需满足等级门槛）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    r = await db.get(models.TownRecipe, key)
    if not r:
        return await render(request, "result.html", db, user=user, ok=False, msg="菜谱不存在",
                            back_href="/games/town/recipes", back_text="返回菜谱")
    p = await get_recipe_progress(db, user.id, key)
    if p.learned:
        return await render(request, "result.html", db, user=user, ok=False, msg="已学会该菜谱",
                            back_href=f"/games/town/recipe/{key}", back_text="返回")
    if st.level < r.unlock_level:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"需要等级 Lv{r.unlock_level}（当前 Lv{st.level}）",
                            back_href=f"/games/town/recipe/{key}", back_text="返回")
    # 学菜费用 = 50 × 菜谱级别
    cost = 50 * r.recipe_level
    if st.coins < cost:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"金币不足（需 {cost}）",
                            back_href=f"/games/town/recipe/{key}", back_text="返回")
    st.coins -= cost
    p.learned = True
    learn_exp = 5 * r.recipe_level
    await add_exp(db, st, learn_exp)
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "learn_recipe", f"{key}:exp{learn_exp}")
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"学会 {r.name}！金币-{cost} 经验+{learn_exp}",
                        back_href="/games/town/recipes", back_text="返回菜谱")


@router.post("/cook/{key}")
async def cook(key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """做菜（消耗食材 + 油量，开始烹饪计时）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if st.cooking_recipe:
        return await render(request, "result.html", db, user=user, ok=False, msg="正在烹饪中，先完成当前的",
                            back_href="/games/town", back_text="返回")
    r = await db.get(models.TownRecipe, key)
    if not r:
        return await render(request, "result.html", db, user=user, ok=False, msg="菜谱不存在",
                            back_href="/games/town/recipes", back_text="返回菜谱")
    p = await get_recipe_progress(db, user.id, key)
    if not p.learned:
        return await render(request, "result.html", db, user=user, ok=False, msg="未学会该菜谱",
                            back_href=f"/games/town/recipe/{key}", back_text="返回")
    # 油量校验
    oil_cost = r.base_oil
    facilities = await get_active_facilities(db, user.id)
    if any(f.facility_key == "oil_stove" for f in facilities):
        oil_cost = int(oil_cost * 0.9)  # 省油灶台 -10%
    if st.oil < oil_cost:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"油量不足（需 {oil_cost}）",
                            back_href="/games/town/oil", back_text="去添油")
    # 食材校验（v0.1.1：缺 1 个可用对应级别万能食材替代）
    ing = json.loads(r.ingredients)
    missing = []  # (key, need, have)
    for k, n in ing.items():
        have = await goods.count_item(db, user.id, k, MODULE_KEY)
        if have < n:
            missing.append((k, n, have))
    wild_used = []  # 记录消耗的万能食材
    if missing:
        # spec：只差 1 个食材才能用万能食材补齐
        if len(missing) == 1:
            mk, mn, mh = missing[0]
            shortage = mn - mh
            if shortage == 1:
                can_sub, wild_key, wild_lv = await check_wild_substitute(db, user.id, mk)
                if can_sub:
                    wild_used.append((wild_key, wild_lv, mk))
                else:
                    item = await goods.get_item_by_key(db, mk)
                    return await render(request, "result.html", db, user=user, ok=False,
                                        msg=f"食材不足：{item.name if item else mk}（缺1个，可用{wild_lv}级万能食材替代）",
                                        back_href=f"/games/town/recipe/{key}", back_text="返回")
            else:
                item = await goods.get_item_by_key(db, mk)
                return await render(request, "result.html", db, user=user, ok=False,
                                    msg=f"食材不足：{item.name if item else mk}（缺{shortage}个，万能食材只能补1个）",
                                    back_href=f"/games/town/recipe/{key}", back_text="返回")
        else:
            item = await goods.get_item_by_key(db, missing[0][0])
            return await render(request, "result.html", db, user=user, ok=False,
                                msg=f"食材不足：{item.name if item else missing[0][0]} 等多种材料缺失",
                                back_href=f"/games/town/recipe/{key}", back_text="返回")
    # 扣除食材 + 油量（缺1个的用万能食材补齐）
    for k, n in ing.items():
        have = await goods.count_item(db, user.id, k, MODULE_KEY)
        if have >= n:
            await goods.remove_item(db, user.id, k, MODULE_KEY, n)
        else:
            # 扣完已有的，剩余 1 个用万能食材
            if have > 0:
                await goods.remove_item(db, user.id, k, MODULE_KEY, have)
    for wild_key, wild_lv, _mk in wild_used:
        await goods.remove_item(db, user.id, wild_key, MODULE_KEY, 1)
    st.oil -= oil_cost
    st.cooking_recipe = key
    st.cooking_started_at = datetime.utcnow()
    await db.commit()
    wild_text = f"（消耗{wild_used[0][1]}级万能食材×1）" if wild_used else ""
    await log.record(db, user.id, MODULE_KEY, "cook", f"{key}:oil{oil_cost}:wild{len(wild_used)}")
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"开始烹饪 {r.name}，约 {r.cook_seconds} 秒（耗油 {oil_cost}）{wild_text}",
                        back_href="/games/town", back_text="返回首页")


@router.post("/finish")
async def finish_cook(request: Request, db: AsyncSession = Depends(get_db)):
    """完成烹饪（获得成品菜 + 熟练度 + 经验）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if not st.cooking_recipe:
        return await render(request, "result.html", db, user=user, ok=False, msg="没有在烹饪",
                            back_href="/games/town", back_text="返回")
    r = await db.get(models.TownRecipe, st.cooking_recipe)
    if not r or (datetime.utcnow() - st.cooking_started_at).total_seconds() < r.cook_seconds:
        return await render(request, "result.html", db, user=user, ok=False, msg="还没烹饪完成",
                            back_href="/games/town", back_text="返回")
    # 获得成品菜
    await goods.add_item(db, user.id, r.output_item_key, MODULE_KEY, 1)
    # 熟练度 +1
    p = await get_recipe_progress(db, user.id, r.key)
    p.proficiency += 1
    # 做菜经验 +2（不论品质，保留旧逻辑）
    craft_exp = 2
    await add_exp(db, st, craft_exp)
    st.dishes_served += 1
    st.cooking_recipe = ""
    st.cooking_started_at = None
    await events.emit(db, user.id, MODULE_KEY, "achievement",
                      {"key": "achv_chef_star2", "delta": 1})
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "finish_cook", r.key)
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"完成 {r.name}×1，熟练度+1，经验+{craft_exp}",
                        back_href="/games/town", back_text="返回首页")


@router.post("/upgrade/{key}")
async def upgrade_recipe(key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """菜谱升级品质（普通→极品→金牌）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    r = await db.get(models.TownRecipe, key)
    if not r:
        return await render(request, "result.html", db, user=user, ok=False, msg="菜谱不存在",
                            back_href="/games/town/recipes", back_text="返回")
    p = await get_recipe_progress(db, user.id, key)
    if not p.learned:
        return await render(request, "result.html", db, user=user, ok=False, msg="未学会该菜谱",
                            back_href=f"/games/town/recipe/{key}", back_text="返回")
    if p.quality == "金牌":
        return await render(request, "result.html", db, user=user, ok=False, msg="已达最高品质",
                            back_href=f"/games/town/recipe/{key}", back_text="返回")
    # 升级需求
    upg = RECIPE_UPGRADE_TABLE.get(r.recipe_level)
    if not upg:
        return await render(request, "result.html", db, user=user, ok=False, msg="无升级配置",
                            back_href=f"/games/town/recipe/{key}", back_text="返回")
    if p.quality == "普通":
        prof_need, gold_need, mat_need, _, _, _, _ = upg
        target = "极品"
        mat_key = "town_dish_fragment"
        special_key = None
        special_need = 0
    else:  # 极品
        _, _, _, prof_need, gold_need, mat_need, special_need = upg
        target = "金牌"
        mat_key = "town_dish_fragment"
        special_key = "town_special_condiment"
    # 校验
    if p.proficiency < prof_need:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"熟练度不足（需 {prof_need}，当前 {p.proficiency}）",
                            back_href=f"/games/town/recipe/{key}", back_text="返回")
    if st.coins < gold_need:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"金币不足（需 {gold_need}）",
                            back_href=f"/games/town/recipe/{key}", back_text="返回")
    if await goods.count_item(db, user.id, mat_key, MODULE_KEY) < mat_need:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"菜谱碎片不足（需 {mat_need}）",
                            back_href=f"/games/town/recipe/{key}", back_text="返回")
    if special_key and await goods.count_item(db, user.id, special_key, MODULE_KEY) < special_need:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"特殊调料不足（需 {special_need}）",
                            back_href=f"/games/town/recipe/{key}", back_text="返回")
    # 扣除
    st.coins -= gold_need
    await goods.remove_item(db, user.id, mat_key, MODULE_KEY, mat_need)
    if special_key:
        await goods.remove_item(db, user.id, special_key, MODULE_KEY, special_need)
    p.quality = target
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "upgrade_recipe", f"{key}:{target}")
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"{r.name} 升级为 {target}！售价系数 {QUALITY_PRICE_COEF[target]}x",
                        back_href=f"/games/town/recipe/{key}", back_text="返回")


@router.post("/shelf/{key}")
async def toggle_shelf(key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """上架/下架菜谱"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    r = await db.get(models.TownRecipe, key)
    if not r:
        raise HTTPException(404)
    p = await get_recipe_progress(db, user.id, key)
    if not p.learned:
        return await render(request, "result.html", db, user=user, ok=False, msg="未学会该菜谱",
                            back_href=f"/games/town/recipe/{key}", back_text="返回")
    p.on_shelf = not p.on_shelf
    await db.commit()
    return RedirectResponse(f"/games/town/recipe/{key}", status_code=303)


# ============================================================
# 营业系统（顾客消费）
# ============================================================
@router.post("/serve")
async def serve_customers(request: Request, db: AsyncSession = Depends(get_db)):
    """营业结算：按顾客周期 180 秒生成顾客消费"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    # 冷却校验
    elapsed = (datetime.utcnow() - st.last_service_at).total_seconds()
    if elapsed < CUSTOMER_CYCLE:
        remain = int(CUSTOMER_CYCLE - elapsed)
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"顾客还没到（剩余 {remain} 秒）",
                            back_href="/games/town", back_text="返回")
    # 油量/桌位校验
    waiters = await get_active_waiters(db, user.id)
    roaches = await get_active_cockroaches(db, user.id)
    serving_tables = calc_serving_tables(st.table_count, len(waiters) + 1, len(roaches))
    if st.oil <= 0:
        return await render(request, "result.html", db, user=user, ok=False, msg="油量为 0，无法营业",
                            back_href="/games/town/oil", back_text="去添油")
    if serving_tables <= 0:
        return await render(request, "result.html", db, user=user, ok=False, msg="无可用桌位（被蟑螂封锁或服务员不足）",
                            back_href="/games/town", back_text="返回")
    # 上架菜
    res = await db.execute(select(models.TownRecipeProgress).where(
        models.TownRecipeProgress.user_id == user.id,
        models.TownRecipeProgress.learned.is_(True),
        models.TownRecipeProgress.on_shelf.is_(True)))
    shelf = []
    for p in res.scalars().all():
        r = await db.get(models.TownRecipe, p.recipe_key)
        if r:
            shelf.append((r, p))
    if not shelf:
        return await render(request, "result.html", db, user=user, ok=False, msg="无上架菜，先去菜谱上架",
                            back_href="/games/town/recipes", back_text="去菜谱")
    # 顾客构成
    _, _, _, _, picky_pct, rare_pct, revenue_coef = star_info(st.stars)
    facilities = await get_active_facilities(db, user.id)
    # 服务员加成
    coin_bonus = 1.0 + 0.03 * len(waiters)  # +3%/人
    satisfaction_bonus = 1.0 + 0.02 * len(waiters)  # +2%/人
    # 营业结算
    total_coin = 0
    total_exp = 0
    customer_log = []
    for _ in range(serving_tables):
        # 顾客类型
        rnd = random.random() * 100
        if rnd < rare_pct:
            ctype = "rare"
        elif rnd < rare_pct + picky_pct:
            ctype = "picky"
        else:
            ctype = "normal"
        coin_coef, exp_coef, _ = CUSTOMER_TYPES[ctype]
        # 点单
        if ctype == "normal":
            r, p = random.choice(shelf)
        else:
            # 挑剔/稀有客指定高阶菜（优先高 recipe_level）
            sorted_shelf = sorted(shelf, key=lambda x: x[0].recipe_level, reverse=True)
            r, p = sorted_shelf[0] if sorted_shelf else random.choice(shelf)
        # 售价 = 基础售价 × 品质系数 × 顾客类型系数 × 星级系数
        price = int(r.base_price * QUALITY_PRICE_COEF[p.quality] * coin_coef * revenue_coef)
        # 经验 = 基础经验 × 顾客类型系数（品质不提升经验）
        exp = int(r.base_exp * exp_coef)
        # 设施加成
        if any(f.facility_key == "trophy" for f in facilities):
            exp += 1
        if any(f.facility_key == "poster" for f in facilities):
            price += 1
        # 满意度（当周期内上菜=1.0）
        total_coin += int(price * coin_bonus)
        total_exp += int(exp * satisfaction_bonus)
        customer_log.append({"type": ctype, "dish": r.name, "coin": int(price * coin_bonus), "exp": int(exp * satisfaction_bonus)})
    st.coins += total_coin
    st.total_revenue += total_coin
    st.total_service += 1
    st.fame += serving_tables
    await add_exp(db, st, total_exp)
    st.last_service_at = datetime.utcnow()
    # 事件上报
    await events.emit(db, user.id, MODULE_KEY, "ranking", {"metric": "dishes", "score": serving_tables})
    await events.emit(db, user.id, MODULE_KEY, "ranking", {"metric": "revenue", "score": total_coin})
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "serve", f"tables{serving_tables}:coin{total_coin}:exp{total_exp}")
    return await render(request, "town/serve_result.html", db, user=user, ok=True,
                        msg=f"营业结算：{serving_tables} 桌 | 金币+{total_coin} | 经验+{total_exp}",
                        customer_log=customer_log, total_coin=total_coin, total_exp=total_exp,
                        serving_tables=serving_tables, st=st,
                        back_href="/games/town", back_text="返回首页")


# ============================================================
# 油量系统
# ============================================================
@router.get("/oil")
async def oil_page(request: Request, db: AsyncSession = Depends(get_db)):
    """油量管理页"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    oil_pct = int(st.oil / st.oil_cap * 100) if st.oil_cap > 0 else 0
    # 当前油壶档位
    pot_index = next((i for i, (cap, _) in enumerate(OIL_POT_TABLE) if cap == st.oil_cap), 0)
    next_pot = OIL_POT_TABLE[pot_index + 1] if pot_index + 1 < len(OIL_POT_TABLE) else None
    return await render(request, "town/oil.html", db, user=user, st=st, oil_pct=oil_pct,
                        pot_index=pot_index, next_pot=next_pot,
                        oil_packs=OIL_PACK_TABLE, exp_need=exp_needed(st.level))


@router.post("/oil/buy/{pack_key}")
async def buy_oil_pack(pack_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """购买补油包"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    pack = OIL_PACK_TABLE.get(pack_key)
    if not pack:
        return await render(request, "result.html", db, user=user, ok=False, msg="补油包不存在",
                            back_href="/games/town/oil", back_text="返回")
    oil_gain, price = pack
    if st.coins < price:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"金币不足（需 {price}）",
                            back_href="/games/town/oil", back_text="返回")
    st.coins -= price
    st.oil = min(st.oil_cap, st.oil + oil_gain)
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "buy_oil", f"{pack_key}:oil{oil_gain}")
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"购买补油包，油量 +{oil_gain}（当前 {st.oil}/{st.oil_cap}）",
                        back_href="/games/town/oil", back_text="返回")


@router.post("/oil/expand")
async def expand_oil_pot(request: Request, db: AsyncSession = Depends(get_db)):
    """油壶扩容"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    pot_index = next((i for i, (cap, _) in enumerate(OIL_POT_TABLE) if cap == st.oil_cap), 0)
    if pot_index + 1 >= len(OIL_POT_TABLE):
        return await render(request, "result.html", db, user=user, ok=False, msg="油壶已达最高档",
                            back_href="/games/town/oil", back_text="返回")
    next_cap, cost = OIL_POT_TABLE[pot_index + 1]
    if st.coins < cost:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"金币不足（需 {cost}）",
                            back_href="/games/town/oil", back_text="返回")
    st.coins -= cost
    st.oil_cap = next_cap
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "expand_oil", f"cap{next_cap}")
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"油壶扩容至 {next_cap}！",
                        back_href="/games/town/oil", back_text="返回")


# ============================================================
# 餐厅升星
# ============================================================
@router.get("/star")
async def star_page(request: Request, db: AsyncSession = Depends(get_db)):
    """升星页"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    normal, fine, gold = await count_learned_by_quality(db, user.id)
    can_apply, apply_msg = can_apply_star(st.stars, st.level, normal, fine, gold,
                                          st.total_service, st.total_revenue)
    next_star = st.stars + 1 if st.stars < 5 else None
    next_req = STAR_APPLY_TABLE.get(next_star) if next_star else None
    next_effect = STAR_TABLE.get(next_star) if next_star else None
    return await render(request, "town/star.html", db, user=user, st=st,
                        normal=normal, fine=fine, gold=gold,
                        can_apply=can_apply, apply_msg=apply_msg,
                        next_star=next_star, next_req=next_req, next_effect=next_effect,
                        exp_need=exp_needed(st.level))


@router.post("/star/apply")
async def apply_star(request: Request, db: AsyncSession = Depends(get_db)):
    """申请升星"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    normal, fine, gold = await count_learned_by_quality(db, user.id)
    can_apply, apply_msg = can_apply_star(st.stars, st.level, normal, fine, gold,
                                          st.total_service, st.total_revenue)
    if not can_apply:
        return await render(request, "result.html", db, user=user, ok=False, msg=f"不满足升星条件：{apply_msg}",
                            back_href="/games/town/star", back_text="返回")
    st.stars += 1
    star_exp = 80 * st.stars
    await add_exp(db, st, star_exp)
    await events.emit(db, user.id, MODULE_KEY, "interact_notify",
                      {"to_id": user.id, "title": "餐厅升星",
                       "content": f"恭喜！餐厅升至 {st.stars} 星"})
    await events.emit(db, user.id, MODULE_KEY, "ranking",
                      {"metric": "stars", "score": st.stars})
    if st.stars >= 2:
        await events.emit(db, user.id, MODULE_KEY, "achievement", {"key": "achv_chef_star2"})
    if st.stars >= 3:
        await events.emit(db, user.id, MODULE_KEY, "icon_light", {"icon_key": "icon_chef"})
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "apply_star", f"star{st.stars}:exp{star_exp}")
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"餐厅升至 {st.stars} 星！经验+{star_exp}",
                        back_href="/games/town", back_text="返回首页")


# ============================================================
# 服务员系统
# ============================================================
@router.get("/waiter")
async def waiter_page(request: Request, db: AsyncSession = Depends(get_db)):
    """服务员管理页"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    waiters = await get_active_waiters(db, user.id)
    _, waiter_total, _, _, _, _, _ = star_info(st.stars)
    waiter_info = []
    for w in waiters:
        friend = await db.get(models.User, w.friend_id)
        remain = max(0, int((w.expire_at - datetime.utcnow()).total_seconds()))
        waiter_info.append({"waiter": w, "friend": friend, "remain": remain})
    # 可雇佣好友列表
    friends = await fsvc.list_friends(db, user.id)
    hired_ids = {w.friend_id for w in waiters}
    hireable = []
    for f in friends:
        if f.friend_id not in hired_ids:
            fu = await db.get(models.User, f.friend_id)
            if fu:
                hireable.append(fu)
    return await render(request, "town/waiter.html", db, user=user, st=st,
                        waiter_info=waiter_info, waiter_total=waiter_total,
                        hireable=hireable, exp_need=exp_needed(st.level))


@router.post("/waiter/hire/{uid}")
async def hire_waiter(uid: int, request: Request, db: AsyncSession = Depends(get_db)):
    """雇佣好友做服务员"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if uid == user.id:
        return await render(request, "result.html", db, user=user, ok=False, msg="不能雇自己",
                            back_href="/games/town/waiter", back_text="返回")
    if not await fsvc.are_friends(db, user.id, uid):
        return await render(request, "result.html", db, user=user, ok=False, msg="只能雇佣好友",
                            back_href="/games/town/waiter", back_text="返回")
    waiters = await get_active_waiters(db, user.id)
    _, waiter_total, _, _, _, _, _ = star_info(st.stars)
    # 总服务员数含系统默认 1 名
    if len(waiters) + 1 >= waiter_total:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"服务员位已满（{waiter_total}）",
                            back_href="/games/town/waiter", back_text="返回")
    if any(w.friend_id == uid for w in waiters):
        return await render(request, "result.html", db, user=user, ok=False, msg="已雇佣该好友",
                            back_href="/games/town/waiter", back_text="返回")
    if st.coins < WAITER_HIRE_COST:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"金币不足（需 {WAITER_HIRE_COST}）",
                            back_href="/games/town/waiter", back_text="返回")
    st.coins -= WAITER_HIRE_COST
    bonus_type = random.choice(["coins", "satisfaction", "speed"])
    w = models.TownWaiter(user_id=user.id, friend_id=uid, bonus_type=bonus_type,
                          hired_at=datetime.utcnow(),
                          expire_at=datetime.utcnow() + timedelta(seconds=WAITER_DURATION))
    db.add(w)
    await events.emit(db, user.id, MODULE_KEY, "interact_notify",
                      {"to_id": uid, "title": "被雇佣为服务员",
                       "content": f"{user.nickname} 雇佣你做服务员 12 小时（加成：{bonus_type}）"})
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "hire_waiter", f"{uid}:{bonus_type}")
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"雇佣成功！加成类型：{bonus_type}（12 小时）",
                        back_href="/games/town/waiter", back_text="返回")


@router.post("/waiter/fire/{waiter_id}")
async def fire_waiter(waiter_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """解雇服务员（提前结束雇佣）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    w = await db.get(models.TownWaiter, waiter_id)
    if not w or w.user_id != user.id:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="服务员不存在", back_href="/games/town/waiter", back_text="返回")
    friend = await db.get(models.User, w.friend_id)
    name = friend.nickname if friend else "未知"
    await db.delete(w)
    await log.record(db, user.id, MODULE_KEY, "fire_waiter", f"{waiter_id}:{w.friend_id}")
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"已解雇服务员 {name}",
                        back_href="/games/town/waiter", back_text="返回")


# ============================================================
# 设施系统
# ============================================================
@router.get("/facility")
async def facility_page(request: Request, db: AsyncSession = Depends(get_db)):
    """设施管理页"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    active = await get_active_facilities(db, user.id)
    active_keys = {f.facility_key for f in active}
    _, _, _, facility_slots, _, _, _ = star_info(st.stars)
    facility_info = []
    for k, (name, price, hours, effect) in FACILITY_TABLE.items():
        remain = 0
        if k in active_keys:
            f = next(x for x in active if x.facility_key == k)
            remain = max(0, int((f.expire_at - datetime.utcnow()).total_seconds()))
        facility_info.append({"key": k, "name": name, "price": price, "hours": hours,
                              "effect": effect, "active": k in active_keys, "remain": remain})
    return await render(request, "town/facility.html", db, user=user, st=st,
                        facility_info=facility_info, facility_slots=facility_slots,
                        exp_need=exp_needed(st.level))


@router.post("/facility/buy/{facility_key}")
async def buy_facility(facility_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """购买设施（24 小时生效）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    fac = FACILITY_TABLE.get(facility_key)
    if not fac:
        return await render(request, "result.html", db, user=user, ok=False, msg="设施不存在",
                            back_href="/games/town/facility", back_text="返回")
    name, price, hours, _ = fac
    active = await get_active_facilities(db, user.id)
    if any(f.facility_key == facility_key for f in active):
        return await render(request, "result.html", db, user=user, ok=False, msg="该设施已生效",
                            back_href="/games/town/facility", back_text="返回")
    _, _, _, facility_slots, _, _, _ = star_info(st.stars)
    if len(active) >= facility_slots:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"设施位已满（{facility_slots}）",
                            back_href="/games/town/facility", back_text="返回")
    if st.coins < price:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"金币不足（需 {price}）",
                            back_href="/games/town/facility", back_text="返回")
    st.coins -= price
    db.add(models.TownFacility(user_id=user.id, facility_key=facility_key,
                               expire_at=datetime.utcnow() + timedelta(hours=hours)))
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "buy_facility", facility_key)
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"购买 {name}，生效 {hours} 小时",
                        back_href="/games/town/facility", back_text="返回")


# ============================================================
# 翻橱柜系统（怀旧核心互动）
# ============================================================
@router.get("/visit/{uid}")
async def visit_town(uid: int, request: Request, db: AsyncSession = Depends(get_db)):
    """访问好友餐厅：翻橱柜"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if await fsvc.is_blocked(db, uid, user.id):
        return await render(request, "result.html", db, user=user, ok=False, msg="对方已拉黑你",
                            back_href="/friends", back_text="返回好友")
    host = await db.get(models.User, uid)
    if not host:
        raise HTTPException(404)
    host_st = await get_state(db, uid)
    # 好友的食材（非上锁）
    invs = await goods.list_inventory(db, uid, MODULE_KEY)
    items = []
    for inv, item in invs:
        if item.type == "ingredient" and inv.quantity > 0 and "oil" not in item.key:
            locked = await locks.is_item_locked(db, uid, MODULE_KEY, item.key)
            items.append({"inv": inv, "item": item, "locked": locked, "qty": inv.quantity})
    # 今日翻柜进度
    dl = await get_daily_log(db, user.id)
    # 对该好友今日已翻次数
    today = date.today().isoformat()
    flip_logs = (await db.execute(select(models.TownFlipLog).where(
        models.TownFlipLog.thief_id == user.id,
        models.TownFlipLog.host_id == uid,
        models.TownFlipLog.created_at >= datetime.strptime(today, "%Y-%m-%d")))).scalars().all()
    flip_count_today = len(flip_logs)
    last_flip = flip_logs[-1] if flip_logs else None
    # 冷却校验
    cooldown_remain = 0
    if last_flip:
        cooldown_remain = max(0, int(FLIP_COOLDOWN - (datetime.utcnow() - last_flip.created_at).total_seconds()))
    # 设施：防翻保鲜柜
    host_facilities = await get_active_facilities(db, uid)
    has_fresh_cabinet = any(f.facility_key == "fresh_cabinet" for f in host_facilities)
    return await render(request, "town/visit.html", db, user=user, host=host, host_st=host_st,
                        items=items, dl=dl, flip_count_today=flip_count_today,
                        cooldown_remain=cooldown_remain, has_fresh_cabinet=has_fresh_cabinet,
                        flip_daily_limit=FLIP_DAILY_LIMIT,
                        flip_per_friend_limit=FLIP_PER_FRIEND_LIMIT)


@router.post("/raid/{uid}/{item_key}")
async def raid(uid: int, item_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """翻橱柜（日限 + 同好友上限 + 冷却 + 衰减 + 物品锁 + 保鲜柜）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if uid == user.id:
        return await render(request, "result.html", db, user=user, ok=False, msg="不能翻自己的",
                            back_href="/friends", back_text="返回好友")
    if await fsvc.is_blocked(db, uid, user.id):
        return await render(request, "result.html", db, user=user, ok=False, msg="对方已拉黑你",
                            back_href="/friends", back_text="返回好友")
    # 日限校验
    dl = await get_daily_log(db, user.id)
    if dl.flip_total >= FLIP_DAILY_LIMIT:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"今日翻柜已达上限({FLIP_DAILY_LIMIT}次)",
                            back_href="/friends", back_text="返回好友")
    # 同好友日限
    today = date.today().isoformat()
    flip_logs = (await db.execute(select(models.TownFlipLog).where(
        models.TownFlipLog.thief_id == user.id,
        models.TownFlipLog.host_id == uid,
        models.TownFlipLog.created_at >= datetime.strptime(today, "%Y-%m-%d")))).scalars().all()
    flip_count_today = len(flip_logs)
    if flip_count_today >= FLIP_PER_FRIEND_LIMIT:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"对该好友今日已翻 {FLIP_PER_FRIEND_LIMIT} 次",
                            back_href=f"/games/town/visit/{uid}", back_text="返回")
    # 冷却校验
    if flip_logs:
        last_flip = flip_logs[-1]
        cooldown_remain = max(0, int(FLIP_COOLDOWN - (datetime.utcnow() - last_flip.created_at).total_seconds()))
        if cooldown_remain > 0:
            return await render(request, "result.html", db, user=user, ok=False,
                                msg=f"冷却中（剩余 {cooldown_remain} 秒）",
                                back_href=f"/games/town/visit/{uid}", back_text="返回")
    # 物品锁校验
    if await locks.is_item_locked(db, uid, MODULE_KEY, item_key):
        return await render(request, "result.html", db, user=user, ok=False, msg="🔒 食材已上锁",
                            back_href=f"/games/town/visit/{uid}", back_text="返回")
    # 防翻保鲜柜：50% 概率翻不到
    host_facilities = await get_active_facilities(db, uid)
    if any(f.facility_key == "fresh_cabinet" for f in host_facilities):
        if random.random() < 0.5:
            return await render(request, "result.html", db, user=user, ok=False,
                                msg="防翻保鲜柜生效，没翻到",
                                back_href=f"/games/town/visit/{uid}", back_text="继续翻")
    # 翻取
    ok_ = await goods.remove_item(db, uid, item_key, MODULE_KEY, 1)
    if not ok_:
        return await render(request, "result.html", db, user=user, ok=False, msg="对方没有这种食材了",
                            back_href=f"/games/town/visit/{uid}", back_text="返回")
    # 大堆叠额外掉落
    extra = 0
    host_inv_qty = await goods.count_item(db, uid, item_key, MODULE_KEY)
    if host_inv_qty >= 10 and random.random() < 0.2:
        extra += 1
    if host_inv_qty >= 30 and random.random() < 0.1:
        extra += 1
    total_get = 1 + extra
    await goods.add_item(db, user.id, item_key, MODULE_KEY, total_get)
    # 收益衰减
    decay_idx = min(flip_count_today, len(FLIP_DECAY) - 1)
    decay = FLIP_DECAY[decay_idx]
    # 经验（衰减后）
    flip_exp = int(1 * decay)
    st = await get_state(db, user.id)
    await add_exp(db, st, flip_exp)
    # 被翻补偿
    host_st = await get_state(db, uid)
    host_st.coins += 1
    host_st.fame += 1
    # 记录
    dl.flip_total += 1
    db.add(models.TownFlipLog(thief_id=user.id, host_id=uid, item_key=item_key,
                              times_today=flip_count_today + 1))
    item = await goods.get_item_by_key(db, item_key)
    await events.emit(db, user.id, MODULE_KEY, "interact_notify",
                      {"to_id": uid, "title": "被翻橱柜",
                       "content": f"{user.nickname} 翻走了你的 {item.name} ×{total_get}"})
    await log.record(db, user.id, MODULE_KEY, "raid", f"{uid}:{item_key}:get{total_get}:decay{decay}")
    await db.commit()
    extra_text = f"（大堆叠额外+{extra}）" if extra > 0 else ""
    decay_text = f"（衰减至 {int(decay*100)}%）" if decay < 1.0 else ""
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"翻到 {item.name} ×{total_get}{extra_text} 经验+{flip_exp}{decay_text}",
                        back_href=f"/games/town/visit/{uid}", back_text="继续翻")


# ============================================================
# 蟑螂与恶作剧
# ============================================================
@router.post("/roach/throw/{uid}")
async def throw_roach(uid: int, request: Request, db: AsyncSession = Depends(get_db)):
    """丢蟑螂（封 1 桌，15 分钟自动消失）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if uid == user.id:
        return await render(request, "result.html", db, user=user, ok=False, msg="不能丢自己",
                            back_href="/friends", back_text="返回好友")
    if await fsvc.is_blocked(db, uid, user.id):
        return await render(request, "result.html", db, user=user, ok=False, msg="对方已拉黑你",
                            back_href="/friends", back_text="返回好友")
    # 日限
    dl = await get_daily_log(db, user.id)
    if dl.roach_throw >= ROACH_DAILY_LIMIT:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"今日丢蟑螂已达上限({ROACH_DAILY_LIMIT}次)",
                            back_href="/friends", back_text="返回好友")
    # 对同一目标冷却
    today = date.today().isoformat()
    last_roach = (await db.execute(select(models.TownCockroach).where(
        models.TownCockroach.thrower_id == user.id,
        models.TownCockroach.user_id == uid,
        models.TownCockroach.created_at >= datetime.strptime(today, "%Y-%m-%d")
    ).order_by(models.TownCockroach.created_at.desc()).limit(1))).scalar_one_or_none()
    if last_roach:
        cooldown_remain = max(0, int(ROACH_COOLDOWN - (datetime.utcnow() - last_roach.created_at).total_seconds()))
        if cooldown_remain > 0:
            return await render(request, "result.html", db, user=user, ok=False,
                                msg=f"对该好友冷却中（剩余 {cooldown_remain} 秒）",
                                back_href=f"/games/town/visit/{uid}", back_text="返回")
    # 单餐厅上限
    existing = await get_active_cockroaches(db, uid)
    if len(existing) >= ROACH_MAX_PER_RESTAURANT:
        return await render(request, "result.html", db, user=user, ok=False, msg="对方餐厅蟑螂已满",
                            back_href=f"/games/town/visit/{uid}", back_text="返回")
    # 卫生香氛：50% 概率抵抗
    host_facilities = await get_active_facilities(db, uid)
    if any(f.facility_key == "sanitizer" for f in host_facilities):
        if random.random() < 0.5:
            return await render(request, "result.html", db, user=user, ok=False,
                                msg="卫生香氛生效，蟑螂被驱散",
                                back_href=f"/games/town/visit/{uid}", back_text="返回")
    db.add(models.TownCockroach(user_id=uid, thrower_id=user.id,
                                expire_at=datetime.utcnow() + timedelta(seconds=ROACH_DURATION)))
    dl.roach_throw += 1
    await events.emit(db, user.id, MODULE_KEY, "interact_notify",
                      {"to_id": uid, "title": "被丢蟑螂",
                       "content": f"{user.nickname} 给你丢了一只蟑螂（封锁 1 桌 15 分钟）"})
    await log.record(db, user.id, MODULE_KEY, "throw_roach", f"{uid}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"丢出蟑螂！对方 1 桌被封锁 15 分钟",
                        back_href=f"/games/town/visit/{uid}", back_text="返回")


@router.post("/roach/clean")
async def clean_roach(request: Request, db: AsyncSession = Depends(get_db)):
    """清理自己餐厅的蟑螂（+2 经验）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    roaches = await get_active_cockroaches(db, user.id)
    if not roaches:
        return await render(request, "result.html", db, user=user, ok=False, msg="没有蟑螂",
                            back_href="/games/town", back_text="返回")
    for r in roaches:
        await db.delete(r)
    await add_exp(db, st, 2 * len(roaches))
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "clean_roach", f"count{len(roaches)}")
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"清理 {len(roaches)} 只蟑螂，经验+{2*len(roaches)}",
                        back_href="/games/town", back_text="返回")


@router.post("/roach/clean/{uid}")
async def help_clean_roach(uid: int, request: Request, db: AsyncSession = Depends(get_db)):
    """帮好友清理蟑螂（+3 经验 +1 人气）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if uid == user.id:
        return await render(request, "result.html", db, user=user, ok=False, msg="用清理自己的入口",
                            back_href=f"/games/town/visit/{uid}", back_text="返回")
    roaches = await get_active_cockroaches(db, uid)
    if not roaches:
        return await render(request, "result.html", db, user=user, ok=False, msg="对方没有蟑螂",
                            back_href=f"/games/town/visit/{uid}", back_text="返回")
    for r in roaches:
        await db.delete(r)
    st = await get_state(db, user.id)
    await add_exp(db, st, 3)
    host_st = await get_state(db, uid)
    host_st.fame += 1
    await events.emit(db, user.id, MODULE_KEY, "interact_notify",
                      {"to_id": uid, "title": "好友帮忙清蟑螂",
                       "content": f"{user.nickname} 帮你清理了 {len(roaches)} 只蟑螂"})
    await log.record(db, user.id, MODULE_KEY, "help_clean_roach", f"{uid}:count{len(roaches)}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"帮好友清理 {len(roaches)} 只蟑螂，经验+3",
                        back_href=f"/games/town/visit/{uid}", back_text="返回")


# ============================================================
# v0.1.1：赛厨 / 厨具 / 技能点 / 厨艺大赛
# ============================================================
@router.get("/chef")
async def chef_page(request: Request, db: AsyncSession = Depends(get_db)):
    """赛厨中心：厨力 / 厨具 / 技能点 / 菜系街道 / 入口"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    tools = await get_chef_tools(db, user.id)
    sk = await get_chef_skill(db, user.id)
    normal, fine, gold = await count_learned_by_quality(db, user.id)
    learned_total = normal + fine + gold
    power = chef_power(st, learned_total, gold, tools, sk)
    skill_allocated = sk.huohou + sk.daogong + sk.chuyi + sk.tiaowei
    skill_remain = SKILL_TOTAL_POINTS - skill_allocated
    # 赛厨今日次数
    dl = await get_daily_log(db, user.id)
    # 最近赛厨记录
    recent = (await db.execute(select(models.TownMatchLog).where(
        models.TownMatchLog.attacker_id == user.id).order_by(
        models.TownMatchLog.created_at.desc()).limit(5))).scalars().all()
    # 大赛报名状态
    today = today_str()
    entry = (await db.execute(select(models.TownContestEntry).where(
        models.TownContestEntry.user_id == user.id,
        models.TownContestEntry.signup_date == today))).scalar_one_or_none()
    zone = contest_zone(st.level)
    await db.commit()
    return await render(request, "town/chef.html", db, user=user, st=st,
                        tools=tools, sk=sk, power=power,
                        skill_remain=skill_remain, skill_total=SKILL_TOTAL_POINTS,
                        skill_names=SKILL_NAMES, chef_tools_cfg=CHEF_TOOLS,
                        cuisine_streets=CUISINE_STREETS,
                        match_used=0, match_limit=MATCH_DAILY_LIMIT,
                        recent=recent, entry=entry, zone=zone,
                        contest_zones=CONTEST_ZONES,
                        exp_need=exp_needed(st.level))


@router.post("/chef/skill_alloc/{skill_key}")
async def chef_skill_alloc(skill_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """分配 1 点技能点（火候/刀功/厨艺/调味）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if skill_key not in SKILL_KEYS:
        return await render(request, "result.html", db, user=user, ok=False, msg="技能非法",
                            back_href="/games/town/chef", back_text="返回")
    sk = await get_chef_skill(db, user.id)
    allocated = sk.huohou + sk.daogong + sk.chuyi + sk.tiaowei
    if allocated >= SKILL_TOTAL_POINTS:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"技能点已分配完（{SKILL_TOTAL_POINTS}点）",
                            back_href="/games/town/chef", back_text="返回")
    setattr(sk, skill_key, getattr(sk, skill_key) + 1)
    await log.record(db, user.id, MODULE_KEY, "chef_skill_alloc", skill_key)
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"{SKILL_NAMES[skill_key]} +1（剩余 {SKILL_TOTAL_POINTS - allocated - 1} 点）",
                        back_href="/games/town/chef", back_text="返回赛厨中心")


@router.post("/chef/skill_reset")
async def chef_skill_reset(request: Request, db: AsyncSession = Depends(get_db)):
    """重置技能点（消耗金币，归还全部已分配点数）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    reset_cost = 2000
    if st.coins < reset_cost:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"金币不足（需 {reset_cost}）",
                            back_href="/games/town/chef", back_text="返回")
    sk = await get_chef_skill(db, user.id)
    sk.huohou = sk.daogong = sk.chuyi = sk.tiaowei = 0
    st.coins -= reset_cost
    await log.record(db, user.id, MODULE_KEY, "chef_skill_reset", "")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"技能点已重置（消耗 {reset_cost} 金币）",
                        back_href="/games/town/chef", back_text="返回赛厨中心")


@router.post("/chef/tool_buy/{tool_key}")
async def chef_tool_buy(tool_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """购买厨具（每类仅 1 件，初始 1 级）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if tool_key not in CHEF_TOOLS:
        return await render(request, "result.html", db, user=user, ok=False, msg="厨具不存在",
                            back_href="/games/town/chef", back_text="返回")
    st = await get_state(db, user.id)
    name, _, price = CHEF_TOOLS[tool_key]
    existing = (await db.execute(select(models.TownChefTool).where(
        models.TownChefTool.user_id == user.id,
        models.TownChefTool.tool_key == tool_key))).scalar_one_or_none()
    if existing:
        return await render(request, "result.html", db, user=user, ok=False, msg=f"已拥有{name}",
                            back_href="/games/town/chef", back_text="返回")
    if st.coins < price:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"金币不足（需 {price}）",
                            back_href="/games/town/chef", back_text="返回")
    st.coins -= price
    db.add(models.TownChefTool(user_id=user.id, tool_key=tool_key, level=1, equipped=True))
    await log.record(db, user.id, MODULE_KEY, "chef_tool_buy", tool_key)
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"购买 {name}（1级），已自动装备",
                        back_href="/games/town/chef", back_text="返回赛厨中心")


@router.post("/chef/tool_upgrade/{tool_key}")
async def chef_tool_upgrade(tool_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """厨具强化（+1 级，消耗金币，等级越高越贵）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if tool_key not in CHEF_TOOLS:
        return await render(request, "result.html", db, user=user, ok=False, msg="厨具不存在",
                            back_href="/games/town/chef", back_text="返回")
    st = await get_state(db, user.id)
    t = (await db.execute(select(models.TownChefTool).where(
        models.TownChefTool.user_id == user.id,
        models.TownChefTool.tool_key == tool_key))).scalar_one_or_none()
    if not t:
        return await render(request, "result.html", db, user=user, ok=False, msg="未拥有该厨具",
                            back_href="/games/town/chef", back_text="返回")
    if t.level >= 10:
        return await render(request, "result.html", db, user=user, ok=False, msg="厨具已满级",
                            back_href="/games/town/chef", back_text="返回")
    cost = 1000 * t.level
    if st.coins < cost:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"金币不足（需 {cost}）",
                            back_href="/games/town/chef", back_text="返回")
    st.coins -= cost
    t.level += 1
    await log.record(db, user.id, MODULE_KEY, "chef_tool_upgrade", f"{tool_key}:lv{t.level}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"{CHEF_TOOLS[tool_key][0]} 强化至 {t.level} 级",
                        back_href="/games/town/chef", back_text="返回赛厨中心")


@router.get("/match")
async def match_page(request: Request, db: AsyncSession = Depends(get_db)):
    """赛厨：选择挑战对手（好友列表）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    tools = await get_chef_tools(db, user.id)
    sk = await get_chef_skill(db, user.id)
    normal, fine, gold = await count_learned_by_quality(db, user.id)
    power = chef_power(st, normal + fine + gold, gold, tools, sk)
    # 好友列表（可挑战）
    flist = await fsvc.list_friends(db, user.id)
    opponents = []
    for f in flist:
        fu = await db.get(models.User, f.friend_id)
        if not fu:
            continue
        f_st = await get_state(db, fu.id)
        f_tools = await get_chef_tools(db, fu.id)
        f_sk = await get_chef_skill(db, fu.id)
        f_n, f_fi, f_g = await count_learned_by_quality(db, fu.id)
        f_power = chef_power(f_st, f_n + f_fi + f_g, f_g, f_tools, f_sk)
        opponents.append({"user": fu, "st": f_st, "power": f_power})
    # 今日赛厨次数
    dl = await get_daily_log(db, user.id)
    await db.commit()
    return await render(request, "town/match.html", db, user=user, st=st, power=power,
                        opponents=opponents, match_used=0, match_limit=MATCH_DAILY_LIMIT,
                        exp_need=exp_needed(st.level))


@router.post("/match/challenge/{uid}")
async def match_challenge(uid: int, request: Request, db: AsyncSession = Depends(get_db)):
    """赛厨挑战：3 评委打分，总分高者胜，平局被挑战方胜"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if uid == user.id:
        return await render(request, "result.html", db, user=user, ok=False, msg="不能挑战自己",
                            back_href="/games/town/match", back_text="返回")
    if not await fsvc.are_friends(db, user.id, uid):
        return await render(request, "result.html", db, user=user, ok=False, msg="只能挑战好友",
                            back_href="/games/town/match", back_text="返回")
    if await fsvc.is_blocked(db, uid, user.id):
        return await render(request, "result.html", db, user=user, ok=False, msg="对方已拉黑你",
                            back_href="/games/town/match", back_text="返回")
    dl = await get_daily_log(db, user.id)
    # 计算双方厨力
    st_a = await get_state(db, user.id)
    tools_a = await get_chef_tools(db, user.id)
    sk_a = await get_chef_skill(db, user.id)
    a_n, a_fi, a_g = await count_learned_by_quality(db, user.id)
    power_a = chef_power(st_a, a_n + a_fi + a_g, a_g, tools_a, sk_a)
    st_d = await get_state(db, uid)
    tools_d = await get_chef_tools(db, uid)
    sk_d = await get_chef_skill(db, uid)
    d_n, d_fi, d_g = await count_learned_by_quality(db, uid)
    power_d = chef_power(st_d, d_n + d_fi + d_g, d_g, tools_d, sk_d)
    # 3 评委打分（spec：各关注不同打分点）
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
    # 胜负判定：总分高者胜，平局被挑战方胜（spec）
    if a_total > d_total:
        winner_id = user.id
        result = "win"
    else:
        winner_id = uid  # 平局或对方分高，都被挑战方胜
        result = "lose"
    # 奖惩
    defender = await db.get(models.User, uid)
    if winner_id == user.id:
        st_a.coins += MATCH_WIN_COIN
        await add_exp(db, st_a, MATCH_WIN_EXP)
        msg = f"赛厨胜利！总分 {a_total}:{d_total}，金币+{MATCH_WIN_COIN} 经验+{MATCH_WIN_EXP}"
    else:
        st_a.coins += MATCH_LOSE_COIN
        msg = f"赛厨失利。总分 {a_total}:{d_total}（平局或分低，被挑战方胜），安慰金币+{MATCH_LOSE_COIN}"
    # 记录
    db.add(models.TownMatchLog(
        attacker_id=user.id, defender_id=uid,
        attacker_score=a_total, defender_score=d_total,
        winner_id=winner_id, detail=json.dumps(judge_detail, ensure_ascii=False)))
    await events.emit(db, user.id, MODULE_KEY, "interact_notify",
                      {"to_id": uid, "title": "被赛厨挑战",
                       "content": f"{user.nickname} 向你发起赛厨，结果：{'你胜' if winner_id == uid else '你负'}（{d_total}:{a_total}）"})
    await events.emit(db, user.id, MODULE_KEY, "ranking",
                      {"metric": "chef_win", "score": 1 if winner_id == user.id else 0})
    await log.record(db, user.id, MODULE_KEY, "match_challenge",
                     f"{uid}:a{a_total}:d{d_total}:{result}")
    await db.commit()
    return await render(request, "town/match_result.html", db, user=user, ok=True, msg=msg,
                        a_total=a_total, d_total=d_total, winner_id=winner_id,
                        judge_detail=judge_detail, defender=defender,
                        back_href="/games/town/match", back_text="继续赛厨")


@router.get("/contest")
async def contest_page(request: Request, db: AsyncSession = Depends(get_db)):
    """厨艺大赛：赛区 / 报名状态 / 历史记录"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    today = today_str()
    zone = contest_zone(st.level)
    # 今日报名
    entry = (await db.execute(select(models.TownContestEntry).where(
        models.TownContestEntry.user_id == user.id,
        models.TownContestEntry.signup_date == today))).scalar_one_or_none()
    # 报名时段校验
    now_hour = datetime.utcnow().hour
    signup_open = CONTEST_SIGNUP_HOUR[0] <= now_hour < CONTEST_SIGNUP_HOUR[1]
    # 历史记录（最近 10 条）
    history = (await db.execute(select(models.TownContestEntry).where(
        models.TownContestEntry.user_id == user.id).order_by(
        models.TownContestEntry.created_at.desc()).limit(10))).scalars().all()
    await db.commit()
    return await render(request, "town/contest.html", db, user=user, st=st,
                        zone=zone, entry=entry, signup_open=signup_open,
                        signup_cost=CONTEST_SIGNUP_COST,
                        contest_zones=CONTEST_ZONES, history=history,
                        exp_need=exp_needed(st.level))


@router.post("/contest/signup")
async def contest_signup(request: Request, db: AsyncSession = Depends(get_db)):
    """厨艺大赛报名（消耗体力，每日 1 次，8-23 时）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    zone = contest_zone(st.level)
    if not zone:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg="等级不足，需 Lv40+ 才能参加厨艺大赛",
                            back_href="/games/town/contest", back_text="返回")
    now_hour = datetime.utcnow().hour
    if not (CONTEST_SIGNUP_HOUR[0] <= now_hour < CONTEST_SIGNUP_HOUR[1]):
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"报名时段为每日 {CONTEST_SIGNUP_HOUR[0]}-{CONTEST_SIGNUP_HOUR[1]} 时",
                            back_href="/games/town/contest", back_text="返回")
    today = today_str()
    existing = (await db.execute(select(models.TownContestEntry).where(
        models.TownContestEntry.user_id == user.id,
        models.TownContestEntry.signup_date == today))).scalar_one_or_none()
    if existing:
        return await render(request, "result.html", db, user=user, ok=False, msg="今日已报名",
                            back_href="/games/town/contest", back_text="返回")
    # spec：报名消耗 20 体力（本平台用金币折算，10 金币/体力）
    cost = CONTEST_SIGNUP_COST * 10
    if st.coins < cost:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"金币不足（需 {cost}，折算自 {CONTEST_SIGNUP_COST} 体力）",
                            back_href="/games/town/contest", back_text="返回")
    st.coins -= cost
    db.add(models.TownContestEntry(user_id=user.id, zone=zone, signup_date=today))
    await log.record(db, user.id, MODULE_KEY, "contest_signup", f"{zone}:{today}")
    await db.commit()
    zone_name = CONTEST_ZONES[zone][0]
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"报名成功！赛区：{zone_name}（{today}），23 时后系统匹配，次日 8 时前公布",
                        back_href="/games/town/contest", back_text="返回大赛")


@router.post("/contest/settle")
async def contest_settle(request: Request, db: AsyncSession = Depends(get_db)):
    """厨艺大赛结算（玩家主动触发：匹配同赛区报名者，单场决胜负）

    spec：23 时后系统从报名玩家中随机匹配对手，决出各赛区冠军
    本平台简化为：玩家点"立即结算"匹配同赛区 NPC/玩家，单场决胜负
    """
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    today = today_str()
    entry = (await db.execute(select(models.TownContestEntry).where(
        models.TownContestEntry.user_id == user.id,
        models.TownContestEntry.signup_date == today))).scalar_one_or_none()
    if not entry:
        return await render(request, "result.html", db, user=user, ok=False, msg="今日未报名",
                            back_href="/games/town/contest", back_text="返回")
    if entry.matched:
        return await render(request, "result.html", db, user=user, ok=False,
                            msg=f"今日已结算：{'胜' if entry.result == 'win' else '负'}",
                            back_href="/games/town/contest", back_text="返回")
    # 找同赛区其他报名者；无则生成 NPC
    others = (await db.execute(select(models.TownContestEntry).where(
        models.TownContestEntry.zone == entry.zone,
        models.TownContestEntry.signup_date == today,
        models.TownContestEntry.user_id != user.id,
        models.TownContestEntry.matched.is_(False)))).scalars().all()
    if others:
        opp_entry = random.choice(others)
        opp_id = opp_entry.user_id
        opp_st = await get_state(db, opp_id)
        opp_tools = await get_chef_tools(db, opp_id)
        opp_sk = await get_chef_skill(db, opp_id)
        opp_n, opp_fi, opp_g = await count_learned_by_quality(db, opp_id)
        opp_power = chef_power(opp_st, opp_n + opp_fi + opp_g, opp_g, opp_tools, opp_sk)
        opp_name = (await db.get(models.User, opp_id)).nickname
    else:
        # NPC 对手：按赛区等级范围生成
        zone_name, lo, hi = CONTEST_ZONES[entry.zone]
        npc_level = random.randint(max(lo, st.level - 3), min(hi, st.level + 3))
        opp_power = npc_level * 12 + random.randint(50, 150)
        opp_id = 0
        opp_name = f"{zone_name}NPC厨师(Lv{npc_level})"
    # 玩家厨力
    tools = await get_chef_tools(db, user.id)
    sk = await get_chef_skill(db, user.id)
    a_n, a_fi, a_g = await count_learned_by_quality(db, user.id)
    power = chef_power(st, a_n + a_fi + a_g, a_g, tools, sk)
    # 单场决胜负（厨力 + 随机）
    a_score = power + random.randint(0, 200)
    d_score = opp_power + random.randint(0, 200)
    if a_score >= d_score:
        entry.result = "win"
        entry.reward_coin = 500
        st.coins += 500
        msg = f"厨艺大赛胜利！击败 {opp_name}（{a_score}:{d_score}），奖励金币+500"
    else:
        entry.result = "lose"
        entry.reward_coin = 100
        st.coins += 100
        msg = f"厨艺大赛失利。负于 {opp_name}（{a_score}:{d_score}），安慰金币+100"
    entry.matched = True
    entry.opponent_id = opp_id
    await events.emit(db, user.id, MODULE_KEY, "ranking",
                      {"metric": "contest_win", "score": 1 if entry.result == "win" else 0})
    await log.record(db, user.id, MODULE_KEY, "contest_settle",
                     f"{entry.zone}:{entry.result}:{a_score}:{d_score}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True, msg=msg,
                        back_href="/games/town/contest", back_text="返回大赛")


# ============================================================
# 规则页
# ============================================================
@router.get("/rules")
async def rules(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return await render(request, "town/rules.html", db, user=user)
