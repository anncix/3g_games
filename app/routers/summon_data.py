"""召唤之王静态配置包（v0.0.8 全量配表定版）

来源说明：
- 战骨/魔魂/战灵槽位、魔魂魂力表、战场时间、联盟/师徒规则 = 公开资料对齐的结构信息
- 经验曲线/120图鉴/技能库/属性生成公式/捕捉公式/掉落表/日常任务 = 复刻定版（可上线）

本文件为纯静态常量，路由层直接 import 使用，不入库。
"""
from __future__ import annotations

import random

# ============================================================
# cfg_constants 常量与枚举
# ============================================================
MAX_LEVEL = 80
TIER_COUNT = 8                      # T1-T8 每段 10 级
RARITY_LIST = ["N", "R", "E", "L"]  # 普通/稀有/史诗/传说
RARITY_GROWTH = {"N": 1.00, "R": 1.08, "E": 1.16, "L": 1.25}
GROWTH_STAR_MUL = {1: 1.00, 2: 1.06, 3: 1.12, 4: 1.18, 5: 1.25}
BATTLE_TURN_ORDER = "SPD_DESC"      # 按速度降序行动
RACE_LIST = ["水", "兽", "虫", "羽", "龙", "亡灵"]
# 环形克制：水>龙>羽>虫>兽>亡灵>水
RACE_COUNTER = {"水": "龙", "龙": "羽", "羽": "虫", "虫": "兽", "兽": "亡灵", "亡灵": "水"}
RACE_BONUS_ADV = 0.12               # 克制方伤害 +12%
RACE_BONUS_DISADV = -0.10           # 被克方伤害 -10%
TEAM_SIZE_DEFAULT = 3
TEAM_SIZE_UNLOCK_4 = 60             # Lv60 解锁第 4 出战位（复刻定版）
PET_SKILL_SLOTS = 4                 # 每只宠最大技能槽
PET_SKILL_SLOT_UNLOCK = {1: 1, 2: 1, 3: 10, 4: 30}  # 槽位 → 宠物等级
PET_STORAGE_BASE = 50
PET_STORAGE_ADD_PER_10LVL = 10

# 战斗判定基础值
CRIT_BASE = 0.05
CRIT_DMG = 1.50
HIT_BASE = 0.95
DODGE_BASE = 0.05
RACE_COEF_ADV = 1.12
RACE_COEF_DISADV = 0.90
RACE_COEF_NEUTRAL = 1.00

# 活力
ENERGY_CAP = 120
ENERGY_REGEN_PER_MIN = 0.2          # 每 5 分钟 +1
FRIEND_REFILL_AMOUNT = 10
FRIEND_REFILL_DAILY_CAP = 5
MENTOR_REFILL_AMOUNT = 40           # 师徒互灌 4 倍
MENTOR_REFILL_DAILY_CAP = 3
COST_STAGE_NORMAL = 2
COST_STAGE_ELITE = 4
COST_DUNGEON = 6
COST_ARENA = 2
COST_BATTLEFIELD = 0                # 战场用结算场次限制

# 每日上限（cfg_daily_limits）
DAILY_LIMITS = {
    "trial_each": 5,
    "tongtian_floor": 20,
    "spirit_tower_floor": 15,
    "arena_free": 10,
    "battlefield_settle": 5,
    "boss": 3,
    "capture": 60,
}

# 段位解锁等级（T1-T8 每 10 级一段）
TIER_UNLOCK_LEVEL = {f"T{i}": (i - 1) * 10 + 1 for i in range(1, 9)}


# ============================================================
# cfg_level_xp（1–80 经验表，方案A）
# 公式：need(L)=120+80*L
# ============================================================
def exp_needed(level: int) -> int:
    """L→L+1 所需经验"""
    if level >= MAX_LEVEL:
        return 0
    return 120 + 80 * level


def exp_cumulative(level: int) -> int:
    """到达 Lv L 的累计经验：cum(L)=40L²+80L-120"""
    if level <= 1:
        return 0
    return 40 * level * level + 80 * level - 120


LEVEL_UNLOCKS = {
    1: "世界地图/捕捉/幻兽列表/商城/背包",
    10: "擂台 / 战骨入口",
    20: "T2 段位（厚甲龟/采矿猴/吞岩兽）",
    30: "魔魂系统（3 槽起始，每 10 级 +1）",
    35: "战灵系统 / 战灵塔",
    40: "战场分线 / 师徒系统 / T4 段位",
    60: "第 4 出战位",
}


# ============================================================
# cfg_items 道具与货币（货币存 SummonState，道具走平台物品字典）
# ============================================================
CURRENCIES = {
    "CUR_COIN": ("铜钱", "基础货币"),
    "CUR_GEM": ("元宝", "高阶货币"),
    "CUR_ENERGY": ("活力", "体力"),
    "CUR_PRESTIGE": ("声望", "PVP 荣誉"),
    "CUR_ARENA": ("擂台币", "擂台代币"),
    "CUR_BF": ("战场币", "战场代币"),
    "CUR_GUILD": ("贡献", "联盟资源"),
    "CUR_MENTOR": ("桃李值", "师徒资源"),
}

# 平台物品字典 key（seed 注册用）：id → (name, type, desc, base_price)
ITEMS = {
    "IT_BALL_N": ("普通捕捉球", "consumable", "捕捉倍率x1.0", 80),
    "IT_BALL_S": ("强力捕捉球", "consumable", "捕捉倍率x1.5", 300),
    "IT_BALL_U": ("超级捕捉球", "consumable", "捕捉倍率x2.2", 900),
    "IT_STONE": ("灵石", "material", "战骨强化材料", 250),
    "IT_SPIRIT_KEY": ("战灵钥匙", "consumable", "战灵开孔", 30),
    "IT_SOUL_POWDER_1": ("魂粉(黄)", "material", "魂力材料", 100),
    "IT_SOUL_POWDER_2": ("魂粉(玄)", "material", "魂力材料", 300),
    "IT_SOUL_POWDER_3": ("魂粉(地)", "material", "魂力材料", 800),
    "IT_SOUL_POWDER_4": ("魂粉(天)", "material", "魂力材料", 2100),
    "IT_REBIRTH": ("重生丹", "consumable", "重生幻兽", 120),
    "IT_REBIRTH_S": ("重生丹碎片", "material", "合成重生丹", 40),
    "IT_SOUL_CHARM": ("追魂法宝", "consumable", "高级猎魂", 100),
    "IT_SOUL_BOX_G": ("地魂宝箱", "box", "开地魂材料", 200),
    "IT_SOUL_BOX_T": ("天魂宝箱", "box", "开天魂材料", 500),
    "IT_SPIRIT_DUST": ("灵力", "material", "战灵洗炼材料", 50),
    "IT_BURN_CRYSTAL": ("焚火晶", "material", "通天塔产出/联盟捐献", 60),
    "IT_GOLD_BAG": ("金袋", "material", "联盟捐献", 100),
    "IT_INNER_PILL": ("内丹", "material", "联盟捐献", 100),
    "BOX_KILL": ("杀戮礼包", "box", "战场击杀奖励", 80),
    "BOX_ARENA": ("擂台宝箱", "box", "擂台奖励", 60),
    "BOX_BF": ("战场宝箱", "box", "战场奖励", 70),
}


# ============================================================
# cfg_shop 商城/兑换（shop, slot, item_id, price_currency, price_amount, limit_daily, limit_weekly, notes）
# ============================================================
SHOP = [
    ("shop_general", 1, "IT_BALL_N", "coins", 80, 30, 0, "普通球"),
    ("shop_general", 2, "IT_BALL_S", "coins", 300, 20, 0, "强力球"),
    ("shop_general", 3, "IT_BALL_U", "coins", 900, 10, 0, "超级球"),
    ("shop_general", 4, "IT_STONE", "coins", 500, 20, 0, "灵石"),
    ("shop_general", 5, "IT_SPIRIT_KEY", "arena_coin", 80, 3, 0, "钥匙（用擂台币换）"),
    ("shop_general", 6, "IT_SOUL_POWDER_1", "coins", 200, 20, 0, "黄魂粉"),
    ("shop_general", 7, "IT_SOUL_POWDER_2", "coins", 600, 15, 0, "玄魂粉"),
    ("shop_general", 8, "IT_SOUL_POWDER_3", "coins", 1600, 10, 0, "地魂粉"),
    ("shop_general", 9, "IT_SOUL_POWDER_4", "coins", 4200, 5, 0, "天魂粉"),
    ("shop_cash", 1, "IT_SOUL_CHARM", "gems", 100, 0, 0, "追魂法宝"),
    ("shop_cash", 2, "IT_REBIRTH", "gems", 120, 1, 0, "重生丹"),
    ("shop_cash", 3, "IT_SPIRIT_KEY", "gems", 30, 5, 0, "战灵钥匙"),
    ("shop_arena", 1, "IT_STONE", "arena_coin", 20, 30, 0, "擂台换灵石"),
    ("shop_arena", 2, "IT_SPIRIT_KEY", "arena_coin", 80, 3, 0, "擂台换钥匙"),
    ("shop_arena", 3, "IT_SOUL_BOX_G", "arena_coin", 120, 2, 0, "擂台换地魂箱"),
    ("shop_arena", 4, "BOX_ARENA", "arena_coin", 60, 5, 0, "擂台换擂台箱"),
    ("shop_bf", 1, "IT_SOUL_POWDER_3", "bf_coin", 25, 20, 0, "战场换地魂粉"),
    ("shop_bf", 2, "IT_SOUL_POWDER_4", "bf_coin", 60, 10, 0, "战场换天魂粉"),
    ("shop_bf", 3, "IT_SPIRIT_DUST", "bf_coin", 15, 50, 0, "战场换灵力"),
    ("shop_bf", 4, "BOX_BF", "bf_coin", 40, 5, 0, "战场换战场箱"),
    ("shop_guild", 1, "IT_STONE", "guild", 5, 50, 0, "联盟换灵石"),
    ("shop_guild", 2, "IT_BALL_S", "guild", 4, 20, 0, "联盟换强力球"),
    ("shop_guild", 3, "IT_SOUL_CHARM", "guild", 60, 1, 0, "联盟换追魂法宝"),
    ("shop_mentor", 1, "IT_REBIRTH_S", "mentor", 10, 30, 0, "桃李换重生碎片"),
    ("shop_mentor", 2, "IT_SOUL_CHARM", "mentor", 80, 1, 0, "桃李换追魂法宝"),
    ("shop_mentor", 3, "IT_SPIRIT_KEY", "mentor", 25, 2, 0, "桃李换钥匙"),
]

SHOP_NAMES = {
    "shop_general": "通用商店",
    "shop_cash": "元宝商店",
    "shop_arena": "擂台兑换",
    "shop_bf": "战场兑换",
    "shop_guild": "联盟兑换",
    "shop_mentor": "师徒兑换",
}

# 货币字段名映射
CURRENCY_FIELD = {
    "coins": ("coins", "铜钱"),
    "gems": ("gems", "元宝"),
    "prestige": ("prestige", "声望"),
    "arena_coin": ("arena_coin", "擂台币"),
    "bf_coin": ("bf_coin", "战场币"),
    "guild": ("guild_coin", "贡献"),
    "mentor": ("mentor_coin", "桃李值"),
}


# ============================================================
# cfg_skill_base（60 基础技能，rank 规则生成 180 技能）
# ============================================================
SKILL_RANK = {1: (1.00, 0.00, 0), 2: (1.35, 0.05, 0), 3: (1.75, 0.10, 1)}
# skill_id → (name, type, school, coef_or_value, cooldown, notes)
SKILLS = {
    "SK_001": ("利爪斩", "active", "PHY", 1.10, 1, "单体物伤"),
    "SK_002": ("破甲击", "active", "PHY", 0.95, 2, "降DEF_PHY"),
    "SK_003": ("撕裂", "active", "PHY", 0.90, 2, "流血2回合"),
    "SK_004": ("连环突袭", "active", "PHY", 0.65, 3, "随机2-3段"),
    "SK_005": ("斩杀线", "passive", "PHY", 0.20, 0, "目标低血增伤"),
    "SK_006": ("反击姿态", "passive", "TANK", 0.18, 0, "受击反击概率"),
    "SK_007": ("坚甲", "passive", "TANK", 0.12, 0, "DEF_PHY%提升"),
    "SK_008": ("法抗", "passive", "TANK", 0.12, 0, "DEF_MAG%提升"),
    "SK_009": ("护盾术", "active", "TANK", 0.18, 3, "按HP生成盾"),
    "SK_010": ("嘲讽", "active", "TANK", 0, 4, "强制目标1回合"),
    "SK_011": ("潮汐箭", "active", "MAG", 1.10, 1, "单体法伤"),
    "SK_012": ("冰封", "active", "CTRL", 0, 4, "冻结1回合"),
    "SK_013": ("寒潮", "active", "MAG", 0.85, 3, "群体法伤"),
    "SK_014": ("法穿印记", "active", "MAG", 0, 3, "降DEF_MAG"),
    "SK_015": ("灼烧", "active", "MAG", 0.70, 2, "灼烧2回合"),
    "SK_016": ("雷击", "active", "CTRL", 0.95, 2, "小概率麻痹"),
    "SK_017": ("加速", "active", "CTRL", 0, 3, "己方速度提升"),
    "SK_018": ("减速", "active", "CTRL", 0, 2, "敌方速度下降"),
    "SK_019": ("沉默咒", "active", "CTRL", 0, 4, "沉默1回合"),
    "SK_020": ("驱散", "active", "CTRL", 0, 4, "驱散1个减益"),
    "SK_021": ("吸血咒", "active", "CURSE", 0.80, 2, "造成伤害并回血"),
    "SK_022": ("诅咒", "active", "CURSE", 0, 3, "受伤加深"),
    "SK_023": ("中毒", "active", "CURSE", 0.65, 2, "毒2回合"),
    "SK_024": ("腐蚀", "active", "CURSE", 0, 3, "降双防"),
    "SK_025": ("复生印记", "passive", "CURSE", 0.20, 0, "濒死免死一次"),
    "SK_026": ("先手压制", "passive", "CTRL", 0.10, 0, "首回合增伤"),
    "SK_027": ("暴击训练", "passive", "PHY", 0.10, 0, "暴击%提升"),
    "SK_028": ("命中校准", "passive", "CTRL", 0.10, 0, "命中%提升"),
    "SK_029": ("闪避身法", "passive", "CTRL", 0.10, 0, "闪避%提升"),
    "SK_030": ("抗暴甲", "passive", "TANK", 0.10, 0, "抗暴%提升"),
    "SK_031": ("水盾", "active", "TANK", 0.16, 3, "水族专属护盾"),
    "SK_032": ("冻结潮", "active", "CTRL", 0, 5, "群体小概率冻结"),
    "SK_033": ("深海回响", "passive", "MAG", 0.12, 0, "法伤增幅"),
    "SK_034": ("兽怒", "active", "PHY", 0, 4, "自增伤+自减防"),
    "SK_035": ("冲撞", "active", "PHY", 1.05, 2, "附带眩晕概率"),
    "SK_036": ("野性再生", "active", "TANK", 0.18, 4, "按HP回血"),
    "SK_037": ("虫群", "active", "CURSE", 0.55, 3, "多段DOT"),
    "SK_038": ("毒扩散", "passive", "CURSE", 0.25, 0, "毒可扩散"),
    "SK_039": ("网缚", "active", "CTRL", 0, 4, "定身1回合"),
    "SK_040": ("风刃", "active", "PHY", 1.00, 1, "羽族物伤"),
    "SK_041": ("追击", "passive", "PHY", 0.18, 0, "击杀后追击"),
    "SK_042": ("雷翼麻痹", "active", "CTRL", 0, 4, "麻痹1回合"),
    "SK_043": ("龙威", "active", "CTRL", 0, 4, "群体降攻"),
    "SK_044": ("龙炎吐息", "active", "MAG", 0.90, 3, "群体灼烧"),
    "SK_045": ("霜息", "active", "CTRL", 0, 4, "单体冻结"),
    "SK_046": ("亡灵虹吸", "active", "CURSE", 0.75, 2, "吸血+降速"),
    "SK_047": ("冥火", "active", "MAG", 1.05, 2, "法伤附灼烧"),
    "SK_048": ("群体诅咒", "active", "CURSE", 0, 5, "群体受伤加深"),
    "SK_049": ("净化之风", "active", "CTRL", 0, 4, "驱散1个增益"),
    "SK_050": ("护主", "passive", "TANK", 0.15, 0, "为队友分摊伤害"),
    "SK_051": ("破魔", "active", "MAG", 1.00, 2, "对护盾增伤"),
    "SK_052": ("反伤结界", "active", "TANK", 0, 5, "反伤2回合"),
    "SK_053": ("血祭", "active", "CURSE", 1.30, 5, "自损换高伤"),
    "SK_054": ("怒火连击", "active", "PHY", 0.60, 4, "三段随机"),
    "SK_055": ("风暴降临", "active", "MAG", 0.80, 4, "群体+降速"),
    "SK_056": ("绝对零度", "active", "CTRL", 0, 6, "冻结+降防"),
    "SK_057": ("天魔降伏", "passive", "PHY", 120, 0, "对应天魂模板"),
    "SK_058": ("守护之魂", "passive", "TANK", 150, 0, "对应天魂模板"),
    "SK_059": ("蹑影逐日", "passive", "CTRL", 8, 0, "对应天魂模板"),
    "SK_060": ("极寿无疆", "passive", "TANK", 0.064, 0, "HP%提升"),
}


def skill_info(skill_id: str, rank: int = 1) -> dict:
    """生成指定阶的技能信息（rank 1-3）"""
    if skill_id not in SKILLS:
        return {"skill_id": skill_id, "name": "未知", "type": "passive",
                "school": "PHY", "coef": 1.0, "cooldown": 0, "notes": "",
                "rank": rank, "proc_add": 0, "ctrl_bonus": 0}
    name, stype, school, coef, cd, notes = SKILLS[skill_id]
    rank_mul, proc_add, ctrl_bonus = SKILL_RANK.get(rank, (1.00, 0.00, 0))
    return {
        "skill_id": skill_id, "name": name, "type": stype, "school": school,
        "coef": round(coef * rank_mul, 3), "cooldown": cd, "notes": notes,
        "rank": rank, "proc_add": proc_add, "ctrl_bonus": ctrl_bonus,
    }


# 技能学习/替换/升阶成本
SKILL_LEARN_COST_COIN = 600
SKILL_REPLACE_COST_COIN = 300
SKILL_RANKUP_COST_COIN = 800
SKILL_RANKUP_NEED_SHARDS = {2: 12, 3: 30}


# ============================================================
# cfg_skill_pools 技能池内容表（PM_* 主池 / PR_* 稀有池）
# ============================================================
SKILL_POOLS = {
    "PM_W_TANK": ["SK_007", "SK_008", "SK_009", "SK_010", "SK_031", "SK_050", "SK_052", "SK_018"],
    "PM_W_MAG": ["SK_011", "SK_013", "SK_014", "SK_012", "SK_032", "SK_033", "SK_017", "SK_020"],
    "PM_B_PHY": ["SK_001", "SK_002", "SK_003", "SK_034", "SK_035", "SK_005", "SK_027", "SK_041"],
    "PM_B_TANK": ["SK_006", "SK_007", "SK_036", "SK_010", "SK_050", "SK_052", "SK_018", "SK_030"],
    "PM_I_CURSE": ["SK_023", "SK_024", "SK_037", "SK_038", "SK_021", "SK_022", "SK_018", "SK_019"],
    "PM_I_CTRL": ["SK_039", "SK_018", "SK_019", "SK_016", "SK_028", "SK_020", "SK_017", "SK_026"],
    "PM_F_PHY": ["SK_040", "SK_041", "SK_004", "SK_027", "SK_017", "SK_018", "SK_029", "SK_026"],
    "PM_F_CTRL": ["SK_017", "SK_018", "SK_042", "SK_016", "SK_019", "SK_028", "SK_029", "SK_026"],
    "PM_D_MAG": ["SK_044", "SK_015", "SK_051", "SK_043", "SK_017", "SK_014", "SK_011", "SK_020"],
    "PM_D_PHY": ["SK_001", "SK_002", "SK_043", "SK_005", "SK_041", "SK_034", "SK_027", "SK_030"],
    "PM_U_CURSE": ["SK_046", "SK_047", "SK_048", "SK_021", "SK_022", "SK_019", "SK_024", "SK_025"],
    "PM_U_TANK": ["SK_007", "SK_008", "SK_052", "SK_050", "SK_030", "SK_019", "SK_020", "SK_025"],
    "PR_OFFENSE": ["SK_004", "SK_054", "SK_053", "SK_051", "SK_056"],
    "PR_CONTROL": ["SK_056", "SK_012", "SK_019", "SK_049", "SK_032"],
    "PR_SURVIVE": ["SK_052", "SK_009", "SK_036", "SK_050", "SK_060"],
    "PR_CURSE": ["SK_048", "SK_053", "SK_024", "SK_025", "SK_046"],
    "PR_DRAGON": ["SK_043", "SK_044", "SK_045", "SK_047", "SK_056"],
    "PR_SOUL": ["SK_057", "SK_058", "SK_059", "SK_060", "SK_033"],
}


# ============================================================
# cfg_pet_skill_pool 120 只技能池映射
# species_id → (signature_skill, pool_main, pool_rare)
# ============================================================
PET_SKILL_POOL = {
    "SZW_0001": ("SK_018", "PM_W_MAG", "PR_CONTROL"),
    "SZW_0002": ("SK_031", "PM_W_TANK", "PR_SURVIVE"),
    "SZW_0003": ("SK_011", "PM_W_MAG", "PR_CONTROL"),
    "SZW_0004": ("SK_003", "PM_B_PHY", "PR_OFFENSE"),
    "SZW_0005": ("SK_007", "PM_B_TANK", "PR_SURVIVE"),
    "SZW_0006": ("SK_004", "PM_B_PHY", "PR_OFFENSE"),
    "SZW_0007": ("SK_023", "PM_I_CURSE", "PR_CURSE"),
    "SZW_0008": ("SK_007", "PM_I_CURSE", "PR_SURVIVE"),
    "SZW_0009": ("SK_028", "PM_I_CTRL", "PR_CONTROL"),
    "SZW_0010": ("SK_017", "PM_F_CTRL", "PR_CONTROL"),
    "SZW_0011": ("SK_040", "PM_F_PHY", "PR_OFFENSE"),
    "SZW_0012": ("SK_042", "PM_F_CTRL", "PR_CONTROL"),
    "SZW_0013": ("SK_015", "PM_D_MAG", "PR_DRAGON"),
    "SZW_0014": ("SK_021", "PM_U_CURSE", "PR_CURSE"),
    "SZW_0015": ("SK_025", "PM_U_CURSE", "PR_SOUL"),
    "SZW_0016": ("SK_007", "PM_W_TANK", "PR_SURVIVE"),
    "SZW_0017": ("SK_012", "PM_W_MAG", "PR_CONTROL"),
    "SZW_0018": ("SK_031", "PM_W_TANK", "PR_SURVIVE"),
    "SZW_0019": ("SK_001", "PM_B_PHY", "PR_OFFENSE"),
    "SZW_0020": ("SK_010", "PM_B_TANK", "PR_SURVIVE"),
    "SZW_0021": ("SK_002", "PM_B_PHY", "PR_OFFENSE"),
    "SZW_0022": ("SK_006", "PM_B_TANK", "PR_SURVIVE"),
    "SZW_0023": ("SK_023", "PM_I_CURSE", "PR_CURSE"),
    "SZW_0024": ("SK_008", "PM_I_CURSE", "PR_SURVIVE"),
    "SZW_0025": ("SK_021", "PM_I_CURSE", "PR_CURSE"),
    "SZW_0026": ("SK_017", "PM_F_CTRL", "PR_CONTROL"),
    "SZW_0027": ("SK_041", "PM_F_PHY", "PR_OFFENSE"),
    "SZW_0028": ("SK_016", "PM_F_CTRL", "PR_CONTROL"),
    "SZW_0029": ("SK_044", "PM_D_MAG", "PR_DRAGON"),
    "SZW_0030": ("SK_019", "PM_U_TANK", "PR_CONTROL"),
    "SZW_0031": ("SK_011", "PM_W_MAG", "PR_OFFENSE"),
    "SZW_0032": ("SK_031", "PM_W_TANK", "PR_SURVIVE"),
    "SZW_0033": ("SK_003", "PM_B_PHY", "PR_OFFENSE"),
    "SZW_0034": ("SK_010", "PM_B_TANK", "PR_SURVIVE"),
    "SZW_0035": ("SK_003", "PM_B_PHY", "PR_OFFENSE"),
    "SZW_0036": ("SK_003", "PM_B_PHY", "PR_OFFENSE"),
    "SZW_0037": ("SK_039", "PM_I_CTRL", "PR_CONTROL"),
    "SZW_0038": ("SK_023", "PM_I_CURSE", "PR_CURSE"),
    "SZW_0039": ("SK_023", "PM_I_CURSE", "PR_CURSE"),
    "SZW_0040": ("SK_042", "PM_F_CTRL", "PR_CONTROL"),
    "SZW_0041": ("SK_040", "PM_F_PHY", "PR_OFFENSE"),
    "SZW_0042": ("SK_040", "PM_F_PHY", "PR_OFFENSE"),
    "SZW_0043": ("SK_043", "PM_D_PHY", "PR_DRAGON"),
    "SZW_0044": ("SK_021", "PM_U_CURSE", "PR_CURSE"),
    "SZW_0045": ("SK_048", "PM_U_CURSE", "PR_SOUL"),
    "SZW_0046": ("SK_031", "PM_W_TANK", "PR_SURVIVE"),
    "SZW_0047": ("SK_031", "PM_W_TANK", "PR_SURVIVE"),
    "SZW_0048": ("SK_011", "PM_W_MAG", "PR_OFFENSE"),
    "SZW_0049": ("SK_003", "PM_B_PHY", "PR_OFFENSE"),
    "SZW_0050": ("SK_010", "PM_B_TANK", "PR_SURVIVE"),
    "SZW_0051": ("SK_003", "PM_B_PHY", "PR_OFFENSE"),
    "SZW_0052": ("SK_002", "PM_I_CURSE", "PR_OFFENSE"),
    "SZW_0053": ("SK_023", "PM_I_CURSE", "PR_CURSE"),
    "SZW_0054": ("SK_039", "PM_I_CTRL", "PR_CONTROL"),
    "SZW_0055": ("SK_042", "PM_F_CTRL", "PR_CONTROL"),
    "SZW_0056": ("SK_040", "PM_F_PHY", "PR_OFFENSE"),
    "SZW_0057": ("SK_042", "PM_F_CTRL", "PR_CONTROL"),
    "SZW_0058": ("SK_044", "PM_D_MAG", "PR_DRAGON"),
    "SZW_0059": ("SK_052", "PM_U_TANK", "PR_SURVIVE"),
    "SZW_0060": ("SK_052", "PM_U_TANK", "PR_SOUL"),
    "SZW_0061": ("SK_011", "PM_W_MAG", "PR_OFFENSE"),
    "SZW_0062": ("SK_031", "PM_W_TANK", "PR_SURVIVE"),
    "SZW_0063": ("SK_032", "PM_W_MAG", "PR_CONTROL"),
    "SZW_0064": ("SK_003", "PM_B_PHY", "PR_OFFENSE"),
    "SZW_0065": ("SK_010", "PM_B_TANK", "PR_SURVIVE"),
    "SZW_0066": ("SK_023", "PM_I_CURSE", "PR_CURSE"),
    "SZW_0067": ("SK_039", "PM_I_CTRL", "PR_CONTROL"),
    "SZW_0068": ("SK_023", "PM_I_CURSE", "PR_CURSE"),
    "SZW_0069": ("SK_042", "PM_F_CTRL", "PR_CONTROL"),
    "SZW_0070": ("SK_040", "PM_F_PHY", "PR_OFFENSE"),
    "SZW_0071": ("SK_040", "PM_F_PHY", "PR_OFFENSE"),
    "SZW_0072": ("SK_044", "PM_D_MAG", "PR_DRAGON"),
    "SZW_0073": ("SK_043", "PM_D_PHY", "PR_DRAGON"),
    "SZW_0074": ("SK_019", "PM_U_TANK", "PR_CONTROL"),
    "SZW_0075": ("SK_048", "PM_U_CURSE", "PR_SOUL"),
    "SZW_0076": ("SK_031", "PM_W_TANK", "PR_SURVIVE"),
    "SZW_0077": ("SK_011", "PM_W_MAG", "PR_OFFENSE"),
    "SZW_0078": ("SK_011", "PM_W_MAG", "PR_OFFENSE"),
    "SZW_0079": ("SK_003", "PM_B_PHY", "PR_OFFENSE"),
    "SZW_0080": ("SK_010", "PM_B_TANK", "PR_SURVIVE"),
    "SZW_0081": ("SK_003", "PM_B_PHY", "PR_OFFENSE"),
    "SZW_0082": ("SK_023", "PM_I_CURSE", "PR_CURSE"),
    "SZW_0083": ("SK_002", "PM_I_CURSE", "PR_OFFENSE"),
    "SZW_0084": ("SK_039", "PM_I_CTRL", "PR_CONTROL"),
    "SZW_0085": ("SK_042", "PM_F_CTRL", "PR_CONTROL"),
    "SZW_0086": ("SK_040", "PM_F_PHY", "PR_OFFENSE"),
    "SZW_0087": ("SK_042", "PM_F_CTRL", "PR_CONTROL"),
    "SZW_0088": ("SK_044", "PM_D_MAG", "PR_DRAGON"),
    "SZW_0089": ("SK_043", "PM_D_PHY", "PR_SOUL"),
    "SZW_0090": ("SK_052", "PM_U_TANK", "PR_SURVIVE"),
    "SZW_0091": ("SK_031", "PM_W_TANK", "PR_SURVIVE"),
    "SZW_0092": ("SK_011", "PM_W_MAG", "PR_OFFENSE"),
    "SZW_0093": ("SK_031", "PM_W_TANK", "PR_SOUL"),
    "SZW_0094": ("SK_003", "PM_B_PHY", "PR_OFFENSE"),
    "SZW_0095": ("SK_010", "PM_B_TANK", "PR_SURVIVE"),
    "SZW_0096": ("SK_003", "PM_B_PHY", "PR_OFFENSE"),
    "SZW_0097": ("SK_023", "PM_I_CURSE", "PR_CURSE"),
    "SZW_0098": ("SK_039", "PM_I_CTRL", "PR_CONTROL"),
    "SZW_0099": ("SK_023", "PM_I_CURSE", "PR_CURSE"),
    "SZW_0100": ("SK_042", "PM_F_CTRL", "PR_CONTROL"),
    "SZW_0101": ("SK_040", "PM_F_PHY", "PR_OFFENSE"),
    "SZW_0102": ("SK_042", "PM_F_CTRL", "PR_CONTROL"),
    "SZW_0103": ("SK_043", "PM_D_PHY", "PR_DRAGON"),
    "SZW_0104": ("SK_044", "PM_D_MAG", "PR_DRAGON"),
    "SZW_0105": ("SK_052", "PM_U_TANK", "PR_SURVIVE"),
    "SZW_0106": ("SK_031", "PM_W_TANK", "PR_SURVIVE"),
    "SZW_0107": ("SK_011", "PM_W_MAG", "PR_OFFENSE"),
    "SZW_0108": ("SK_032", "PM_W_MAG", "PR_CONTROL"),
    "SZW_0109": ("SK_003", "PM_B_PHY", "PR_OFFENSE"),
    "SZW_0110": ("SK_010", "PM_B_TANK", "PR_SURVIVE"),
    "SZW_0111": ("SK_023", "PM_I_CURSE", "PR_CURSE"),
    "SZW_0112": ("SK_039", "PM_I_CTRL", "PR_CONTROL"),
    "SZW_0113": ("SK_023", "PM_I_CURSE", "PR_CURSE"),
    "SZW_0114": ("SK_042", "PM_F_CTRL", "PR_CONTROL"),
    "SZW_0115": ("SK_040", "PM_F_PHY", "PR_OFFENSE"),
    "SZW_0116": ("SK_042", "PM_F_CTRL", "PR_CONTROL"),
    "SZW_0117": ("SK_043", "PM_D_PHY", "PR_DRAGON"),
    "SZW_0118": ("SK_044", "PM_D_MAG", "PR_DRAGON"),
    "SZW_0119": ("SK_043", "PM_D_PHY", "PR_SOUL"),
    "SZW_0120": ("SK_048", "PM_U_CURSE", "PR_SOUL"),
}


# ============================================================
# cfg_pet_species（120 图鉴）
# id → (name, race, tier, rarity, role, pool, signature_desc)
# ============================================================
PETS = {
    "SZW_0001": ("潮芽鱼", "水", "T1", "N", "CTRL", "WC", "减速"),
    "SZW_0002": ("清泉龟", "水", "T1", "N", "TANK", "WC", "护盾"),
    "SZW_0003": ("泡泡鲛", "水", "T1", "R", "MAG", "WE", "法攻叠层"),
    "SZW_0004": ("岩牙狼", "兽", "T1", "N", "PHY", "WC", "流血"),
    "SZW_0005": ("角豚兽", "兽", "T1", "N", "TANK", "WC", "开场减伤"),
    "SZW_0006": ("砂爪猫", "兽", "T1", "R", "PHY", "WE", "连击"),
    "SZW_0007": ("毒针蚁", "虫", "T1", "N", "CURSE", "WC", "叠毒"),
    "SZW_0008": ("蛊壳虫", "虫", "T1", "N", "TANK", "WC", "抗性"),
    "SZW_0009": ("翳雾蛛", "虫", "T1", "R", "CTRL", "WE", "降命中"),
    "SZW_0010": ("风羽雀", "羽", "T1", "N", "CTRL", "WC", "加速"),
    "SZW_0011": ("雷翎隼", "羽", "T1", "N", "PHY", "WC", "暴击微增"),
    "SZW_0012": ("飘翼鸢", "羽", "T1", "R", "CTRL", "WE", "眩晕"),
    "SZW_0013": ("幼炎龙", "龙", "T1", "E", "MAG", "DG", "灼烧"),
    "SZW_0014": ("骨灯灵", "亡灵", "T1", "N", "CURSE", "WC", "吸血"),
    "SZW_0015": ("幽灯魇", "亡灵", "T1", "L", "CURSE", "BS", "复生"),
    "SZW_0016": ("冰鳞鲟", "水", "T2", "N", "TANK", "WC", "物防提升"),
    "SZW_0017": ("寒潮鳗", "水", "T2", "N", "MAG", "WC", "冰缓"),
    "SZW_0018": ("厚甲龟", "水", "T2", "E", "TANK", "WE", "护盾随血增"),
    "SZW_0019": ("赤鬃犬", "兽", "T2", "N", "PHY", "WC", "撕裂"),
    "SZW_0020": ("铜角牛", "兽", "T2", "N", "TANK", "WC", "嘲讽"),
    "SZW_0021": ("采矿猴", "兽", "T2", "R", "PHY", "WE", "破甲"),
    "SZW_0022": ("吞岩兽", "兽", "T2", "E", "TANK", "DG", "反击强化"),
    "SZW_0023": ("腐沼蝇", "虫", "T2", "N", "CURSE", "WC", "毒扩散"),
    "SZW_0024": ("巢铠甲", "虫", "T2", "N", "TANK", "WC", "减伤"),
    "SZW_0025": ("紫雾虫", "虫", "T2", "R", "CURSE", "WE", "毒吸联动"),
    "SZW_0026": ("翔风雀", "羽", "T2", "N", "CTRL", "WC", "速度提升"),
    "SZW_0027": ("穿云燕", "羽", "T2", "N", "PHY", "WC", "连击倾向"),
    "SZW_0028": ("风雷蝶", "羽", "T2", "R", "CTRL", "WE", "麻痹"),
    "SZW_0029": ("烬息龙", "龙", "T2", "R", "MAG", "WE", "灼烧爆发"),
    "SZW_0030": ("影缚魂", "亡灵", "T2", "L", "CTRL", "BS", "开场沉默"),
    "SZW_0031": ("渊潮鲛", "水", "T3", "N", "MAG", "WC", "冻结概率"),
    "SZW_0032": ("玄水螺", "水", "T3", "R", "TANK", "WE", "护盾反伤"),
    "SZW_0033": ("狂牙獾", "兽", "T3", "N", "PHY", "WC", "流血延长"),
    "SZW_0034": ("岩背熊", "兽", "T3", "N", "TANK", "WC", "物防壁垒"),
    "SZW_0035": ("赤爪豹", "兽", "T3", "R", "PHY", "WE", "连击+"),
    "SZW_0036": ("獠角豺", "兽", "T3", "N", "PHY", "WC", "破甲"),
    "SZW_0037": ("蛊雾蛛", "虫", "T3", "N", "CTRL", "WC", "降速"),
    "SZW_0038": ("噬心蠹", "虫", "T3", "N", "CURSE", "WC", "DOT叠层"),
    "SZW_0039": ("毒巢后", "虫", "T3", "R", "CURSE", "WE", "毒伤窗口"),
    "SZW_0040": ("断翼鸦", "羽", "T3", "N", "CTRL", "WC", "降命中"),
    "SZW_0041": ("雷隼骑", "羽", "T3", "R", "PHY", "WE", "先手暴击"),
    "SZW_0042": ("云刃鹫", "羽", "T3", "N", "PHY", "WC", "穿透"),
    "SZW_0043": ("苍焰幼龙", "龙", "T3", "E", "PHY", "DG", "威压降防"),
    "SZW_0044": ("冥骨犬", "亡灵", "T3", "R", "CURSE", "WE", "吸血流血"),
    "SZW_0045": ("咒墓王", "亡灵", "T3", "L", "CURSE", "BS", "诅咒回血"),
    "SZW_0046": ("海潮鲸", "水", "T4", "N", "TANK", "WC", "高血抗压"),
    "SZW_0047": ("冰壳蟹", "水", "T4", "R", "TANK", "WE", "双防提升"),
    "SZW_0048": ("海龙鱼", "水", "T4", "E", "MAG", "DG", "冰潮AOE"),
    "SZW_0049": ("砂暴獾", "兽", "T4", "N", "PHY", "WC", "暴击提升"),
    "SZW_0050": ("铁骨犀", "兽", "T4", "R", "TANK", "WE", "嘲讽减伤"),
    "SZW_0051": ("落魂兽", "兽", "T4", "E", "PHY", "DG", "斩杀增伤"),
    "SZW_0052": ("穿刺蝎", "虫", "T4", "N", "PHY", "WC", "破甲"),
    "SZW_0053": ("腐翳蜂", "虫", "T4", "N", "CURSE", "WC", "DOT扩散"),
    "SZW_0054": ("毒母蛛", "虫", "T4", "R", "CTRL", "WE", "网缚"),
    "SZW_0055": ("落日雕", "羽", "T4", "N", "CTRL", "WC", "速度爆发"),
    "SZW_0056": ("风刃鸢", "羽", "T4", "N", "PHY", "WC", "连击"),
    "SZW_0057": ("雷鸣隼", "羽", "T4", "R", "CTRL", "WE", "麻痹控制"),
    "SZW_0058": ("霜息龙", "龙", "T4", "R", "MAG", "WE", "冻结窗口"),
    "SZW_0059": ("冥甲尸", "亡灵", "T4", "N", "TANK", "WC", "抗性"),
    "SZW_0060": ("幽王骸", "亡灵", "T4", "L", "TANK", "BS", "回魂护盾"),
    "SZW_0061": ("深渊鲛", "水", "T5", "N", "MAG", "WC", "冰缓连锁"),
    "SZW_0062": ("潮汐螺皇", "水", "T5", "R", "TANK", "WE", "护盾强化"),
    "SZW_0063": ("玄海龙鳝", "水", "T5", "E", "CTRL", "DG", "冻结降速"),
    "SZW_0064": ("狂角狮", "兽", "T5", "N", "PHY", "WC", "斩击增伤"),
    "SZW_0065": ("岩背巨熊", "兽", "T5", "R", "TANK", "WE", "反伤"),
    "SZW_0066": ("群噬蠊", "虫", "T5", "N", "CURSE", "WC", "叠毒加速"),
    "SZW_0067": ("蛊巢将", "虫", "T5", "R", "CTRL", "WE", "降命中降速"),
    "SZW_0068": ("腐王蛛", "虫", "T5", "N", "CURSE", "WC", "吸血放大"),
    "SZW_0069": ("风雷鹰", "羽", "T5", "N", "CTRL", "WC", "先手优势"),
    "SZW_0070": ("云刃隼王", "羽", "T5", "R", "PHY", "WE", "追击"),
    "SZW_0071": ("飓翼鹫", "羽", "T5", "N", "PHY", "WC", "穿透"),
    "SZW_0072": ("苍炎龙", "龙", "T5", "N", "MAG", "WC", "灼烧"),
    "SZW_0073": ("星纹龙", "龙", "T5", "E", "PHY", "DG", "威压破防"),
    "SZW_0074": ("影咒僧", "亡灵", "T5", "N", "CTRL", "WC", "沉默"),
    "SZW_0075": ("冥渊王座", "亡灵", "T5", "L", "CURSE", "BS", "群诅咒"),
    "SZW_0076": ("寒渊鲸", "水", "T6", "N", "TANK", "WC", "高血护盾"),
    "SZW_0077": ("冰潮鲛王", "水", "T6", "R", "MAG", "WE", "冻结+"),
    "SZW_0078": ("玄潮龙鱼", "水", "T6", "E", "MAG", "DG", "法穿增益"),
    "SZW_0079": ("狂獠虎机", "兽", "T6", "N", "PHY", "WC", "暴击提升"),
    "SZW_0080": ("铁角巨犀", "兽", "T6", "R", "TANK", "WE", "嘲讽减伤"),
    "SZW_0081": ("霸爪王豹", "兽", "T6", "E", "PHY", "DG", "斩杀强化"),
    "SZW_0082": ("毒云蜂后", "虫", "T6", "N", "CURSE", "WC", "DOT扩散"),
    "SZW_0083": ("腐化螳", "虫", "T6", "R", "PHY", "WE", "破甲流血"),
    "SZW_0084": ("蛊皇", "虫", "T6", "N", "CTRL", "WC", "降速降防"),
    "SZW_0085": ("风暴隼", "羽", "T6", "N", "CTRL", "WC", "先手爆发"),
    "SZW_0086": ("雷翼鸢王", "羽", "T6", "R", "PHY", "WE", "连击追击"),
    "SZW_0087": ("天翔鹫", "羽", "T6", "N", "CTRL", "WC", "闪避提升"),
    "SZW_0088": ("烬星龙", "龙", "T6", "R", "MAG", "WE", "灼烧转爆"),
    "SZW_0089": ("冥炎龙裔", "龙", "T6", "L", "PHY", "BS", "威压灼烧"),
    "SZW_0090": ("骸骨将", "亡灵", "T6", "N", "TANK", "WC", "抗性"),
    "SZW_0091": ("玄冰螺皇", "水", "T7", "N", "TANK", "WC", "护盾增强"),
    "SZW_0092": ("深海龙鲛", "水", "T7", "R", "MAG", "WE", "冻结法穿"),
    "SZW_0093": ("潮汐霸主", "水", "T7", "L", "TANK", "BS", "群体护盾"),
    "SZW_0094": ("狂岩狮王", "兽", "T7", "N", "PHY", "WC", "暴击提升"),
    "SZW_0095": ("铁背蛮熊", "兽", "T7", "R", "TANK", "WE", "反伤强化"),
    "SZW_0096": ("兽神角斗", "兽", "T7", "E", "PHY", "DG", "破甲斩杀"),
    "SZW_0097": ("毒巢女皇", "虫", "T7", "N", "CURSE", "WC", "毒扩散"),
    "SZW_0098": ("蛊翼皇蜂", "虫", "T7", "R", "CTRL", "WE", "麻痹降命中"),
    "SZW_0099": ("腐渊蠹王", "虫", "T7", "E", "CURSE", "DG", "吸血放大"),
    "SZW_0100": ("风雷天隼", "羽", "T7", "N", "CTRL", "WC", "先手压制"),
    "SZW_0101": ("云裂鸢", "羽", "T7", "R", "PHY", "WE", "追击强化"),
    "SZW_0102": ("雷霆鹫王", "羽", "T7", "E", "CTRL", "DG", "群麻痹"),
    "SZW_0103": ("苍穹龙", "龙", "T7", "N", "PHY", "WC", "威压破防"),
    "SZW_0104": ("星辉龙", "龙", "T7", "R", "MAG", "WE", "星火灼烧"),
    "SZW_0105": ("冥主骸王", "亡灵", "T7", "N", "TANK", "WC", "抗性高"),
    "SZW_0106": ("深渊鲸皇", "水", "T8", "N", "TANK", "WC", "高血护盾"),
    "SZW_0107": ("冰海圣鲛", "水", "T8", "R", "MAG", "WE", "冻结稳定"),
    "SZW_0108": ("潮冕龙鲛", "水", "T8", "E", "CTRL", "DG", "冻结驱散"),
    "SZW_0109": ("霸爪战王", "兽", "T8", "N", "PHY", "WC", "斩杀强化"),
    "SZW_0110": ("岩甲巨兽", "兽", "T8", "R", "TANK", "WE", "嘲讽减伤"),
    "SZW_0111": ("蛊渊皇", "虫", "T8", "N", "CURSE", "WC", "DOT扩散"),
    "SZW_0112": ("腐天女皇", "虫", "T8", "R", "CTRL", "WE", "降命中降速"),
    "SZW_0113": ("虫巢灾主", "虫", "T8", "E", "CURSE", "DG", "吸血爆发"),
    "SZW_0114": ("天风神隼", "羽", "T8", "N", "CTRL", "WC", "先手压制"),
    "SZW_0115": ("雷羽王", "羽", "T8", "R", "PHY", "WE", "追击连击"),
    "SZW_0116": ("苍穹翼圣", "羽", "T8", "N", "CTRL", "WC", "闪避提升"),
    "SZW_0117": ("星烬龙王", "龙", "T8", "R", "PHY", "WE", "威压破防"),
    "SZW_0118": ("霜烬龙皇", "龙", "T8", "E", "MAG", "DG", "冻灼双态"),
    "SZW_0119": ("幽冥龙祖", "龙", "T8", "L", "PHY", "BS", "双威压"),
    "SZW_0120": ("归墟死王", "亡灵", "T8", "L", "CURSE", "BS", "群诅咒复生"),
}


def pet_info(species_id: str) -> dict:
    """图鉴基础信息"""
    name, race, tier, rarity, role, pool, sig = PETS[species_id]
    return {"id": species_id, "name": name, "race": race, "tier": tier,
            "rarity": rarity, "role": role, "pool": pool, "signature": sig}


def pet_skill_pool_info(species_id: str) -> dict:
    """技能池映射信息"""
    if species_id not in PET_SKILL_POOL:
        return {"signature": "SK_001", "pool_main": "PM_B_PHY", "pool_rare": "PR_OFFENSE"}
    sig, pm, pr = PET_SKILL_POOL[species_id]
    return {"signature": sig, "pool_main": pm, "pool_rare": pr}


# ============================================================
# 属性生成（公式化：段位基础范围 + 定位系数 + 成长步长 + 资质）
# ============================================================
# tier → (hp_min, hp_max, atk_min, atk_max, def_min, def_max, spd_min, spd_max)
TIER_BASE_RANGES = {
    "T1": (180, 260, 18, 28, 10, 18, 10, 16),
    "T2": (260, 360, 28, 40, 18, 26, 14, 20),
    "T3": (360, 480, 40, 56, 26, 36, 18, 24),
    "T4": (480, 620, 56, 76, 36, 48, 22, 28),
    "T5": (620, 780, 76, 100, 48, 62, 26, 32),
    "T6": (780, 960, 100, 128, 62, 78, 30, 36),
    "T7": (960, 1160, 128, 160, 78, 96, 34, 40),
    "T8": (1160, 1400, 160, 200, 96, 118, 38, 44),
}

# role → (HP, ATK_PHY, ATK_MAG, DEF_PHY, DEF_MAG, SPD) 系数
ROLE_COEF = {
    "TANK": (1.25, 0.85, 0.85, 1.15, 1.15, 0.95),
    "PHY": (0.95, 1.22, 0.70, 0.95, 0.95, 1.05),
    "MAG": (0.92, 0.70, 1.22, 0.95, 0.95, 1.00),
    "CTRL": (0.92, 0.85, 0.85, 0.92, 0.92, 1.20),
    "CURSE": (1.05, 1.05, 1.05, 1.00, 1.00, 0.95),
}

# 每级成长步长基数
STEP_BASE = {"HP": 6, "ATK": 0.9, "DEF": 0.7, "SPD": 0.06}

# 资质区间
APTITUDE_MIN = 0.85
APTITUDE_MAX = 1.15
GROWTH_STAR_MIN = 1
GROWTH_STAR_MAX = 5
RECOMMEND_KEEP_GROWTH_STAR = 3


def roll_aptitudes() -> dict:
    """生成 6 维资质（0.85–1.15）"""
    return {s: round(random.uniform(APTITUDE_MIN, APTITUDE_MAX), 3)
            for s in ["hp", "atk_phy", "atk_mag", "def_phy", "def_mag", "spd"]}


def roll_pet_stats(species_id: str, level: int = 1, growth_stars: int = 3,
                   aptitudes: dict | None = None) -> dict:
    """公式生成个体属性
    BaseStat = Uniform(range_min..range_max) × aptitude × role_coef
    Stat(L) = floor(BaseStat + (L-1) × StepStat)
    StepStat = StepBase × rarity_mul × growth_star_mul
    """
    info = pet_info(species_id)
    tr = TIER_BASE_RANGES[info["tier"]]
    rc = ROLE_COEF[info["role"]]
    rg = RARITY_GROWTH[info["rarity"]]
    sg = GROWTH_STAR_MUL.get(growth_stars, 1.12)
    if aptitudes is None:
        aptitudes = roll_aptitudes()
    # 基础值（段位范围 × 资质 × 定位系数）
    hp_base = random.uniform(tr[0], tr[1]) * aptitudes["hp"] * rc[0]
    atk_phy_base = random.uniform(tr[2], tr[3]) * aptitudes["atk_phy"] * rc[1]
    atk_mag_base = random.uniform(tr[2], tr[3]) * aptitudes["atk_mag"] * rc[2]
    def_phy_base = random.uniform(tr[4], tr[5]) * aptitudes["def_phy"] * rc[3]
    def_mag_base = random.uniform(tr[4], tr[5]) * aptitudes["def_mag"] * rc[4]
    spd_base = random.uniform(tr[6], tr[7]) * aptitudes["spd"] * rc[5]
    # 每级成长步长
    step_hp = STEP_BASE["HP"] * rg * sg
    step_atk = STEP_BASE["ATK"] * rg * sg
    step_def = STEP_BASE["DEF"] * rg * sg
    step_spd = STEP_BASE["SPD"] * rg * sg
    L = level
    hp = int(hp_base + (L - 1) * step_hp)
    atk_phy = max(1, int(atk_phy_base + (L - 1) * step_atk))
    atk_mag = max(1, int(atk_mag_base + (L - 1) * step_atk))
    def_phy = max(1, int(def_phy_base + (L - 1) * step_def))
    def_mag = max(1, int(def_mag_base + (L - 1) * step_def))
    spd = max(1, int(spd_base + (L - 1) * step_spd))
    crit = round(CRIT_BASE + (0.02 if info["rarity"] in ("E", "L") else 0), 3)
    return {"hp": hp, "atk_phy": atk_phy, "atk_mag": atk_mag,
            "def_phy": def_phy, "def_mag": def_mag, "spd": spd, "crit": crit,
            "aptitudes": aptitudes}


def pet_skill_slots_for_level(pet_level: int) -> int:
    """宠物可用技能槽位数（槽4需 Lv30）"""
    n = 0
    for slot, need_lv in PET_SKILL_SLOT_UNLOCK.items():
        if pet_level >= need_lv:
            n += 1
    return min(PET_SKILL_SLOTS, n)


def roll_pet_skills(species_id: str, pet_level: int = 1) -> list:
    """按图鉴技能池 + 宠物等级抽取技能
    槽1: 签名技能（Lv1）
    槽2: 主池随机（Lv1）
    槽3: 主池随机（Lv10）
    槽4: 稀有池随机（Lv30）
    """
    spi = pet_skill_pool_info(species_id)
    skills = [spi["signature"]]
    main_pool = SKILL_POOLS.get(spi["pool_main"], [])
    rare_pool = SKILL_POOLS.get(spi["pool_rare"], [])
    # 槽2（Lv1）
    if pet_level >= PET_SKILL_SLOT_UNLOCK[2]:
        candidates = [s for s in main_pool if s not in skills]
        if candidates:
            skills.append(random.choice(candidates))
    # 槽3（Lv10）
    if pet_level >= PET_SKILL_SLOT_UNLOCK[3] and len(skills) < 3:
        candidates = [s for s in main_pool if s not in skills]
        if candidates:
            skills.append(random.choice(candidates))
    # 槽4（Lv30）
    if pet_level >= PET_SKILL_SLOT_UNLOCK[4] and len(skills) < 4:
        candidates = [s for s in rare_pool if s not in skills]
        if candidates:
            skills.append(random.choice(candidates))
    return skills


def roll_wild_pet(tier: str) -> dict:
    """生成一个野生遭遇幻兽（含等级/属性/技能/资质）"""
    tier_pets = pets_in_tier(tier)
    species_id = random.choice(tier_pets)
    info = pet_info(species_id)
    tier_num = int(tier[1])
    lvl = random.randint(tier_num * 10 - 9, tier_num * 10)
    stars = random.choices([1, 2, 3, 4, 5], weights=[30, 30, 25, 10, 5])[0]
    aptitudes = roll_aptitudes()
    stats = roll_pet_stats(species_id, lvl, stars, aptitudes)
    skills = roll_pet_skills(species_id, lvl)
    return {"species_id": species_id, "level": lvl, "growth_stars": stars,
            "aptitudes": aptitudes, "skills": skills, **stats, "info": info}


# ============================================================
# 捕捉系统（公式：基础率 × 球倍率 + 级差 + 保底）
# ============================================================
CAPTURE_BASE_RATE = {"N": 0.35, "R": 0.22, "E": 0.12, "L": 0.06}
CAPTURE_BALL_MUL = {"IT_BALL_N": 1.0, "IT_BALL_S": 1.5, "IT_BALL_U": 2.2}
# (玩家-宠物等级差阈值, 成功率加成)  正差=宠物弱=更易抓
CAPTURE_LEVEL_DIFF = [
    (10, 0.10), (5, 0.05), (1, 0.01), (0, 0.00),
    (-1, -0.02), (-3, -0.06), (-5, -0.10), (-10, -0.20),
]
CAPTURE_MIN_RATE = 0.01
CAPTURE_MAX_RATE = 0.95
# rarity → (连续失败触发次数, 每次触发加成, 加成上限)
CAPTURE_PITY = {
    "N": (8, 0.08, 0.16),
    "R": (10, 0.10, 0.20),
    "E": (12, 0.10, 0.20),
    "L": (15, 0.10, 0.20),
}


def capture_level_diff_add(player_level: int, pet_level: int) -> float:
    """等级差加成（玩家高于宠物=更易抓）"""
    diff = player_level - pet_level
    for threshold, add in CAPTURE_LEVEL_DIFF:
        if diff >= threshold:
            return add
    return CAPTURE_LEVEL_DIFF[-1][1]


def capture_success_rate(rarity: str, ball_id: str, player_level: int,
                         pet_level: int, pity_fails: int = 0) -> float:
    """计算最终捕捉成功率，clamp 到 [0.01, 0.95]"""
    base = CAPTURE_BASE_RATE.get(rarity, 0.35)
    mul = CAPTURE_BALL_MUL.get(ball_id, 1.0)
    diff_add = capture_level_diff_add(player_level, pet_level)
    pity_bonus = 0.0
    if rarity in CAPTURE_PITY:
        trigger, bonus, max_b = CAPTURE_PITY[rarity]
        pity_bonus = min(max_b, (pity_fails // trigger) * bonus)
    rate = base * mul + diff_add + pity_bonus
    return max(CAPTURE_MIN_RATE, min(CAPTURE_MAX_RATE, rate))


# ============================================================
# 幻兽经验来源（cfg_pet_xp_sources）
# ============================================================
PET_XP_SOURCES = {
    "stage_normal_win": 8,
    "stage_elite_win": 14,
    "dungeon_win": 22,
    "arena_win": 10,
    "arena_loss": 6,
    "battlefield_settle": 18,
    "tower_floor": 6,
}


# ============================================================
# 重生（cfg_rebirth）
# ============================================================
REBIRTH = {
    "cost_item": "IT_REBIRTH",
    "reroll_growth_star": True,
    "reroll_aptitudes": True,
    "reroll_skills": True,
    "lock_signature": False,
}


# ============================================================
# 地图结构（每段：普通关/精英关/副本/BOSS）
# ============================================================
STAGES_PER_TIER = 15
TIER_STRUCTURE = {
    "T1": (10, 3, 1, 1),
    "T2": (10, 5, 2, 1),
    "T3": (10, 5, 2, 1),
    "T4": (10, 5, 2, 1),
    "T5": (10, 5, 2, 1),
    "T6": (10, 5, 2, 1),
    "T7": (10, 5, 2, 1),
    "T8": (10, 5, 2, 1),
}

POOL_WEIGHTS = {"WC": 10, "WE": 6, "DG": 2, "BS": 1, "EV": 3}
RARITY_WEIGHTS_BY_TIER = {
    "T1": {"N": 70, "R": 22, "E": 6, "L": 2},
    "T2": {"N": 65, "R": 24, "E": 8, "L": 3},
    "T3": {"N": 60, "R": 26, "E": 10, "L": 4},
    "T4": {"N": 55, "R": 28, "E": 12, "L": 5},
    "T5": {"N": 50, "R": 28, "E": 14, "L": 8},
    "T6": {"N": 45, "R": 30, "E": 15, "L": 10},
    "T7": {"N": 40, "R": 30, "E": 17, "L": 13},
    "T8": {"N": 35, "R": 30, "E": 18, "L": 17},
}


def pets_in_tier(tier: str) -> list[str]:
    return [pid for pid, v in PETS.items() if v[2] == tier]


def pets_in_pool(tier: str, pool: str) -> list[str]:
    return [pid for pid, v in PETS.items() if v[2] == tier and v[5] == pool]


# ============================================================
# 掉落表（4 套：普通/精英/副本/BOSS）
# (item_id, weight, min, max)
# ============================================================
DROP_NORMAL = [
    ("CUR_COIN", 60, 60, 120),
    ("IT_BALL_N", 20, 1, 2),
    ("IT_STONE", 10, 0, 1),
    ("IT_SOUL_POWDER_1", 10, 0, 1),
]
DROP_ELITE = [
    ("CUR_COIN", 45, 120, 220),
    ("IT_BALL_S", 20, 1, 2),
    ("IT_STONE", 15, 1, 2),
    ("IT_SOUL_POWDER_1", 10, 1, 2),
    ("IT_SOUL_POWDER_2", 10, 0, 1),
]
DROP_DUNGEON = [
    ("CUR_COIN", 35, 220, 380),
    ("IT_BALL_U", 15, 1, 1),
    ("IT_STONE", 15, 2, 4),
    ("IT_SOUL_POWDER_2", 15, 1, 2),
    ("IT_SOUL_POWDER_3", 10, 0, 1),
    ("IT_SPIRIT_DUST", 10, 0, 60),
]
DROP_BOSS = [
    ("CUR_COIN", 30, 380, 650),
    ("IT_SOUL_POWDER_3", 15, 1, 2),
    ("IT_SOUL_POWDER_4", 10, 0, 1),
    ("IT_SPIRIT_KEY", 10, 0, 1),
    ("IT_SOUL_CHARM", 5, 0, 1),
    ("BOX_ARENA", 15, 1, 1),
    ("BOX_BF", 15, 1, 1),
]

DROP_TABLES = {
    "normal": DROP_NORMAL,
    "elite": DROP_ELITE,
    "dungeon": DROP_DUNGEON,
    "boss": DROP_BOSS,
}


def roll_drop(table_key: str, tier_mul: float = 1.0) -> list[tuple[str, int]]:
    """从掉落表抽取，返回 [(item_id, qty), ...]
    tier_mul: 段位加成（影响数量，不影响是否掉落）
    """
    table = DROP_TABLES.get(table_key, DROP_NORMAL)
    results = []
    for item_id, weight, lo, hi in table:
        if random.random() * 100 < weight:
            base = random.randint(lo, hi) if hi > 0 else lo
            qty = max(base, int(base * tier_mul)) if item_id == "CUR_COIN" else base
            if qty > 0:
                results.append((item_id, qty))
    return results


# ============================================================
# 日常任务（cfg_daily_tasks）
# task_id → (name, open_level, daily_limit, metric, reward_str)
# ============================================================
DAILY_TASKS = [
    ("D001", "完成普通关10次", 1, 1, "stage_normal_win", "CUR_COIN:600"),
    ("D002", "完成精英关3次", 1, 1, "stage_elite_win", "CUR_COIN:500|IT_BALL_S:2"),
    ("D003", "完成副本2次", 1, 1, "dungeon_win", "IT_STONE:3|IT_SOUL_POWDER_1:2"),
    ("D004", "擂台挑战10次", 10, 1, "arena_battle", "CUR_ARENA:120|CUR_PRESTIGE:80"),
    ("D005", "战骨强化3次", 10, 1, "bone_upgrade", "IT_STONE:2|CUR_COIN:300"),
    ("D006", "通天塔推进10层", 1, 1, "tower_floor", "IT_BURN_CRYSTAL:20|CUR_COIN:800"),
    ("D007", "猎魂3次", 30, 1, "soul_hunt", "CUR_COIN:1000|IT_SOUL_POWDER_2:1"),
    ("D008", "战灵塔推进8层", 35, 1, "spirit_tower_floor", "IT_SPIRIT_DUST:180|IT_SPIRIT_KEY:1"),
    ("D009", "战场结算3场", 40, 1, "battlefield_settle", "CUR_BF:120|CUR_PRESTIGE:90|BOX_KILL:3"),
    ("D010", "联盟捐献焚火晶20个", 1, 1, "guild_donate", "CUR_GUILD:20"),
    ("D011", "师徒互灌1次", 40, 1, "mentor_refill", "CUR_ENERGY:40|CUR_MENTOR:10"),
    ("D012", "捕捉成功1次", 1, 1, "capture_success", "IT_BALL_N:2|CUR_COIN:200"),
]

# 已实现的日常指标（其余为"即将开放"）
IMPLEMENTED_METRICS = {
    "stage_normal_win", "stage_elite_win", "dungeon_win", "capture_success",
    "arena_battle", "bone_upgrade", "tower_floor", "soul_hunt",
    "spirit_tower_floor", "battlefield_settle", "guild_donate", "mentor_refill",
}


def parse_reward(reward_str: str) -> list[tuple[str, int]]:
    """解析奖励字符串 'CUR_COIN:600|IT_BALL_S:2' → [(id, qty), ...]"""
    rewards = []
    for part in reward_str.split("|"):
        if ":" in part:
            iid, qty = part.split(":", 1)
            rewards.append((iid, int(qty)))
    return rewards


# ============================================================
# 战骨系统（cfg_bone_parts + cfg_bone_upgrade）
# ============================================================
# part_id → (name, stats列表)
BONE_PARTS = {
    "BONE_HEAD": ("头骨", ["HP", "DEF_MAG"]),
    "BONE_CHEST": ("胸骨", ["DEF_PHY", "DEF_MAG"]),
    "BONE_ARM": ("臂骨", ["ATK_PHY", "ATK_MAG"]),
    "BONE_LEG": ("腿骨", ["DEF_PHY", "SPD"]),
    "BONE_HAND": ("手骨", ["ATK_PHY", "ATK_MAG"]),
    "BONE_TAIL": ("尾骨", ["SPD"]),
    "BONE_CORE": ("元魂", ["ATK_PHY", "ATK_MAG", "HP"]),
}
BONE_PART_NAMES = ["头骨", "胸骨", "臂骨", "腿骨", "手骨", "尾骨", "元魂"]  # 向后兼容

# 战骨强化公式（100 级，规律化去重）
# coin_cost = 200 + 60×level
# stone_cost = 1 + floor(level/5)
# atk_pct=0.008 / def_pct=0.007 / hp_pct=0.007 / spd_flat=0.4（恒定）
BONE_UPGRADE_BONUS = {"atk_pct": 0.008, "def_pct": 0.007, "hp_pct": 0.007, "spd_flat": 0.4}


def bone_upgrade_cost(level: int) -> tuple[int, int]:
    """战骨强化消耗 (coin, stone)"""
    coin = 200 + 60 * level
    stone = 1 + level // 5
    return coin, stone


# ============================================================
# 魔魂系统（cfg_soul_rarity + cfg_soul_hunt + cfg_soul_slots + cfg_soul_xp + cfg_soul_feed）
# ============================================================
# tier → (name, coef_vs_tian)
SOUL_RARITY = {
    "WASTE": ("废魂", 0),
    "YELLOW": ("黄魂", 0.125),
    "MYSTIC": ("玄魂", 0.25),
    "EARTH": ("地魂", 0.5),
    "HEAVEN": ("天魂", 1.0),
    "GOD": ("神魂", 0),
}
SOUL_RARITY_NAMES = ["废魂", "黄魂", "玄魂", "地魂", "天魂"]  # 向后兼容（不含神魂特殊）

# 猎魂师：(hunter_name, price_coin, price_charm, outputs列表)
SOUL_HUNT = [
    ("艾米", 8000, 0, ["WASTE", "YELLOW"]),
    ("科科", 10000, 0, ["WASTE", "YELLOW", "MYSTIC"]),
    ("波尔", 20000, 0, ["WASTE", "YELLOW", "MYSTIC", "EARTH"]),
    ("沃特", 40000, 0, ["WASTE", "YELLOW", "MYSTIC", "EARTH"]),
    ("凯文", 60000, 0, ["WASTE", "YELLOW", "MYSTIC", "EARTH", "HEAVEN"]),
    ("沃特(高级)", 0, 4, ["EARTH", "GOD"]),
    ("凯文(高级)", 0, 6, ["EARTH", "HEAVEN", "GOD"]),
]

# 魔魂槽位：30级起3槽，每10级+1，最多8槽
SOUL_SLOTS = {30: 3, 40: 4, 50: 5, 60: 6, 70: 7, 80: 8}

# 魔魂升级魂力（from_lvl → to_lvl → need_soul_xp）
SOUL_XP = {
    (1, 2): 2000, (2, 3): 4000, (3, 4): 8000, (4, 5): 16000,
    (5, 6): 32000, (6, 7): 64000, (7, 8): 128000,
    (8, 9): 256000, (9, 10): 512000,
}

# 吞噬收益：tier → feed_xp
SOUL_FEED = {
    "YELLOW": 50, "MYSTIC": 100, "EARTH": 200, "HEAVEN": 400, "GOD": 1000,
}


def soul_slots_for_level(level: int) -> int:
    """魔魂槽位数（30级起3槽，每10级+1，最多8）"""
    if level < 30:
        return 0
    return min(8, 3 + (level - 30) // 10)


# ============================================================
# 战灵系统（cfg_spirit_slots + cfg_spirit_quality_weights + cfg_spirit_affixes）
# ============================================================
# slot → element
SPIRIT_SLOTS = {1: "水", 2: "土", 3: "火", 4: "木", 5: "金", 6: "神"}
SPIRIT_ELEMENTS = ["水", "土", "火", "木", "金", "神"]  # 向后兼容

# 品质权重：quality → (fixed_w, pct_w, special_w)
SPIRIT_QUALITY_WEIGHTS = {
    "普通": (1.00, 0.00, 0.00),
    "精良": (0.80, 0.20, 0.00),
    "优秀": (0.50, 0.45, 0.05),
    "传奇": (0.25, 0.60, 0.15),
}

# 词条池：affix_id → (name, type, stat, min, max)
SPIRIT_AFFIXES = {
    "AF_001": ("生命", "flat", "HP", 30, 90),
    "AF_002": ("物攻", "flat", "ATK_PHY", 5, 18),
    "AF_003": ("魔攻", "flat", "ATK_MAG", 5, 18),
    "AF_004": ("物防", "flat", "DEF_PHY", 4, 14),
    "AF_005": ("魔防", "flat", "DEF_MAG", 4, 14),
    "AF_006": ("速度", "flat", "SPD", 1, 4),
    "AF_101": ("生命%", "pct", "HP%", 0.02, 0.06),
    "AF_102": ("物攻%", "pct", "ATK_PHY%", 0.02, 0.06),
    "AF_103": ("魔攻%", "pct", "ATK_MAG%", 0.02, 0.06),
    "AF_104": ("物防%", "pct", "DEF_PHY%", 0.02, 0.06),
    "AF_105": ("魔防%", "pct", "DEF_MAG%", 0.02, 0.06),
    "AF_106": ("速度%", "pct", "SPD%", 0.02, 0.06),
    "AF_201": ("暴击%", "special", "CRIT%", 0.02, 0.06),
    "AF_202": ("抗暴%", "special", "ANTI_CRIT%", 0.02, 0.06),
    "AF_203": ("命中%", "special", "HIT%", 0.02, 0.06),
    "AF_204": ("闪避%", "special", "DODGE%", 0.02, 0.06),
}

# ============================================================
# cfg_spirit_reroll_cost 战灵洗炼费用（当日第 N 次）
# 规则：前 3 次免费，第 4 次起消耗铜钱+灵力，线性递增，第 30 次封顶
# ============================================================
# roll_no → (is_free, coin_cost, spirit_dust_cost)
SPIRIT_REROLL_COST = {
    1: (1, 0, 0), 2: (1, 0, 0), 3: (1, 0, 0),
    4: (0, 500, 20), 5: (0, 750, 30), 6: (0, 1000, 40),
    7: (0, 1250, 50), 8: (0, 1500, 60), 9: (0, 1750, 70),
    10: (0, 2000, 80), 11: (0, 2250, 90), 12: (0, 2500, 100),
    13: (0, 2750, 110), 14: (0, 3000, 120), 15: (0, 3250, 130),
    16: (0, 3500, 140), 17: (0, 3750, 150), 18: (0, 4000, 160),
    19: (0, 4250, 170), 20: (0, 4500, 180), 21: (0, 4750, 190),
    22: (0, 5000, 200), 23: (0, 5250, 210), 24: (0, 5500, 220),
    25: (0, 5750, 230), 26: (0, 6000, 240), 27: (0, 6250, 250),
    28: (0, 6500, 260), 29: (0, 6750, 270), 30: (0, 7000, 280),
}
SPIRIT_REROLL_FREE_COUNT = 3       # 每日前 3 次免费
SPIRIT_REROLL_DAILY_CAP = 30       # 每日封顶 30 次

# cfg_spirit_reroll_lock_cost 锁词条额外费用（叠加到洗炼费用上）
# lock_count → (extra_coin_cost, extra_spirit_dust_cost, notes)
SPIRIT_REROLL_LOCK_COST = {
    0: (0, 0, "不锁"),
    1: (800, 30, "锁1条"),
    2: (1600, 60, "锁2条"),
    3: (2600, 100, "锁3条（3词条全开后）"),
}


def spirit_reroll_cost(roll_no: int, lock_count: int = 0) -> tuple[int, int, bool]:
    """战灵洗炼费用（当日第 roll_no 次，锁 lock_count 条词条）
    返回 (coin_cost, spirit_dust_cost, is_free)
    注：is_free 仅当 roll_no 在免费区间且未锁词条时为 True
    """
    if roll_no < 1:
        roll_no = 1
    if roll_no > SPIRIT_REROLL_DAILY_CAP:
        roll_no = SPIRIT_REROLL_DAILY_CAP
    is_free, coin, dust = SPIRIT_REROLL_COST[roll_no]
    extra_coin, extra_dust, _ = SPIRIT_REROLL_LOCK_COST.get(lock_count, (0, 0, ""))
    # 锁词条则不再免费
    if lock_count > 0:
        is_free = 0
    return coin + extra_coin, dust + extra_dust, bool(is_free)


# ============================================================
# 擂台（cfg_arena）
# ============================================================
ARENA = {
    "daily_free": 10,
    "daily_extra_cost_energy": 2,
    "win_prestige": 12,
    "win_arena_coin": 18,
    "loss_prestige": 4,
    "loss_arena_coin": 8,
    "daily_first_win_bonus": "BOX_ARENA",
    "season_days": 7,
    "season_reward_top100_prestige": 800,
    "season_reward_top100_arena_coin": 1200,
    "season_reward_top100_box": 1,
}
ARENA_DAILY_FREE = 10  # 向后兼容


# ============================================================
# 战场（cfg_battlefield + cfg_kill_box_drops）
# ============================================================
BATTLEFIELD = {
    "open_time": "06:00-24:00",
    "low_level_max": 39,
    "high_level_min": 40,
    "daily_join_limit": 5,
    "win_prestige": 30,
    "win_bf_coin": 35,
    "loss_prestige": 12,
    "loss_bf_coin": 18,
    "kill_box_item": "BOX_KILL",
    "kill_box_daily_cap": 30,
}
BATTLEFIELD_LOW_MAX = 39    # 向后兼容
BATTLEFIELD_HIGH_MIN = 40   # 向后兼容

# 杀戮礼包掉落池：(item_id, weight, min, max)
KILL_BOX_DROPS = [
    ("CUR_COIN", 50, 800, 1800),
    ("IT_STONE", 18, 1, 3),
    ("IT_SOUL_POWDER_1", 14, 1, 3),
    ("IT_SOUL_POWDER_2", 10, 1, 2),
    ("IT_SPIRIT_DUST", 6, 30, 80),
    ("IT_SPIRIT_KEY", 2, 1, 1),
]


# ============================================================
# 联盟（cfg_alliance_donation + cfg_alliance_skills + cfg_alliance_storage）
# ============================================================
# 捐献：item_id → contribution
ALLIANCE_DONATION = {
    "IT_BURN_CRYSTAL": 1,
    "IT_GOLD_BAG": 10,
    "IT_INNER_PILL": 10,
}

# 联盟技能：skill_id → (name, max_level, per_level_bonus, cost_contrib_base, cost_contrib_step)
ALLIANCE_SKILLS = {
    "GSK_HP": ("联盟生命", 10, 0.01, 20, 10),
    "GSK_ATK": ("联盟攻击", 10, 0.01, 20, 10),
    "GSK_DEF": ("联盟防御", 10, 0.01, 20, 10),
    "GSK_SPD": ("联盟速度", 10, 0.01, 20, 10),
}

# cfg_alliance_skill_level_cost 联盟技能逐级消耗（0级→1级 ... 9级→10级）
# to_level → (contrib_cost_this_level, contrib_cost_cumulative, bonus_total)
ALLIANCE_SKILL_LEVEL_COST = {
    1: (20, 20, 0.01), 2: (30, 50, 0.02), 3: (40, 90, 0.03),
    4: (50, 140, 0.04), 5: (60, 200, 0.05), 6: (70, 270, 0.06),
    7: (80, 350, 0.07), 8: (90, 440, 0.08), 9: (100, 540, 0.09),
    10: (110, 650, 0.10),
}


def alliance_skill_cost(skill_id: str, from_level: int) -> tuple[int, int, float]:
    """联盟技能升级消耗（from_level → from_level+1）
    返回 (contrib_cost_this_level, contrib_cost_cumulative, bonus_total_after)
    满级或非法参数返回 (0, 当前累计, 当前总加成)
    """
    if skill_id not in ALLIANCE_SKILLS:
        return (0, 0, 0.0)
    max_lv = ALLIANCE_SKILLS[skill_id][1]
    to_level = from_level + 1
    if to_level < 1 or to_level > max_lv:
        # 已满级或越界：返回当前级累计与加成
        cur = ALLIANCE_SKILL_LEVEL_COST.get(from_level, (0, 0, 0.0))
        return (0, cur[1], cur[2])
    return ALLIANCE_SKILL_LEVEL_COST[to_level]


def alliance_skill_cumulative_cost(skill_id: str, to_level: int) -> int:
    """联盟技能升到 to_level 的累计贡献消耗"""
    if skill_id not in ALLIANCE_SKILLS or to_level < 1:
        return 0
    max_lv = ALLIANCE_SKILLS[skill_id][1]
    if to_level > max_lv:
        to_level = max_lv
    return ALLIANCE_SKILL_LEVEL_COST[to_level][1]

# 联盟寄存室
ALLIANCE_STORAGE = {
    "free_store_times_daily": 1,
    "extra_store_cost_contrib": 15,
}


# ============================================================
# 师徒（cfg_master_apprentice）
# ============================================================
MASTER_APPRENTICE = {
    "master_min_level": 40,
    "apprentice_max_level": 30,
    "graduate_level": 35,
    "mentor_refill_multiplier": 4,
    "graduate_reward_mentor_value": 120,
    "graduate_reward_prestige": 60,
    "graduate_reward_box": "BOX_ARENA",
}
MASTER_MIN_LEVEL = 40        # 向后兼容
APPRENTICE_MAX_LEVEL = 30    # 向后兼容
GRADUATE_LEVEL = 35          # 向后兼容


# ============================================================
# 塔楼层
# ============================================================
TONGTIAN_TOWER_FLOORS = 50
SPIRIT_TOWER_FLOORS = 30


# ============================================================
# v0.2.6 主线任务链（收集 + 推进，来源：召唤之王原版玩法 + zol.com 攻略）
# (sort, 名称, 解锁等级, 目标描述, 奖励)
# ============================================================
MAIN_QUESTS = [
    (1, "初次捕捉", 1, "捕捉第一只幻兽", "灵石×5、普通捕捉球×3"),
    (2, "图鉴开启", 5, "图鉴收录5只幻兽", "经验+500、灵石×10"),
    (3, "战骨强化", 10, "强化战骨1次", "魂粉(黄)×3、灵石×8"),
    (4, "通天塔", 15, "通关通天塔10层", "经验+1000、焚火晶×2"),
    (5, "擂台首胜", 20, "擂台PVP首胜", "比武勋章×2、灵石×20"),
    (6, "魂之猎手", 30, "猎魂10次", "魂粉(玄)×5、追魂法宝×1"),
    (7, "联盟加入", 40, "加入联盟", "金袋×2、联盟贡献+100"),
    (8, "幻兽大师", 60, "图鉴收录50只幻兽", "重生丹×1、魂粉(地)×3、称号：幻兽大师"),
]
