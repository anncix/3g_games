"""幻想西游生成器（v0.2.3 扩展版 / v0.2.2 定版）

按 spec《QQ家园幻想西游完整详细资料》落地 v0.2.2 新增模块，v0.2.3 全网检索补全扩展数据：
- 5 门派（将军府/方寸山/龙宫/月宫/普陀山）+ 45 技能（每门派 9 个，4 类型）
- 装备库（6 品质 × 6 部位 × 3 等级档 = 108 件通用 + 8 件龙宫叉系列）
- 22 副本（v0.2.3 新增大雁塔/盘丝洞/降妖除魔，含普通/困难双难度）
- 13 宠物（1-150 级携带）
- 10 场景（九大区域世界地图）
- 14 药品与经验道具（HP/MP/复活/经验/Buff）+ v0.2.3 新增 14 种药品完整参数表
- 13 怪物（覆盖九大区域场景）
- v0.2.3 新增：19 种高级升级材料 + 12 条长安城坐标

设计：
- 静态常量从 routers/xyou_data.py 引入，本生成器只负责入库（幂等）
- 装备按品质×部位×等级档批量生成，落 Item 字典 + XyouEquip 表
- 装备 key 规范：xyou_eq_{quality_pinyin}_{slot_pinyin}_{lvl}
- 龙宫叉系列 key 规范：xyou_lg_w{1-8}
- 全部物品同步落 Item 字典（module_key=xyou），可被背包/商店引用

幂等：以 key 存在性判断，已存在则跳过；可断点续跑。
闭环：场景→出口引用场景 key；副本→入口引用场景 key；技能→门派 key；装备→品质/部位全覆盖。
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import models
from .platform import goods
from .routers import xyou_data as XY


# 品质 / 部位拼音缩写
_QUALITY_PINYIN = {"白": "bai", "蓝": "lan", "紫": "zi", "金": "jin", "神": "shen", "圣": "sheng"}
_SLOT_PINYIN = {"武器": "wuqi", "头盔": "toukui", "盔甲": "kuijia", "靴子": "xuezi", "戒指": "jiezhi", "手镯": "shouzhuo"}

# 装备生成档位（等级需求）
_EQUIP_LEVEL_TIERS = [10, 40, 80]


async def seed_xyou(db: AsyncSession, log=print) -> dict:
    """幂等生成幻想西游 v0.2.3 全量数据；返回新增计数"""
    stats = {
        "scenes": 0, "skills": 0, "equips": 0, "longgong_weapons": 0,
        "dungeons": 0, "pets": 0, "items": 0, "potions": 0,
        "medicines": 0, "materials": 0, "coords": 0,  # v0.2.3 新增计数
    }

    # ---------- 1. 10 场景（spec：九大区域世界地图）----------
    for key, name, region, lvl_min, intro, exits in XY.SCENES:
        if not await db.get(models.XyouScene, key):
            db.add(models.XyouScene(
                key=key, name=name, region=region, level_min=lvl_min,
                intro=intro, exits=exits,
            ))
            stats["scenes"] += 1
    await db.commit()

    # ---------- 2. 45 技能（spec：5 门派 × 9 技能，4 类型）----------
    for key, name, sect, stype, ulvl, csilver, cmp, effect in XY.SKILLS:
        if not await db.get(models.XyouSkill, key):
            db.add(models.XyouSkill(
                key=key, name=name, sect_key=sect, skill_type=stype,
                unlock_level=ulvl, cost_silver=csilver, cost_mp=cmp, effect=effect,
            ))
            stats["skills"] += 1
    await db.commit()

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
                if not await goods.get_item_by_key(db, key):
                    await goods.ensure_item(
                        db, key, name, "equip", "xyou", False, price,
                        f"{quality}品质{slot}部位置备，需求等级{lvl}"
                    )
                    stats["items"] += 1

                # 落 XyouEquip 表
                if not await db.get(models.XyouEquip, key):
                    db.add(models.XyouEquip(
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
    await db.commit()

    # ---------- 4. 龙宫叉完整升级路线（spec：8 件套）----------
    for key, name, quality, lvl, price, desc in XY.LONGGONG_WEAPON_CHAIN:
        # 落 Item 字典
        if not await goods.get_item_by_key(db, key):
            await goods.ensure_item(
                db, key, name, "equip", "xyou", False, price,
                f"龙宫专属·{desc}"
            )
            stats["items"] += 1

        # 落 XyouEquip 表
        if not await db.get(models.XyouEquip, key):
            stats_b = XY.gen_equip_stats("武器", quality, lvl)
            db.add(models.XyouEquip(
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
    await db.commit()

    # ---------- 5. 22 副本（spec：15-240 级，含普通/困难双难度 + v0.2.3 新增 3 个）----------
    for key, name, lvl_min, lvl_max, scene, diff, r_exp, r_silver, drop_q in XY.DUNGEONS:
        if not await db.get(models.XyouDungeon, key):
            db.add(models.XyouDungeon(
                key=key, name=name, level_min=lvl_min, level_max=lvl_max,
                scene=scene, difficulty=diff,
                reward_exp=r_exp, reward_silver=r_silver, drop_quality=drop_q,
            ))
            stats["dungeons"] += 1
    await db.commit()

    # ---------- 6. 13 宠物（spec：1-150 级携带等级）----------
    for key, name, lvl_req, b_hp, b_atk, b_def, skill, rate in XY.PETS:
        if not await db.get(models.XyouPet, key):
            db.add(models.XyouPet(
                key=key, name=name, level_req=lvl_req,
                base_hp=b_hp, base_atk=b_atk, base_def=b_def,
                skill=skill, capture_rate=rate,
            ))
            stats["pets"] += 1
    await db.commit()

    # ---------- 7. 14 药品与经验道具（spec：HP/MP/复活/经验/Buff）----------
    for key, name, ptype, value, price, desc in XY.POTIONS_AND_PROPS:
        if not await goods.get_item_by_key(db, key):
            item_type = "prop"
            if ptype == "exp":
                item_type = "prop"
            await goods.ensure_item(
                db, key, name, item_type, "xyou", True, price, desc
            )
            stats["potions"] += 1
    await db.commit()

    # ---------- 8. v0.2.3 新增：14 种药品完整参数表（含等级需求+获取方式）----------
    for key, name, ptype, lvl_req, value, price, source in XY.MEDICINES_EXPANDED:
        if not await goods.get_item_by_key(db, key):
            await goods.ensure_item(
                db, key, name, "prop", "xyou", True, price,
                f"{ptype.upper()} 药品·恢复 {value}，需求等级 {lvl_req}，来源：{source}"
            )
            stats["medicines"] += 1
    await db.commit()

    # ---------- 9. v0.2.3 新增：19 种高级升级材料（spec 参数补全）----------
    for key, name, purpose, source in XY.ADVANCED_MATERIALS:
        # 落 Item 字典
        if not await goods.get_item_by_key(db, key):
            await goods.ensure_item(
                db, key, name, "material", "xyou", True, 0,
                f"{purpose}；来源：{source}"
            )
        # 落 XyouMaterial 表
        if not await db.get(models.XyouMaterial, key):
            db.add(models.XyouMaterial(
                key=key, name=name, purpose=purpose, source=source,
            ))
            stats["materials"] += 1
    await db.commit()

    # ---------- 10. v0.2.3 新增：12 条长安城坐标（spec 参数补全）----------
    for place, coord, npc_func in XY.CHANGAN_COORDS:
        # 用 place 作去重键：查询是否已存在该 place 的坐标
        res = await db.execute(
            select(models.XyouCoord).where(
                models.XyouCoord.scene_key == "changan",
                models.XyouCoord.place == place,
            ).limit(1)
        )
        if not res.scalar_one_or_none():
            db.add(models.XyouCoord(
                scene_key="changan", place=place, coord=coord, npc_or_func=npc_func,
            ))
            stats["coords"] += 1
    await db.commit()

    log(f"[xyou-v023] 场景+{stats['scenes']} 技能+{stats['skills']} "
        f"装备+{stats['equips']} 龙宫叉+{stats['longgong_weapons']} "
        f"副本+{stats['dungeons']} 宠物+{stats['pets']} "
        f"物品字典+{stats['items']} 药品+{stats['potions']} "
        f"扩展药品+{stats['medicines']} 高级材料+{stats['materials']} 坐标+{stats['coords']}")
    return stats

