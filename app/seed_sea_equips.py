"""纵横四海装备件名生成器（v0.1.6 · spec 全部装备件名清单）

按 spec《纵横四海全部装备件名》补齐装备部件件名：
- 官方确认件名 19 个（confirmed=True，来自主线文本/百科）
- 命名规律推测件名 ~55 个（confirmed=False，按命名后缀规律生成）

命名规律（spec 归纳）：
- 武器: 剑/斩/权杖/弯刀/指环
- 头盔: 皇冠/战盔
- 衣服: 战铠/战甲
- 腰带: 束腰
- 鞋子: 战靴/之靴
- 配饰: 戒/恋/配饰

幂等：以 key 存在性判断，已存在则跳过；可断点续跑。
闭环：set_key 引用 SeaEquipSet.key（散件 set_key 为空）。
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import models


async def seed_sea_equips(db: AsyncSession, log=print):
    """幂等生成纵横四海装备件名；返回新增计数"""
    stats = {"confirmed": 0, "guessed": 0}

    # ---------- 1. 官方确认件名 19 个（confirmed=True）----------
    confirmed = [
        # 天魔防具套装（130级，4件防具）
        ("ep_tianmo_crown", "天魔荆棘皇冠", "set_tianmo_armor", "头盔", 130,
         "主线天工神剪第228环戈迪默处领取设计图，广州铁匠铺欧治子锻造", True),
        ("ep_tianmo_armor", "天魔玄夜战铠", "set_tianmo_armor", "衣服", 130,
         "主线天魔归来第454环击杀天魔尼菲斯获取设计图", True),
        ("ep_tianmo_belt", "天魔碧玉束腰", "set_tianmo_armor", "腰带", 130,
         "主线天工神剪第158环艾斯处领取设计图", True),
        ("ep_tianmo_boots", "天魔风沙之靴", "set_tianmo_armor", "鞋子", 130,
         "主线天工神剪第340环红眼狂刀处领取设计图", True),
        # 天魔武器（140级）
        ("ep_tianmo_wand", "天魔轮回权杖", "set_tianmo_wand", "武器", 140,
         "天魔战场/充值/合成", True),
        # 地魔双环（80级，2件副手）
        ("ep_dimo_ring_left", "地魔指环(左)", "set_dimo_ring", "副手", 80,
         "主线妖气长安奖励", True),
        ("ep_dimo_ring_right", "地魔指环(右)", "set_dimo_ring", "副手", 80,
         "妖气长安击杀地魔概率掉落", True),
        # 地魔防具套装奖励配饰
        ("ep_dimo_huihun", "地魔回魂之恋", "set_dimo_armor", "配饰", 95,
         "主线地魔宝藏奖励", True),
        # 地魔武器
        ("ep_dimo_jufeng", "地魔飓风斩", "set_dila", "武器", 95,
         "主线蒂拉之剑奖励", True),
        # 地魔恋战（110级）
        ("ep_dimo_lianzhan", "地魔恋战", "set_dimo_lianzhan", "武器", 110,
         "天魔战场兑换", True),
        # 蒂拉之剑
        ("ep_dila_sword", "蒂拉之剑", "set_dila", "武器", 95,
         "主线蒂拉之剑任务赠送", True),
        # 海誓戒（135级）
        ("ep_haishi_ring", "海誓戒", "set_haishi", "配饰", 135,
         "情侣副本掉落海誓戒碎片+刻刀合成", True),
        # 强力散件
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
        # 奔月套装武器（30级）
        ("ep_benyue_sword", "月剑", "set_benyue", "武器", 30,
         "奔月套装武器/合成/踢球/充值", True),
    ]
    for key, name, set_key, slot, lvl, src, conf in confirmed:
        if not await db.get(models.SeaEquipPiece, key):
            db.add(models.SeaEquipPiece(key=key, name=name, set_key=set_key, slot=slot,
                                        level_req=lvl, source=src, confirmed=conf))
            stats["confirmed"] += 1
    await db.commit()

    # ---------- 2. 命名规律推测件名（confirmed=False）----------
    # 部位后缀映射（spec 命名规律）
    slot_suffix = {
        "武器": "之剑", "头盔": "战盔", "衣服": "战甲",
        "腰带": "束腰", "鞋子": "战靴",
    }
    # 标准防具四件 + 武器（多数套装结构）
    standard_slots = ["武器", "头盔", "衣服", "腰带", "鞋子"]
    armor_only_slots = ["头盔", "衣服", "腰带", "鞋子"]  # 纯防具套装

    # (set_key, 套装前缀, level_req, slots, source)
    guessed_sets = [
        # 武士套装（5级，武器+4防具）
        ("set_bushi", "武士", 5, standard_slots, "邀请码赠送/威尼斯探险副本"),
        # 哥伦布套装（30级）
        ("set_columbus", "哥伦布", 30, standard_slots, "威尼斯花园师徒兑换"),
        # 霸者套装（45级）
        ("set_bazhe", "霸者", 45, standard_slots, "威尼斯花园师徒兑换"),
        # 奔月套装（30级，武器已确认，仅补防具4件）
        ("set_benyue", "奔月", 30, armor_only_slots, "开普敦踢球/泉州铁匠铺合成/充值"),
        # 麦哲伦套装
        ("set_magezhe", "麦哲伦", 1, standard_slots, "聚宝盆活动白嫖"),
        # 七海套装
        ("set_qihai", "七海", 1, standard_slots, "单笔充值198送"),
        # 海盗王套装
        ("set_haidao", "海盗王", 1, standard_slots, "单笔充值198送"),
        # 蒂拉套装（武器已确认，仅补防具4件）
        ("set_dila", "蒂拉", 95, armor_only_slots, "已基本绝版/主线送蒂拉之剑"),
        # 地魔防具套装（95级，复刻版命名推测）
        ("set_dimo_armor", "地魔", 95, armor_only_slots, "主线任务地魔宝藏"),
        # 虚无套装（纯防具）
        ("set_xuwu", "虚无", 1, armor_only_slots, "充值/开普敦踢球极低概率"),
        # 烈焰套装（纯防具）
        ("set_lieyan", "烈焰", 1, armor_only_slots, "充值获取"),
        # 四象圣套（纯防具）
        ("set_sixiang", "四象", 1, armor_only_slots, "充值/开普敦踢球极低概率"),
        # 玉兔套装（武器+4防具+配饰，氪佬专属）
        ("set_yutu", "玉兔", 1, standard_slots + ["配饰"], "氪佬专属998三配+998武器+528x4防具"),
    ]
    for set_key, prefix, lvl, slots, src in guessed_sets:
        for slot in slots:
            suffix = "戒" if slot == "配饰" else slot_suffix[slot]
            name = f"{prefix}{suffix}"
            key = f"ep_{set_key[4:]}_{slot}"
            if not await db.get(models.SeaEquipPiece, key):
                db.add(models.SeaEquipPiece(key=key, name=name, set_key=set_key, slot=slot,
                                            level_req=lvl, source=src, confirmed=False))
                stats["guessed"] += 1
    await db.commit()

    log(f"[sea-equips] 官方确认件名+{stats['confirmed']} 命名规律推测件名+{stats['guessed']}")
    return stats
