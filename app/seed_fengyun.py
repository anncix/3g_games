"""风云三国生成器（v0.2.0 · spec 三国 MMORPG 全系统资料库 + 全网检索补全）

按 spec《QQ风云三国全系统资料》落地 v0.2.0 新增模块：
- 13 城市（蜀4 / 魏4 / 吴3 / 中立2，spec 三区域城市 + 中立洛阳）
- 30 技能（3 职业 × 10 技能，4 类型 active/passive/auxiliary/status）
- 装备库（5 品质 × 7 部位 × 3 等级档位 = 105 件，覆盖 spec "上千件装备"样例规模）
- v0.2.0 官方装备系列（7 系列 × 7 件套 = 48 件，全网检索补全 doc88.com 道具编码表）
  百战(白·1级)/烈风(蓝·1级)/凰霞(绿·16级)/龙翔(蓝·30级)/霆震(紫·50级)/霆震·精(紫+·60级)/幻灵(橙·70级)
- v0.2.0 顶级名器（11 件，spec 明示十大名剑 + 三国名器）
  鱼肠剑/七星龙渊剑/巨阙剑/承影剑/七圣刀 + 倚天剑/丈八蛇矛/方天画戟/青龙偃月刀/龙胆枪/华蜓
- v0.2.0 顶级 BOSS/神兽（14 只，spec 明示龙之九子 + 烛龙 + 四大神兽）
- 13 副本（蜀4 + 魏4 + 吴3 + 终极2，覆盖 spec 等级段 16-60）
- 5 级军团等级（spec 军团系统）
- 15 称号（6 前缀 + 6 后缀 + 3 配对隐藏，spec 称号系统）
- 21 成就（3 难度 × 9 类型，spec 成就系统 12 类型样例）
- 虎符道具（军团创建/升级）+ 演武/魔钻相关消耗品

设计：
- 静态常量从 routers/fengyun_data.py 引入，本生成器只负责入库（幂等）
- 装备按品质×部位×等级档批量生成，落 Item 字典 + FengyunEquip 表
- 装备 key 规范：fy_eq_{quality_pinyin}_{slot_pinyin}_{lvl}
- v0.2.0 官方系列装备 key 规范：fy_s_{series}_{slot}，主属性按 spec 精确数值
- v0.2.0 顶级名器 key 规范：fy_nw_{name}，BOSS key 规范：boss_{name}
- 全部物品同步落 Item 字典（module_key=fengyun），可被背包/商店引用

幂等：以 key 存在性判断，已存在则跳过；可断点续跑。
闭环：城市→副本入口引用城市 key；技能→职业 key；装备→品质/部位全覆盖。
"""
from sqlalchemy.ext.asyncio import AsyncSession

from . import models
from .platform import goods
from .routers import fengyun_data as FY


# 品质 / 部位拼音缩写
_QUALITY_PINYIN = {"普通": "pt", "精良": "jl", "卓越": "zy", "史诗": "ss", "神器": "sq"}
_SLOT_PINYIN = {"头": "tou", "手": "shou", "衣": "yi", "腿": "tui", "鞋": "xie", "裤子": "kuzi", "饰品": "shipin"}

# 装备生成档位（等级需求）
_EQUIP_LEVEL_TIERS = [10, 30, 50]


async def seed_fengyun(db: AsyncSession, log=print) -> dict:
    """幂等生成风云三国 v0.1.9 全量数据；返回新增计数"""
    stats = {
        "cities": 0, "skills": 0, "equips": 0, "dungeons": 0,
        "titles": 0, "achievements": 0, "items": 0,
        "series_equips": 0, "named_weapons": 0, "bosses": 0,
    }

    # ---------- 1. 14 城市（spec：魏蜀吴三区域 + 中立洛阳）----------
    for key, name, faction, intro in FY.CITIES:
        if not await db.get(models.FengyunCity, key):
            db.add(models.FengyunCity(key=key, name=name, faction=faction, intro=intro))
            stats["cities"] += 1
    await db.commit()

    # ---------- 2. 30 技能（spec：3 职业 × 10 技能，4 类型）----------
    for key, name, cls, stype, ulvl, csilver, cexp, effect in FY.SKILLS:
        if not await db.get(models.FengyunSkill, key):
            db.add(models.FengyunSkill(
                key=key, name=name, class_key=cls, skill_type=stype,
                unlock_level=ulvl, cost_silver=csilver, cost_exp=cexp, effect=effect,
            ))
            stats["skills"] += 1
    await db.commit()

    # ---------- 3. 装备库（5 品质 × 7 部位 × 3 等级档 = 105 件）----------
    for quality in FY.EQUIP_QUALITIES:
        qpy = _QUALITY_PINYIN[quality]
        for slot in FY.EQUIP_SLOTS:
            spy = _SLOT_PINYIN[slot]
            for lvl in _EQUIP_LEVEL_TIERS:
                key = f"fy_eq_{qpy}_{spy}_{lvl}"
                name = f"{quality}{slot}·{('初阶' if lvl == 10 else '中阶' if lvl == 30 else '高阶')}"
                stats_b = FY.gen_equip_stats(slot, quality, lvl)
                price = FY.gen_equip_price(quality, lvl)

                # 落 Item 字典（装备作为可堆叠=N 的物品）
                if not await goods.get_item_by_key(db, key):
                    await goods.ensure_item(
                        db, key, name, "equip", "fengyun", False, price,
                        f"{quality}品质{slot}部位置备，需求等级{lvl}"
                    )
                    stats["items"] += 1

                # 落 FengyunEquip 表
                if not await db.get(models.FengyunEquip, key):
                    db.add(models.FengyunEquip(
                        key=key, name=name, quality=quality, slot=slot,
                        class_req="",  # 通用装备
                        level_req=lvl,
                        atk_bonus=stats_b.get("atk_bonus", 0),
                        def_bonus=stats_b.get("def_bonus", 0),
                        hp_bonus=stats_b.get("hp_bonus", 0),
                        price=price,
                    ))
                    stats["equips"] += 1
    await db.commit()

    # ---------- 3b. v0.2.0 官方装备系列（7 系列 × 7 件套，全网检索补全）----------
    # 来源：doc88.com 道具编码表，spec 明示百战/烈风/凰霞/龙翔/霆震/霆震·精/幻灵
    for key, name, slot, cls_req, quality, lvl, attr_key, attr_val in FY.EQUIP_SERIES:
        # 落 Item 字典
        if not await goods.get_item_by_key(db, key):
            await goods.ensure_item(
                db, key, name, "equip", "fengyun", False,
                FY.gen_equip_price(quality, lvl),
                f"{quality}品质{slot}（{cls_req}），需求等级{lvl}，{attr_key}+{attr_val}"
            )
            stats["items"] += 1
        # 落 FengyunEquip 表（主属性按 spec 精确数值）
        if not await db.get(models.FengyunEquip, key):
            atk_b = attr_val if attr_key == "atk" else 0
            def_b = attr_val if attr_key == "def" else 0
            db.add(models.FengyunEquip(
                key=key, name=name, quality=quality, slot=slot,
                class_req=cls_req if cls_req != "all" else "",
                level_req=lvl,
                atk_bonus=atk_b, def_bonus=def_b, hp_bonus=0,
                price=FY.gen_equip_price(quality, lvl),
            ))
            stats["series_equips"] += 1
    await db.commit()

    # ---------- 3c. v0.2.0 顶级名器（11 件，spec 明示十大名剑 + 三国名器）----------
    for key, name, wtype, cls_req, quality, lvl, attr_key, attr_val, drop_from in FY.NAMED_WEAPONS:
        if not await goods.get_item_by_key(db, key):
            await goods.ensure_item(
                db, key, name, "equip", "fengyun", False,
                FY.gen_equip_price(quality, lvl),
                f"{quality}品质{wtype}（{cls_req}），需求等级{lvl}，{attr_key}+{attr_val}。{drop_from}"
            )
            stats["items"] += 1
        if not await db.get(models.FengyunEquip, key):
            atk_b = attr_val if attr_key == "atk" else 0
            def_b = attr_val if attr_key == "def" else 0
            db.add(models.FengyunEquip(
                key=key, name=name, quality=quality, slot=wtype,
                class_req=cls_req if cls_req != "all" else "",
                level_req=lvl,
                atk_bonus=atk_b, def_bonus=def_b, hp_bonus=0,
                price=FY.gen_equip_price(quality, lvl),
            ))
            stats["named_weapons"] += 1
    await db.commit()

    # ---------- 3d. v0.2.0 顶级 BOSS/神兽掉落表（14 只，spec 明示龙之九子+烛龙+四大神兽）----------
    # 仅落 Item 字典作为 BOSS 凭证（战斗系统引用），不入 FengyunEquip 表
    for boss_key, boss_name, boss_lvl, boss_type, drop_quality, boss_intro in FY.WORLD_BOSSES:
        item_key = f"fy_boss_token_{boss_key}"
        if not await goods.get_item_by_key(db, item_key):
            await goods.ensure_item(
                db, item_key, f"{boss_name}凭证", "material", "fengyun", True,
                FY.gen_equip_price(drop_quality, boss_lvl),
                f"{boss_type}级 BOSS【{boss_name}】(Lv.{boss_lvl}) 击杀凭证。{boss_intro}。掉落{drop_quality}品质装备"
            )
            stats["items"] += 1
            stats["bosses"] += 1
    await db.commit()

    # ---------- 4. 军团虎符道具（spec：5 级军团，虎符升级道具）----------
    for lvl, _, _, item_name in FY.LEGION_LEVELS:
        key = f"fy_tiger_fu_{lvl}"
        if not await goods.get_item_by_key(db, key):
            await goods.ensure_item(
                db, key, item_name, "material", "fengyun", True, 500 * lvl,
                f"{item_name}：军团升至 {lvl} 级所需道具"
            )
            stats["items"] += 1
    await db.commit()

    # ---------- 5. 13 副本（spec：按阵营 × 等级段）----------
    for key, name, faction, lmin, lmax, city, npc, exp, silver in FY.DUNGEONS:
        if not await db.get(models.FengyunDungeon, key):
            db.add(models.FengyunDungeon(
                key=key, name=name, faction=faction,
                level_min=lmin, level_max=lmax,
                city=city, npc=npc,
                reward_exp=exp, reward_silver=silver,
            ))
            stats["dungeons"] += 1
    await db.commit()

    # ---------- 6. 14 称号（spec：前缀+后缀+配对，激发隐藏属性）----------
    for key, name, ttype, grade, hp, atk, df in FY.TITLES:
        if not await db.get(models.FengyunTitle, key):
            db.add(models.FengyunTitle(
                key=key, name=name, title_type=ttype, grade=grade,
                hp_bonus=hp, atk_bonus=atk, def_bonus=df,
            ))
            stats["titles"] += 1
    await db.commit()

    # ---------- 7. 20 成就（spec：3 难度 × 9 类型样例）----------
    for key, name, diff, cat, desc, hp, mp, atk, df, dodge, crit in FY.ACHIEVEMENTS:
        if not await db.get(models.FengyunAchievement, key):
            db.add(models.FengyunAchievement(
                key=key, name=name, difficulty=diff, category=cat, desc=desc,
                hp_bonus=hp, mp_bonus=mp, atk_bonus=atk, def_bonus=df,
                dodge_bonus=dodge, crit_bonus=crit,
            ))
            stats["achievements"] += 1
    await db.commit()

    # ---------- 8. 演武/魔钻相关消耗品 ----------
    consumables = [
        ("fy_exp_card_2x", "双倍经验卡",  100, "使用后 1 小时内打怪经验翻倍"),
        ("fy_hp_potion",   "回血丹",       20, "战斗中恢复 200 HP"),
        ("fy_mp_potion",   "回蓝丹",       30, "战斗中恢复 100 MP"),
        ("fy_yuanfen",     "缘分值包",    200, "增加 1 点缘分值（创建军团消耗）"),
        ("fy_silver_pack", "银两包",       50, "打开获得 1000 银两"),
        ("fy_moz_monthly", "魔钻月卡",   1200, "30 天魔钻特权（6 大特权）"),
    ]
    for key, name, price, desc in consumables:
        if not await goods.get_item_by_key(db, key):
            await goods.ensure_item(db, key, name, "prop", "fengyun", True, price, desc)
            stats["items"] += 1
    await db.commit()

    log(f"[fengyun-v020] 城市+{stats['cities']} 技能+{stats['skills']} "
        f"装备+{stats['equips']} 官方系列+{stats['series_equips']} 名器+{stats['named_weapons']} "
        f"BOSS+{stats['bosses']} 副本+{stats['dungeons']} "
        f"称号+{stats['titles']} 成就+{stats['achievements']} "
        f"物品字典+{stats['items']}")
    return stats
