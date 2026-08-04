"""风云三国生成器（同步 SQLAlchemy 版）

由 /Users/mubai/3g_games/app/seed_fengyun.py 迁移改写：
- 异步 `await db.get(...)` -> 同步 `db.query(...).filter(...).first()`
- 模型挂载到 qqgames 新表（FengyunCity 等 11 张 + ItemFengyun 物品字典）
- 幂等：以 key 存在性判断，已存在则跳过；可断点续跑；分批提交

数据量（与 3g_games 保持一致）：
- 13 城市（CITIES）
- 30 技能（SKILLS，3 职业 × 10）
- 105 装备（EQUIP 质量 × 部位 × 等级档，用 gen_equip_stats 生成）
- 48 系列装备（EQUIP_SERIES）
- 11 名器（NAMED_WEAPONS）
- 14 BOSS（WORLD_BOSSES，落 BOSS 凭证物品）
- 13 副本（DUNGEONS）
- 15 称号（TITLES）
- 21 成就（ACHIEVEMENTS）
- 189 物品（写入 ItemFengyun：105装备+48系列+11名器+14BOSS凭证+5虎符+6消耗品）
"""
from sqlalchemy.orm import Session

from models.models import (
    FengyunCity, FengyunSkill, FengyunEquip, FengyunDungeon,
    FengyunTitle, FengyunAchievement, ItemFengyun,
)
from routers import fengyun_data as FY

BATCH = 20

# 品质 / 部位拼音缩写
_QUALITY_PINYIN = {"普通": "pt", "精良": "jl", "卓越": "zy", "史诗": "ss", "神器": "sq"}
_SLOT_PINYIN = {"头": "tou", "手": "shou", "衣": "yi", "腿": "tui", "鞋": "xie", "裤子": "kuzi", "饰品": "shipin"}

# 装备生成档位（等级需求）
_EQUIP_LEVEL_TIERS = [10, 30, 50]

# 演武/魔钻相关消耗品
_CONSUMABLES = [
    ("fy_exp_card_2x", "双倍经验卡",  100, "使用后 1 小时内打怪经验翻倍"),
    ("fy_hp_potion",   "回血丹",       20, "战斗中恢复 200 HP"),
    ("fy_mp_potion",   "回蓝丹",       30, "战斗中恢复 100 MP"),
    ("fy_yuanfen",     "缘分值包",    200, "增加 1 点缘分值（创建军团消耗）"),
    ("fy_silver_pack", "银两包",       50, "打开获得 1000 银两"),
    ("fy_moz_monthly", "魔钻月卡",   1200, "30 天魔钻特权（6 大特权）"),
]


def _ensure_item(db: Session, key: str, name: str, type_: str, price: int, desc: str) -> bool:
    """幂等写入 ItemFengyun 物品字典；返回是否新增"""
    if not db.query(ItemFengyun).filter(ItemFengyun.key == key).first():
        db.add(ItemFengyun(key=key, name=name, type=type_, module_key="fengyun",
                           sell_price=price, description=desc))
        return True
    return False


def seed_fengyun_full(db: Session, log=print):
    """幂等生成风云三国 v0.1.9 全量数据；返回新增计数"""
    stats = {
        "cities": 0, "skills": 0, "equips": 0, "dungeons": 0,
        "titles": 0, "achievements": 0, "items": 0,
        "series_equips": 0, "named_weapons": 0, "bosses": 0,
    }

    # ---------- 1. 13 城市（spec：魏蜀吴三区域 + 中立洛阳）----------
    for key, name, faction, intro in FY.CITIES:
        if not db.query(FengyunCity).filter(FengyunCity.key == key).first():
            db.add(FengyunCity(key=key, name=name, faction=faction, intro=intro))
            stats["cities"] += 1
    db.commit()

    # ---------- 2. 30 技能（spec：3 职业 × 10 技能，4 类型）----------
    for key, name, cls, stype, ulvl, csilver, cexp, effect in FY.SKILLS:
        if not db.query(FengyunSkill).filter(FengyunSkill.key == key).first():
            db.add(FengyunSkill(
                key=key, name=name, class_key=cls, skill_type=stype,
                unlock_level=ulvl, cost_silver=csilver, cost_exp=cexp, effect=effect,
            ))
            stats["skills"] += 1
    db.commit()

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

                if _ensure_item(db, key, name, "equip", price,
                                f"{quality}品质{slot}部位置备，需求等级{lvl}"):
                    stats["items"] += 1

                if not db.query(FengyunEquip).filter(FengyunEquip.key == key).first():
                    db.add(FengyunEquip(
                        key=key, name=name, quality=quality, slot=slot,
                        class_req="",  # 通用装备
                        level_req=lvl,
                        atk_bonus=stats_b.get("atk_bonus", 0),
                        def_bonus=stats_b.get("def_bonus", 0),
                        hp_bonus=stats_b.get("hp_bonus", 0),
                        price=price,
                    ))
                    stats["equips"] += 1
    db.commit()

    # ---------- 3b. v0.2.0 官方装备系列（7 系列 × 7 件套 = 48 件）----------
    for key, name, slot, cls_req, quality, lvl, attr_key, attr_val in FY.EQUIP_SERIES:
        if _ensure_item(db, key, name, "equip", FY.gen_equip_price(quality, lvl),
                        f"{quality}品质{slot}（{cls_req}），需求等级{lvl}，{attr_key}+{attr_val}"):
            stats["items"] += 1
        if not db.query(FengyunEquip).filter(FengyunEquip.key == key).first():
            atk_b = attr_val if attr_key == "atk" else 0
            def_b = attr_val if attr_key == "def" else 0
            db.add(FengyunEquip(
                key=key, name=name, quality=quality, slot=slot,
                class_req=cls_req if cls_req != "all" else "",
                level_req=lvl,
                atk_bonus=atk_b, def_bonus=def_b, hp_bonus=0,
                price=FY.gen_equip_price(quality, lvl),
            ))
            stats["series_equips"] += 1
    db.commit()

    # ---------- 3c. v0.2.0 顶级名器（11 件）----------
    for key, name, wtype, cls_req, quality, lvl, attr_key, attr_val, drop_from in FY.NAMED_WEAPONS:
        if _ensure_item(db, key, name, "equip", FY.gen_equip_price(quality, lvl),
                        f"{quality}品质{wtype}（{cls_req}），需求等级{lvl}，{attr_key}+{attr_val}。{drop_from}"):
            stats["items"] += 1
        if not db.query(FengyunEquip).filter(FengyunEquip.key == key).first():
            atk_b = attr_val if attr_key == "atk" else 0
            def_b = attr_val if attr_key == "def" else 0
            db.add(FengyunEquip(
                key=key, name=name, quality=quality, slot=wtype,
                class_req=cls_req if cls_req != "all" else "",
                level_req=lvl,
                atk_bonus=atk_b, def_bonus=def_b, hp_bonus=0,
                price=FY.gen_equip_price(quality, lvl),
            ))
            stats["named_weapons"] += 1
    db.commit()

    # ---------- 3d. v0.2.0 顶级 BOSS/神兽掉落凭证（14 只）----------
    for boss_key, boss_name, boss_lvl, boss_type, drop_quality, boss_intro in FY.WORLD_BOSSES:
        item_key = f"fy_boss_token_{boss_key}"
        if _ensure_item(db, item_key, f"{boss_name}凭证", "material",
                        FY.gen_equip_price(drop_quality, boss_lvl),
                        f"{boss_type}级 BOSS【{boss_name}】(Lv.{boss_lvl}) 击杀凭证。{boss_intro}。掉落{drop_quality}品质装备"):
            stats["items"] += 1
            stats["bosses"] += 1
    db.commit()

    # ---------- 4. 军团虎符道具（5 级虎符）----------
    for lvl, _, _, item_name in FY.LEGION_LEVELS:
        key = f"fy_tiger_fu_{lvl}"
        if _ensure_item(db, key, item_name, "material", 500 * lvl,
                        f"{item_name}：军团升至 {lvl} 级所需道具"):
            stats["items"] += 1
    db.commit()

    # ---------- 5. 13 副本（spec：按阵营 × 等级段）----------
    for key, name, faction, lmin, lmax, city, npc, exp, silver in FY.DUNGEONS:
        if not db.query(FengyunDungeon).filter(FengyunDungeon.key == key).first():
            db.add(FengyunDungeon(
                key=key, name=name, faction=faction,
                level_min=lmin, level_max=lmax,
                city=city, npc=npc,
                reward_exp=exp, reward_silver=silver,
            ))
            stats["dungeons"] += 1
    db.commit()

    # ---------- 6. 15 称号（prefix + suffix + pair）----------
    for key, name, ttype, grade, hp, atk, df in FY.TITLES:
        if not db.query(FengyunTitle).filter(FengyunTitle.key == key).first():
            db.add(FengyunTitle(
                key=key, name=name, title_type=ttype, grade=grade,
                hp_bonus=hp, atk_bonus=atk, def_bonus=df,
            ))
            stats["titles"] += 1
    db.commit()

    # ---------- 7. 21 成就（3 难度 × 9 类型）----------
    for key, name, diff, cat, desc, hp, mp, atk, df, dodge, crit in FY.ACHIEVEMENTS:
        if not db.query(FengyunAchievement).filter(FengyunAchievement.key == key).first():
            db.add(FengyunAchievement(
                key=key, name=name, difficulty=diff, category=cat, desc=desc,
                hp_bonus=hp, mp_bonus=mp, atk_bonus=atk, def_bonus=df,
                dodge_bonus=dodge, crit_bonus=crit,
            ))
            stats["achievements"] += 1
    db.commit()

    # ---------- 8. 演武/魔钻相关消耗品 ----------
    for key, name, price, desc in _CONSUMABLES:
        if _ensure_item(db, key, name, "prop", price, desc):
            stats["items"] += 1
    db.commit()

    log(f"[fengyun-full] 城市+{stats['cities']} 技能+{stats['skills']} "
        f"装备+{stats['equips']} 官方系列+{stats['series_equips']} 名器+{stats['named_weapons']} "
        f"BOSS+{stats['bosses']} 副本+{stats['dungeons']} "
        f"称号+{stats['titles']} 成就+{stats['achievements']} "
        f"物品字典+{stats['items']}")
    return stats


def seed_fengyun_equips(db: Session, log=print) -> dict:
    """兼容别名：仅生成装备库（105）+ 系列 + 名器 + BOSS + 虎符 + 消耗品入库"""
    return seed_fengyun_full(db, log)