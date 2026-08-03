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
