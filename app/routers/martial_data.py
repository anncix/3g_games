"""精武堂静态配置包（v0.1.0 定版）

来源：用户提供的《精武堂完整玩法解析 + 结构与系统解析 + 页面树全量拆解》
口径：怀旧 / 旧逻辑 / WAP 层级页 / 可复刻落地，还原玩法结构与产品节奏。

本文件为纯静态常量与公式函数，路由层直接 import 使用，不入库。
"""
from __future__ import annotations

import json
import math
import random

# ============================================================
# 常量与枚举
# ============================================================
MAX_LEVEL = 80
# 四维基础属性
ATTR_KEYS = ["strength", "agility", "physique", "inner_power"]
ATTR_NAMES = {
    "strength": "力量", "agility": "敏捷",
    "physique": "体魄", "inner_power": "内息",
}
ATTR_DESC = {
    "strength": "影响外功攻击、部分装备需求",
    "agility": "影响命中、闪避、暴击、速度",
    "physique": "影响气血、防御、生存",
    "inner_power": "影响内功攻击、技能效果",
}
ATTR_PER_LEVEL = 3  # 每升一级给 3 点属性点
RESET_COST_SILVER = 5000  # 洗点消耗银两

# 派生属性基础值
BASE_HP = 100
BASE_OUTER_ATK = 10
BASE_INNER_ATK = 10
BASE_OUTER_DEF = 5
BASE_INNER_DEF = 5
BASE_HIT = 10
BASE_DODGE = 5
BASE_SPEED = 10
BASE_CRIT = 0.05

CRIT_MUL = 1.5

# 战神宫（spec：分层修炼 + 排位混战，来源 zol.com 玩家攻略）
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


# ============================================================
# 经验曲线（方案A，平台统一）
# ============================================================
def exp_needed(level: int) -> int:
    """L→L+1 所需经验"""
    if level >= MAX_LEVEL:
        return 0
    return 120 + 80 * level


# ============================================================
# 装备系统
# ============================================================
EQUIP_SLOTS = ["weapon", "armor", "bracer", "belt", "boots", "necklace", "ring", "secret"]
EQUIP_SLOT_NAMES = {
    "weapon": "武器", "armor": "衣服", "bracer": "护腕", "belt": "腰带",
    "boots": "鞋子", "necklace": "项链", "ring": "戒指", "secret": "秘籍",
}
# 品质：白/绿/蓝/紫/橙
EQUIP_QUALITIES = ["white", "green", "blue", "purple", "orange"]
EQUIP_QUALITY_NAMES = {
    "white": "白", "green": "绿", "blue": "蓝", "purple": "紫", "orange": "橙",
}
EQUIP_QUALITY_COEF = {"white": 1.0, "green": 1.3, "blue": 1.6, "purple": 2.0, "orange": 2.5}

# 每个部位的主属性条目：stat_key → base 值（白品质基础）
# stat_key 对应派生属性增量字段
EQUIP_SLOT_STATS = {
    "weapon": {"outer_atk": 8, "inner_atk": 4},
    "armor": {"outer_def": 6, "hp": 40},
    "bracer": {"outer_atk": 4, "outer_def": 3},
    "belt": {"hp": 50, "inner_def": 3},
    "boots": {"speed": 6, "dodge": 4},
    "necklace": {"inner_atk": 6, "hit": 5},
    "ring": {"outer_atk": 5, "inner_atk": 5},
    "secret": {"hp": 30, "crit": 0.02, "speed": 4},
}

# 强化表：strengthen_level → (silver_cost, stone_cost, success_rate, stat_bonus_per_level)
STRENGTHEN_TABLE = {
    1: (500, 1, 1.00, 2),
    2: (800, 1, 0.95, 2),
    3: (1200, 2, 0.90, 3),
    4: (1800, 2, 0.85, 3),
    5: (2600, 3, 0.80, 4),
    6: (3800, 3, 0.70, 4),
    7: (5500, 4, 0.60, 5),
    8: (8000, 5, 0.50, 6),
    9: (12000, 6, 0.40, 7),
    10: (18000, 8, 0.30, 8),
}
STRENGTHEN_MAX = 10


def gen_equip_stats(slot: str, quality: str) -> dict:
    """生成一件装备的基础属性（按部位+品质）"""
    base = EQUIP_SLOT_STATS.get(slot, {})
    coef = EQUIP_QUALITY_COEF.get(quality, 1.0)
    stats = {}
    for k, v in base.items():
        if isinstance(v, float):
            stats[k] = round(v * coef, 4)
        else:
            stats[k] = int(v * coef)
    return stats


def equip_total_stats(equip) -> dict:
    """计算单件装备（含强化）贡献的总属性
    equip 需有 stats(JSON str) 与 strengthen 字段
    """
    try:
        base = json.loads(equip.stats) if isinstance(equip.stats, str) else dict(equip.stats)
    except (json.JSONDecodeError, TypeError):
        base = {}
    bonus_lv = STRENGTHEN_TABLE.get(equip.strengthen, (0, 0, 0, 0))[3]
    total = {}
    for k, v in base.items():
        # 强化加成只加在主数值（整数属性）上，crit 等小数属性按比例略加
        if isinstance(v, float):
            total[k] = round(v + bonus_lv * 0.002, 4)
        else:
            total[k] = v + bonus_lv
    return total


# ============================================================
# 技能系统
# ============================================================
# skill_id → (name, school, type, coef, unlock_level, learn_cost_silver, upgrade_cost_silver, desc)
# school: outer(外功)/inner(内功)/passive(被动增益)
# type: active/passive
SKILLS = {
    "SKM_01": ("劈山掌", "outer", "active", 1.20, 1, 0, 800, "外功单体，稳定输出"),
    "SKM_02": ("连环腿", "outer", "active", 1.55, 5, 600, 1200, "外功高伤，需5级"),
    "SKM_03": ("烈焰掌", "inner", "active", 1.30, 8, 1000, 1600, "内功单体，附灼烧感"),
    "SKM_04": ("冰心诀", "inner", "active", 1.00, 12, 1500, 2000, "内功，附带减速"),
    "SKM_05": ("踏雪无痕", "passive", "passive", 0, 10, 800, 1200, "被动：速度+8/级"),
    "SKM_06": ("铁布衫", "passive", "passive", 0, 10, 800, 1200, "被动：外防+6/级"),
    "SKM_07": ("金钟罩", "passive", "passive", 0, 15, 1200, 1800, "被动：内防+6/级"),
    "SKM_08": ("暴击心法", "passive", "passive", 0, 15, 1200, 1800, "被动：暴击+0.01/级"),
    "SKM_09": ("鹰眼术", "passive", "passive", 0, 12, 1000, 1500, "被动：命中+6/级"),
    "SKM_10": ("吸血功", "passive", "passive", 0, 20, 2000, 2400, "被动：攻击吸血8%/级(上限)"),
    # v0.1.7：spec 精武堂手机版 15 技能（攻击5/辅助5/特殊5）
    # 攻击类 5 个
    "SKM_11": ("剑影留痕", "outer", "active", 1.25, 1, 0, 800, "外功攻击·剑气残影"),
    "SKM_12": ("御剑通灵", "outer", "active", 1.40, 6, 600, 1200, "外功高伤·御剑术"),
    "SKM_13": ("剑气凌风", "inner", "active", 1.35, 10, 1000, 1600, "内功攻击·剑风"),
    "SKM_14": ("人剑合一", "inner", "active", 1.60, 16, 1500, 2200, "内功高伤·人剑合一"),
    "SKM_15": ("潇湘剑雨", "outer", "active", 1.80, 22, 2000, 2800, "外功终极·剑雨群伤"),
    # 辅助类 5 个（被动增益）
    "SKM_16": ("妙手回春", "passive", "passive", 0, 8, 800, 1200, "被动：气血+30/级"),
    "SKM_17": ("神清气朗", "passive", "passive", 0, 10, 800, 1200, "被动：内息+20/级"),
    "SKM_18": ("金钟护体", "passive", "passive", 0, 12, 1000, 1500, "被动：外防+8/级"),
    "SKM_19": ("武神附体", "passive", "passive", 0, 18, 1500, 2000, "被动：外攻+10/级"),
    "SKM_20": ("五灵归宗", "passive", "passive", 0, 25, 2000, 2400, "被动：全属性+5/级"),
    # 特殊类 5 个（特殊机制）
    "SKM_21": ("吸星功法", "inner", "active", 1.10, 12, 1200, 1600, "内功·吸取对方内力"),
    "SKM_22": ("三清缚影", "inner", "active", 0.90, 14, 1200, 1600, "内功·束缚对方行动"),
    "SKM_23": ("斗转星移", "outer", "active", 1.00, 16, 1500, 2000, "外功·反弹伤害"),
    "SKM_24": ("回风扫叶", "outer", "active", 1.45, 18, 1800, 2200, "外功群伤·横扫"),
    "SKM_25": ("天罗地网", "inner", "active", 1.50, 24, 2200, 2800, "内功终极·困敌群伤"),
}
SKILL_MAX_LEVEL = 5


def skill_passive_bonus(skill_id: str, level: int) -> dict:
    """被动技能对属性的加成"""
    bonus = {}
    if skill_id == "SKM_05":
        bonus["speed"] = 8 * level
    elif skill_id == "SKM_06":
        bonus["outer_def"] = 6 * level
    elif skill_id == "SKM_07":
        bonus["inner_def"] = 6 * level
    elif skill_id == "SKM_08":
        bonus["crit"] = round(0.01 * level, 4)
    elif skill_id == "SKM_09":
        bonus["hit"] = 6 * level
    # v0.1.7：spec 手机版辅助类被动
    elif skill_id == "SKM_16":
        bonus["hp"] = 30 * level
    elif skill_id == "SKM_17":
        bonus["inner_power"] = 20 * level
    elif skill_id == "SKM_18":
        bonus["outer_def"] = 8 * level
    elif skill_id == "SKM_19":
        bonus["outer_atk"] = 10 * level
    elif skill_id == "SKM_20":
        bonus["outer_atk"] = 5 * level
        bonus["inner_atk"] = 5 * level
        bonus["outer_def"] = 5 * level
        bonus["inner_def"] = 5 * level
    return bonus


# ============================================================
# 修炼系统
# ============================================================
CULTIVATE_EXP_PER_HOUR = 200      # 普通修炼每小时经验
CULTIVATE_SILVER_PER_HOUR = 120   # 普通修炼每小时银两
BIGUAN_EXP_MUL = 2.0              # 闭关经验倍率
BIGUAN_SILVER_MUL = 1.5           # 闭关银两倍率
CULTIVATE_CAP_HOURS = 12          # 离线收益最多累计 12 小时
BIGUAN_COST_HONOR = 20            # 闭关消耗荣誉（次数限制由日限控制）
BIGUAN_DAILY_LIMIT = 2            # 每日闭关次数上限


def cultivate_yield(seconds: int, biguan: bool) -> tuple[int, int]:
    """计算修炼收益（秒数）→ (exp, silver)，按 12h 封顶"""
    capped = min(seconds, CULTIVATE_CAP_HOURS * 3600)
    hours = capped / 3600
    em = BIGUAN_EXP_MUL if biguan else 1.0
    sm = BIGUAN_SILVER_MUL if biguan else 1.0
    exp = int(CULTIVATE_EXP_PER_HOUR * hours * em)
    silver = int(CULTIVATE_SILVER_PER_HOUR * hours * sm)
    return exp, silver


# ============================================================
# 比武场（PVP）
# ============================================================
ARENA_DAILY_FREE = 10              # 每日免费次数
ARENA_EXTRA_COST_HONOR = 5         # 额外次数消耗荣誉
ARENA_WIN_SCORE = 12               # 胜利得分
ARENA_LOSS_SCORE = -4              # 失败扣分（不低于0）
ARENA_WIN_HONOR = 5                # 胜利荣誉
ARENA_LOSS_HONOR = 1               # 失败荣誉
ARENA_SEASON_DAYS = 7


# ============================================================
# PVE 挑战关卡（阶梯式）
# ============================================================
# stage_id → (name, required_level, enemy_power_mul, reward_silver, reward_exp, drop_item, drop_qty, drop_rate)
PVE_STAGES = {
    "S01": ("木人桩", 1, 0.8, 200, 60, "MT_STRENGTH_STONE", 1, 0.3),
    "S02": ("山贼小卒", 3, 1.0, 300, 90, "MT_STRENGTH_STONE", 1, 0.4),
    "S03": ("山贼头目", 6, 1.2, 500, 150, "MT_IRON_ESSENCE", 1, 0.35),
    "S04": ("江湖恶霸", 10, 1.4, 800, 220, "MT_IRON_ESSENCE", 2, 0.4),
    "S05": ("武馆教头", 15, 1.7, 1200, 320, "MT_REFINE_STONE", 1, 0.3),
    "S06": ("武林高手", 20, 2.0, 1800, 460, "MT_REFINE_STONE", 2, 0.35),
    "S07": ("一代宗师", 30, 2.5, 3000, 700, "MT_BONE_POWDER", 1, 0.3),
    "S08": ("隐世高人", 45, 3.2, 5000, 1100, "MT_BONE_POWDER", 2, 0.35),
    "S09": ("武林盟主", 60, 4.0, 8000, 1600, "MT_RESET_TOKEN", 1, 0.2),
}
PVE_DAILY_ATTEMPT = 10  # 每日挑战总次数


# ============================================================
# 日常任务 + 活跃奖励（用户提供的两套表）
# ============================================================
# task_id → (name, open_level, target_type, target_value, reward_silver, reward_exp,
#            reward_item_1, qty_1, reward_item_2, qty_2, activity_point)
DAILY_TASKS = {
    "D001": ("领取一次修炼收益", 1, "cultivate_claim", 1, 1000, 120, "MT_STRENGTH_STONE", 1, "", 0, 8),
    "D002": ("完成普通挑战5次", 1, "pve_normal_win", 5, 1200, 180, "MT_SMALL_PILL", 2, "", 0, 10),
    "D003": ("完成精英挑战2次", 10, "pve_elite_win", 2, 1800, 240, "MT_STRENGTH_STONE", 2, "MT_BONE_POWDER", 1, 10),
    "D004": ("进行装备强化3次", 10, "equip_strengthen", 3, 1500, 160, "MT_STRENGTH_STONE", 2, "", 0, 8),
    "D005": ("完成1次装备打造", 12, "equip_craft", 1, 2000, 220, "MT_IRON_ESSENCE", 3, "", 0, 10),
    "D006": ("比武场挑战5次", 15, "pvp_arena_try", 5, 1800, 220, "MT_ARENA_TICKET", 1, "", 0, 10),
    "D007": ("比武场获胜2次", 15, "pvp_arena_win", 2, 2200, 260, "MT_ARENA_MEDAL", 2, "", 0, 12),
    "D008": ("完成悬赏任务2次", 18, "bounty_finish", 2, 1800, 240, "MT_BOUNTY_TOKEN", 2, "", 0, 10),
    "D009": ("完成帮派捐献1次", 20, "guild_donate", 1, 1200, 120, "MT_GUILD_CONTRIB_BOX", 1, "", 0, 6),
    "D010": ("帮派任务完成1次", 20, "guild_task_finish", 1, 1800, 180, "MT_GUILD_TOKEN", 2, "", 0, 8),
    "D011": ("挑战BOSS1次", 25, "boss_try", 1, 2600, 320, "MT_REFINE_STONE", 2, "", 0, 12),
    "D012": ("消耗属性点1次", 1, "attr_add", 1, 800, 100, "MT_RESET_TOKEN_FRAG", 1, "", 0, 6),
}

# 活跃奖励档位：activity_point → (silver, exp, item_1, qty_1, item_2, qty_2)
DAILY_ACTIVITY_REWARDS = {
    20: (1000, 120, "MT_SMALL_PILL", 2, "", 0),
    40: (1500, 180, "MT_STRENGTH_STONE", 2, "", 0),
    60: (2200, 240, "MT_BONE_POWDER", 2, "MT_SMALL_PILL", 2),
    80: (3000, 320, "MT_REFINE_STONE", 2, "MT_GUILD_TOKEN", 2),
    100: (5000, 500, "MT_RESET_TOKEN_FRAG", 3, "MT_ARENA_MEDAL", 3),
}


# ============================================================
# 帮派（门派）
# ============================================================
GUILD_CREATE_COST_SILVER = 10000   # 创建帮派消耗
GUILD_DONATE = {
    "silver_1000": (1000, 10),     # 捐 1000 银两 → 10 贡献
    "silver_5000": (5000, 60),     # 捐 5000 银两 → 60 贡献
    "honor_10": (10, 80),          # 捐 10 荣誉 → 80 贡献
}
GUILD_DONATE_DAILY_LIMIT = 3
# 贡献商店：item_key → (cost_contrib, notes)
GUILD_SHOP = {
    "MT_STRENGTH_STONE": (5, "强化石"),
    "MT_IRON_ESSENCE": (15, "玄铁精华"),
    "MT_REFINE_STONE": (30, "精炼石"),
    "MT_RESET_TOKEN_FRAG": (20, "洗点碎片"),
    "MT_SMALL_PILL": (3, "小还丹"),
}


# ============================================================
# 派生属性计算（公式来自用户提供的定版）
# ============================================================
def calc_stats(level: int, attrs: dict, equip_bonuses: dict, skill_bonuses: dict) -> dict:
    """计算派生属性
    attrs: {strength, agility, physique, inner_power}
    equip_bonuses: 各装备贡献的属性汇总 {hp, outer_atk, ...}
    skill_bonuses: 被动技能贡献的属性汇总
    返回完整派生属性 dict
    """
    s = attrs.get("strength", 0)
    a = attrs.get("agility", 0)
    p = attrs.get("physique", 0)
    i = attrs.get("inner_power", 0)
    eb = equip_bonuses
    sb = skill_bonuses

    def sum_by(key):
        return eb.get(key, 0) + sb.get(key, 0)

    hp = BASE_HP + p * 20 + level * 15 + sum_by("hp")
    outer_atk = BASE_OUTER_ATK + s * 3 + level * 2 + sum_by("outer_atk")
    inner_atk = BASE_INNER_ATK + i * 3 + level * 2 + sum_by("inner_atk")
    outer_def = BASE_OUTER_DEF + p * 2 + s * 1 + level * 1.5 + sum_by("outer_def")
    inner_def = BASE_INNER_DEF + p * 1 + i * 2 + level * 1.5 + sum_by("inner_def")
    hit = BASE_HIT + a * 2 + level * 1 + sum_by("hit")
    dodge = BASE_DODGE + a * 1.5 + level * 0.5 + sum_by("dodge")
    crit = BASE_CRIT + a * 0.0004 + sum_by("crit")
    speed = BASE_SPEED + a * 2 + sum_by("speed")
    return {
        "hp": int(hp), "outer_atk": int(outer_atk), "inner_atk": int(inner_atk),
        "outer_def": int(outer_def), "inner_def": int(inner_def),
        "hit": int(hit), "dodge": int(dodge),
        "crit": round(min(crit, 0.80), 4), "speed": int(speed),
    }


def calc_power(stats: dict, skill_score: int, equip_score: int) -> int:
    """战力计算（展示值）"""
    p = (stats["hp"] * 0.20
         + stats["outer_atk"] * 1.8 + stats["inner_atk"] * 1.8
         + stats["outer_def"] * 1.3 + stats["inner_def"] * 1.3
         + stats["hit"] * 0.8 + stats["dodge"] * 0.8
         + stats["speed"] * 1.2
         + skill_score + equip_score)
    return int(p)


def skill_total_score(learned: dict) -> int:
    """已学技能总分（skill_id → level）"""
    score = 0
    for sid, lv in learned.items():
        if sid in SKILLS:
            # 主动技能按 coef*level*10，被动按 level*8
            coef = SKILLS[sid][3]
            score += int((coef * 10 + 8) * lv) if coef else 8 * lv
    return score


def equip_total_score(equips: list) -> int:
    """装备总分（品质+强化）"""
    qmap = EQUIP_QUALITY_COEF
    score = 0
    for e in equips:
        score += int(qmap.get(e.quality, 1.0) * 30 + e.strengthen * 10)
    return score


# ============================================================
# 战斗结算（半自动回合制，文字战报式）
# ============================================================
def _def_reduce(def_val: int, level: int) -> float:
    return def_val / (def_val + 200 + level * 20)


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def auto_battle(atk_stats: dict, atk_level: int, atk_active_skill: tuple | None,
                def_stats: dict, def_level: int, max_rounds: int = 12) -> dict:
    """自动回合战斗结算
    atk_active_skill: (skill_id, level) 或 None（用普攻）
    返回 {win, rounds, log: [...], atk_hp_left, def_hp_left}
    """
    a_hp = atk_stats["hp"]
    d_hp = def_stats["hp"]
    a_max = a_hp
    log = []

    # 出手顺序：速度高者先手
    a_first = atk_stats["speed"] >= def_stats["speed"]
    # 命中率
    hit_rate = _clamp(atk_stats["hit"] / (atk_stats["hit"] + def_stats["dodge"] + 1), 0.25, 0.95)
    crit_rate = _clamp(atk_stats["crit"], 0.05, 0.60)

    sid, slevel = (None, 0)
    if atk_active_skill:
        sid, slevel = atk_active_skill
    # 主动技能系数（升阶略增）
    if sid and sid in SKILLS and SKILLS[sid][2] == "active":
        base_coef = SKILLS[sid][3]
        skill_coef = base_coef * (1.0 + 0.08 * (slevel - 1))
        skill_name = SKILLS[sid][0]
    else:
        skill_coef = 1.0
        skill_name = "普攻"

    # 吸血率（来自 SKM_10 学习等级，由调用方在 atk_stats 里不体现，此处简化为 0）
    lifesteal = 0.0

    for rnd in range(1, max_rounds + 1):
        if a_hp <= 0 or d_hp <= 0:
            break
        # 攻击方打防御方
        order = [("A", a_hp, atk_stats, atk_level, d_hp, def_stats, def_level)] if a_first else \
                [("D", d_hp, def_stats, def_level, a_hp, atk_stats, atk_level)]
        # 简化：双方交替出手，A先
        for actor in (["A", "D"] if a_first else ["D", "A"]):
            if a_hp <= 0 or d_hp <= 0:
                break
            if actor == "A":
                attacker, atk_lv, defender, def_lv = atk_stats, atk_level, def_stats, def_level
                cur_d_hp = d_hp
            else:
                attacker, atk_lv, defender, def_lv = def_stats, def_level, atk_stats, atk_level
                cur_d_hp = a_hp
            if cur_d_hp <= 0:
                continue
            # 命中判定
            if random.random() > hit_rate:
                log.append({"round": rnd, "actor": actor, "skill": "普攻", "dmg": 0,
                            "miss": True, "crit": False, "a_hp": a_hp, "d_hp": d_hp})
                continue
            # 暴击判定
            is_crit = random.random() < crit_rate
            crit_mul = CRIT_MUL if is_crit else 1.0
            # 选用主攻：A 用技能，D 用普攻
            coef = skill_coef if actor == "A" else 1.0
            sname = skill_name if actor == "A" else "普攻"
            # 外功/内功取较高者
            outer_dmg = (attacker["outer_atk"] * coef) * (1 - _def_reduce(defender["outer_def"], def_lv))
            inner_dmg = (attacker["inner_atk"] * coef) * (1 - _def_reduce(defender["inner_def"], def_lv))
            raw = max(outer_dmg, inner_dmg) * crit_mul * random.uniform(0.95, 1.05)
            dmg = max(1, math.floor(raw))
            if actor == "A":
                d_hp -= dmg
                if is_crit and lifesteal:
                    a_hp = min(a_max, a_hp + int(dmg * lifesteal))
            else:
                a_hp -= dmg
            log.append({"round": rnd, "actor": actor, "skill": sname, "dmg": dmg,
                        "miss": False, "crit": is_crit, "a_hp": max(0, a_hp), "d_hp": max(0, d_hp)})
    win = a_hp > 0 and (d_hp <= 0 or a_hp >= d_hp)
    if a_hp <= 0 and d_hp <= 0:
        win = a_hp >= d_hp
    return {"win": win, "rounds": len(log), "log": log,
            "atk_hp_left": max(0, a_hp), "def_hp_left": max(0, d_hp)}


def make_enemy(stage_id: str, player_level: int) -> dict:
    """根据关卡生成敌人属性（按玩家等级 + 关卡倍率缩放）"""
    stage = PVE_STAGES.get(stage_id)
    mul = stage[2] if stage else 1.0
    base_lvl = max(1, player_level)
    attrs = {
        "strength": int(5 * mul + base_lvl * 0.3),
        "agility": int(4 * mul + base_lvl * 0.3),
        "physique": int(6 * mul + base_lvl * 0.4),
        "inner_power": int(3 * mul + base_lvl * 0.2),
    }
    return calc_stats(base_lvl, attrs, {}, {})


# ============================================================
# v0.2.5：WAP 原版资料补全（参考层，不改动现有战斗/属性/装备系统）
# 来源：用户提供的《QQ家园精武堂完整游戏系统资料》（2009.10-2015.06 WAP 文字武侠网游）
# 说明：当前模块采用 PC 版四维属性+8部位+5品质设定（v0.1.0 定版），
#       以下为 WAP 原版纯文字资料常量，供"资料图鉴"页面展示原版风貌，
#       不替换现有 exp_needed 公式 / 战斗 / 装备逻辑，零行为变更。
# ============================================================

# ---------- 等级称号表（WAP 原版）----------
LEVEL_TITLES = [
    (2, 9, "无名小卒/初入江湖"),
    (10, 19, "武林新丁"),
    (20, 29, "江湖小虾"),
    (30, 39, "后起之秀"),
    (40, 49, "武林高手"),
    (50, 59, "风尘奇侠"),
    (60, 69, "无双隐士"),
    (70, 79, "世外高人"),
    (80, 89, "江湖侠隐"),
    (90, 999, "无敌圣者"),
]

# ---------- 主流加点流派（WAP 原版：体/智/力/耐/敏 5 属性，每级 3 点，80 级以上 5 点）----------
ADD_POINT_SCHOOLS = [
    ("猛攻型", "4力1耐1敏 / 4力2耐", "高攻爆发"),
    ("高防型", "4耐2力 / 4耐1力1血", "持久战"),
    ("迅猛型", "3力3敏 / 4力2敏", "刺客先手"),
    ("平衡型", "2力2耐1敏1血", "新手推荐"),
]

# ---------- WAP 原版 1-87 级精确升级经验表 ----------
# 注：当前 exp_needed() 公式为平台统一曲线（120+80*level），此处保留原版精确值供资料页展示
EXP_TABLE_WAP = {
    1: 20, 2: 64, 3: 150, 4: 252, 5: 441, 6: 768, 7: 1120, 8: 1584, 9: 2280,
    10: 3168, 11: 4056, 12: 5292, 13: 6780, 14: 8738, 15: 10767, 16: 13080,
    17: 16104, 18: 19488, 19: 23348, 20: 27720, 21: 32520, 22: 37888, 23: 44505,
    24: 51100, 25: 59124, 26: 67894, 27: 77528, 28: 87978, 29: 100386, 30: 112840,
    31: 127380, 32: 143260, 33: 160308, 34: 178688, 35: 198454, 36: 221229,
    37: 245680, 38: 271715, 39: 299700, 40: 329719, 41: 361504, 42: 397440,
    43: 435840, 44: 476600, 45: 519792, 46: 565704, 47: 616950, 48: 671346,
    49: 728757, 50: 789264, 51: 853470, 52: 924381, 53: 998955, 54: 1077864,
    55: 1160656, 56: 1247732, 57: 1343062, 58: 1443555, 59: 1549032, 60: 1659625,
    61: 1779950, 62: 1906370, 63: 2038674, 64: 2177409, 65: 2321925, 66: 2478976,
    67: 2642913, 68: 2814346, 69: 2999412, 70: 3185663, 71: 3387285, 72: 3596594,
    73: 3822580, 74: 4050064, 75: 4294598, 76: 4698233, 77: 5122848, 78: 5587200,
    79: 6084232, 80: 6617040, 81: 7197410, 82: 8025220, 83: 8939656, 84: 9949100,
    85: 11032479, 86: 12224520, 87: 13517103,
}

# ---------- 战神宫 7 层完整数据（WAP 原版：场景/矿产/酒窖，早期仅开放前 3 层）----------
# 注：当前 WARSHRINE["max_floor"]=3 仅开放前 3 层，此处保留原版 7 层全貌供资料页展示
WARSHRINE_7FLOORS = [
    (1, "山下修身馆", "陨铜矿", "杂粮酿"),
    (2, "战神山前平台", "星铜矿", "三花酒"),
    (3, "战神山门", "陨铁矿", "竹叶酒"),
    (4, "战神大殿", "星铁矿", "玉泉酒"),
    (5, "战神回廊", "寒铁矿", "杏花香"),
    (6, "战神云台", "玄晶矿", "千里醉"),
    (7, "战神旋梯", "陨晶矿", "白坠春"),
]

# ---------- 四圣兽宠物系统（WAP 原版：最多 3 只，同时 1 只携带/附身，40 级开启附身）----------
PETS_FOUR_BEASTS = [
    {
        "key": "dragon", "name": "东方神龙", "main_attr": "气血",
        "evolution": "眼镜蛇→灵蛇→蛇妖→蛟龙→东方神龙",
        "skill": "凝血——最高恢复主人25%气血",
        "eval": "附身最强，'万血宠'是极品象征",
        "soul_sand": "龙砂(气+伤)",
    },
    {
        "key": "tiger", "name": "玄冥神虎", "main_attr": "速度",
        "evolution": "小虎→灵虎→虎王→斑斓圣虎→玄冥神虎",
        "skill": "瞬移——主人闪避+10%",
        "eval": "高速流首选",
        "soul_sand": "虎砂(速+伤)",
    },
    {
        "key": "phoenix", "name": "不死凤凰", "main_attr": "精气",
        "evolution": "战鹰→青鸾→凤凰→火凤凰→不死凤凰",
        "skill": "噬魔——禁止对方4回合用技能",
        "eval": "克制技能流",
        "soul_sand": "凤砂(精+伤)",
    },
    {
        "key": "turtle", "name": "神龟玄武", "main_attr": "防御",
        "evolution": "小海龟→灵龟→龟仙→龟圣→神龟玄武",
        "skill": "格挡——格挡一回合，最高减100%伤害",
        "eval": "携带最强(挡90%攻击)，附身差",
        "soul_sand": "龟砂(防+伤)",
    },
]
# 宠物等级阶段：野兽(1-19)→灵兽(20-39)→妖兽(40-59)→圣兽(60-79)→神兽(80-100)，满级100
PET_LEVEL_STAGES = [
    (1, 19, "野兽"), (20, 39, "灵兽"), (40, 59, "妖兽"),
    (60, 79, "圣兽"), (80, 100, "神兽"),
]
PET_MAX_LEVEL = 100
PET_ATTACH_MULT = {"气血": 2.0, "伤害": 0.5, "速度": 0.1, "防御": 1.3}  # 附身加成倍数

# 吞砂顿悟：星级上限 14 星，9-14 星升星加血表
PET_SOUL_SAND_MAX_STAR = 14
PET_STAR_HP_BONUS = {9: 1540, 10: 1610, 11: 1680, 12: 1750, 13: 1820}  # 9-13星升星加血
PET_SOUL_GUARD_TOTAL_HP = 6580  # 魂之守护：9升13星保护属性不变，共加血

# ---------- 命力祈福系统（WAP 原版后期：升级战神至尊套装）----------
BLESSING_LIFE_POWER = [
    ("念福佑", 500, "千年玄玉/灵玉/神玉(10-30级)"),
    ("烧福香", 700, "五行玄玉/灵玉/神玉(40-60级)"),
    ("写福愿", 1000, "寒髓玄玉/灵玉/神玉(70-90级)+精炼魔石"),
    ("挂福袋", 1200, "金焰玄玉/灵玉/神玉(100-120级)+精炼灵石"),
    ("拜福神", 1500, "雷火玄玉/灵玉(130-140级)+精炼圣石"),
]

# ---------- 武魂段位系统（WAP 原版：武林大会获胜获武魂，累计提升段位）----------
WUHUN_RANK_SYSTEM = {
    "source": "武林大会获胜获得",
    "usage": "累计武魂提升段位，是精武宝库买图谱的前置",
    "shop": "精武宝库：段位达标可买护甲/头盔/护腕/靴子高级图谱",
    "fragment": "武魂碎片：增加段位的道具",
}

# ---------- 帮派心法（WAP 原版：5 种，1-10 级，每级等效对应数量潜能点）----------
# 心法/属性/1级(技能点/帮贡/=潜能)
GUILD_XINFA = [
    ("强身", "力量", "2000技能点/10帮贡/=1潜能"),
    ("凝气", "气血", "同上递增"),
    ("易筋", "防御", "同上递增"),
    ("洗髓", "精气", "同上递增"),
    ("轻身", "速度", "同上递增"),
]
GUILD_XINFA_MAX_LEVEL = 10
GUILD_XINFA_LEVEL_COST = {  # 等级→(技能点, 帮贡, =潜能数)
    1: (2000, 10, 1), 2: (2500, 20, 2), 5: (4000, 50, 5), 10: (6500, 100, 10),
}

# ---------- WAP 原版锻造配方（5 部位 3 等级，图谱+模具+材料）----------
FORGE_RECIPES_WAP = [
    ("松纹剑", "武器", 30, "松纹剑图(150元宝)+剑模(50元宝)+精铁×3"),
    ("锋灵剑", "武器", 40, "锋灵剑图+剑模+精钢×3"),
    ("流光剑", "武器", 50, "流光剑图(200元宝)+剑模(100元宝)+寒铁石×3"),
    ("耀瞳华服", "衣服", 30, "华服图+五等棉布+丝麻线×3"),
    ("幽冥冷衫", "衣服", 40, "冷衫图+四等棉布+竹丝线×3"),
    ("沧月薄衣", "衣服", 50, "薄衣图+三等棉布+尼龙线×3"),
    ("疾影闪巾", "帽子", 30, "闪巾图+棉布+丝线×3"),
    ("白鳞发带", "帽子", 40, "发带图+棉布+丝线×3"),
    ("麒麟冠", "帽子", 50, "麒麟冠图+棉布+丝线×3"),
    ("嵌甲靴", "靴子", 30, "靴图+皮革+线×3"),
    ("鹿皮靴", "靴子", 40, "靴图+鹿皮+线×3"),
    ("猛虎靴", "靴子", 50, "靴图+虎皮+线×3"),
    ("诸葛之魂", "项链", 30, "项链图+珠玉+线×3"),
    ("翡翠项链", "项链", 40, "项链图+翡翠+线×3"),
    ("飞龙腰带", "项链", 50, "腰带图+飞龙鳞+线×3"),
]

# ---------- 体力系统（WAP 原版）----------
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

# ---------- 武林大会规则（WAP 原版：全服淘汰赛）----------
WULIN_DA_HUI = {
    "open_level": 10,
    "cost_stamina": 20,        # 不返还
    "divisions": ["初级(1-29)", "中级(30-49)", "高级(50+)"],
    "schedule": "每天报名，次日凌晨比赛",
    "reward": "G币+武魂，胜场越多奖励越丰",
    "titles": ["精武王", "亚军", "四强", "八强"],
}

# ---------- 四货币体系（WAP 原版）----------
CURRENCIES_WAP = [
    ("G币", "免费", "家园分财宝/打工/比武/Q币返利", "白装、基础道具、入帮"),
    ("元宝", "收费", "充值卡/Q币(1元≈100元宝)", "图谱、剑模、强化符、加成卡、大力丸、会旗、喇叭"),
    ("银票", "交易", "充值卡、帮战奖励、元宝兑换", "交易大厅买玩家装备(≥40级可交易)"),
    ("帮贡", "帮派", "捐矿石、基金券、活动", "学心法、用香炉/古树"),
]

# ---------- 15 技能推荐组合（WAP 原版：最多学 11 个含默认）----------
SKILL_RECOMMENDATIONS = [
    ("通用", "妙手回春+三清缚影+人剑合一+潇湘剑雨+神清气朗"),
    ("猛攻", "全攻击+武神附体+三清+天罗+斗转"),
    ("高防", "剑影+潇湘+金钟+妙手等辅助"),
]
# 推荐核心技能标注
SKILL_CORE_PICKS = {
    "攻击": "潇湘剑雨(大招·可秒杀)",
    "辅助": "妙手回春(回血)",
    "特殊": "三清缚影(封印·不耗气)/天罗地网(控制·不耗气)/移形换影(可越级挑战高10级)",
}

# ---------- 经验获取途径（WAP 原版）----------
EXP_SOURCES_WAP = [
    ("练功房", "20体力/4小时", "基础经验，每分钟1技能点"),
    ("战神宫", "15体力/2小时", "20级开启，1层1.5倍，高层递增"),
    ("比武PK", "10体力/次", "胜利获经验+材料"),
    ("帮派古树", "帮贡", "每天1次免费"),
    ("加成卡", "元宝", "修炼经验加倍"),
]

# ---------- 装备强化要点（WAP 原版：上限 50 级，耐久 500 次）----------
EQUIP_STRENGTHEN_WAP = {
    "max_level": 50,
    "durability": 500,          # 每次比武扣 1 点，精石修复
    "fail_penalty": "装备不消失，但附加属性清零",
    "full_stats_ref": "攻+16、速+4、精+105、气+120、防+8、属性+4%",
    "tips": "凌晨成功率高；1-5级普通符，5-10级高级符，10级以上每天1-2次",
}

# ---------- 帮派场景建筑（WAP 原版）----------
GUILD_BUILDINGS = [
    ("闻香炉/战旗", "回体力，每天3次（首次免费）"),
    ("温泉/古树", "每天1次免费经验，互动加声望"),
    ("矿洞", "每人每天采2次，矿石用于帮派升级"),
    ("书院", "学帮派技能/心法"),
    ("工坊", "帮主升级建筑"),
    ("聚义厅", "帮派管理"),
]

# ---------- 帮派加入/创建条件（WAP 原版）----------
GUILD_JOIN_CREATE = {
    "join_level": 20, "join_cost": "500G币", "join_contrib": 5,
    "create_level": 40, "create_cost": "会旗(元宝购买)",
    "war_signup": "帮主每周一", "member_signup": "每周三中午",
}


# ============================================================
# v0.2.6 主线任务链（武学成长线，来源：精武堂WAP原版玩法 + 用户资料）
# (sort, 名称, 解锁等级, 目标描述, 奖励)
# ============================================================
MAIN_QUESTS = [
    (1, "初入江湖", 1, "达到10级·称号武林新丁", "经验+100、银两+500"),
    (2, "修炼有成", 10, "练功房修炼5次", "经验+500、强化石×2"),
    (3, "技能初成", 15, "学习3个技能", "经验+800、银两+1000"),
    (4, "比武切磋", 20, "比武场获胜5次", "经验+1200、比武勋章×2"),
    (5, "战神宫", 25, "战神宫通关3层", "经验+3000、精炼石×1"),
    (6, "加入帮派", 30, "加入或创建帮派", "经验+2000、帮派令×1"),
    (7, "装备锻造", 40, "锻造1件装备", "经验+2500、玄铁精华×2"),
    (8, "武林大会", 50, "参加武林大会", "经验+5000、武魂碎片×1、称号：武林高手"),
]

