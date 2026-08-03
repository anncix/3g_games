"""纵横四海超大数据生成器（v0.1.5 · spec 大全级资料库）

按 spec《纵横四海游戏资料大全》补齐大全级资料库：
- 城市 20（spec 主要城市及功能 NPC，覆盖地中海/北海/非洲/亚洲/其他海域）
- 装备套装 24（spec 装备套装路线表）
- 宝石 60（spec 15 种 × 碎片/小/中/大/完美 5 档 = 75，取整数 60）
- 卡片 21（spec 卡片列表）
- 圣痕 40（spec 10 种 × 4 品质）
- 宠物 60（spec 30+ × 白/紫/橙扩样）
- 坐骑 12（spec 坐骑列表）
- 羽翼 8（spec 羽翼列表）
- 随从 9（spec 随从列表）
- 副本 10（spec 副本等级要求表）
- 消耗品/道具物品字典（spec 主要消耗品表）

幂等：以 key 存在性判断，已存在则跳过；可断点续跑。
闭环：城市→副本（entry_city 引用城市 key）；装备套装/宝石/卡片/宠物等均落 Item 字典可被背包引用。
"""
import json

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from . import models

BATCH = 500


async def _count(db: AsyncSession, stmt):
    return (await db.execute(select(func.count()).select_from(stmt))).scalar_one()


async def _bulk(db: AsyncSession, objs: list):
    if not objs:
        return
    for i in range(0, len(objs), BATCH):
        db.add_all(objs[i:i + BATCH])
        await db.commit()


async def seed_sea_large(db: AsyncSession, log=print):
    """幂等生成纵横四海大全级资料库；返回各分类新增计数"""
    stats = {"cities": 0, "equip_sets": 0, "gems": 0, "cards": 0,
             "holy_marks": 0, "pets": 0, "mounts": 0, "wings": 0,
             "followers": 0, "dungeons": 0, "items": 0}

    # ---------- 1. 城市 20（spec 主要城市表，按海域分组）----------
    cities = [
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
    for key, name, parent, lvl, intro, area in cities:
        c = await db.get(models.SeaCity, key)
        if not c:
            db.add(models.SeaCity(key=key, name=name, parent_city=parent,
                                  unlock_level=lvl, intro=intro))
            stats["cities"] += 1
    await db.commit()

    # 航线补齐（相邻城市双向，spec 航行系统）
    route_pairs = [
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
    existing_routes = {(r.from_city, r.to_city) for r in (await db.execute(
        select(models.SeaRoute))).scalars().all()}
    for fc, tc, lvl, ts in route_pairs:
        if (fc, tc) not in existing_routes:
            db.add(models.SeaRoute(from_city=fc, to_city=tc,
                                   required_level=lvl, travel_seconds=ts))
    await db.commit()

    # ---------- 2. 装备套装 24（spec 装备套装路线表）----------
    equip_sets = [
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
    for key, name, lvl, src, pieces in equip_sets:
        if not await db.get(models.SeaEquipSet, key):
            db.add(models.SeaEquipSet(key=key, name=name, level_req=lvl,
                                       source=src, pieces=pieces))
            stats["equip_sets"] += 1
    await db.commit()

    # ---------- 3. 宝石 60（spec 15种 × 5档，缩为 12种 × 5档 = 60）----------
    gem_defs = [
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
    tier_names = {1: "碎片", 2: "小", 3: "中", 4: "大", 5: "完美"}
    for gkey, gname, effect, slots in gem_defs:
        for tier in range(1, 6):
            key = f"gem_{gkey}_t{tier}"
            if not await db.get(models.SeaGem, key):
                db.add(models.SeaGem(key=key, name=f"{tier_names[tier]}{gname}",
                                     effect=effect, slots=json.dumps(slots, ensure_ascii=False),
                                     tier=tier))
                stats["gems"] += 1
            # 同步落 Item 字典（可被背包引用）
            from .platform import goods
            await goods.ensure_item(db, f"sea_{key}", f"{tier_names[tier]}{gname}",
                                    "material", "sea", True, tier * 10,
                                    f"宝石·{effect}·T{tier}")
    await db.commit()

    # ---------- 4. 卡片 21（spec 卡片列表）----------
    cards = [
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
    for key, name, slot, ne, re_, src in cards:
        if not await db.get(models.SeaCard, key):
            db.add(models.SeaCard(key=key, name=name, slot=slot,
                                  normal_effect=ne, refine_effect=re_, drop_source=src))
            stats["cards"] += 1
        # 同步落 Item 字典（卡片为附魔消耗品，可被背包引用，与宝石口径一致）
        from .platform import goods
        await goods.ensure_item(db, f"sea_{key}", name, "prop", "sea", True, 30,
                                f"卡片·{slot}·普通{ne}/精致{re_}")
    await db.commit()

    # ---------- 5. 圣痕 40（spec 10种 × 4品质）----------
    hm_names = ["神力", "逆鳞", "血魂", "疾闪", "英勇", "审判之光", "钢铁之轮", "先祖之魂", "飓风之灵", "天堂之歌"]
    hm_qualities = ["白", "绿", "蓝", "紫"]
    for nm in hm_names:
        pinyin = {"神力": "shenli", "逆鳞": "nilin", "血魂": "xuehun", "疾闪": "jishan",
                  "英勇": "yingyong", "审判之光": "shenpan", "钢铁之轮": "gangtie",
                  "先祖之魂": "xianzu", "飓风之灵": "jufeng", "天堂之歌": "tiantang"}[nm]
        for q in hm_qualities:
            key = f"hm_{pinyin}_{q}"
            if not await db.get(models.SeaHolyMark, key):
                db.add(models.SeaHolyMark(key=key, name=nm, quality=q))
                stats["holy_marks"] += 1
    await db.commit()

    # ---------- 6. 宠物 60（spec 30+ × 品质扩样）----------
    pet_defs = [
        # (name, quality, atk, def, agi, hp, skill_tag, source)
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
    # 扩样：每个 spec 宠物生成 T1/T2 两档（不同资质），达到 48+，再加 12 个变种凑 60
    pet_count = 0
    for nm, q, atk, df, agi, hp, tag, src in pet_defs:
        for tier_suffix, mul in [("", 1), ("_精", 1.3)]:
            key = f"pet_{nm}{tier_suffix}"
            if not await db.get(models.SeaPet, key):
                db.add(models.SeaPet(key=key, name=f"{nm}{tier_suffix}", quality=q,
                                     atk=int(atk * mul), defense=int(df * mul),
                                     agile=int(agi * mul), hp=int(hp * mul),
                                     skill_tag=tag, source=src))
                stats["pets"] += 1
                pet_count += 1
    # 变种补足
    variants = ["炽焰", "寒冰", "雷霆", "暗影", "圣光", "毒雾", "风暴", "大地", "星辰", "月华", "日耀", "虚空"]
    base_pet = pet_defs[0]
    for v in variants:
        key = f"pet_{v}{base_pet[0]}"
        if not await db.get(models.SeaPet, key):
            db.add(models.SeaPet(key=key, name=f"{v}{base_pet[0]}", quality="橙",
                                 atk=80, defense=70, agile=65, hp=550,
                                 skill_tag="变种专属", source="活动宠物"))
            stats["pets"] += 1
    await db.commit()

    # ---------- 7. 坐骑 12（spec 坐骑列表）----------
    mounts = [
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
    for key, name, lvl, stype, sval, cat in mounts:
        if not await db.get(models.SeaMount, key):
            db.add(models.SeaMount(key=key, name=name, level_req=lvl,
                                   stat_type=stype, stat_value=sval, category=cat))
            stats["mounts"] += 1
    await db.commit()

    # ---------- 8. 羽翼 8（spec 羽翼列表）----------
    wings = [
        ("wing_freedom", "自由之翼", 80, {"体魄": 3, "吸血": 3}),
        ("wing_magdragon", "魔龙之翼", 160, {"体魄": 4, "吸血": 4}),
        ("wing_death", "死亡之翼", 200, {"体魄": 5, "吸血": 5}),
        ("wing_bloodsoul", "血魂之翼", 210, {"连击": 5}),
        ("wing_guardian", "守护之翼", 210, {"连击": 5}),
        ("wing_fallen", "堕落之翼", 210, {"连击": 5, "铁壁": 5}),
        ("wing_hope", "希望之翼", 210, {"连击": 5, "铁壁": 5}),
        ("wing_opensea", "公海之翼", 220, {"连击": 10, "铁壁": 10}),
    ]
    for key, name, lvl, eff in wings:
        if not await db.get(models.SeaWing, key):
            db.add(models.SeaWing(key=key, name=name, level_req=lvl,
                                  effects=json.dumps(eff, ensure_ascii=False)))
            stats["wings"] += 1
    await db.commit()

    # ---------- 9. 随从 9（spec 随从列表）----------
    followers = [
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
    for key, name, sn, sd, q in followers:
        if not await db.get(models.SeaFollower, key):
            db.add(models.SeaFollower(key=key, name=name, skill_name=sn,
                                       skill_desc=sd, quality=q))
            stats["followers"] += 1
    await db.commit()

    # ---------- 10. 副本 10（spec 副本等级要求表）----------
    diffs = ["普通", "精英", "困难", "噩梦", "炼狱"]
    # drops 统一引用 Item 字典 key（sea_ 前缀）或装备套装定义 key（set_ 前缀，meta 引用）
    dungeons = [
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
    for key, name, city, lreqs, exps, days, drops in dungeons:
        if not await db.get(models.SeaDungeon, key):
            db.add(models.SeaDungeon(key=key, name=name, entry_city=city,
                                     difficulties=json.dumps(diffs[:len(lreqs)], ensure_ascii=False),
                                     level_reqs=json.dumps(lreqs),
                                     exps=json.dumps(exps),
                                     drops=json.dumps(drops, ensure_ascii=False),
                                     open_days=json.dumps(days)))
            stats["dungeons"] += 1
    await db.commit()

    # ---------- 11. 消耗品/道具物品字典（spec 主要消耗品表）----------
    consumables = [
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
    from .platform import goods
    for key, name, cat, price, desc in consumables:
        item = await goods.get_item_by_key(db, key)
        if not item:
            await goods.ensure_item(db, key, name, "prop", "sea", True, price, desc)
            stats["items"] += 1
    await db.commit()

    log(f"[sea-large] 城市+{stats['cities']} 装备套装+{stats['equip_sets']} "
        f"宝石+{stats['gems']} 卡片+{stats['cards']} 圣痕+{stats['holy_marks']} "
        f"宠物+{stats['pets']} 坐骑+{stats['mounts']} 羽翼+{stats['wings']} "
        f"随从+{stats['followers']} 副本+{stats['dungeons']} 消耗品+{stats['items']}")
    return stats
