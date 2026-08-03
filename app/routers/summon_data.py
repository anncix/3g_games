"""召唤之王静态配置包（v0.0.5 可跑服定版）

来源说明：
- 战骨/魔魂/战灵槽位、魔魂魂力表、战场时间、联盟/师徒规则 = 公开资料对齐的结构信息
- 经验曲线/120图鉴/技能库/地图掉落与商店 = 复刻定版（可上线），非原版数据库

本文件为纯静态常量，路由层直接 import 使用，不入库。
"""
from __future__ import annotations

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
PET_STORAGE_BASE = 50
PET_STORAGE_ADD_PER_10LVL = 10

# 活力
ENERGY_CAP = 120
ENERGY_REGEN_PER_MIN = 0.2          # 每 5 分钟 +1
FRIEND_REFILL_AMOUNT = 10
FRIEND_REFILL_DAILY_CAP = 5
COST_STAGE_NORMAL = 2
COST_STAGE_ELITE = 4
COST_ARENA = 2

# 战斗公式定版
CRIT_BASE = 0.05
CRIT_DMG = 1.50
HIT_BASE = 0.95
DODGE_BASE = 0.05

# 抓捕球倍率
BALL_MULTIPLIER = {"IT_BALL_N": 1.0, "IT_BALL_S": 1.5, "IT_BALL_U": 2.2}
CAPTURE_DAILY_LIMIT = 30            # 每日抓捕上限

# 段位解锁等级（T1-T8 每 10 级一段）
TIER_UNLOCK_LEVEL = {f"T{i}": (i - 1) * 10 + 1 for i in range(1, 9)}
# 每段地图关卡数
STAGES_PER_TIER = 15


# ============================================================
# cfg_level_xp（1–80 经验表，方案A）
# need_xp: 升到下一级所需；cum_to_level: 到达该级累计；cum_to_next: 升到下一级累计
# 公式：need(L)=120+80*L（对齐平台方案A）
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


# ============================================================
# cfg_level_unlocks 等级解锁
# ============================================================
LEVEL_UNLOCKS = {
    1: "世界地图/捕捉/幻兽列表",
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

# 平台物品字典 key（seed 注册用）
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
}


# ============================================================
# cfg_shop 商城/兑换
# ============================================================
# (shop, item_id, currency, price, daily_limit)
SHOP = [
    ("shop_general", "IT_BALL_N", "coins", 80, 30),
    ("shop_general", "IT_BALL_S", "coins", 300, 20),
    ("shop_general", "IT_BALL_U", "coins", 900, 10),
    ("shop_general", "IT_STONE", "coins", 500, 20),
    ("shop_general", "IT_SOUL_POWDER_1", "coins", 200, 20),
    ("shop_cash", "IT_BALL_U", "gems", 30, 5),
    ("shop_cash", "IT_REBIRTH", "gems", 120, 1),
]


# ============================================================
# cfg_skill_base（60 基础技能，rank 规则生成 180 技能）
# ============================================================
SKILL_RANK = {1: (1.00, 0.00, 0), 2: (1.35, 0.05, 0), 3: (1.75, 0.10, 1)}
# skill_id, name, type, school, coef_or_value, cooldown, notes
SKILLS = {
    "SK_001": ("利爪斩", "active", "PHY", 1.10, 1, "单体物伤"),
    "SK_002": ("破甲击", "active", "PHY", 0.95, 2, "降物防"),
    "SK_003": ("撕裂", "active", "PHY", 0.90, 2, "流血2回合"),
    "SK_004": ("连环突袭", "active", "PHY", 0.65, 3, "随机2-3段"),
    "SK_005": ("斩杀线", "passive", "PHY", 0.20, 0, "目标低血增伤"),
    "SK_006": ("反击姿态", "passive", "TANK", 0.18, 0, "受击反击概率"),
    "SK_007": ("坚甲", "passive", "TANK", 0.12, 0, "物防%提升"),
    "SK_008": ("法抗", "passive", "TANK", 0.12, 0, "魔防%提升"),
    "SK_009": ("护盾术", "active", "TANK", 0.18, 3, "按HP生成盾"),
    "SK_010": ("嘲讽", "active", "TANK", 0, 4, "强制目标1回合"),
    "SK_011": ("潮汐箭", "active", "MAG", 1.10, 1, "单体法伤"),
    "SK_012": ("冰封", "active", "CTRL", 0, 4, "冻结1回合"),
    "SK_013": ("寒潮", "active", "MAG", 0.85, 3, "群体法伤"),
    "SK_014": ("法穿印记", "active", "MAG", 0, 3, "降魔防"),
    "SK_015": ("灼烧", "active", "MAG", 0.70, 2, "灼烧2回合"),
    "SK_016": ("雷击", "active", "CTRL", 0.95, 2, "小概率麻痹"),
    "SK_017": ("加速", "active", "CTRL", 0, 3, "己方速度提升"),
    "SK_018": ("减速", "active", "CTRL", 0, 2, "敌方速度下降"),
    "SK_019": ("沉默咒", "active", "CTRL", 0, 4, "沉默1回合"),
    "SK_020": ("驱散", "active", "CTRL", 0, 4, "驱散1个减益"),
    "SK_021": ("吸血咒", "active", "CURSE", 0.80, 2, "伤害并回血"),
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
    "SK_057": ("天魔降伏", "passive", "PHY", 120, 0, "天魂模板"),
    "SK_058": ("守护之魂", "passive", "TANK", 150, 0, "天魂模板"),
    "SK_059": ("蹑影逐日", "passive", "CTRL", 8, 0, "天魂模板"),
    "SK_060": ("极寿无疆", "passive", "TANK", 0.064, 0, "HP%提升"),
}


def skill_info(skill_id: str, rank: int = 1) -> dict:
    """生成指定阶的技能信息（rank 1-3）"""
    name, stype, school, coef, cd, notes = SKILLS[skill_id]
    rank_mul, proc_add, ctrl_bonus = SKILL_RANK.get(rank, (1.00, 0.00, 0))
    return {
        "skill_id": skill_id, "name": name, "type": stype, "school": school,
        "coef": round(coef * rank_mul, 3), "cooldown": cd, "notes": notes,
        "rank": rank, "proc_add": proc_add, "ctrl_bonus": ctrl_bonus,
    }


# ============================================================
# cfg_pet_species（120 图鉴）
# id, name, race, tier, rarity, role, pool, signature
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


# ============================================================
# cfg_pet_skill_pool 种族/职业 → 技能池映射（生成个体技能用）
# ============================================================
ROLE_SKILL_POOL = {
    "PHY": ["SK_001", "SK_002", "SK_003", "SK_004", "SK_027"],
    "TANK": ["SK_006", "SK_007", "SK_008", "SK_009", "SK_030"],
    "MAG": ["SK_011", "SK_013", "SK_014", "SK_015", "SK_033"],
    "CTRL": ["SK_012", "SK_016", "SK_017", "SK_018", "SK_028"],
    "CURSE": ["SK_021", "SK_022", "SK_023", "SK_024", "SK_025"],
}


# ============================================================
# cfg_maps_capture 地图抓捕池权重
# ============================================================
POOL_WEIGHTS = {"WC": 10, "WE": 6, "DG": 2, "BS": 1, "EV": 3}
# 稀有度抽取权重（按段位微调，高段位稀有更高）
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
    """该段位所有幻兽 id"""
    return [pid for pid, v in PETS.items() if v[2] == tier]


def pets_in_pool(tier: str, pool: str) -> list[str]:
    """该段位指定产出池的幻兽 id"""
    return [pid for pid, v in PETS.items() if v[2] == tier and v[5] == pool]


# ============================================================
# 个体属性生成（按种族/稀有度/成长星 + 等级）
# ============================================================
# 种族基础属性倾向（HP/物攻/魔攻/物防/魔防/速度）
RACE_BASE = {
    "水": (110, 18, 22, 14, 12, 9),
    "兽": (100, 26, 14, 12, 10, 12),
    "虫": (95, 20, 16, 14, 12, 11),
    "羽": (85, 22, 18, 9, 10, 16),
    "龙": (120, 24, 24, 14, 14, 11),
    "亡灵": (105, 20, 22, 12, 14, 10),
}
ROLE_BONUS = {
    "PHY": (0, 6, 0, 0, 0, 0),
    "TANK": (20, 0, 0, 4, 4, -2),
    "MAG": (0, 0, 6, 0, 0, 0),
    "CTRL": (-5, 0, 0, 0, 0, 4),
    "CURSE": (0, 0, 2, 0, 0, 0),
}


def roll_pet_stats(species_id: str, level: int = 1, growth_stars: int = 3) -> dict:
    """按图鉴+等级+成长星生成个体属性"""
    info = pet_info(species_id)
    base = RACE_BASE[info["race"]]
    bonus = ROLE_BONUS[info["role"]]
    rg = RARITY_GROWTH[info["rarity"]]
    sg = GROWTH_STAR_MUL.get(growth_stars, 1.12)
    # 等级成长系数（每级 +8%）
    lvl_mul = 1.0 + 0.08 * (level - 1)
    total_mul = rg * sg * lvl_mul
    hp = int((base[0] + bonus[0]) * total_mul)
    atk_phy = max(1, int((base[1] + bonus[1]) * total_mul))
    atk_mag = max(1, int((base[2] + bonus[2]) * total_mul))
    def_phy = max(1, int((base[3] + bonus[3]) * total_mul))
    def_mag = max(1, int((base[4] + bonus[4]) * total_mul))
    spd = max(1, int((base[5] + bonus[5]) * total_mul))
    crit = round(CRIT_BASE + (0.02 if info["rarity"] in ("E", "L") else 0), 3)
    return {"hp": hp, "atk_phy": atk_phy, "atk_mag": atk_mag,
            "def_phy": def_phy, "def_mag": def_mag, "spd": spd, "crit": crit}


def roll_wild_pet(tier: str) -> dict:
    """生成一个野生遭遇幻兽（含等级/属性/技能）"""
    import random
    tier_pets = pets_in_tier(tier)
    species_id = random.choice(tier_pets)
    info = pet_info(species_id)
    # 等级随段位
    tier_num = int(tier[1])
    lvl = random.randint(tier_num * 10 - 9, tier_num * 10)
    stars = random.choices([1, 2, 3, 4, 5], weights=[30, 30, 25, 10, 5])[0]
    stats = roll_pet_stats(species_id, lvl, stars)
    # 技能：职业池取 2 个
    pool = ROLE_SKILL_POOL.get(info["role"], ROLE_SKILL_POOL["PHY"])
    skills = random.sample(pool, min(2, len(pool)))
    return {"species_id": species_id, "level": lvl, "growth_stars": stars,
            "skills": skills, **stats, "info": info}


# ============================================================
# 高级系统规则（战骨/魔魂/战灵/塔/战场/联盟/师徒）
# 仅作规则展示与解锁节点，核心循环先跑通
# ============================================================
BONE_PARTS = ["头骨", "胸骨", "臂骨", "腿骨", "手骨", "尾骨", "元魂"]
SOUL_RARITY = {"废魂": 0, "黄魂": 0.125, "玄魂": 0.25, "地魂": 0.5, "天魂": 1.0}
SOUL_SLOTS = {30: 3, 40: 4, 50: 5, 60: 6, 70: 7, 80: 8}
SPIRIT_SLOTS = ["水", "土", "火", "木", "金", "神"]
TONGTIAN_TOWER_FLOORS = 50
SPIRIT_TOWER_FLOORS = 30
ARENA_DAILY_FREE = 10
BATTLEFIELD_LOW_MAX = 39
BATTLEFIELD_HIGH_MIN = 40
MASTER_MIN_LEVEL = 40
APPRENTICE_MAX_LEVEL = 30
GRADUATE_LEVEL = 35


def soul_slots_for_level(level: int) -> int:
    """魔魂槽位数（30级起3槽，每10级+1，最多8）"""
    if level < 30:
        return 0
    return min(8, 3 + (level - 30) // 10)
