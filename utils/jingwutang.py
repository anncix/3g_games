"""
精武堂核心工具模块
包含：数据初始化、属性计算、修炼、技能、战斗、宠物等核心逻辑
"""
import random
import math
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models.models import (
    JingwuRole, JingwuItem, JingwuEquipment, JingwuFabao,
    JingwuWuhun, JingwuDungeon, JingwuTitle, JingwuSkill,
    JingwuUserSkill, JingwuPetTemplate, JingwuPet,
    JingwuTalisman, JingwuLevelExp, BattleLog, User, Wallet
)
from utils.common import change_currency, add_item as platform_add_item, add_notification

# ============================================================
# 一、基础配置数据
# ============================================================

# 15个技能配置
SKILL_TEMPLATES = [
    # ---- 默认技能 ----
    {"skill_code": "xixing", "name": "吸星功法", "description": "吸人内力为己用，战斗中可吸取对方精气",
     "icon": "🌀", "skill_type": "drain", "mp_cost": 8, "damage_mult": 0.8,
     "lifesteal_pct": 0.3, "effect_json": json.dumps({"drain_mp": 5, "drain_hp_pct": 0.15}),
     "price_gcoin": 0, "price_sp": 0, "req_level": 1, "is_default": True, "quality": "good"},

    # ---- 攻击类技能 ----
    {"skill_code": "yijian", "name": "一剑封喉", "description": "凌厉一剑，直取要害，造成150%伤害",
     "icon": "⚔️", "skill_type": "attack", "mp_cost": 12, "damage_mult": 1.5,
     "price_gcoin": 500, "price_sp": 5, "req_level": 5, "quality": "common"},
    {"skill_code": "liexin", "name": "裂心斩", "description": "霸刀一击，造成180%伤害，有几率暴击",
     "icon": "🗡️", "skill_type": "attack", "mp_cost": 18, "damage_mult": 1.8,
     "effect_json": json.dumps({"crit_bonus": 20}),
     "price_gcoin": 1200, "price_sp": 10, "req_level": 15, "quality": "good"},
    {"skill_code": "qishang", "name": "七伤拳", "description": "先伤己后伤人，造成220%伤害但自损5%气血",
     "icon": "👊", "skill_type": "attack", "mp_cost": 25, "damage_mult": 2.2,
     "effect_json": json.dumps({"self_damage_pct": 0.05}),
     "price_gcoin": 3000, "price_sp": 20, "req_level": 30, "quality": "excellent"},
    {"skill_code": "xianglong", "name": "降龙十八掌", "description": "丐帮绝学，刚猛无俦，造成250%伤害",
     "icon": "🐉", "skill_type": "attack", "mp_cost": 35, "damage_mult": 2.5,
     "price_gcoin": 8000, "price_sp": 40, "req_level": 50, "quality": "epic"},
    {"skill_code": "dugu", "name": "独孤九剑", "description": "剑魔独孤求败所创，造成300%伤害，无视20%防御",
     "icon": "⚡", "skill_type": "attack", "mp_cost": 50, "damage_mult": 3.0,
     "effect_json": json.dumps({"armor_pen": 0.2}),
     "price_gcoin": 20000, "price_sp": 80, "req_level": 70, "quality": "legendary"},

    # ---- 控制类技能 ----
    {"skill_code": "tianluo", "name": "天罗地网", "description": "封印对方2回合无法攻击",
     "icon": "🕸️", "skill_type": "control", "mp_cost": 20, "damage_mult": 0.3,
     "control_turns": 2, "price_gcoin": 2000, "price_sp": 15, "req_level": 20, "quality": "good"},
    {"skill_code": "sanqing", "name": "三清缚影", "description": "道家封印术，封印对方3回合，造成少量伤害",
     "icon": "🔮", "skill_type": "control", "mp_cost": 35, "damage_mult": 0.5,
     "control_turns": 3, "price_gcoin": 6000, "price_sp": 30, "req_level": 45, "quality": "excellent"},
    {"skill_code": "dingxue", "name": "点穴手", "description": "封穴截脉，封印对方1回合，但命中后必暴击",
     "icon": "👆", "skill_type": "control", "mp_cost": 15, "damage_mult": 1.2,
     "control_turns": 1, "effect_json": json.dumps({"guaranteed_crit": True}),
     "price_gcoin": 800, "price_sp": 8, "req_level": 10, "quality": "common"},

    # ---- 回血类技能 ----
    {"skill_code": "huichun", "name": "回春术", "description": "恢复25%最大气血",
     "icon": "💚", "skill_type": "heal", "mp_cost": 15, "heal_pct": 0.25,
     "price_gcoin": 1000, "price_sp": 8, "req_level": 8, "quality": "common"},
    {"skill_code": "miaoshou", "name": "妙手回春", "description": "恢复40%最大气血，解除异常状态",
     "icon": "🌿", "skill_type": "heal", "mp_cost": 30, "heal_pct": 0.40,
     "effect_json": json.dumps({"cleanse": True}),
     "price_gcoin": 5000, "price_sp": 25, "req_level": 40, "quality": "excellent"},
    {"skill_code": "changsheng", "name": "长生诀", "description": "恢复60%最大气血，持续回血2回合",
     "icon": "🌸", "skill_type": "heal", "mp_cost": 45, "heal_pct": 0.60,
     "effect_json": json.dumps({"hot_pct": 0.1, "hot_turns": 2}),
     "price_gcoin": 15000, "price_sp": 60, "req_level": 65, "quality": "epic"},

    # ---- 反弹/增益类 ----
    {"skill_code": "jinge", "name": "金钟罩", "description": "反弹30%伤害，持续2回合",
     "icon": "🔔", "skill_type": "counter", "mp_cost": 20, "counter_pct": 0.30,
     "effect_json": json.dumps({"counter_turns": 2}),
     "price_gcoin": 1500, "price_sp": 12, "req_level": 12, "quality": "good"},
    {"skill_code": "tiebu", "name": "铁布衫", "description": "反弹50%伤害，防御提升30%，持续2回合",
     "icon": "🛡️", "skill_type": "counter", "mp_cost": 30, "counter_pct": 0.50,
     "effect_json": json.dumps({"counter_turns": 2, "defense_buff": 0.3}),
     "price_gcoin": 7000, "price_sp": 35, "req_level": 40, "quality": "excellent"},
    {"skill_code": "xisui", "name": "洗髓经", "description": "易筋洗髓，全属性提升15%，持续3回合",
     "icon": "📿", "skill_type": "buff", "mp_cost": 40,
     "effect_json": json.dumps({"all_buff": 0.15, "buff_turns": 3}),
     "price_gcoin": 12000, "price_sp": 50, "req_level": 55, "quality": "epic"},
]

# 头衔配置
TITLE_CONFIGS = [
    {"title_code": "newbie", "name": "武林新丁", "color": "#95a5a6", "req_level": 1, "req_win": 0},
    {"title_code": "disciple", "name": "江湖小虾", "color": "#2ecc71", "req_level": 10, "req_win": 10},
    {"title_code": "knight", "name": "江湖侠客", "color": "#3498db", "req_level": 20, "req_win": 50},
    {"title_code": "hero", "name": "风尘奇侠", "color": "#9b59b6", "req_level": 35, "req_win": 200},
    {"title_code": "master", "name": "一代宗师", "color": "#f39c12", "req_level": 50, "req_win": 500},
    {"title_code": "legend", "name": "武林传奇", "color": "#e74c3c", "req_level": 70, "req_win": 1500},
    {"title_code": "saint", "name": "武林至尊", "color": "#ffd700", "req_level": 90, "req_win": 5000},
]

# 宠物模板 (4种族：1龙(主血) 2虎(主速) 3凤(主精) 4龟(主防))
PET_TEMPLATES = [
    {"pet_code": "wolf", "name": "雪狼", "race": 2, "race_name": "虎", "quality": "common", "icon": "🐺",
     "talent_name": "狼爪连击", "talent_desc": "攻击时有几率连击",
     "base_hp": 200, "base_mp": 50, "base_damage": 25, "base_defense": 10, "base_speed": 15,
     "grow_hp": 10, "grow_mp": 5, "grow_damage": 2, "grow_defense": 1, "grow_speed": 2,
     "possess_bonus_json": {"damage": 15, "speed": 5},
     "battle_skill": "狼爪连击", "price_gcoin": 2000, "price_yuanbao": 0,
     "description": "雪原之狼，敏捷善战"},
    {"pet_code": "tiger", "name": "白虎", "race": 2, "race_name": "虎", "quality": "good", "icon": "🐯",
     "talent_name": "虎啸山林", "talent_desc": "提升伤害力",
     "base_hp": 350, "base_mp": 50, "base_damage": 40, "base_defense": 20, "base_speed": 12,
     "grow_hp": 15, "grow_mp": 5, "grow_damage": 3, "grow_defense": 2, "grow_speed": 1,
     "possess_bonus_json": {"damage": 30, "defense": 10, "hp": 200},
     "battle_skill": "虎啸山林", "price_gcoin": 8000, "price_yuanbao": 0,
     "description": "百兽之王，力大无穷"},
    {"pet_code": "eagle", "name": "苍鹰", "race": 2, "race_name": "虎", "quality": "good", "icon": "🦅",
     "talent_name": "鹰击长空", "talent_desc": "提升速度和暴击",
     "base_hp": 180, "base_mp": 50, "base_damage": 35, "base_defense": 8, "base_speed": 25,
     "grow_hp": 8, "grow_mp": 5, "grow_damage": 3, "grow_defense": 1, "grow_speed": 3,
     "possess_bonus_json": {"speed": 20, "crit": 5},
     "battle_skill": "鹰击长空", "price_gcoin": 6000, "price_yuanbao": 0,
     "description": "翱翔天际，速度极快"},
    {"pet_code": "dragon", "name": "神龙", "race": 1, "race_name": "龙", "quality": "legendary", "icon": "🐉",
     "talent_name": "龙腾四海", "talent_desc": "龙凝血，大幅提升气血",
     "base_hp": 800, "base_mp": 100, "base_damage": 80, "base_defense": 40, "base_speed": 20,
     "grow_hp": 30, "grow_mp": 10, "grow_damage": 5, "grow_defense": 3, "grow_speed": 2,
     "possess_bonus_json": {"damage": 60, "defense": 25, "hp": 500, "crit": 10},
     "battle_skill": "龙腾四海", "price_gcoin": 50000, "price_yuanbao": 0,
     "description": "上古神龙，万兽臣服"},
    {"pet_code": "phoenix", "name": "凤凰", "race": 3, "race_name": "凤", "quality": "epic", "icon": "🔥",
     "talent_name": "浴火重生", "talent_desc": "凤噬魔，提升精气和恢复",
     "base_hp": 500, "base_mp": 150, "base_damage": 55, "base_defense": 25, "base_speed": 18,
     "grow_hp": 20, "grow_mp": 15, "grow_damage": 4, "grow_defense": 2, "grow_speed": 2,
     "possess_bonus_json": {"damage": 40, "hp": 300, "mp": 200},
     "battle_skill": "浴火重生", "price_gcoin": 30000, "price_yuanbao": 0,
     "description": "不死神鸟，浴火重生"},
]

# 修炼类型
TRAINING_TYPES = {
    "normal": {"name_zh": "普通修炼", "stamina_cost": 20, "exp_per_min": 10, "sp_per_min": 0.5, "gcoin_per_min": 2},
    "advanced": {"name_zh": "高级修炼", "stamina_cost": 30, "exp_per_min": 20, "sp_per_min": 1.0, "gcoin_per_min": 5},
}

# 属性名映射
STAT_NAMES = {
    "con": {"zh": "体质", "field": "con_point"},
    "int": {"zh": "智力", "field": "int_point"},
    "str": {"zh": "力量", "field": "str_point"},
    "end": {"zh": "耐力", "field": "end_point"},
    "agi": {"zh": "敏捷", "field": "agi_point"},
}

# 战神宫（分层修炼 + 排位混战，来源 zol.com 玩家攻略）
# 角色已有 war_god_floor 字段记录当前层数，本常量供展示/结算使用
WARSHRINE = {
    "min_level": 20,              # 进入等级
    "max_floor": 3,               # 当前开放前3层
    "stamina_cost": 15,           # 修炼一次消耗体力
    "duration_hours": 2,          # 修炼时长
    "exp_mul": {1: 1.5, 2: 3.0, 3: 4.5},   # 各层经验倍率
    "floor_cap": {1: 999, 2: 50, 3: 20},   # 各层人数上限
    "rank_interval_hours": 4,     # 排位战间隔
    "must_stop_cultivate": True,  # 必须停止练功房修炼
}

# 战神宫 7 层完整数据（WAP 原版：场景/矿产/酒窖，早期仅开放前 3 层）
WARSHRINE_7FLOORS = [
    (1, "山下修身馆", "陨铜矿", "杂粮酿"),
    (2, "战神山前平台", "星铜矿", "三花酒"),
    (3, "战神山门", "陨铁矿", "竹叶酒"),
    (4, "战神大殿", "星铁矿", "玉泉酒"),
    (5, "战神回廊", "寒铁矿", "杏花香"),
    (6, "战神云台", "玄晶矿", "千里醉"),
    (7, "战神旋梯", "陨晶矿", "白坠春"),
]

# 体力系统（WAP 原版）
STAMINA_SYSTEM = {
    "base_cap": 100,           # 基础上限
    "vip_bonus": 0.20,         # 魔钻/VIP +20%（Lv1-Lv7 从 120 起）
    "cost_arena": 10,          # 比武 10/次
    "cost_cultivate": 20,      # 练功房 20
    "cost_warshrine": 15,      # 战神宫 15
    "cost_wulin": 20,          # 武林大会 20
    "recover_daily_full": True,  # 每天自然回满 100
    "daliwan_per_day": 4,       # 大力丸每天 4 次回体力
    "xianglu_per_day": 3,       # 闻香炉每天 3 次
}

# 武林大会规则（WAP 原版：全服淘汰赛）
WULIN_DA_HUI = {
    "open_level": 10,
    "cost_stamina": 20,        # 不返还
    "divisions": ["初级(1-29)", "中级(30-49)", "高级(50+)"],
    "schedule": "每天报名，次日凌晨比赛",
    "reward": "G币+武魂，胜场越多奖励越丰",
    "titles": ["精武王", "亚军", "四强", "八强"],
}

# 四货币体系（WAP 原版）
CURRENCIES_WAP = [
    ("G币", "免费", "家园分财宝/打工/比武/Q币返利", "白装、基础道具、入帮"),
    ("元宝", "收费", "充值卡/Q币(1元≈100元宝)", "图谱、剑模、强化符、加成卡、大力丸、会旗、喇叭"),
    ("银票", "交易", "充值卡、帮战奖励、元宝兑换", "交易大厅买玩家装备(≥40级可交易)"),
    ("帮贡", "帮派", "捐矿石、基金券、活动", "学心法、用香炉/古树"),
]


# ============================================================
# 二、数据初始化
# ============================================================

def init_jingwu_data(db: Session):
    """初始化精武堂基础数据：技能、等级、头衔、宠物模板、装备模板"""
    # 初始化技能
    for st in SKILL_TEMPLATES:
        existing = db.query(JingwuSkill).filter(JingwuSkill.skill_code == st["skill_code"]).first()
        if not existing:
            db.add(JingwuSkill(**st))

    # 初始化等级经验配置 (1-100级)
    for lv in range(1, 101):
        existing = db.query(JingwuLevelExp).filter(JingwuLevelExp.level == lv).first()
        exp_req = int(100 * math.pow(1.15, lv - 1))
        title_name = None
        for t in TITLE_CONFIGS:
            if t["req_level"] <= lv:
                title_name = t["name"]
        if not existing:
            db.add(JingwuLevelExp(level=lv, exp_needed=exp_req, title_name=title_name,
                                  max_sp=100, potential_gain=3,
                                  exp_4h_normal=exp_req // 6, exp_4h_xiuzhen=exp_req // 3))

    # 初始化头衔
    for tc in TITLE_CONFIGS:
        existing = db.query(JingwuTitle).filter(JingwuTitle.title_code == tc["title_code"]).first()
        if not existing:
            db.add(JingwuTitle(
                title_code=tc["title_code"], name=tc["name"], color=tc.get("color", "#333"),
                level_required=tc["req_level"], req_win=tc.get("req_win", 0),
                description=f"{tc['name']}头衔", bonus_json={},
            ))

    # 初始化宠物模板
    for pt in PET_TEMPLATES:
        existing = db.query(JingwuPetTemplate).filter(JingwuPetTemplate.pet_code == pt["pet_code"]).first()
        if not existing:
            db.add(JingwuPetTemplate(**pt))

    db.commit()


def calculate_exp_for_level(level: int) -> int:
    return int(100 * math.pow(1.15, level - 1))


# ============================================================
# 三、属性与战力计算
# ============================================================

def calculate_stats(role: JingwuRole):
    """计算角色战斗属性（含装备、宠物附身、法宝、武魂加成）"""
    # 基础属性 = 等级成长 + 属性点加点
    hp = 100 + role.level * 20 + role.con_point * 20
    mp = 50 + role.level * 5 + role.int_point * 15
    damage = 10 + role.level * 3 + role.str_point * 3
    defense = 5 + role.level * 2 + role.end_point * 2
    speed = 10 + role.level + role.agi_point * 2
    accuracy = 100 + role.level * 2 + role.agi_point
    dodge = 5 + role.agi_point * 2
    crit = 5 + role.level * 0.2 + role.str_point * 0.1
    crit_damage = 150 + role.str_point

    # 装备加成
    for eq in role.equipments:
        if eq.is_equipped:
            enhance_mult = 1 + eq.enhance_level * 0.1
            damage += int(eq.damage * enhance_mult)
            defense += int(eq.defense * enhance_mult)
            hp += int(eq.hp * enhance_mult)
            speed += int(eq.speed * enhance_mult)
            accuracy += eq.accuracy
            dodge += eq.dodge
            crit += eq.crit
            crit_damage += eq.crit_damage

    # 法宝加成
    if role.talisman_id:
        tl = role.talisman
        if tl:
            damage += tl.damage
            defense += tl.defense
            hp += tl.hp
            speed += tl.speed
            crit += tl.crit

    # 宠物附身加成
    for pet in role.pets:
        if pet.is_possessing:
            try:
                bonus = json.loads(JingwuPetTemplate.possess_bonus_json) if False else None
            except Exception:
                bonus = None
            # 直接从宠物属性换算加成（简化）
            hp += pet.max_hp // 5
            damage += pet.damage // 3
            defense += pet.defense // 3
            speed += pet.speed // 4

    return {
        "hp": int(hp),
        "mp": int(mp),
        "max_hp": int(hp),
        "max_mp": int(mp),
        "damage": int(damage),
        "defense": int(defense),
        "speed": int(speed),
        "accuracy": int(accuracy),
        "dodge": int(dodge),
        "crit": min(95, int(crit)),
        "crit_damage": int(crit_damage),
    }


def calculate_combat_power(role: JingwuRole) -> int:
    """计算战斗力"""
    stats = calculate_stats(role)
    base = stats["damage"] * 2 + stats["defense"] * 1.5 + stats["speed"] + stats["max_hp"] // 10
    attr_bonus = (role.str_point * 5 + role.con_point * 3 + role.agi_point * 2 + role.end_point * 2 + role.int_point * 2)
    level_bonus = role.level * 50
    equip_bonus = 0
    for eq in role.equipments:
        if eq.is_equipped:
            enhance_mult = 1 + eq.enhance_level * 0.1
            equip_bonus += (eq.damage * enhance_mult * 2 + eq.defense * enhance_mult * 1.5 + eq.hp // 10 + eq.speed)
    skill_bonus = len(role.skill_pool or []) * 100 + role.skill_points
    pet_bonus = 0
    for pet in role.pets:
        if pet.is_battling or pet.is_possessing:
            pet_bonus += pet.damage * 2 + pet.max_hp // 20 + pet.level * 30
    return int(base + attr_bonus + level_bonus + equip_bonus + skill_bonus + pet_bonus)


def apply_stats_to_role(role: JingwuRole):
    """将计算后的属性应用到角色"""
    stats = calculate_stats(role)
    old_max_hp = role.max_hp
    old_max_mp = role.max_mp
    role.max_hp = stats["max_hp"]
    role.max_mp = stats["max_mp"]
    role.damage = stats["damage"]
    role.defense = stats["defense"]
    role.speed = stats["speed"]
    role.accuracy = stats["accuracy"]
    role.dodge = stats["dodge"]
    role.crit = stats["crit"]
    role.crit_damage = stats["crit_damage"]
    # 同步旧字段
    role.base_damage = stats["damage"]
    role.base_defense = stats["defense"]
    role.base_speed = stats["speed"]
    role.base_accuracy = stats["accuracy"]
    role.base_dodge = stats["dodge"]
    role.base_crit = stats["crit"]
    role.base_crit_damage = stats["crit_damage"]
    # 升级后满血/满蓝
    if role.max_hp > (old_max_hp or 0):
        role.hp = role.max_hp
    if role.max_mp > (old_max_mp or 0):
        role.mp = role.max_mp
    # 同步体力字段
    role.stamina = role.sp
    role.max_stamina = role.max_sp
    role.combat_power = calculate_combat_power(role)


def get_title_for_level(level: int, db: Session):
    """根据等级获取头衔"""
    title = None
    for t in TITLE_CONFIGS:
        if level >= t["req_level"]:
            title = t
    return title


# ============================================================
# 四、体力自动恢复
# ============================================================

def recover_stamina(role: JingwuRole):
    """每分钟自动恢复1点体力"""
    now = datetime.utcnow()
    if not role.last_sp_recover:
        role.last_sp_recover = now
        return
    elapsed = (now - role.last_sp_recover).total_seconds()
    recover = int(elapsed // 60)
    if recover > 0:
        role.sp = min(role.max_sp, role.sp + recover)
        role.stamina = role.sp
        role.last_sp_recover = now - timedelta(seconds=elapsed % 60)


def use_xianglu(role: JingwuRole, db: Session) -> tuple:
    """使用闻香炉恢复体力"""
    now = datetime.utcnow()
    if role.xianglu_last_use and (now - role.xianglu_last_use).total_seconds() < 3600:
        remaining = 3600 - int((now - role.xianglu_last_use).total_seconds())
        return False, f"闻香炉冷却中，还需{remaining // 60}分钟"
    recover = 30 + role.xianglu_level * 10
    role.sp = min(role.max_sp, role.sp + recover)
    role.stamina = role.sp
    role.xianglu_last_use = now
    db.commit()
    return True, f"使用闻香炉恢复了{recover}点体力！"


# ============================================================
# 五、角色创建
# ============================================================

def create_jingwu_character(db: Session, user: User, name: str, gender: str = "male"):
    """创建精武堂角色，分配初始属性，学习默认技能"""
    role = JingwuRole(
        user_id=user.id,
        name=name,
        gender=1 if gender == "male" else 2,
        profession="common",
        potential=3,
        con_point=0,
        int_point=0,
        str_point=0,
        end_point=0,
        agi_point=0,
        level=1,
        exp=0,
        gcoin=1000,
        skill_points=5,
        hp=100,
        mp=50,
        sp=100,
        max_sp=100,
        last_sp_recover=datetime.utcnow(),
    )
    db.add(role)
    db.flush()

    # 创建副本记录
    dungeon = JingwuDungeon(role_id=role.id)
    db.add(dungeon)

    # 初始装备
    starter_weapon = JingwuEquipment(
        owner_id=role.id, slot="weapon", name="新手木剑", level_required=1,
        quality="common", damage=5, is_equipped=True, gem_slots=1,
    )
    db.add(starter_weapon)
    starter_armor = JingwuEquipment(
        owner_id=role.id, slot="armor", name="粗布衣", level_required=1,
        quality="common", defense=3, hp=50, is_equipped=True, gem_slots=1,
    )
    db.add(starter_armor)

    # 初始道具
    initial_items = [
        ("大力神丸", "prop", "恢复30点体力", 10, "good"),
        ("小还丹", "prop", "恢复100点气血", 20, "common"),
        ("大还丹", "prop", "满血恢复", 5, "excellent"),
        ("雪参玉蟾丸", "prop", "恢复全部气血和精气", 3, "epic"),
    ]
    for iname, icat, idesc, iqty, iqual in initial_items:
        db.add(JingwuItem(owner_id=role.id, item_type="prop", category=icat,
                          name=iname, description=idesc, quantity=iqty, quality=iqual))

    # 学习默认技能：吸星功法
    default_skill = db.query(JingwuSkill).filter(JingwuSkill.skill_code == "xixing").first()
    if default_skill:
        us = JingwuUserSkill(owner_id=role.id, skill_id=default_skill.id, is_equipped=True, level=1)
        db.add(us)
        role.skills_learned = [default_skill.id]
        role.skill_pool = [default_skill.id]

    # 计算并应用属性
    apply_stats_to_role(role)
    role.hp = role.max_hp
    role.mp = role.max_mp

    db.commit()
    db.refresh(role)
    return role


# ============================================================
# 六、加点系统
# ============================================================

def allocate_point(role: JingwuRole, stat: str, db: Session) -> tuple:
    """
    加潜能点
    stat: con/int/str/end/agi
    """
    if role.potential <= 0:
        return False, "没有可用的潜能点！"
    stat_map = {"con": "con_point", "int": "int_point", "str": "str",
                "end": "end_point", "agi": "agi_point",
                # 兼容旧字段
                "mag": "int_point", "def": "end_point"}
    if stat not in stat_map:
        return False, "无效的属性！"
    field = stat_map[stat]
    setattr(role, field, getattr(role, field) + 1)
    role.potential -= 1
    apply_stats_to_role(role)
    # 加点后恢复部分气血/精气对应比例
    if stat == "con":
        role.hp = role.max_hp
    elif stat == "int":
        role.mp = role.max_mp
    db.commit()
    stat_name = STAT_NAMES.get(stat, {}).get("zh", stat)
    return True, f"{stat_name}+1！"


# ============================================================
# 七、修炼系统
# ============================================================

def start_training(role: JingwuRole, training_type: str = "normal") -> tuple:
    """开始修炼，消耗体力"""
    if role.train_status != 0 and role.is_training:
        return False, "你已经在修炼中了！"
    tt = TRAINING_TYPES.get(training_type, TRAINING_TYPES["normal"])
    if role.sp < tt["stamina_cost"]:
        return False, f"体力不足！需要{tt['stamina_cost']}点体力"
    role.sp -= tt["stamina_cost"]
    role.stamina = role.sp
    role.train_status = 1
    role.is_training = True
    role.train_type = training_type
    role.training_type = training_type
    role.train_start = datetime.utcnow()
    role.training_start = role.train_start
    role.train_end = role.train_start + timedelta(hours=4)
    role.training_end = role.train_end
    return True, f"开始{tt['name_zh']}，消耗{tt['stamina_cost']}体力，最长4小时"


def process_training(role: JingwuRole, db: Session):
    """
    处理修炼进度：
    - 每分钟获得经验、技能点、G币
    - 修炼满4小时自动停止并结算
    - 走火入魔状态检查
    """
    if role.train_status == 0:
        return False

    now = datetime.utcnow()

    # 走火入魔状态检查
    if role.train_status == 3 and role.possess_end_time:
        if now >= role.possess_end_time:
            # 走火入魔结束，损失20%气血
            role.hp = max(1, int(role.max_hp * 0.8))
            role.train_status = 0
            role.possess_end_time = None
            db.commit()
            return True
        return False

    # 气血不顺状态（train_status=2）
    if role.train_status == 2 and role.possess_end_time:
        if now >= role.possess_end_time:
            role.train_status = 1  # 恢复修炼
            role.possess_end_time = None
            db.commit()

    if not role.train_start:
        return False

    # 计算修炼时长
    end_time = role.train_end or (role.train_start + timedelta(hours=4))
    effective_now = min(now, end_time)
    elapsed_minutes = int((effective_now - role.train_start).total_seconds() / 60)

    if elapsed_minutes <= 0:
        return False

    tt = TRAINING_TYPES.get(role.train_type or "normal", TRAINING_TYPES["normal"])
    gained_exp = int(elapsed_minutes * tt["exp_per_min"] * (1 + role.level * 0.01))
    gained_sp = int(elapsed_minutes * tt["sp_per_min"])
    gained_gcoin = int(elapsed_minutes * tt["gcoin_per_min"])

    # 已经结算过的就不重复（简单增量：每次只计算新产生的）
    # 为简化，使用累计方式存储并每次commit
    if not hasattr(role, '_training_credited_min'):
        role._training_credited_min = 0

    new_minutes = elapsed_minutes - getattr(role, '_training_credited_min', 0)
    if new_minutes > 0:
        role.exp += int(new_minutes * tt["exp_per_min"] * (1 + role.level * 0.01))
        role.skill_points += int(new_minutes * tt["sp_per_min"])
        role.gcoin += int(new_minutes * tt["gcoin_per_min"])
        role._training_credited_min = elapsed_minutes

    # 修炼结束自动停止
    if now >= end_time:
        _complete_training(role, db)
        return True

    db.commit()
    return False


def _complete_training(role: JingwuRole, db: Session):
    """修炼完成结算（含升级检查）"""
    leveled_up = False
    while role.exp >= calculate_exp_for_level(role.level):
        role.exp -= calculate_exp_for_level(role.level)
        role.level += 1
        role.potential += 3
        leveled_up = True

    if leveled_up:
        apply_stats_to_role(role)
        role.hp = role.max_hp
        role.mp = role.max_mp

    role.train_status = 0
    role.is_training = False
    role.train_type = None
    role.training_type = None
    role.train_start = None
    role.training_start = None
    role.train_end = None
    role.training_end = None
    if hasattr(role, '_training_credited_min'):
        delattr(role, '_training_credited_min')
    apply_stats_to_role(role)
    db.commit()


def stop_training(role: JingwuRole, db: Session) -> tuple:
    """停止修炼并领取奖励"""
    if role.train_status == 0 and not role.is_training:
        return False, "你没有在修炼中！"
    process_training(role, db)  # 先结算到当前
    _complete_training(role, db)
    return True, "修炼结束，已领取经验和技能点！"


def get_training_time_remaining(role: JingwuRole):
    """获取修炼剩余时间文字"""
    if role.train_status == 0 and not role.is_training:
        return None
    now = datetime.utcnow()
    end = role.train_end or role.training_end
    if not end:
        return None
    remaining = end - now
    if remaining.total_seconds() <= 0:
        return "即将完成"
    total_min = int(remaining.total_seconds() // 60)
    hours = total_min // 60
    minutes = total_min % 60
    if role.train_status == 2:
        return f"气血不顺，需治疗"
    if role.train_status == 3:
        return f"⚠️ 走火入魔！"
    if hours > 0:
        return f"{hours}小时{minutes}分钟"
    return f"{minutes}分钟"


def get_training_progress(role: JingwuRole) -> dict:
    """获取修炼进度详情"""
    if role.train_status == 0 and not role.is_training:
        return {"is_training": False}
    now = datetime.utcnow()
    start = role.train_start or role.training_start
    end = role.train_end or role.training_end
    if not start or not end:
        return {"is_training": False}
    total_sec = (end - start).total_seconds()
    elapsed_sec = min((now - start).total_seconds(), total_sec)
    elapsed_min = int(elapsed_sec // 60)
    tt = TRAINING_TYPES.get(role.train_type or "normal", TRAINING_TYPES["normal"])
    return {
        "is_training": True,
        "status": role.train_status,
        "status_text": {0: "空闲", 1: "修炼中", 2: "气血不顺", 3: "走火入魔"}.get(role.train_status, "未知"),
        "elapsed_minutes": elapsed_min,
        "remaining_text": get_training_time_remaining(role),
        "gained_exp": int(elapsed_min * tt["exp_per_min"] * (1 + role.level * 0.01)),
        "gained_sp": int(elapsed_min * tt["sp_per_min"]),
        "gained_gcoin": int(elapsed_min * tt["gcoin_per_min"]),
        "type_name": tt["name_zh"],
    }


def steal_exp(thief: JingwuRole, target: JingwuRole, db: Session) -> tuple:
    """吸星功法：偷取修炼中好友的经验"""
    if thief.sp < 5:
        return False, "体力不足（需要5点）"
    if target.train_status != 1 and not target.is_training:
        return False, "对方不在修炼中，无法吸取！"
    if thief.id == target.id:
        return False, "不能对自己使用！"

    thief.sp -= 5
    thief.stamina = thief.sp

    # 偷取量 = 对方已获得经验的5-15%
    t_prog = get_training_progress(target)
    stolen_exp = int(t_prog.get("gained_exp", 0) * random.uniform(0.05, 0.15))
    stolen_sp = int(t_prog.get("gained_sp", 0) * random.uniform(0.05, 0.12))
    stolen_gcoin = int(t_prog.get("gained_gcoin", 0) * random.uniform(0.05, 0.10))

    # 有概率失败/被发现
    if random.random() < 0.25:
        # 失败：反受其害，损失少量气血
        thief.hp = max(1, thief.hp - int(thief.max_hp * 0.05))
        db.commit()
        return False, "吸星失败，被对方真气反震，受到轻伤！"

    thief.exp += stolen_exp
    thief.skill_points += stolen_sp
    thief.gcoin += stolen_gcoin
    # 被偷者损失部分
    target.exp = max(0, target.exp - stolen_exp // 2)
    target.skill_points = max(0, target.skill_points - stolen_sp // 2)

    # 检查升级
    _check_level_up(thief, db)
    db.commit()
    return True, f"吸星成功！偷取了{stolen_exp}经验、{stolen_sp}技能点、{stolen_gcoin}G币"


def harass_target(actor: JingwuRole, target: JingwuRole, db: Session) -> tuple:
    """骚扰修炼中的玩家：有几率让其气血不顺或走火入魔"""
    if actor.sp < 8:
        return False, "体力不足（需要8点）"
    if target.train_status != 1 and not target.is_training:
        return False, "对方不在修炼中！"
    if actor.id == target.id:
        return False, "不能骚扰自己！"

    actor.sp -= 8
    actor.stamina = actor.sp

    roll = random.random()
    now = datetime.utcnow()
    if roll < 0.3:
        # 走火入魔（1分钟内治疗免损失，否则损失20%气血）
        target.train_status = 3
        target.is_training = False
        target.possess_end_time = now + timedelta(minutes=1)
        msg = f"骚扰成功！{target.name}走火入魔！需在1分钟内治疗"
    elif roll < 0.65:
        # 气血不顺
        target.train_status = 2
        target.possess_end_time = now + timedelta(minutes=2)
        msg = f"骚扰成功！{target.name}气血不顺，修炼效率大降"
    else:
        # 失败
        msg = f"骚扰失败！{target.name}毫无察觉"

    db.commit()
    return True, msg


def treat_possession(role: JingwuRole, db: Session) -> tuple:
    """治疗走火入魔/气血不顺"""
    if role.train_status not in (2, 3):
        return False, "你没有异常状态需要治疗"
    # 1分钟内治疗免损失
    role.train_status = 0
    role.possess_end_time = None
    db.commit()
    return True, "治疗成功！恢复正常，可以继续修炼"


# ============================================================
# 八、技能系统
# ============================================================

def learn_skill(role: JingwuRole, skill_id: int, db: Session) -> tuple:
    """学习技能（消耗G币+技能点）"""
    skill = db.query(JingwuSkill).filter(JingwuSkill.id == skill_id).first()
    if not skill:
        return False, "技能不存在"
    # 已学检查
    for us in role.user_skills:
        if us.skill_id == skill_id:
            return False, "你已经学会此技能"
    if role.level < skill.req_level:
        return False, f"需要等级{skill.req_level}"
    if role.gcoin < skill.price_gcoin:
        return False, f"G币不足（需要{skill.price_gcoin}）"
    if role.skill_points < skill.price_sp:
        return False, f"技能点不足（需要{skill.price_sp}）"

    role.gcoin -= skill.price_gcoin
    role.skill_points -= skill.price_sp

    us = JingwuUserSkill(owner_id=role.id, skill_id=skill_id, is_equipped=False, level=1)
    db.add(us)
    db.flush()

    learned = list(role.skills_learned or [])
    learned.append(skill_id)
    role.skills_learned = learned
    db.commit()
    return True, f"成功学习【{skill.name}】！"


def toggle_skill_equip(role: JingwuRole, user_skill_id: int, db: Session) -> tuple:
    """装配/卸下技能到技能池"""
    us = db.query(JingwuUserSkill).filter(
        JingwuUserSkill.id == user_skill_id,
        JingwuUserSkill.owner_id == role.id
    ).first()
    if not us:
        return False, "未学习该技能"

    pool = list(role.skill_pool or [])
    if us.is_equipped:
        us.is_equipped = False
        if us.skill_id in pool:
            pool.remove(us.skill_id)
        role.skill_pool = pool
        db.commit()
        return True, f"已卸下【{us.skill.name}】"
    else:
        if len(pool) >= 10:
            return False, "技能池已满（最多10个技能），请先卸下其他技能"
        us.is_equipped = True
        pool.append(us.skill_id)
        role.skill_pool = pool
        apply_stats_to_role(role)
        db.commit()
        return True, f"已装配【{us.skill.name}】到技能池"


def get_equipped_skills(role: JingwuRole, db: Session):
    """获取角色已装备技能列表"""
    pool_ids = role.skill_pool or []
    if not pool_ids:
        return []
    skills = db.query(JingwuSkill).filter(JingwuSkill.id.in_(pool_ids)).all()
    return skills


# ============================================================
# 九、宠物系统
# ============================================================

def get_active_pet(role: JingwuRole):
    """获取出战宠物"""
    for pet in role.pets:
        if pet.is_battling:
            return pet
    return None


def toggle_pet_battle(role: JingwuRole, pet_id: int, db: Session) -> tuple:
    """切换宠物出战状态"""
    pet = db.query(JingwuPet).filter(JingwuPet.id == pet_id, JingwuPet.owner_id == role.id).first()
    if not pet:
        return False, "宠物不存在"
    if pet.is_battling:
        pet.is_battling = False
        db.commit()
        apply_stats_to_role(role)
        return True, f"{pet.name}已休息"
    else:
        # 先取消其他出战宠物
        for p in role.pets:
            p.is_battling = False
            p.is_possessing = False
        pet.is_battling = True
        db.commit()
        apply_stats_to_role(role)
        return True, f"{pet.name}跟随出战！"


def toggle_pet_possess(role: JingwuRole, pet_id: int, db: Session) -> tuple:
    """切换宠物附身状态"""
    pet = db.query(JingwuPet).filter(JingwuPet.id == pet_id, JingwuPet.owner_id == role.id).first()
    if not pet:
        return False, "宠物不存在"
    if pet.is_possessing:
        pet.is_possessing = False
        db.commit()
        apply_stats_to_role(role)
        return True, f"{pet.name}取消附身"
    else:
        for p in role.pets:
            p.is_possessing = False
            p.is_battling = False
        pet.is_possessing = True
        db.commit()
        apply_stats_to_role(role)
        return True, f"{pet.name}附身成功！人物属性提升"


def buy_pet(role: JingwuRole, pet_code: str, db: Session) -> tuple:
    """购买宠物"""
    tpl = db.query(JingwuPetTemplate).filter(JingwuPetTemplate.pet_code == pet_code).first()
    if not tpl:
        return False, "宠物不存在"
    if role.gcoin < tpl.price_gcoin:
        return False, f"G币不足（需要{tpl.price_gcoin}）"
    role.gcoin -= tpl.price_gcoin
    pet = JingwuPet(
        owner_id=role.id,
        pet_code=tpl.pet_code,
        name=tpl.name,
        nickname=tpl.name,
        quality=tpl.quality,
        level=1, exp=0, intimacy=0,
        hp=tpl.base_hp, max_hp=tpl.base_hp,
        damage=tpl.base_damage, defense=tpl.base_defense, speed=tpl.base_speed,
        skills_json=json.dumps([tpl.battle_skill]) if tpl.battle_skill else None,
    )
    db.add(pet)
    db.commit()
    return True, f"成功获得【{tpl.name}】！"


# ============================================================
# 十、战斗核心系统（回合制）
# ============================================================

def simulate_battle(attacker: JingwuRole, defender: JingwuRole, db: Session, is_dungeon: bool = False) -> dict:
    """
    回合制战斗模拟
    - 速度决定先手
    - 每回合随机从技能池选可用技能（精气足够）
    - 攻击/控制/回血/反弹/增益/宠物出招
    """
    log = []
    rounds = 0
    max_rounds = 30

    # 初始化战斗状态
    a_stats = calculate_stats(attacker)
    d_stats = calculate_stats(defender)

    a_hp = a_stats["max_hp"]
    a_mp = a_stats["max_mp"]
    a_max_hp = a_stats["max_hp"]
    a_max_mp = a_stats["max_mp"]
    a_dmg = a_stats["damage"]
    a_def = a_stats["defense"]
    a_spd = a_stats["speed"]
    a_dodge = a_stats["dodge"]
    a_crit = a_stats["crit"]
    a_critdmg = a_stats["crit_damage"]
    a_name = attacker.name

    d_hp = d_stats["max_hp"]
    d_mp = d_stats["max_mp"]
    d_max_hp = d_stats["max_hp"]
    d_max_mp = d_stats["max_mp"]
    d_dmg = d_stats["damage"]
    d_def = d_stats["defense"]
    d_spd = d_stats["speed"]
    d_dodge = d_stats["dodge"]
    d_crit = d_stats["crit"]
    d_name = defender.name

    # 宠物战斗数据
    a_pet = get_active_pet(attacker) if not is_dungeon else None
    d_pet = get_active_pet(defender) if not is_dungeon else None
    a_pet_hp = a_pet.hp if a_pet else 0
    a_pet_dmg = a_pet.damage if a_pet else 0
    d_pet_hp = d_pet.hp if d_pet else 0
    d_pet_dmg = d_pet.damage if d_pet else 0

    # 控制状态
    a_stun = 0  # 被封印回合数
    d_stun = 0
    # 反弹状态
    a_counter = 0
    a_counter_pct = 0
    d_counter = 0
    d_counter_pct = 0
    # buff状态
    a_buff_turns = 0
    a_buff_pct = 0
    d_buff_turns = 0
    d_buff_pct = 0
    # 持续回血
    a_hot_turns = 0
    a_hot_pct = 0
    d_hot_turns = 0
    d_hot_pct = 0

    # 获取双方技能
    a_skills = get_equipped_skills(attacker, db) if not is_dungeon else []
    d_skills = get_equipped_skills(defender, db) if not is_dungeon else []
    if not a_skills:
        a_skills = [_default_attack_skill()]
    if not d_skills and not is_dungeon:
        d_skills = [_default_attack_skill()]

    if is_dungeon:
        log.append(f"【副本战斗】{a_name}(Lv.{attacker.level}) VS {d_name}")
    else:
        log.append(f"【比武开始】{a_name}(Lv.{attacker.level} 战力{a_stats['damage']*2+a_def*1+a_spd}) "
                   f"VS {d_name}(Lv.{defender.level} 战力{d_stats['damage']*2+d_def*1+d_spd})")

    # 速度决定先手
    if a_spd >= d_spd:
        first, second = "a", "d"
        log.append(f"🚀 {a_name}速度更快，先手出招！")
    else:
        first, second = "d", "a"
        log.append(f"🚀 {d_name}速度更快，先手出招！")

    winner = None
    reward_gcoin = 0
    reward_exp = 0
    reward_items = []

    def get_available_skills(skills, cur_mp):
        """获取精气足够的技能"""
        available = [s for s in skills if s.mp_cost <= cur_mp]
        return available if available else [_default_attack_skill()]

    def apply_skill(skill, actor_hp, actor_mp, actor_max_hp, actor_max_mp, actor_dmg,
                    target_hp, target_mp, target_max_hp, target_def,
                    actor_stun, target_stun,
                    actor_counter_pct, target_counter, target_counter_pct,
                    actor_buff_pct, target_hot_turns, target_hot_pct,
                    actor_dodge, actor_crit, actor_critdmg,
                    actor_name, target_name, pet_dmg, pet_hp, is_pet_turn=False):
        """
        执行一个技能，返回 (new_target_hp, new_actor_hp, new_actor_mp, new_target_mp,
                          new_target_stun, new_actor_counter_pct, new_actor_counter_turns,
                          new_actor_buff_pct, new_actor_buff_turns, new_actor_hot_pct, new_actor_hot_turns,
                          log_lines, damage_dealt)
        """
        lines = []
        damage_dealt = 0
        mp_cost = skill.mp_cost if not is_pet_turn else 0
        actor_mp = max(0, actor_mp - mp_cost)

        if not is_pet_turn:
            lines.append(f"💠 {actor_name}使用【{skill.name}】（消耗{mp_cost}精气）")
        else:
            lines.append(f"🐾 {actor_name}的宠物释放【{skill.name}】")

        # Buff类
        if skill.skill_type == "buff":
            try:
                eff = json.loads(skill.effect_json) if skill.effect_json else {}
            except Exception:
                eff = {}
            buff_val = eff.get("all_buff", 0.15)
            buff_turns_val = eff.get("buff_turns", 3)
            actor_dmg = int(actor_dmg * (1 + buff_val))
            lines.append(f"✨ {actor_name}全属性提升{int(buff_val*100)}%，持续{buff_turns_val}回合")
            return (target_hp, actor_hp, actor_mp, target_mp, target_stun,
                    actor_counter_pct, 0,
                    buff_val, buff_turns_val, 0, 0, lines, 0)

        # 回血类
        if skill.skill_type == "heal":
            heal_amt = int(actor_max_hp * skill.heal_pct)
            actor_hp = min(actor_max_hp, actor_hp + heal_amt)
            lines.append(f"💚 {actor_name}恢复了{heal_amt}点气血！")
            try:
                eff = json.loads(skill.effect_json) if skill.effect_json else {}
            except Exception:
                eff = {}
            if eff.get("cleanse"):
                actor_stun = 0
                lines.append(f"✨ 异常状态已解除！")
            if eff.get("hot_pct"):
                hot_pct_val = eff["hot_pct"]
                hot_turns_val = eff.get("hot_turns", 2)
                return (target_hp, actor_hp, actor_mp, target_mp, target_stun,
                        actor_counter_pct, 0,
                        actor_buff_pct, 0, hot_pct_val, hot_turns_val, lines, 0)
            return (target_hp, actor_hp, actor_mp, target_mp, target_stun,
                    actor_counter_pct, 0,
                    actor_buff_pct, 0, 0, 0, lines, 0)

        # 反弹类
        if skill.skill_type == "counter":
            try:
                eff = json.loads(skill.effect_json) if skill.effect_json else {}
            except Exception:
                eff = {}
            counter_turns = eff.get("counter_turns", 2)
            def_buff = eff.get("defense_buff", 0)
            lines.append(f"🔔 {actor_name}开启{skill.name}，反弹{int(skill.counter_pct*100)}%伤害，持续{counter_turns}回合")
            if def_buff:
                lines.append(f"🛡️ 防御提升{int(def_buff*100)}%")
            return (target_hp, actor_hp, actor_mp, target_mp, target_stun,
                    skill.counter_pct, counter_turns,
                    actor_buff_pct, 0, 0, 0, lines, 0)

        # 攻击类 & 控制类 & 吸血类
        if skill.skill_type in ("attack", "control", "drain"):
            # 命中判定
            hit_roll = random.randint(1, 100)
            if hit_roll <= actor_dodge:
                lines.append(f"💨 {target_name}闪避了攻击！")
                return (target_hp, actor_hp, actor_mp, target_mp, target_stun,
                        actor_counter_pct, 0,
                        actor_buff_pct, 0, 0, 0, lines, 0)

            # 暴击判定
            is_crit = random.randint(1, 100) <= actor_crit
            try:
                eff = json.loads(skill.effect_json) if skill.effect_json else {}
            except Exception:
                eff = {}
            if eff.get("guaranteed_crit"):
                is_crit = True

            # 伤害计算
            base_dmg = max(1, actor_dmg - target_def // 2)
            mult = skill.damage_mult
            if is_pet_turn:
                base_dmg = pet_dmg
                mult = 1.0
            damage = int(base_dmg * mult * random.uniform(0.9, 1.1))
            if is_crit:
                damage = int(damage * (actor_critdmg / 100.0))
            if eff.get("armor_pen"):
                armor_pen = eff["armor_pen"]
                damage = int(base_dmg * mult * (1 + armor_pen) * random.uniform(0.9, 1.1) * (actor_critdmg / 100.0 if is_crit else 1))

            # 自损（七伤拳）
            if eff.get("self_damage_pct"):
                self_dmg = int(actor_max_hp * eff["self_damage_pct"])
                actor_hp = max(1, actor_hp - self_dmg)
                lines.append(f"💔 {actor_name}自损{self_dmg}气血")

            damage = max(1, damage)
            target_hp -= damage
            damage_dealt = damage

            crit_text = "💥暴击！" if is_crit else ""
            lines.append(f"⚔️ {target_name}受到{damage}点伤害{crit_text}")

            # 反弹判定
            if target_counter_pct > 0 and not is_pet_turn:
                reflect = int(damage * target_counter_pct)
                actor_hp = max(1, actor_hp - reflect)
                lines.append(f"🔔 反弹！{actor_name}受到{reflect}点反弹伤害")

            # 吸血
            if skill.lifesteal_pct > 0 or eff.get("drain_hp_pct"):
                drain_pct = skill.lifesteal_pct or eff.get("drain_hp_pct", 0)
                drain_hp = int(damage * drain_pct)
                actor_hp = min(actor_max_hp, actor_hp + drain_hp)
                lines.append(f"🌀 {actor_name}吸取{drain_hp}点气血")
            if eff.get("drain_mp"):
                drain_mp = eff["drain_mp"]
                target_mp = max(0, target_mp - drain_mp)
                actor_mp = min(actor_max_mp, actor_mp + drain_mp)
                lines.append(f"🌀 吸取{drain_mp}点精气")

            # 控制
            new_target_stun = target_stun
            if skill.control_turns > 0:
                new_target_stun = skill.control_turns
                lines.append(f"🔒 {target_name}被封印{skill.control_turns}回合无法行动！")

            return (target_hp, actor_hp, actor_mp, target_mp, new_target_stun,
                    actor_counter_pct, 0,
                    actor_buff_pct, 0, 0, 0, lines, damage_dealt)

        return (target_hp, actor_hp, actor_mp, target_mp, target_stun,
                actor_counter_pct, 0, actor_buff_pct, 0, 0, 0, lines, 0)

    def process_turn(side):
        """处理一方的回合，返回是否继续"""
        nonlocal a_hp, d_hp, a_mp, d_mp, a_stun, d_stun
        nonlocal a_counter, a_counter_pct, d_counter, d_counter_pct
        nonlocal a_buff_turns, a_buff_pct, d_buff_turns, d_buff_pct
        nonlocal a_hot_turns, a_hot_pct, d_hot_turns, d_hot_pct
        nonlocal a_pet_hp, d_pet_hp, winner, reward_gcoin, reward_exp, reward_items

        if side == "a":
            actor_name, target_name = a_name, d_name
            actor_hp, target_hp = a_hp, d_hp
            actor_mp, target_mp = a_mp, d_mp
            actor_max_hp, target_max_hp = a_max_hp, d_max_hp
            actor_max_mp, target_max_mp = a_max_mp, d_max_mp
            actor_dmg, target_def = a_dmg, d_def
            actor_dodge_val, actor_crit_val, actor_critdmg_val = a_dodge, a_crit, a_critdmg
            actor_stun, target_stun = a_stun, d_stun
            actor_counter_pct, target_counter_pct = a_counter_pct, d_counter_pct
            actor_buff_pct, actor_buff_turns = a_buff_pct, a_buff_turns
            actor_hot_pct, actor_hot_turns = a_hot_pct, a_hot_turns
            pet_dmg_val, pet_hp_val = a_pet_dmg, a_pet_hp
            actor_skills = a_skills
            is_atk = True
        else:
            actor_name, target_name = d_name, a_name
            actor_hp, target_hp = d_hp, a_hp
            actor_mp, target_mp = d_mp, a_mp
            actor_max_hp, target_max_hp = d_max_hp, a_max_hp
            actor_max_mp, target_max_mp = d_max_mp, a_max_mp
            actor_dmg, target_def = d_dmg, a_def
            actor_dodge_val, actor_crit_val, actor_critdmg_val = d_dodge, d_crit, d_critdmg
            actor_stun, target_stun = d_stun, a_stun
            actor_counter_pct, target_counter_pct = d_counter_pct, a_counter_pct
            actor_buff_pct, actor_buff_turns = d_buff_pct, d_buff_turns
            actor_hot_pct, actor_hot_turns = d_hot_pct, d_hot_turns
            pet_dmg_val, pet_hp_val = d_pet_dmg, d_pet_hp
            actor_skills = d_skills
            is_atk = False

        # 持续回血
        if actor_hot_turns > 0:
            hot_heal = int(actor_max_hp * actor_hot_pct)
            actor_hp = min(actor_max_hp, actor_hp + hot_heal)
            log.append(f"🌸 {actor_name}持续回血{hot_heal}点")
            actor_hot_turns -= 1

        # 被封印
        if actor_stun > 0:
            log.append(f"🔒 {actor_name}被封印，无法行动！")
            actor_stun -= 1
            # 反弹/buff回合递减
            if side == "a":
                if a_counter > 0: a_counter -= 1
                else: a_counter_pct = 0
                if a_buff_turns > 0: a_buff_turns -= 1
                else: a_buff_pct = 0
                a_hot_turns = max(0, a_hot_turns - 1)
                a_stun = actor_stun
            else:
                if d_counter > 0: d_counter -= 1
                else: d_counter_pct = 0
                if d_buff_turns > 0: d_buff_turns -= 1
                else: d_buff_pct = 0
                d_hot_turns = max(0, d_hot_turns - 1)
                d_stun = actor_stun
            return True

        # 低血量自动使用回血技能
        heal_skills = [s for s in actor_skills if s.skill_type == "heal" and s.mp_cost <= actor_mp]
        if actor_hp < actor_max_hp * 0.3 and heal_skills:
            chosen = random.choice(heal_skills)
        else:
            avail = get_available_skills(actor_skills, actor_mp)
            chosen = random.choice(avail)

        # 应用buff加成到伤害
        effective_dmg = int(actor_dmg * (1 + actor_buff_pct))

        res = apply_skill(chosen, actor_hp, actor_mp, actor_max_hp, actor_max_mp, effective_dmg,
                          target_hp, target_mp, target_max_hp, target_def,
                          actor_stun, target_stun,
                          actor_counter_pct, target_counter, target_counter_pct,
                          actor_buff_pct, actor_hot_turns, actor_hot_pct,
                          actor_dodge_val, actor_crit_val, actor_critdmg_val,
                          actor_name, target_name, 0, 0, is_pet_turn=False)
        (new_target_hp, new_actor_hp, new_actor_mp, new_target_mp, new_target_stun,
         new_actor_counter_pct, new_actor_counter_turns,
         new_actor_buff_pct, new_actor_buff_turns, new_actor_hot_pct, new_actor_hot_turns,
         lines, damage_dealt) = res
        log.extend(lines)

        # 宠物出招（不占人物回合）
        if side == "a" and a_pet and a_pet_hp > 0:
            pet_skill = _pet_attack_skill()
            pet_res = apply_skill(pet_skill, new_actor_hp, new_actor_mp, actor_max_hp, actor_max_mp,
                                  effective_dmg, new_target_hp, new_target_mp, target_max_hp, target_def,
                                  actor_stun, new_target_stun,
                                  new_actor_counter_pct, target_counter, target_counter_pct,
                                  new_actor_buff_pct, 0, 0,
                                  actor_dodge_val, actor_crit_val, actor_critdmg_val,
                                  actor_name, target_name, a_pet_dmg, a_pet_hp, is_pet_turn=True)
            (new_target_hp, new_actor_hp, new_actor_mp, new_target_mp, new_target_stun2,
             _, _, _, _, _, _, pet_lines, pet_dmg_dealt) = pet_res
            log.extend(pet_lines)
            new_target_stun = max(new_target_stun, new_target_stun2)
            # 宠物也可能被反伤（简化：忽略宠物受伤）

        if side == "d" and d_pet and d_pet_hp > 0:
            pet_skill = _pet_attack_skill()
            pet_res = apply_skill(pet_skill, new_actor_hp, new_actor_mp, actor_max_hp, actor_max_mp,
                                  effective_dmg, new_target_hp, new_target_mp, target_max_hp, target_def,
                                  actor_stun, new_target_stun,
                                  new_actor_counter_pct, target_counter, target_counter_pct,
                                  new_actor_buff_pct, 0, 0,
                                  actor_dodge_val, actor_crit_val, actor_critdmg_val,
                                  actor_name, target_name, d_pet_dmg, d_pet_hp, is_pet_turn=True)
            (new_target_hp, new_actor_hp, new_actor_mp, new_target_mp, new_target_stun2,
             _, _, _, _, _, _, pet_lines, pet_dmg_dealt) = pet_res
            log.extend(pet_lines)
            new_target_stun = max(new_target_stun, new_target_stun2)

        # 写回状态
        if side == "a":
            a_hp, d_hp = new_actor_hp, new_target_hp
            a_mp, d_mp = new_actor_mp, new_target_mp
            a_stun, d_stun = actor_stun, new_target_stun
            a_counter_pct = new_actor_counter_pct if new_actor_counter_turns > 0 else a_counter_pct
            a_counter = new_actor_counter_turns
            a_buff_pct = new_actor_buff_pct if new_actor_buff_turns > 0 else 0
            a_buff_turns = new_actor_buff_turns
            a_hot_pct = new_actor_hot_pct
            a_hot_turns = new_actor_hot_turns
            # 递减对方反弹
            if d_counter > 0:
                d_counter -= 1
            else:
                d_counter_pct = 0
        else:
            d_hp, a_hp = new_actor_hp, new_target_hp
            d_mp, a_mp = new_actor_mp, new_target_mp
            d_stun, a_stun = actor_stun, new_target_stun
            d_counter_pct = new_actor_counter_pct if new_actor_counter_turns > 0 else d_counter_pct
            d_counter = new_actor_counter_turns
            d_buff_pct = new_actor_buff_pct if new_actor_buff_turns > 0 else 0
            d_buff_turns = new_actor_buff_turns
            d_hot_pct = new_actor_hot_pct
            d_hot_turns = new_actor_hot_turns
            if a_counter > 0:
                a_counter -= 1
            else:
                a_counter_pct = 0

        return True

    # 主战斗循环
    while rounds < max_rounds and a_hp > 0 and d_hp > 0:
        rounds += 1
        log.append(f"——— 第{rounds}回合 ———")
        for side in (first, second):
            if a_hp <= 0 or d_hp <= 0:
                break
            process_turn(side)

    # 判定结果
    if a_hp > 0 and d_hp <= 0:
        winner = attacker
        log.append(f"🏆【战斗结束】{a_name}获胜！（{rounds}回合）")
    elif d_hp > 0 and a_hp <= 0:
        winner = defender if not is_dungeon else None
        if winner:
            log.append(f"💀【战斗结束】{d_name}获胜！（{rounds}回合）")
        else:
            log.append(f"💀【副本结束】挑战失败...")
    elif a_hp > d_hp:
        winner = attacker
        log.append(f"🏆【战斗结束】{a_name}凭血量优势获胜！")
    elif d_hp > a_hp:
        winner = defender if not is_dungeon else None
        if winner:
            log.append(f"💀【战斗结束】{d_name}凭血量优势获胜！")
    else:
        winner = None
        log.append("⚖️【战斗结束】平局！")

    # 奖励计算
    if winner == attacker:
        if not is_dungeon:
            reward_gcoin = random.randint(50, 150) + role_level_bonus(attacker.level)
            reward_exp = random.randint(20, 60) + role_level_bonus(attacker.level) // 2
        else:
            reward_gcoin = random.randint(200, 500)
            reward_exp = random.randint(100, 300)
        attacker.wins_today = (attacker.wins_today or 0) + 1
        attacker.wins_total = (attacker.wins_total or 0) + 1
        attacker.exp += reward_exp
        attacker.gcoin += reward_gcoin
        # 材料掉落
        if not is_dungeon and random.random() < 0.3:
            materials = ["千年玄玉", "千年灵玉", "天权强化符", "小还丹"]
            drop = random.choice(materials)
            reward_items.append(drop)
            _add_jingwu_item(attacker, drop, 1, db)
        if is_dungeon:
            reward_items.extend(_dungeon_drops(defender, db))
            for item_name in reward_items:
                _add_jingwu_item(attacker, item_name, 1, db)
            reward_gcoin += 500
        if not is_dungeon:
            defender.losses_today = (defender.losses_today or 0) + 1
            defender.losses_total = (defender.losses_total or 0) + 1
    elif winner == defender and not is_dungeon:
        reward_gcoin = random.randint(20, 50)
        reward_exp = random.randint(5, 15)
        defender.wins_today = (defender.wins_today or 0) + 1
        defender.wins_total = (defender.wins_total or 0) + 1
        defender.exp += reward_exp
        defender.gcoin += reward_gcoin
        attacker.losses_today = (attacker.losses_today or 0) + 1
        attacker.losses_total = (attacker.losses_total or 0) + 1

    # 更新角色HP（战后）
    attacker.hp = max(1, int(a_hp * 0.7))  # 战后恢复30%
    attacker.mp = max(1, int(a_mp))
    attacker.stamina = max(0, (attacker.stamina or attacker.sp) - 10)
    attacker.sp = attacker.stamina
    attacker.last_battle_at = datetime.utcnow()

    # 检查升级
    _check_level_up(attacker, db)
    if not is_dungeon and winner == defender:
        _check_level_up(defender, db)

    # 记录战斗日志
    battle_log = BattleLog(
        attacker_id=attacker.id,
        defender_id=defender.id if not is_dungeon else 0,
        winner_id=winner.id if winner else None,
        battle_type="dungeon" if is_dungeon else "pvp",
        rounds=rounds,
        log="\n".join(log),
        reward_silver=reward_gcoin,
        reward_exp=reward_exp,
        reward_items=json.dumps(reward_items, ensure_ascii=False) if reward_items else None,
    )
    db.add(battle_log)
    db.commit()

    return {
        "winner": winner,
        "winner_name": winner.name if winner else "平局",
        "log": "\n".join(log),
        "log_list": log,
        "rounds": rounds,
        "reward_gcoin": reward_gcoin,
        "reward_exp": reward_exp,
        "reward_items": reward_items,
        "attacker_hp_remaining": a_hp,
        "defender_hp_remaining": d_hp,
    }


def _default_attack_skill():
    """普通攻击（无技能时使用）"""
    return _FakeSkill(name="普通攻击", skill_type="attack", mp_cost=0, damage_mult=1.0,
                      heal_pct=0, control_turns=0, counter_pct=0, lifesteal_pct=0,
                      effect_json=None)


def _pet_attack_skill():
    """宠物攻击"""
    return _FakeSkill(name="宠物攻击", skill_type="attack", mp_cost=0, damage_mult=1.2,
                      heal_pct=0, control_turns=0, counter_pct=0, lifesteal_pct=0,
                      effect_json=None)


class _FakeSkill:
    """临时技能对象（用于普通攻击/宠物攻击）"""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def _check_level_up(role: JingwuRole, db: Session):
    """检查升级"""
    leveled_up = False
    while role.exp >= calculate_exp_for_level(role.level):
        role.exp -= calculate_exp_for_level(role.level)
        role.level += 1
        role.potential += 3
        leveled_up = True
    if leveled_up:
        apply_stats_to_role(role)
        role.hp = role.max_hp
        role.mp = role.max_mp


def role_level_bonus(level: int) -> int:
    return int(level * 2)


def _dungeon_drops(boss_role, db: Session):
    """副本掉落（简化）"""
    drops = []
    mats = ["千年玄玉", "千年灵玉", "天权强化符", "摇光宝石符", "大还丹"]
    n = random.randint(1, 3)
    for _ in range(n):
        drops.append(random.choice(mats))
    if random.random() < 0.1:
        drops.append("北极星")
    return drops


# ============================================================
# 十一、物品/背包工具
# ============================================================

def get_item_quantity(role: JingwuRole, item_name: str) -> int:
    for item in role.items:
        if item.name == item_name:
            return item.quantity
    return 0


def _add_jingwu_item(role: JingwuRole, item_name: str, quantity: int, db: Session, quality: str = "common"):
    """添加物品到精武堂背包"""
    existing = None
    for item in role.items:
        if item.name == item_name:
            existing = item
            break
    if existing:
        existing.quantity += quantity
    else:
        item_info = None
        for it in INITIAL_ITEMS:
            if it["name_zh"] == item_name:
                item_info = it
                break
        item = JingwuItem(
            owner_id=role.id,
            item_type=item_info["item_type"] if item_info else "material",
            category=item_info["category"] if item_info else "material",
            name=item_name,
            description=item_info.get("desc_zh", "") if item_info else "",
            quantity=quantity,
            quality=item_info["quality"] if item_info else quality,
        )
        db.add(item)


def add_item(role: JingwuRole, item_name: str, quantity: int, quality: str = "common", db: Session = None):
    _add_jingwu_item(role, item_name, quantity, db, quality)


def consume_item(role: JingwuRole, item_name: str, quantity: int, db: Session) -> bool:
    for item in role.items:
        if item.name == item_name:
            if item.quantity >= quantity:
                item.quantity -= quantity
                if item.quantity <= 0:
                    db.delete(item)
                return True
            return False
    return False


def use_item(role: JingwuRole, item_id: int, db: Session) -> tuple:
    item = db.query(JingwuItem).filter(JingwuItem.id == item_id, JingwuItem.owner_id == role.id).first()
    if not item:
        return False, "物品不存在"
    if item.name == "大力神丸":
        role.sp = min(role.max_sp, role.sp + 30)
        role.stamina = role.sp
        item.quantity -= 1
    elif item.name == "小还丹":
        role.hp = min(role.max_hp, role.hp + 100)
        item.quantity -= 1
    elif item.name == "大还丹":
        role.hp = role.max_hp
        item.quantity -= 1
    elif item.name == "雪参玉蟾丸":
        role.hp = role.max_hp
        role.mp = role.max_mp
        item.quantity -= 1
    else:
        return False, "该物品无法直接使用"
    if item.quantity <= 0:
        db.delete(item)
    apply_stats_to_role(role)
    db.commit()
    return True, "使用成功"


def equip_item(role: JingwuRole, equipment_id: int, db: Session):
    eq = db.query(JingwuEquipment).filter(
        JingwuEquipment.id == equipment_id,
        JingwuEquipment.owner_id == role.id
    ).first()
    if not eq:
        return False
    for other in role.equipments:
        if other.slot == eq.slot and other.is_equipped and other.id != eq.id:
            other.is_equipped = False
    eq.is_equipped = True
    apply_stats_to_role(role)
    db.commit()
    return True


# 保留旧引用兼容
INITIAL_ITEMS = [
    {"item_type": "prop", "category": "prop", "name_zh": "大力神丸", "quality": "excellent", "desc_zh": "恢复体力"},
    {"item_type": "prop", "category": "prop", "name_zh": "小还丹", "quality": "good", "desc_zh": "恢复少量气血"},
    {"item_type": "prop", "category": "prop", "name_zh": "大还丹", "quality": "excellent", "desc_zh": "恢复大量气血"},
    {"item_type": "prop", "category": "prop", "name_zh": "雪参玉蟾丸", "quality": "epic", "desc_zh": "恢复全部气血和精气"},
    {"item_type": "material", "category": "material", "name_zh": "千年玄玉", "quality": "legendary", "desc_zh": "锻造神级装备必备"},
    {"item_type": "material", "category": "material", "name_zh": "千年灵玉", "quality": "legendary", "desc_zh": "锻造神级装备必备"},
    {"item_type": "material", "category": "material", "name_zh": "天权强化符", "quality": "excellent", "desc_zh": "强化装备"},
    {"item_type": "material", "category": "material", "name_zh": "摇光宝石符", "quality": "excellent", "desc_zh": "镶嵌宝石"},
    {"item_type": "material", "category": "material", "name_zh": "北极星", "quality": "legendary", "desc_zh": "提升北极星等级"},
]

# 兼容旧导入
PROFESSIONS = {
    "common": {"name_zh": "普通", "name_en": "Common", "req_level": 1},
    "swordsman": {"name_zh": "剑客", "name_en": "Swordsman", "req_level": 20},
    "blade": {"name_zh": "刀客", "name_en": "Blade Master", "req_level": 20},
    "fist": {"name_zh": "拳师", "name_en": "Brawler", "req_level": 20},
    "assassin": {"name_zh": "刺客", "name_en": "Assassin", "req_level": 40},
    "mage": {"name_zh": "术士", "name_en": "Mage", "req_level": 40},
    "healer": {"name_zh": "医师", "name_en": "Healer", "req_level": 40},
}
FABAO_LIST = []
DUNGEON_STAGES = []
TRANSFER_PATHS = {}
EQUIPMENT_SLOTS = {
    "weapon": {"name_zh": "武器", "name_en": "Weapon"},
    "helmet": {"name_zh": "头盔", "name_en": "Helmet"},
    "armor": {"name_zh": "铠甲", "name_en": "Armor"},
    "boots": {"name_zh": "战靴", "name_en": "Boots"},
    "ring": {"name_zh": "戒指", "name_en": "Ring"},
    "necklace": {"name_zh": "项链", "name_en": "Necklace"},
}
QUALITY_COLORS = {
    "common": "#95a5a6", "good": "#2ecc71", "excellent": "#3498db",
    "epic": "#9b59b6", "legendary": "#f39c12", "divine": "#e74c3c",
}
POLARIS_STARS = []
DIVINE_EQUIPMENT_RECIPES = []

# 以下函数为兼容旧router保留的桩
def do_transfer(role, path, db): pass
def upgrade_polaris(role, db): pass
def enhance_equipment(role, equipment_id, db): return False, "暂未开放"
def socket_gem(role, equipment_id, gem_name, db): return False, "暂未开放"
def forge_divine_equipment(role, recipe_index, db): return False, "暂未开放"
def upgrade_star(role, star_index, db): return False, "暂未开放"
def reset_dungeon_attempts(role, db): pass
