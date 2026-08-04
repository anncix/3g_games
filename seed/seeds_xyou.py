"""幻想西游生成器（同步 SQLAlchemy 版）

由 /Users/mubai/3g_games/app/seed_xyou.py 迁移改写：
- 异步 `await db.get(...)` -> 同步 `db.query(...).filter(...).first()`
- 模型挂载到 qqgames 新表（XyouScene 等 11 张 + ItemXyou 物品字典）
- 幂等：以 key 存在性判断，已存在则跳过；可断点续跑；分批提交

数据量（与 3g_games 保持一致）：
- 10 场景（SCENES）
- 45 技能（SKILLS，5 门派 × 9）
- 108 装备（EQUIP 6 品质 × 6 部位 × 3 等级档，用 gen_equip_stats 生成）
- 8 龙宫叉（LONGGONG_WEAPON_CHAIN）
- 22 副本（DUNGEONS）
- 13 宠物（PETS）
- 14 药品（POTIONS_AND_PROPS）+ 14 扩展药品（MEDICINES_EXPANDED）
- 19 高级材料（ADVANCED_MATERIALS）
- 12 长安坐标（CHANGAN_COORDS）
- 物品（写入 ItemXyou）
"""
from sqlalchemy.orm import Session

from models.models import (
    XyouScene, XyouSkill, XyouEquip, XyouDungeon, XyouPet,
    XyouMaterial, XyouCoord, ItemXyou,
)
from routers import xyou_data as XY

BATCH = 20

# 品质 / 部位拼音缩写
_QUALITY_PINYIN = {"白": "bai", "蓝": "lan", "紫": "zi", "金": "jin", "神": "shen", "圣": "sheng"}
_SLOT_PINYIN = {"武器": "wuqi", "头盔": "toukui", "盔甲": "kuijia", "靴子": "xuezi", "戒指": "jiezhi", "手镯": "shouzhuo"}

# 装备生成档位（等级需求）
_EQUIP_LEVEL_TIERS = [10, 40, 80]


def _ensure_item(db: Session, key: str, name: str, type_: str, price: int, desc: str) -> bool:
    """幂等写入 ItemXyou 物品字典；返回是否新增"""
    if not db.query(ItemXyou).filter(ItemXyou.key == key).first():
        db.add(ItemXyou(key=key, name=name, type=type_, module_key="xyou",
                        sell_price=price, description=desc))
        return True
    return False


def seed_xyou_full(db: Session, log=print):
    """幂等生成幻想西游 v0.2.3 全量数据；返回新增计数"""
    stats = {
        "scenes": 0, "skills": 0, "equips": 0, "longgong_weapons": 0,
        "dungeons": 0, "pets": 0, "items": 0, "potions": 0,
        "medicines": 0, "materials": 0, "coords": 0,
    }

    # ---------- 1. 10 场景（spec：九大区域世界地图）----------
    for key, name, region, lvl_min, intro, exits in XY.SCENES:
        if not db.query(XyouScene).filter(XyouScene.key == key).first():
            db.add(XyouScene(key=key, name=name, region=region, level_min=lvl_min,
                             intro=intro, exits=exits))
            stats["scenes"] += 1
    db.commit()

    # ---------- 2. 45 技能（spec：5 门派 × 9 技能，4 类型）----------
    for key, name, sect, stype, ulvl, csilver, cmp, effect in XY.SKILLS:
        if not db.query(XyouSkill).filter(XyouSkill.key == key).first():
            db.add(XyouSkill(
                key=key, name=name, sect_key=sect, skill_type=stype,
                unlock_level=ulvl, cost_silver=csilver, cost_mp=cmp, effect=effect,
            ))
            stats["skills"] += 1
    db.commit()

    # ---------- 3. 装备库（6 品质 × 6 部位 × 3 等级档 = 108 件通用）----------
    for quality in XY.EQUIP_QUALITIES:
        qpy = _QUALITY_PINYIN[quality]
        for slot in XY.EQUIP_SLOTS:
            spy = _SLOT_PINYIN[slot]
            for lvl in _EQUIP_LEVEL_TIERS:
                key = f"xyou_eq_{qpy}_{spy}_{lvl}"
                tier_name = "初阶" if lvl == 10 else "中阶" if lvl == 40 else "高阶"
                name = f"{quality}品质{slot}·{tier_name}"
                stats_b = XY.gen_equip_stats(slot, quality, lvl)
                price = XY.gen_equip_price(quality, lvl)

                # 落 Item 字典
                if _ensure_item(db, key, name, "equip", price,
                                f"{quality}品质{slot}部位置备，需求等级{lvl}"):
                    stats["items"] += 1

                # 落 XyouEquip 表
                if not db.query(XyouEquip).filter(XyouEquip.key == key).first():
                    db.add(XyouEquip(
                        key=key, name=name, quality=quality, slot=slot,
                        sect_req="",  # 通用装备
                        level_req=lvl,
                        atk_bonus=stats_b.get("atk_bonus", 0),
                        def_bonus=stats_b.get("def_bonus", 0),
                        hp_bonus=stats_b.get("hp_bonus", 0),
                        mp_bonus=stats_b.get("mp_bonus", 0),
                        price=price,
                    ))
                    stats["equips"] += 1
    db.commit()

    # ---------- 4. 龙宫叉完整升级路线（spec：8 件套）----------
    for key, name, quality, lvl, price, desc in XY.LONGGONG_WEAPON_CHAIN:
        # 落 Item 字典
        if _ensure_item(db, key, name, "equip", price, f"龙宫专属·{desc}"):
            stats["items"] += 1
        # 落 XyouEquip 表
        if not db.query(XyouEquip).filter(XyouEquip.key == key).first():
            stats_b = XY.gen_equip_stats("武器", quality, lvl)
            db.add(XyouEquip(
                key=key, name=name, quality=quality, slot="武器",
                sect_req="longgong",  # 龙宫专属
                level_req=lvl,
                atk_bonus=stats_b.get("atk_bonus", 0),
                def_bonus=stats_b.get("def_bonus", 0),
                hp_bonus=stats_b.get("hp_bonus", 0),
                mp_bonus=stats_b.get("mp_bonus", 0),
                price=price,
            ))
            stats["longgong_weapons"] += 1
    db.commit()

    # ---------- 5. 22 副本（spec：15-240 级，含普通/困难双难度）----------
    for key, name, lvl_min, lvl_max, scene, diff, r_exp, r_silver, drop_q in XY.DUNGEONS:
        if not db.query(XyouDungeon).filter(XyouDungeon.key == key).first():
            db.add(XyouDungeon(
                key=key, name=name, level_min=lvl_min, level_max=lvl_max,
                scene=scene, difficulty=diff,
                reward_exp=r_exp, reward_silver=r_silver, drop_quality=drop_q,
            ))
            stats["dungeons"] += 1
    db.commit()

    # ---------- 6. 13 宠物（spec：1-150 级携带等级）----------
    for key, name, lvl_req, b_hp, b_atk, b_def, skill, rate in XY.PETS:
        if not db.query(XyouPet).filter(XyouPet.key == key).first():
            db.add(XyouPet(
                key=key, name=name, level_req=lvl_req,
                base_hp=b_hp, base_atk=b_atk, base_def=b_def,
                skill=skill, capture_rate=rate,
            ))
            stats["pets"] += 1
    db.commit()

    # ---------- 7. 14 药品与经验道具（spec：HP/MP/复活/经验/Buff）----------
    for key, name, ptype, value, price, desc in XY.POTIONS_AND_PROPS:
        if _ensure_item(db, key, name, "prop", price, desc):
            stats["potions"] += 1
    db.commit()

    # ---------- 8. 14 种药品完整参数表（含等级需求+获取方式）----------
    for key, name, ptype, lvl_req, value, price, source in XY.MEDICINES_EXPANDED:
        if _ensure_item(db, key, name, "prop", price,
                        f"{ptype.upper()} 药品·恢复 {value}，需求等级 {lvl_req}，来源：{source}"):
            stats["medicines"] += 1
    db.commit()

    # ---------- 9. 19 种高级升级材料（spec 参数补全）----------
    for key, name, purpose, source in XY.ADVANCED_MATERIALS:
        # 落 Item 字典
        if _ensure_item(db, key, name, "material", 0, f"{purpose}；来源：{source}"):
            stats["items"] += 1
        # 落 XyouMaterial 表
        if not db.query(XyouMaterial).filter(XyouMaterial.key == key).first():
            db.add(XyouMaterial(key=key, name=name, purpose=purpose, source=source))
            stats["materials"] += 1
    db.commit()

    # ---------- 10. 12 条长安城坐标（spec 参数补全）----------
    for place, coord, npc_func in XY.CHANGAN_COORDS:
        exists = db.query(XyouCoord).filter(
            XyouCoord.scene_key == "changan",
            XyouCoord.place == place,
        ).first()
        if not exists:
            db.add(XyouCoord(scene_key="changan", place=place, coord=coord, npc_or_func=npc_func))
            stats["coords"] += 1
    db.commit()

    log(f"[xyou-v023] 场景+{stats['scenes']} 技能+{stats['skills']} "
        f"装备+{stats['equips']} 龙宫叉+{stats['longgong_weapons']} "
        f"副本+{stats['dungeons']} 宠物+{stats['pets']} "
        f"物品字典+{stats['items']} 药品+{stats['potions']} "
        f"扩展药品+{stats['medicines']} 高级材料+{stats['materials']} 坐标+{stats['coords']}")
    return stats


def seed_xyou_equips(db: Session, log=print) -> dict:
    """兼容别名：仅生成装备库（108）+ 龙宫叉 + 其余入库"""
    return seed_xyou_full(db, log)