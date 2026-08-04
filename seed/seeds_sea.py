"""纵横四海完整数据生成器（同步 SQLAlchemy 版）

由 /Users/mubai/3g_games/app/seed_sea_large.py + seed_sea_v018.py + seed_sea_equips.py
迁移改写：
- 异步 `await db.execute(...)` / `await db.get(...)` -> 同步 `db.query(...).get(...)`
- `db.add_all(...)` -> 分批 `db.add_all(...) + db.commit()`
- 模型挂载到 qqgames 新表（ItemSea/SeaDungeon/SeaEquipSet/SeaEquipPiece/SeaHolyMark/
  SeaShip/SeaMainQuest/SeaCitySpecialty/SeaPetSkill）及扩展的已有表
  （SeaCity/SeaRoute/SeaGem/SeaCard/SeaPet/SeaMount/SeaWing/SeaFollower）

数据量（与 3g_games 保持一致）：
- 城市 20（seed_sea_large）+ 16 补全（seed_sea_v018）= 36，合并进 qqgames SeaCity
- 装备套装 24 / 宝石 60 / 卡片 21 / 圣痕 40 / 宠物 60 / 坐骑 12 / 羽翼 8 / 随从 9 / 副本 10
- 船只 14 / 主线任务 12 / 宠物技能 23 / 城市特产 34 / 装备件名 79
- 物品字典 ItemSea：宝石 60 + 卡片 21 + 消耗品 41 + 船只 14 = 136

幂等：以 key 存在性判断，已存在则跳过；可断点续跑。
"""
import json

from sqlalchemy.orm import Session

from models.models import (
    SeaCity, SeaRoute, SeaGem, SeaCard, SeaPet, SeaMount, SeaWing, SeaFollower,
    SeaDungeon, SeaEquipSet, SeaEquipPiece, SeaHolyMark, SeaShip,
    SeaMainQuest, SeaCitySpecialty, SeaPetSkill, ItemSea,
)


def _ensure_item(db: Session, key: str, name: str, type_: str, price: int, desc: str) -> bool:
    """幂等写入 ItemSea 物品字典；返回是否新增"""
    if not db.query(ItemSea).filter(ItemSea.key == key).first():
        db.add(ItemSea(key=key, name=name, type=type_, module_key="sea",
                       sell_price=price, description=desc))
        return True
    return False


# ---------- v0.1.5：城市/套装/宝石/卡片/圣痕/宠物/坐骑/羽翼/随从/副本/消耗品 ----------
SEA_CITIES = [
    # (key, name, parent, unlock_level, intro, sea_area)
    ("venice", "威尼斯", "port_a", 1, "地中海明珠，珠宝店/占星屋/广场/花园/赌场", "地中海"),
    ("athens", "雅典", "venice", 3, "东门通往巨鲸副本", "地中海"),
    ("london", "伦敦", "port_a", 5, "花园温莎副本/铁匠铺强化/王宫觉醒", "北海"),
    ("amsterdam", "阿姆斯特丹", "london", 8, "北门基德的宝藏副本", "北海"),
    ("copenhagen", "哥本哈根", "london", 10, "南门黑龙挂刷/码头黄金航线", "北海"),
    ("capetown", "开普敦", "port_a", 15, "东门贝河副本/球场踢球/西门野外", "非洲"),
    ("saintgeorge", "圣乔治", "capetown", 30, "广场120级毁灭副本", "非洲"),
    ("dakar", "达喀尔", "capetown", 20, "西门养人毒蝎/人形仙人掌挂刷", "非洲"),
    ("mombasa", "蒙巴萨", "capetown", 25, "东门野外", "非洲"),
    ("mozambique", "莫桑比克", "capetown", 28, "北门野外", "非洲"),
    ("quanzhou", "泉州", "port_a", 35, "东门五行副本/铁匠铺/古董店/珠宝店", "亚洲"),
    ("changan", "长安", "quanzhou", 40, "西门诸葛副本/赌场/铁匠铺精炼", "亚洲"),
    ("yangzhou", "扬州", "changan", 45, "北门情侣副本-月老阁/怡红院", "亚洲"),
    ("kyoto", "京都", "changan", 50, "幕府小日本-房屋材料", "亚洲"),
    ("lisbon", "里斯本", "port_a", 12, "码头白银航线/商店", "亚洲"),
    ("aden", "亚丁", "capetown", 33, "珠宝店大宝石合成", "亚洲"),
    ("hormuz", "荷姆兹", "aden", 36, "珠宝店中宝石/北门牛头山", "亚洲"),
    ("atlantis", "亚特兰蒂斯", "saintgeorge", 60, "广场圣诞老人装备捐献/雪人币", "其他"),
    ("ceylon", "锡兰", "mombasa", 22, "酒馆沈茂挂刷", "其他"),
    ("port_a", "启航港", "", 1, "你的起点，宁静的小港", "地中海"),
]

SEA_CITIES_ADD = [
    # (key, name, region, unlock_level, intro)
    ("marseille", "马赛", "地中海", 4, "地中海·白银航线终点，产盐和乳酪"),
    ("istanbul", "伊斯坦堡", "地中海", 6, "地中海·丝织品产地，特殊商店出售解毒剂/固元膏/加速剂"),
    ("tunis", "突尼斯", "地中海", 5, "地中海·杏仁和橄榄油产地"),
    ("alexandria", "亚历山大", "地中海", 7, "地中海·橄榄油产地"),
    ("algiers", "阿尔及尔", "地中海", 5, "地中海·杏仁和橄榄油产地"),
    ("ragusa", "拉古扎", "地中海", 6, "地中海·杏仁和橄榄油产地"),
    ("nantes", "南特", "北海", 9, "北海·黄金航线终点，产葡萄酒和小麦"),
    ("hamburg", "汉堡", "北海", 7, "北海·鱼肉和锦织品产地"),
    ("oslo", "奥斯陆", "北海", 8, "北海·鱼肉/木材/绒织品产地"),
    ("rwanda", "卢旺达", "非洲", 22, "非洲·琥珀和珊瑚产地"),
    ("madagascar", "马达加斯加", "非洲", 26, "非洲·木材和毛皮产地"),
    ("mumbai", "孟买", "印度洋", 24, "印度洋·米/皮草/胡椒产地，可购多桅小型帆船"),
    ("osaka", "大阪", "东亚", 52, "东亚·漆器和茶具产地"),
    ("hangzhou", "杭州", "东亚", 48, "东亚·丝织品产地"),
    ("guangzhou", "广州", "东亚", 46, "东亚·麝香产地，铁匠铺"),
    ("malacca", "马六甲", "东亚", 38, "东亚·肉桂产地"),
]

ROUTE_PAIRS = [
    ("port_a", "venice", 1, 30), ("port_a", "london", 1, 30),
    ("port_a", "capetown", 1, 60), ("port_a", "quanzhou", 1, 90),
    ("port_a", "lisbon", 1, 30), ("venice", "athens", 3, 30),
    ("london", "amsterdam", 5, 30), ("london", "copenhagen", 5, 30),
    ("capetown", "dakar", 15, 45), ("capetown", "mombasa", 15, 45),
    ("capetown", "saintgeorge", 15, 60), ("mombasa", "mozambique", 25, 30),
    ("mombasa", "ceylon", 22, 45), ("quanzhou", "changan", 35, 30),
    ("changan", "yangzhou", 40, 30), ("changan", "kyoto", 40, 45),
    ("capetown", "aden", 33, 60), ("aden", "hormuz", 36, 30),
    ("saintgeorge", "atlantis", 60, 90),
]

EQUIP_SETS = [
    ("set_bushi", "武士套装", 5, "填邀请码赠送/威尼斯探险副本掉落", 4),
    ("set_columbus", "哥伦布套装", 30, "威尼斯花园师徒兑换", 4),
    ("set_benyue", "奔月套装", 30, "开普敦踢球/泉州铁匠铺合成/充值", 4),
    ("set_bazhe", "霸者套装", 45, "威尼斯花园师徒兑换", 4),
    ("set_dimo_ring", "地魔双环", 80, "左环主线送/右环天魔战场", 2),
    ("set_dimo_armor", "地魔防具套装", 95, "主线任务地魔宝藏", 4),
    ("set_wangshi", "往事如风", 100, "强力散件配饰", 1),
    ("set_dimo_lianzhan", "地魔恋战", 110, "天魔战场兑换", 4),
    ("set_shengming", "生命的意义", 128, "强力散件武器", 1),
    ("set_tianmo_armor", "天魔防具套装", 130, "天魔战场/充值/合成", 4),
    ("set_haishi", "海誓山盟", 135, "情侣副本掉落海誓戒碎片", 2),
    ("set_tianmo_wand", "天魔轮回权杖", 140, "天魔战场/充值/合成", 1),
    ("set_fuchou", "复仇", 159, "强力散件武器", 1),
    ("set_magezhe", "麦哲伦套装", 1, "聚宝盆活动白嫖", 4),
    ("set_qihai", "七海套装", 1, "单笔充值198送", 4),
    ("set_haidao", "海盗王套装", 1, "单笔充值198送", 4),
    ("set_dila", "蒂拉套装", 1, "已基本绝版/主线送蒂拉之剑", 4),
    ("set_xuwu", "虚无套装", 1, "充值/开普敦踢球极低概率", 4),
    ("set_lieyan", "烈焰套装", 1, "充值获取", 4),
    ("set_sixiang", "四象圣套", 1, "充值/开普敦踢球极低概率", 4),
    ("set_yutu", "玉兔套装", 1, "氪佬专属998三配+998武器+528x4防具", 5),
    ("set_wushi_lv1", "散件Lv15", 15, "过渡装备", 1),
    ("set_yujia", "渔家套装", 1, "新手初始装备", 4),
    ("set_xinghai", "星海套装", 1, "活动限定", 4),
]

GEM_DEFS = [
    ("green", "绿宝石", "毒攻", ["主手", "副手", "头盔", "躯体", "腰部", "脚", "配饰"]),
    ("snaketooth", "蛇牙", "麻痹攻击", ["主手", "副手"]),
    ("whalebone", "鲸须", "致命一击", ["主手", "副手"]),
    ("dragonball", "龙珠", "体力上限+500", ["手持", "头戴", "身穿"]),
    ("purple", "紫宝石", "全属性小幅", ["配饰"]),
    ("red", "红宝石", "攻击加成", ["主手", "副手"]),
    ("blue", "蓝宝石", "防御加成", ["头盔", "躯体", "腰部", "脚"]),
    ("orange", "橙宝石", "全属性中幅", ["主手", "副手", "头盔", "躯体", "腰部", "脚", "配饰"]),
    ("cateye", "猫眼石", "升星材料", []),
    ("xuantie", "玄铁石", "五行副本专用", []),
    ("amber", "琥珀石", "巨鲸副本专用", []),
    ("longquan", "龙泉宝石", "升星材料", []),
]
GEM_TIER_NAMES = {1: "碎片", 2: "小", 3: "中", 4: "大", 5: "完美"}

CARDS = [
    ("card_leiwente", "莱温特卡片", "腰/头/躯体/脚", "体力+0.5%", "体力+1.5%", "丧钟镇副本BOSS"),
    ("card_modiaola", "莫迪奥拉卡片", "手持", "攻击+1.0%", "攻击+3.0%", "黑暗深渊副本BOSS"),
    ("card_badela", "巴德拉卡片", "手持", "攻击+0.5%", "攻击+1.5%", "玛雅潘大地祭坛"),
    ("card_langren", "狼人卡片", "手持/配饰", "攻击+11", "攻击+21", "爱丁堡狼牙堡"),
    ("card_feiyishou", "飞翼兽卡片", "手持/配饰", "体力+30、攻击+3", "体力+90、攻击+5", "长安封印之地"),
    ("card_goblin", "贪婪的哥布林", "配饰", "防御+0.5%", "防御+1.5%", "荷姆兹牛头寨12层"),
    ("card_huitailang", "灰太狼卡片", "腰/头/躯体/脚", "防御+11", "防御+21", "伊斯坦堡牧场"),
    ("card_luba", "泉州路霸卡片", "全部位", "抗反弹+3%", "抗反弹+5%", "泉州白云山"),
    ("card_xianrenzhang", "巨型仙人掌卡片", "全部位", "反弹+3%", "反弹+5%", "达喀尔西门"),
    ("card_youling", "幽灵卡片", "全部位", "抗诅咒+3%", "抗诅咒+5%", "威尼斯荒树林"),
    ("card_toukuang", "偷矿者卡片", "全部位", "抗迟缓+3%", "抗迟缓+5%", "威尼斯矿山"),
    ("card_juxiong", "巨熊卡片", "全部位", "虚弱+3%", "虚弱+5%", "威尼斯后山"),
    ("card_baiyexiang", "白野象卡片", "全部位", "沮丧+3%", "沮丧+5%", "开普敦草原深处"),
    ("card_xiangrikui", "变异向日葵卡片", "全部位", "毒+3%", "毒+5%", "汉堡沙丘"),
    ("card_jiangshi", "吸血僵尸卡片", "全部位", "抗诅咒+3%", "抗诅咒+5%", "伦敦吸血鬼坟墓"),
    ("card_tianlang", "天狼蜘蛛卡片", "腰/头/躯体/脚", "敏捷+5", "敏捷+10", "开普敦沼泽荒岛"),
    ("card_moguifei", "变异魔鬼鱼卡片", "腰/头/躯体/脚", "体力+20、敏捷+1", "体力+60、敏捷+3", "蒙巴萨东门"),
    ("card_huobianfu", "火蝙蝠卡片", "全部位", "诅咒+3%", "诅咒+5%", "莫桑比克北门"),
    ("card_shilaimu", "变异史莱姆卡片", "头/躯体/脚/腰", "体力+30、防御+3", "体力+90、防御+5", "封印迷阵"),
    ("card_taijian", "假太监卡片", "全部位", "抗毒+3%", "抗毒+5%", "长安东城门"),
    ("card_aisi", "艾斯卡片", "全部位", "麻痹+3%", "麻痹+5%", "活动限定"),
]

HOLY_MARK_NAMES = ["神力", "逆鳞", "血魂", "疾闪", "英勇", "审判之光", "钢铁之轮", "先祖之魂", "飓风之灵", "天堂之歌"]
HOLY_MARK_PINYIN = {"神力": "shenli", "逆鳞": "nilin", "血魂": "xuehun", "疾闪": "jishan",
                    "英勇": "yingyong", "审判之光": "shenpan", "钢铁之轮": "gangtie",
                    "先祖之魂": "xianzu", "飓风之灵": "jufeng", "天堂之歌": "tiantang"}
HOLY_MARK_QUALITIES = ["白", "绿", "蓝", "紫"]

PET_DEFS = [
    ("月虎", "白", 30, 28, 20, 200, "攻防参半", "新手宠物"),
    ("暗狼", "白", 38, 20, 18, 180, "攻击力高", "新手宠物"),
    ("龙猫", "白", 25, 20, 30, 180, "攻敏参半", "新手宠物"),
    ("霸熊", "白", 18, 35, 25, 220, "防敏参半", "新手宠物"),
    ("QQ宠物", "白", 22, 22, 22, 200, "易出疗伤", "新手宠物"),
    ("麒麟", "紫", 60, 55, 50, 500, "远古宠物", "远古宠物蛋"),
    ("九尾狐", "紫", 55, 50, 60, 480, "远古宠物", "远古宠物蛋"),
    ("雷霆战鹰", "紫", 65, 45, 65, 460, "远古宠物", "远古宠物蛋"),
    ("海豚", "橙", 50, 50, 50, 450, "均衡发展每级+3", "活动宠物"),
    ("圣龙", "橙", 80, 50, 45, 500, "主攻击", "活动宠物"),
    ("梦玲", "橙", 45, 80, 45, 550, "主防御", "活动宠物"),
    ("神兽", "橙", 70, 60, 55, 520, "专属技能", "活动宠物"),
    ("雪精灵", "橙", 65, 65, 60, 500, "专属技能", "活动宠物"),
    ("犬神", "橙", 75, 55, 60, 490, "专属技能", "活动宠物"),
    ("梦魔", "橙", 70, 50, 70, 470, "专属技能", "活动宠物"),
    ("刑天", "橙", 85, 70, 40, 550, "专属技能", "活动宠物"),
    ("雪熊宝宝", "橙", 60, 75, 45, 530, "专属技能", "活动宠物"),
    ("球球", "橙", 55, 55, 70, 480, "专属技能", "活动宠物"),
    ("财神", "橙", 50, 50, 50, 450, "专属技能", "活动宠物"),
    ("汤小帅", "橙", 65, 60, 55, 500, "专属技能", "活动宠物"),
    ("叫兽", "橙", 60, 65, 50, 510, "专属技能", "活动宠物"),
    ("粽子君", "橙", 58, 58, 58, 490, "专属技能", "活动宠物"),
    ("鲜花金古绿", "橙", 68, 58, 60, 500, "专属技能", "活动宠物"),
    ("轰天彩吟猪", "橙", 72, 62, 55, 520, "专属技能", "活动宠物"),
]
PET_VARIANTS = ["炽焰", "寒冰", "雷霆", "暗影", "圣光", "毒雾", "风暴", "大地", "星辰", "月华", "日耀", "虚空"]

MOUNTS = [
    ("mount_lionvulture", "暴风狮鹫", 80, "flat", 100, "普通"),
    ("mount_scorpio", "炽焰战蝎", 160, "flat", 200, "普通"),
    ("mount_ancientbeast", "仙境古兽", 200, "flat", 300, "普通"),
    ("mount_darkwolf", "暗月战狼", 210, "pct", 5, "黑暗军团"),
    ("mount_whitetiger", "圣灵白虎", 210, "pct", 5, "神圣军团"),
    ("mount_giantturtle", "巨型海龟", 210, "pct", 10, "稀有"),
    ("mount_thunderrhino", "雷霆巨犀", 210, "pct", 20, "黑暗军团"),
    ("mount_mammoth", "猛犸巨象", 210, "pct", 20, "神圣军团"),
    ("mount_hellhorse", "地狱战马", 210, "pct", 30, "稀有"),
    ("mount_voidshadow", "虚空幻影", 210, "pct", 45, "稀有"),
    ("mount_magiccarpet", "魔法飞毯", 210, "pct", 55, "稀有"),
    ("mount_mechviper", "机甲蝰蛇", 210, "pct", 65, "稀有"),
]

WINGS = [
    ("wing_freedom", "自由之翼", 80, {"体魄": 3, "吸血": 3}),
    ("wing_magdragon", "魔龙之翼", 160, {"体魄": 4, "吸血": 4}),
    ("wing_death", "死亡之翼", 200, {"体魄": 5, "吸血": 5}),
    ("wing_bloodsoul", "血魂之翼", 210, {"连击": 5}),
    ("wing_guardian", "守护之翼", 210, {"连击": 5}),
    ("wing_fallen", "堕落之翼", 210, {"连击": 5, "铁壁": 5}),
    ("wing_hope", "希望之翼", 210, {"连击": 5, "铁壁": 5}),
    ("wing_opensea", "公海之翼", 220, {"连击": 10, "铁壁": 10}),
]

FOLLOWERS = [
    ("follower_luffy", "路飞", "橡胶巨人枪", "10%概率造成当前攻击5倍伤害，但接下来停止攻击2回合", "传说"),
    ("follower_zoro", "索隆", "三刀流鬼斩", "10%概率连续3次攻击（可与连击叠加），但当前回合额外承受20%伤害", "传说"),
    ("follower_sanj", "香吉士", "恶魔风脚", "10%概率让对手全部防具耐久度降为0", "传说"),
    ("follower_brook", "布鲁克", "镇魂之歌", "10%概率让对手全部首饰耐久度降为0", "传说"),
    ("follower_franky", "福兰奇", "终极铁鎚", "10%概率让对手武器耐久度降为0", "传说"),
    ("follower_robin", "罗宾", "十六轮花", "26%概率幻化16个分身躲避敌人攻击", "传说"),
    ("follower_nami", "娜美", "雷霆万钧", "成功闪避后让敌人额外受到10000点雷电伤害", "传说"),
    ("follower_chopper", "乔巴", "野性强化", "进入战斗后随从攻防敏提升50%", "传说"),
    ("follower_usopp", "乌索普", "必杀火星鸟", "10%概率对对手额外造成5000点火焰伤害", "传说"),
]

DUNGEON_DIFFS = ["普通", "精英", "困难", "噩梦", "炼狱"]
DUNGEONS = [
    ("dgn_venice_explore", "威尼斯探险", "venice", [5, 15, 25, 35, 45],
     [8000, 16000, 24000, 36000, 48000], [1, 2, 3, 4, 5, 6, 0], ["set_bushi"]),
    ("dgn_windsor", "温莎庄园", "london", [30, 40, 50, 60, 70],
     [80000, 160000, 240000, 360000, 480000], [1], ["sea_card_leiwente"]),
    ("dgn_beihe", "贝河副本", "capetown", [50, 80, 100, 120, 150],
     [180000, 280000, 380000, 480000, 580000], [2, 6, 0], ["sea_gem_cateye_t1"]),
    ("dgn_wuxing", "五行阵", "quanzhou", [60, 90, 120, 150, 180],
     [280000, 380000, 480000, 580000, 680000], [3, 6, 0], ["sea_gem_xuantie_t1"]),
    ("dgn_juwei", "巨鲸副本", "athens", [60, 75, 90, 105, 120],
     [180000, 280000, 380000, 480000, 580000], [4, 6, 0], ["sea_gem_amber_t1"]),
    ("dgn_zhuge", "诸葛副本", "changan", [60, 80, 100, 120, 180],
     [280000, 380000, 480000, 580000, 680000], [5, 6, 0], ["sea_gem_longquan_t1"]),
    ("dgn_kid_treasure", "基德的宝藏", "amsterdam", [110, 120],
     [200000, 300000], [1, 6, 0], ["sea_pet_egg_ancient"]),
    ("dgn_tianmo_chaos", "天魔之乱", "venice", [135],
     [500000], [2, 6, 0], ["set_tianmo_armor"]),
    ("dng_couple", "情侣副本", "yangzhou", [135],
     [500000], [3, 6, 0], ["set_haishi"]),
    ("dgn_saintgeorge", "圣乔治广场", "saintgeorge", [120],
     [800000], [1, 2, 3, 4, 5, 6, 0], ["set_tianmo_wand"]),
]

CONSUMABLES = [
    ("sea_med_guyuan", "固元膏", "药品", 5, "解除负面buff"),
    ("sea_med_erguotou", "二锅头", "药品", 5, "解除负面buff"),
    ("sea_med_wanneng", "万能药", "药品", 15, "解除负面buff"),
    ("sea_med_jiedu", "解毒剂", "药品", 8, "解除中毒"),
    ("sea_med_naiping", "奶瓶", "药品", 10, "恢复体力"),
    ("sea_med_tilibao", "体力宝", "药品", 20, "恢复体力"),
    ("sea_exp_double", "双倍经验卡", "经验", 30, "经验加成"),
    ("sea_exp_triple", "三倍经验卡", "经验", 60, "经验加成"),
    ("sea_exp_xuanyuan", "玄元清心丹", "经验", 50, "+1%当前等级经验"),
    ("sea_pet_egg", "宠物蛋", "宠物", 100, "孵化宠物"),
    ("sea_pet_egg_ancient", "远古宠物蛋", "宠物", 500, "孵化远古宠物"),
    ("sea_pet_zizhi", "资质丹", "宠物", 80, "宠物培养"),
    ("sea_pet_shengxing", "升星丹", "宠物", 120, "宠物升星"),
    ("sea_pet_fuhuo", "复活丹", "宠物", 50, "宠物复活"),
    ("sea_pet_xiulian", "修炼丹", "宠物", 40, "宠物修炼"),
    ("sea_pet_mowen", "魔纹果实", "宠物", 200, "宠物40级领悟第9技能"),
    ("sea_equip_longquan_water", "龙泉水", "装备", 30, "装备强化升星"),
    ("sea_equip_longquan_zheng", "正龙泉水", "装备", 100, "装备强化升星"),
    ("sea_equip_shenshui", "强化神水", "装备", 50, "提高强化成功率"),
    ("sea_equip_yuhuo", "浴火之蝶", "装备", 20, "2个合成1奔月碎片"),
    ("sea_equip_benyue_frag", "奔月碎片", "装备", 80, "100碎片=1奔月散件"),
    ("sea_equip_soul_crystal", "灵魂结晶", "装备", 60, "天魔合成/山寨宝库"),
    ("sea_equip_soul_stone", "灵魂晶石", "装备", 80, "觉醒材料"),
    ("sea_equip_dimo_frag", "地魔碎片", "装备", 100, "合成天魔装备"),
    ("sea_equip_tianmo_frag", "天魔碎片", "装备", 150, "合成天魔装备"),
    ("sea_equip_ronghe", "融合剂", "装备", 80, "天魔之乱副本掉落"),
    ("sea_equip_tianmo_cannian", "天魔残念", "装备", 100, "天魔之乱副本掉落"),
    ("sea_equip_haishi_frag", "海誓戒碎片", "装备", 120, "情侣副本掉落"),
    ("sea_equip_kedao", "刻刀", "装备", 90, "情侣副本掉落"),
    ("sea_event_waika", "参赛外卡", "活动", 30, "开普敦踢球/邀请码奖励"),
    ("sea_event_feihuo", "飞火流星", "活动", 30, "开普敦踢球/邀请码奖励"),
    ("sea_event_sanseball", "三色球", "活动", 30, "开普敦踢球/邀请码奖励"),
    ("sea_event_silver_coin", "白银硬币", "活动", 10, "航线入场材料"),
    ("sea_event_gold_coin", "黄金硬币", "活动", 10, "航线入场材料"),
    ("sea_follower_refresh", "随从刷新卡", "随从", 50, "随从操作"),
    ("sea_follower_inherit", "传承之书", "随从", 100, "随从传承"),
    ("sea_follower_qidi", "启迪之书", "随从精灵", 80, "开启技能槽"),
    ("sea_house_license", "房屋建造许可证", "房屋", 200, "房屋建造材料"),
    ("sea_house_gluer", "格鲁尔之牙", "房屋", 150, "房屋建造材料"),
    ("sea_house_snowman", "雪人币", "房屋", 50, "房屋建造材料"),
    ("sea_cur_wuxing_stone", "五行石", "装备", 300, "装备转生材料"),
]

# ---------- v0.1.8：船只/主线任务/宠物技能/城市特产 ----------
SHIPS = [
    ("ship_light_wood", "轻木帆船", "威尼斯", 1000, "铜", 35, 15),
    ("ship_single_mast", "单桅帆船", "威尼斯", 5000, "铜", 55, 15),
    ("ship_single_lateen", "单桅三角帆船", "伦敦", 8000, "铜", 60, 15),
    ("ship_lateen", "三角帆船", "伦敦", 12000, "铜", 65, 15),
    ("ship_light_lateen", "轻型三角帆船", "伦敦", 15000, "铜", 70, 20),
    ("ship_medium", "中型帆船", "伦敦", 30000, "铜", 75, 7),
    ("ship_multi_small", "多桅小型帆船", "开普敦/孟买", 9000, "铜", 60, 7),
    ("ship_mixed_fast", "混合式快船", "开普敦/孟买", 85000, "铜", 80, 30),
    ("ship_flandre", "佛兰德帆船", "开普敦/孟买", 100000, "铜", 90, 46),
    ("ship_chinese", "中国式帆船", "泉州", 150000, "铜", 95, 46),
    ("ship_three_mast", "三桅帆船", "泉州", 200000, "铜", 95, 30),
    ("ship_three_mast_large", "三桅大型帆船", "泉州", 300000, "铜", 100, 61),
    ("ship_spanish_galleon", "西班牙大帆船", "伦敦", 250000, "铜", 100, 92),
    ("ship_ming_yongle", "明永乐大帆船", "商城", 2, "金贝", 150, 76),
]

MAIN_QUESTS = [
    ("mq_meiwei", "美味任务", 10, "基础奖励", 1),
    ("mq_xunyi", "寻裔之路", 30, "基础奖励", 2),
    ("mq_jubaopen", "聚宝盆", 100, "三龙珠碎片", 3),
    ("mq_yaoqi_changan", "妖气长安", 350, "地魔指环(左)、龙珠×2", 4),
    ("mq_dimo_baozang", "地魔宝藏", 550, "地魔防具四件、地魔回魂之恋、龙珠×2", 5),
    ("mq_dila_sword", "蒂拉之剑", 361, "地魔飓风斩、龙珠×1", 6),
    ("mq_tianmo_legend", "天魔传奇", 319, "龙珠×1", 7),
    ("mq_yuli_baochao", "玉历宝钞", 370, "小龙珠×2、聚凝石×2", 8),
    ("mq_fudi_chouxin", "釜底抽薪", 370, "龙珠×1、魑魅魍魉戒指×1", 9),
    ("mq_tianmo_guilai", "天魔归来", 458, "龙珠×1、天魔玄夜战铠设计图", 10),
    ("mq_tiangong_shenjian", "天工神剪", 251, "天魔碧玉腰带/风沙之靴/荆刺设计图", 11),
    ("mq_fengyin_mizhen", "封印迷阵", 450, "最终主线", 12),
]

PET_SKILLS = [
    ("ps_weiya", "威压", "本次战斗中让对手攻防敏降低10%", "T0"),
    ("ps_nuhou", "怒吼", "本次战斗中让自己攻防敏提升10%", "T0"),
    ("ps_mihuo", "迷惑", "20%概率让对手宠物退出战斗", "T0"),
    ("ps_shixue", "嗜血", "20%概率恢复攻击力50%的血量", "T1"),
    ("ps_xieren", "卸刃", "20%概率卸掉对方手持武器", "T0"),
    ("ps_xiejia", "卸甲", "20%概率卸掉对方盔甲", "T0"),
    ("ps_xiepei", "卸配", "20%概率卸掉对方配饰", "T0"),
    ("ps_wudi", "无敌", "20%概率无视对手攻击", "T0"),
    ("ps_boduo", "剥夺", "20%概率清除对手宠物天赋", "T0"),
    ("ps_mianxie", "免卸", "30%概率防止被卸刃/卸甲/卸配", "T0"),
    ("ps_fengxue", "封血", "20%概率阻止敌方自动回血", "T1"),
    ("ps_fengdu", "封毒", "50%概率让对手无法触发中毒", "T2"),
    ("ps_fengma", "封麻", "50%概率让对手无法触发麻痹", "T2"),
    ("ps_fengxu", "封虚", "50%概率让对手无法触发虚弱", "T2"),
    ("ps_shengguang", "圣光", "50%概率让对手无法触发诅咒", "T2"),
    ("ps_jinghua", "净化", "20%概率清除一切负面效果", "T1"),
    ("ps_zhenfu", "振幅", "本次战斗增加20点士气", "T2"),
    ("ps_qingfeng", "清风", "本次战斗增加20点敏捷", "T2"),
    ("ps_yushen", "御身", "本次战斗增加20点防御", "T2"),
    ("ps_liren", "利刃", "本次战斗增加20点攻击", "T2"),
    ("ps_manma", "谩骂", "20%概率将对手幸运值降到最低", "T2"),
    ("ps_shenxu", "身虚", "增加20%虚弱概率", "T2"),
    ("ps_jinzhong", "金钟", "增加10%反弹概率", "T2"),
]

CITY_SPECIALTIES = {
    "venice": ("威尼斯", "地中海", ["葡萄酒", "橄榄油"]),
    "lisbon": ("里斯本", "地中海", ["葡萄干", "盐", "杏仁"]),
    "marseille": ("马赛", "地中海", ["盐", "乳酪"]),
    "athens": ("雅典", "地中海", ["绘画", "雕刻"]),
    "istanbul": ("伊斯坦堡", "地中海", ["丝织品"]),
    "tunis": ("突尼斯", "地中海", ["杏仁", "橄榄油"]),
    "alexandria": ("亚历山大", "地中海", ["橄榄油"]),
    "algiers": ("阿尔及尔", "地中海", ["杏仁", "橄榄油"]),
    "ragusa": ("拉古扎", "地中海", ["杏仁", "橄榄油"]),
    "london": ("伦敦", "北海", ["毛织品", "马铃薯"]),
    "amsterdam": ("阿姆斯特丹", "北海", ["毛织品", "乳酪"]),
    "nantes": ("南特", "北海", ["葡萄酒", "小麦"]),
    "hamburg": ("汉堡", "北海", ["鱼肉", "锦织品"]),
    "oslo": ("奥斯陆", "北海", ["鱼肉", "木材", "绒织品"]),
    "copenhagen": ("哥本哈根", "北海", ["大豆", "牛肉", "玻璃"]),
    "saintgeorge": ("圣乔治", "非洲", ["象牙"]),
    "dakar": ("达喀尔", "非洲", ["盐"]),
    "rwanda": ("卢旺达", "非洲", ["琥珀", "珊瑚"]),
    "capetown": ("开普敦", "非洲", ["鱼肉", "葡萄酒"]),
    "mozambique": ("莫桑比克", "非洲", ["鱼肉", "豆蔻"]),
    "madagascar": ("马达加斯加", "非洲", ["木材", "毛皮"]),
    "mombasa": ("蒙巴萨", "非洲", ["犀牛角", "甜椒"]),
    "aden": ("亚丁", "印度洋", ["咖啡", "小麦"]),
    "hormuz": ("荷姆兹", "印度洋", ["盐"]),
    "ceylon": ("锡兰", "印度洋", ["可可", "香草", "茶"]),
    "mumbai": ("孟买", "印度洋", ["米", "皮草", "胡椒"]),
    "changan": ("长安", "东亚", ["小麦"]),
    "quanzhou": ("泉州", "东亚", ["茶", "陶瓷器"]),
    "kyoto": ("京都", "东亚", ["榛子", "人参"]),
    "osaka": ("大阪", "东亚", ["漆器", "茶具"]),
    "hangzhou": ("杭州", "东亚", ["丝织品"]),
    "guangzhou": ("广州", "东亚", ["麝香"]),
    "yangzhou": ("扬州", "东亚", ["锦花"]),
    "malacca": ("马六甲", "东亚", ["肉桂"]),
}

# ---------- v0.1.6：装备件名 79 ----------
EQUIP_CONFIRMED = [
    ("ep_tianmo_crown", "天魔荆棘皇冠", "set_tianmo_armor", "头盔", 130,
     "主线天工神剪第228环戈迪默处领取设计图，广州铁匠铺欧治子锻造", True),
    ("ep_tianmo_armor", "天魔玄夜战铠", "set_tianmo_armor", "衣服", 130,
     "主线天魔归来第454环击杀天魔尼菲斯获取设计图", True),
    ("ep_tianmo_belt", "天魔碧玉束腰", "set_tianmo_armor", "腰带", 130,
     "主线天工神剪第158环艾斯处领取设计图", True),
    ("ep_tianmo_boots", "天魔风沙之靴", "set_tianmo_armor", "鞋子", 130,
     "主线天工神剪第340环红眼狂刀处领取设计图", True),
    ("ep_tianmo_wand", "天魔轮回权杖", "set_tianmo_wand", "武器", 140,
     "天魔战场/充值/合成", True),
    ("ep_dimo_ring_left", "地魔指环(左)", "set_dimo_ring", "副手", 80,
     "主线妖气长安奖励", True),
    ("ep_dimo_ring_right", "地魔指环(右)", "set_dimo_ring", "副手", 80,
     "妖气长安击杀地魔概率掉落", True),
    ("ep_dimo_huihun", "地魔回魂之恋", "set_dimo_armor", "配饰", 95,
     "主线地魔宝藏奖励", True),
    ("ep_dimo_jufeng", "地魔飓风斩", "set_dila", "武器", 95,
     "主线蒂拉之剑奖励", True),
    ("ep_dimo_lianzhan", "地魔恋战", "set_dimo_lianzhan", "武器", 110,
     "天魔战场兑换", True),
    ("ep_dila_sword", "蒂拉之剑", "set_dila", "武器", 95,
     "主线蒂拉之剑任务赠送", True),
    ("ep_haishi_ring", "海誓戒", "set_haishi", "配饰", 135,
     "情侣副本掉落海誓戒碎片+刻刀合成", True),
    ("ep_wangshi", "往事如风", "set_wangshi", "配饰", 100,
     "散件掉落/交易", True),
    ("ep_shengming", "生命的意义", "set_shengming", "武器", 128,
     "散件掉落/交易", True),
    ("ep_fuchou", "复仇", "set_fuchou", "武器", 159,
     "散件掉落/交易", True),
    ("ep_chimei", "魑魅魍魉", "", "配饰", 1,
     "主线釜底抽薪第150环", True),
    ("ep_lengshi", "冷石弯刀", "", "武器", 1,
     "牛头山怪物掉落", True),
    ("ep_liushi", "流失岁月", "", "配饰", 1,
     "牛头山怪物掉落", True),
    ("ep_benyue_sword", "月剑", "set_benyue", "武器", 30,
     "奔月套装武器/合成/踢球/充值", True),
]

EQUIP_SLOT_SUFFIX = {
    "武器": "之剑", "头盔": "战盔", "衣服": "战甲",
    "腰带": "束腰", "鞋子": "战靴",
}
EQUIP_STANDARD_SLOTS = ["武器", "头盔", "衣服", "腰带", "鞋子"]
EQUIP_ARMOR_SLOTS = ["头盔", "衣服", "腰带", "鞋子"]
EQUIP_GUESSED_SETS = [
    ("set_bushi", "武士", 5, EQUIP_STANDARD_SLOTS, "邀请码赠送/威尼斯探险副本"),
    ("set_columbus", "哥伦布", 30, EQUIP_STANDARD_SLOTS, "威尼斯花园师徒兑换"),
    ("set_bazhe", "霸者", 45, EQUIP_STANDARD_SLOTS, "威尼斯花园师徒兑换"),
    ("set_benyue", "奔月", 30, EQUIP_ARMOR_SLOTS, "开普敦踢球/泉州铁匠铺合成/充值"),
    ("set_magezhe", "麦哲伦", 1, EQUIP_STANDARD_SLOTS, "聚宝盆活动白嫖"),
    ("set_qihai", "七海", 1, EQUIP_STANDARD_SLOTS, "单笔充值198送"),
    ("set_haidao", "海盗王", 1, EQUIP_STANDARD_SLOTS, "单笔充值198送"),
    ("set_dila", "蒂拉", 95, EQUIP_ARMOR_SLOTS, "已基本绝版/主线送蒂拉之剑"),
    ("set_dimo_armor", "地魔", 95, EQUIP_ARMOR_SLOTS, "主线任务地魔宝藏"),
    ("set_xuwu", "虚无", 1, EQUIP_ARMOR_SLOTS, "充值/开普敦踢球极低概率"),
    ("set_lieyan", "烈焰", 1, EQUIP_ARMOR_SLOTS, "充值获取"),
    ("set_sixiang", "四象", 1, EQUIP_ARMOR_SLOTS, "充值/开普敦踢球极低概率"),
    ("set_yutu", "玉兔", 1, EQUIP_STANDARD_SLOTS + ["配饰"], "氪佬专属998三配+998武器+528x4防具"),
]


def seed_sea_full(db: Session, log=print):
    """幂等生成纵横四海完整数据；返回各分类新增计数"""
    stats = {"cities": 0, "routes": 0, "equip_sets": 0, "gems": 0, "cards": 0,
             "holy_marks": 0, "pets": 0, "mounts": 0, "wings": 0, "followers": 0,
             "dungeons": 0, "ships": 0, "quests": 0, "skills": 0,
             "specialties": 0, "pieces": 0, "items": 0}

    # ---------- 1. 城市（20 + 16 补全）群合并进 SeaCity ----------
    for key, name, parent, lvl, intro, area in SEA_CITIES:
        if not db.query(SeaCity).filter(SeaCity.city_code == key).first():
            db.add(SeaCity(city_code=key, name=name, region=area,
                           level_range=f"{lvl}-{lvl + 9}", description=intro,
                           unlock_rule_json=json.dumps({"parent_city": parent, "unlock_level": lvl})))
            stats["cities"] += 1
    for key, name, region, lvl, intro in SEA_CITIES_ADD:
        if not db.query(SeaCity).filter(SeaCity.city_code == key).first():
            db.add(SeaCity(city_code=key, name=name, region=region,
                           level_range=f"{lvl}-{lvl + 9}", description=intro,
                           unlock_rule_json=json.dumps({"unlock_level": lvl})))
            stats["cities"] += 1
    db.commit()
    # 修正里斯本区域标注（v0.1.5 原"亚洲"，spec 为"地中海"）
    lisbon = db.query(SeaCity).filter(SeaCity.city_code == "lisbon").first()
    if lisbon and "亚洲" in (lisbon.description or ""):
        lisbon.region = "地中海"
        lisbon.description = "地中海·白银航线起点，产葡萄干/盐/杏仁"
    db.commit()

    # ---------- 2. 航线 ----------
    existing_routes = {(r.from_city_code, r.to_city_code)
                       for r in db.query(SeaRoute).all()}
    for fc, tc, lvl, ts in ROUTE_PAIRS:
        if (fc, tc) not in existing_routes:
            db.add(SeaRoute(from_city_code=fc, to_city_code=tc,
                            danger_level=lvl, travel_time=ts))
            stats["routes"] += 1
    db.commit()

    # ---------- 3. 装备套装 24 ----------
    for key, name, lvl, src, pieces in EQUIP_SETS:
        if not db.query(SeaEquipSet).filter(SeaEquipSet.key == key).first():
            db.add(SeaEquipSet(key=key, name=name, level_req=lvl, source=src, pieces=pieces))
            stats["equip_sets"] += 1
    db.commit()

    # ---------- 4. 宝石 60 + 物品字典 ----------
    for gkey, gname, effect, slots in GEM_DEFS:
        for tier in range(1, 6):
            key = f"gem_{gkey}_t{tier}"
            if not db.query(SeaGem).filter(SeaGem.key == key).first():
                db.add(SeaGem(key=key, name=f"{GEM_TIER_NAMES[tier]}{gname}",
                              effect=effect, slots=json.dumps(slots, ensure_ascii=False),
                              tier=tier))
                stats["gems"] += 1
            if _ensure_item(db, f"sea_{key}", f"{GEM_TIER_NAMES[tier]}{gname}",
                            "material", tier * 10, f"宝石·{effect}·T{tier}"):
                stats["items"] += 1
    db.commit()

    # ---------- 5. 卡片 21 + 物品字典 ----------
    for key, name, slot, ne, re_, src in CARDS:
        if not db.query(SeaCard).filter(SeaCard.key == key).first():
            db.add(SeaCard(key=key, name=name, slot=slot,
                           normal_effect=ne, refine_effect=re_, drop_source=src))
            stats["cards"] += 1
        if _ensure_item(db, f"sea_{key}", name, "prop", 30,
                        f"卡片·{slot}·普通{ne}/精致{re_}"):
            stats["items"] += 1
    db.commit()

    # ---------- 6. 圣痕 40 ----------
    for nm in HOLY_MARK_NAMES:
        pinyin = HOLY_MARK_PINYIN[nm]
        for q in HOLY_MARK_QUALITIES:
            key = f"hm_{pinyin}_{q}"
            if not db.query(SeaHolyMark).filter(SeaHolyMark.key == key).first():
                db.add(SeaHolyMark(key=key, name=nm, quality=q))
                stats["holy_marks"] += 1
    db.commit()

    # ---------- 7. 宠物 60 ----------
    base_pet = PET_DEFS[0]
    for nm, q, atk, df, agi, hp, tag, src in PET_DEFS:
        for tier_suffix, mul in [("", 1), ("_精", 1.3)]:
            key = f"pet_{nm}{tier_suffix}"
            if not db.query(SeaPet).filter(SeaPet.key == key).first():
                db.add(SeaPet(key=key, name=f"{nm}{tier_suffix}", quality=q,
                              atk=int(atk * mul), defense=int(df * mul),
                              agile=int(agi * mul), hp=int(hp * mul),
                              skill_tag=tag, source=src))
                stats["pets"] += 1
    for v in PET_VARIANTS:
        key = f"pet_{v}{base_pet[0]}"
        if not db.query(SeaPet).filter(SeaPet.key == key).first():
            db.add(SeaPet(key=key, name=f"{v}{base_pet[0]}", quality="橙",
                          atk=80, defense=70, agile=65, hp=550,
                          skill_tag="变种专属", source="活动宠物"))
            stats["pets"] += 1
    db.commit()

    # ---------- 8. 坐骑 12（level_req → level_required）----------
    for key, name, lvl, stype, sval, cat in MOUNTS:
        if not db.query(SeaMount).filter(SeaMount.key == key).first():
            db.add(SeaMount(key=key, name=name, level_required=lvl,
                            stat_type=stype, stat_value=sval, category=cat))
            stats["mounts"] += 1
    db.commit()

    # ---------- 9. 羽翼 8（level_req → level_required）----------
    for key, name, lvl, eff in WINGS:
        if not db.query(SeaWing).filter(SeaWing.key == key).first():
            db.add(SeaWing(key=key, name=name, level_required=lvl,
                           effects=json.dumps(eff, ensure_ascii=False)))
            stats["wings"] += 1
    db.commit()

    # ---------- 10. 随从 9 ----------
    for key, name, sn, sd, q in FOLLOWERS:
        if not db.query(SeaFollower).filter(SeaFollower.key == key).first():
            db.add(SeaFollower(key=key, name=name, skill_name=sn,
                               skill_desc=sd, quality=q))
            stats["followers"] += 1
    db.commit()

    # ---------- 11. 副本 10 ----------
    for key, name, city, lreqs, exps, days, drops in DUNGEONS:
        if not db.query(SeaDungeon).filter(SeaDungeon.key == key).first():
            db.add(SeaDungeon(key=key, name=name, entry_city=city,
                              difficulties=json.dumps(DUNGEON_DIFFS[:len(lreqs)], ensure_ascii=False),
                              level_reqs=json.dumps(lreqs), exps=json.dumps(exps),
                              drops=json.dumps(drops, ensure_ascii=False),
                              open_days=json.dumps(days)))
            stats["dungeons"] += 1
    db.commit()

    # ---------- 12. 消耗品/道具物品字典 41 ----------
    for key, name, cat, price, desc in CONSUMABLES:
        if _ensure_item(db, key, name, "prop", price, desc):
            stats["items"] += 1
    db.commit()

    # ---------- 13. 船只 14 + 物品字典 ----------
    for key, name, buy_city, price, currency, load, consume in SHIPS:
        item_key = f"sea_{key}"
        if _ensure_item(db, item_key, name, "ship", price,
                        f"船只·载重{load}·消耗{consume}铜/百海里·{buy_city}购买"):
            stats["items"] += 1
        if not db.query(SeaShip).filter(SeaShip.key == key).first():
            db.add(SeaShip(key=key, name=name, buy_city=buy_city, price=price,
                           currency=currency, load=load, consume_per_100=consume))
            stats["ships"] += 1
    db.commit()

    # ---------- 14. 主线任务 12 ----------
    for key, name, rounds, reward, sort in MAIN_QUESTS:
        if not db.query(SeaMainQuest).filter(SeaMainQuest.key == key).first():
            db.add(SeaMainQuest(key=key, name=name, rounds=rounds,
                                reward_desc=reward, sort=sort))
            stats["quests"] += 1
    db.commit()

    # ---------- 15. 宠物技能 23 ----------
    for key, name, effect, tier in PET_SKILLS:
        if not db.query(SeaPetSkill).filter(SeaPetSkill.key == key).first():
            db.add(SeaPetSkill(key=key, name=name, effect=effect, tier=tier))
            stats["skills"] += 1
    db.commit()

    # ---------- 16. 城市特产 34 ----------
    for city_key, (city_name, region, specs) in CITY_SPECIALTIES.items():
        if not db.query(SeaCitySpecialty).filter(SeaCitySpecialty.city_key == city_key).first():
            db.add(SeaCitySpecialty(city_key=city_key, city_name=city_name, region=region,
                                    specialties=json.dumps(specs, ensure_ascii=False)))
            stats["specialties"] += 1
    db.commit()

    # ---------- 17. 装备件名 79 ----------
    pieces = []
    for key, name, set_key, slot, lvl, src, conf in EQUIP_CONFIRMED:
        if not db.query(SeaEquipPiece).filter(SeaEquipPiece.key == key).first():
            db.add(SeaEquipPiece(key=key, name=name, set_key=set_key, slot=slot,
                                 level_req=lvl, source=src, confirmed=conf))
            stats["pieces"] += 1
    for set_key, prefix, lvl, slots, src in EQUIP_GUESSED_SETS:
        for slot in slots:
            suffix = "戒" if slot == "配饰" else EQUIP_SLOT_SUFFIX[slot]
            name = f"{prefix}{suffix}"
            key = f"ep_{set_key[4:]}_{slot}"
            if not db.query(SeaEquipPiece).filter(SeaEquipPiece.key == key).first():
                db.add(SeaEquipPiece(key=key, name=name, set_key=set_key, slot=slot,
                                     level_req=lvl, source=src, confirmed=False))
                stats["pieces"] += 1
    db.commit()

    log(f"[sea-full] 城市+{stats['cities']} 航线+{stats['routes']} 套装+{stats['equip_sets']} "
        f"宝石+{stats['gems']} 卡片+{stats['cards']} 圣痕+{stats['holy_marks']} 宠物+{stats['pets']} "
        f"坐骑+{stats['mounts']} 羽翼+{stats['wings']} 随从+{stats['followers']} 副本+{stats['dungeons']} "
        f"船只+{stats['ships']} 主线+{stats['quests']} 技能+{stats['skills']} 特产+{stats['specialties']} "
        f"装备件+{stats['pieces']} 物品字典+{stats['items']}")
    return stats