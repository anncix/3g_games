"""种子数据：模块注册 / 物品字典 / 作物 / 菜谱 / 花种 / 城市 / 图标 / 成就 / 管理员

注意：模块资源仍走平台物品字典（ensure_item），商店只引用字典物品。
"""
import asyncio
import json
from datetime import datetime, timedelta

from sqlalchemy import select

from .database import init_db, SessionLocal
from . import models
from .platform import goods, icons
from .deps import hash_password


async def seed():
    await init_db()
    async with SessionLocal() as db:
        # ---------- 管理员 & 演示用户 ----------
        admin = await db.get(models.User, 1) if await db.get(models.User, 1) else None
        if not admin:
            admin = models.User(id=1, username="admin", password_hash=hash_password("admin123"),
                                nickname="站长", is_admin=True, city="北京", coins=999999)
            db.add(admin)
            demo = models.User(id=2, username="demo", password_hash=hash_password("demo123"),
                               nickname="阿强", city="上海", coins=2000, signature="怀念家园的夏天")
            db.add(demo)
            demo2 = models.User(id=3, username="lily", password_hash=hash_password("lily123"),
                                nickname="小莉", city="广州", gender=2, coins=1500)
            db.add(demo2)
            await db.commit()

        # ---------- 模块注册 ----------
        modules = [
            ("farm", "阳光农场", "种菜浇水偷菜，回访节奏明确", "/games/farm", 1, True),
            ("town", "美味小镇", "食材短缺翻橱柜，添油升星", "/games/town", 2, True),
            ("garden", "魔法花园", "合成花种点亮花谱，偷花送花", "/games/garden", 3, True),
            ("sea", "纵横四海", "城市航线推进，任务遭遇装备成长", "/games/sea", 4, True),
            ("summon", "召唤之王", "图鉴抓捕回合战斗，种族克制段位推进", "/games/summon", 5, True),
            ("martial", "精武堂", "修炼加点装备强化，比武对抗帮派社交", "/games/martial", 6, True),
        ]
        for key, name, intro, entry, sort, en in modules:
            m = await db.get(models.Module, key)
            if not m:
                db.add(models.Module(key=key, name=name, intro=intro, entry=entry, sort=sort, enabled=en))
        await db.commit()

        # ---------- 物品字典（平台 + 模块） ----------
        # 平台道具
        await goods.ensure_item(db, "coin_pack_s", "小金币包", "prop", "platform", True, 0, "加速道具")
        await goods.ensure_item(db, "accel_30m", "半小时加速", "prop", "platform", True, 0, "作物/烹饪/航海加速30分钟")
        # 农场
        await goods.ensure_item(db, "farm_seed_radish", "萝卜种子", "crop", "farm", True, 5, "种下60秒成熟")
        await goods.ensure_item(db, "farm_radish", "萝卜", "crop", "farm", True, 10, "收获物")
        await goods.ensure_item(db, "farm_seed_tomato", "番茄种子", "crop", "farm", True, 20, "种下120秒成熟")
        await goods.ensure_item(db, "farm_tomato", "番茄", "crop", "farm", True, 25, "收获物")
        # 小镇食材（按 6 级食材等级，对齐菜谱级别 1-6）
        # 1级食材（Lv1 解锁）
        await goods.ensure_item(db, "town_ing_rice", "大米", "ingredient", "town", True, 5, "1级食材·基础主食")
        await goods.ensure_item(db, "town_ing_egg", "鸡蛋", "ingredient", "town", True, 6, "1级食材·基础辅料")
        await goods.ensure_item(db, "town_ing_veg", "青菜", "ingredient", "town", True, 4, "1级食材·基础蔬菜")
        # 2级食材（Lv10 解锁）
        await goods.ensure_item(db, "town_ing_meat", "猪肉", "ingredient", "town", True, 8, "2级食材·常见荤料")
        await goods.ensure_item(db, "town_ing_tofu", "豆腐", "ingredient", "town", True, 7, "2级食材·豆制品")
        await goods.ensure_item(db, "town_ing_noodle", "面条", "ingredient", "town", True, 9, "2级食材·主食")
        # 3级食材（Lv20 解锁）
        await goods.ensure_item(db, "town_ing_chicken", "鸡肉", "ingredient", "town", True, 12, "3级食材·禽类")
        await goods.ensure_item(db, "town_ing_fish", "鲜鱼", "ingredient", "town", True, 14, "3级食材·水产")
        await goods.ensure_item(db, "town_ing_mushroom", "香菇", "ingredient", "town", True, 10, "3级食材·菌菇")
        # 4级食材（Lv35 解锁）
        await goods.ensure_item(db, "town_ing_beef", "牛肉", "ingredient", "town", True, 18, "4级食材·高级荤料")
        await goods.ensure_item(db, "town_ing_shrimp", "大虾", "ingredient", "town", True, 20, "4级食材·高档水产")
        # 5级食材（Lv50 解锁）
        await goods.ensure_item(db, "town_ing_crab", "膏蟹", "ingredient", "town", True, 28, "5级食材·珍稀水产")
        await goods.ensure_item(db, "town_ing_truffle", "松露", "ingredient", "town", True, 32, "5级食材·珍稀食材")
        # 6级食材/神秘食材（Lv65 解锁）
        await goods.ensure_item(db, "town_ing_abalone", "鲍鱼", "ingredient", "town", True, 45, "6级食材·海味珍品")
        await goods.ensure_item(db, "town_ing_mystery", "神秘食材", "ingredient", "town", True, 50, "6级食材·活动限定")
        # 成品菜（按 6 级菜谱对应）
        await goods.ensure_item(db, "town_dish_lv1", "蛋炒饭", "ingredient", "town", True, 18, "1级菜成品")
        await goods.ensure_item(db, "town_dish_lv2", "红烧肉", "ingredient", "town", True, 36, "2级菜成品")
        await goods.ensure_item(db, "town_dish_lv3", "香菇鸡", "ingredient", "town", True, 68, "3级菜成品")
        await goods.ensure_item(db, "town_dish_lv4", "葱爆牛肉", "ingredient", "town", True, 118, "4级菜成品")
        await goods.ensure_item(db, "town_dish_lv5", "松露膏蟹", "ingredient", "town", True, 198, "5级菜成品")
        await goods.ensure_item(db, "town_dish_lv6", "鲍鱼盛宴", "ingredient", "town", True, 320, "6级菜成品·名菜")
        # 升级材料
        await goods.ensure_item(db, "town_dish_fragment", "菜谱碎片", "material", "town", True, 15, "升极品/金牌材料")
        await goods.ensure_item(db, "town_special_condiment", "特殊调料", "material", "town", True, 40, "升金牌专用材料")
        # 花园物品字典已在下方"花种/花朵/花谱"小节统一注册
        # 航海装备
        await goods.ensure_item(db, "sea_equip_sail", "船帆", "equip", "sea", False, 50, "提升战力")
        await goods.ensure_item(db, "sea_equip_cannon", "火炮", "equip", "sea", False, 80, "大幅战力")
        # 召唤之王道具（v1.0 全量：捕捉球/材料/重生丹/魂系/战灵/联盟捐献/礼包）
        await goods.ensure_item(db, "IT_BALL_N", "普通捕捉球", "consumable", "summon", True, 40, "捕捉倍率x1.0")
        await goods.ensure_item(db, "IT_BALL_S", "强力捕捉球", "consumable", "summon", True, 150, "捕捉倍率x1.5")
        await goods.ensure_item(db, "IT_BALL_U", "超级捕捉球", "consumable", "summon", True, 450, "捕捉倍率x2.2")
        await goods.ensure_item(db, "IT_STONE", "灵石", "material", "summon", True, 250, "战骨强化材料")
        await goods.ensure_item(db, "IT_SOUL_POWDER_1", "魂粉(黄)", "material", "summon", True, 100, "魂力材料")
        await goods.ensure_item(db, "IT_SOUL_POWDER_2", "魂粉(玄)", "material", "summon", True, 300, "魂力材料")
        await goods.ensure_item(db, "IT_SOUL_POWDER_3", "魂粉(地)", "material", "summon", True, 800, "魂力材料")
        await goods.ensure_item(db, "IT_SOUL_POWDER_4", "魂粉(天)", "material", "summon", True, 2100, "魂力材料")
        await goods.ensure_item(db, "IT_SPIRIT_KEY", "战灵钥匙", "consumable", "summon", True, 30, "战灵开孔")
        await goods.ensure_item(db, "IT_REBIRTH", "重生丹", "consumable", "summon", True, 120, "重生幻兽")
        await goods.ensure_item(db, "IT_REBIRTH_S", "重生丹碎片", "material", "summon", True, 40, "合成重生丹")
        await goods.ensure_item(db, "IT_SOUL_CHARM", "追魂法宝", "consumable", "summon", True, 100, "高级猎魂")
        await goods.ensure_item(db, "IT_SOUL_BOX_G", "地魂宝箱", "box", "summon", True, 200, "开地魂材料")
        await goods.ensure_item(db, "IT_SOUL_BOX_T", "天魂宝箱", "box", "summon", True, 500, "开天魂材料")
        await goods.ensure_item(db, "IT_SPIRIT_DUST", "灵力", "material", "summon", True, 50, "战灵洗炼材料")
        await goods.ensure_item(db, "IT_BURN_CRYSTAL", "焚火晶", "material", "summon", True, 60, "通天塔产出/联盟捐献")
        await goods.ensure_item(db, "IT_GOLD_BAG", "金袋", "material", "summon", True, 100, "联盟捐献")
        await goods.ensure_item(db, "IT_INNER_PILL", "内丹", "material", "summon", True, 100, "联盟捐献")
        await goods.ensure_item(db, "BOX_KILL", "杀戮礼包", "box", "summon", True, 80, "战场击杀奖励")
        await goods.ensure_item(db, "BOX_ARENA", "擂台宝箱", "box", "summon", True, 60, "擂台奖励")
        await goods.ensure_item(db, "BOX_BF", "战场宝箱", "box", "summon", True, 70, "战场奖励")

        # 精武堂道具（v0.1.0：强化/打造/精炼/洗点/比武/帮派材料）
        await goods.ensure_item(db, "MT_STRENGTH_STONE", "强化石", "material", "martial", True, 20, "装备强化材料")
        await goods.ensure_item(db, "MT_IRON_ESSENCE", "玄铁精华", "material", "martial", True, 50, "装备打造材料")
        await goods.ensure_item(db, "MT_REFINE_STONE", "精炼石", "material", "martial", True, 80, "高级强化材料")
        await goods.ensure_item(db, "MT_BONE_POWDER", "骨粉", "material", "martial", True, 60, "精英挑战掉落")
        await goods.ensure_item(db, "MT_RESET_TOKEN_FRAG", "洗点碎片", "material", "martial", True, 40, "洗点道具碎片")
        await goods.ensure_item(db, "MT_RESET_TOKEN", "洗点丹", "material", "martial", True, 200, "BOSS掉落洗点道具")
        await goods.ensure_item(db, "MT_SMALL_PILL", "小还丹", "prop", "martial", True, 30, "日常回复道具")
        await goods.ensure_item(db, "MT_ARENA_TICKET", "比武券", "prop", "martial", True, 50, "比武场挑战券")
        await goods.ensure_item(db, "MT_ARENA_MEDAL", "比武勋章", "material", "martial", True, 100, "比武荣誉象征")
        await goods.ensure_item(db, "MT_BOUNTY_TOKEN", "悬赏令", "prop", "martial", True, 60, "悬赏任务凭证")
        await goods.ensure_item(db, "MT_GUILD_CONTRIB_BOX", "帮派贡献箱", "prop", "martial", True, 80, "帮派贡献奖励")
        await goods.ensure_item(db, "MT_GUILD_TOKEN", "帮派令", "material", "martial", True, 70, "帮派任务凭证")

        # ---------- 作物字典 ----------
        crops = [
            ("radish", "萝卜", 60, 4, "farm_seed_radish", "farm_radish", 10, 30),
            ("tomato", "番茄", 120, 4, "farm_seed_tomato", "farm_tomato", 20, 80),
        ]
        for key, name, gs, st, seed, harvest, exp, price in crops:
            c = await db.get(models.Crop, key)
            if not c:
                db.add(models.Crop(key=key, name=name, grow_seconds=gs, stages=st,
                                   seed_item_key=seed, harvest_item_key=harvest, harvest_exp=exp, price=price))
        await db.commit()

        # ---------- 菜谱字典（v0.0.4：6级菜 × 3品质，按方案C定版数值） ----------
        # (key, name, recipe_level, ingredients_json, cook_seconds, output_item_key,
        #  base_price, base_exp, base_oil, unlock_level)
        # 数值对齐 RECIPE_LEVEL_TABLE：1级(Lv1,18,2,30s,8油) ... 6级(Lv65,320,24,180s,50油)
        recipes = [
            # 1级菜（Lv1 解锁，1级食材）
            ("fried_rice", "蛋炒饭", 1, json.dumps({"town_ing_rice": 2, "town_ing_egg": 1}), 30, "town_dish_lv1", 18, 2, 8, 1),
            ("veg_noodle", "青菜面", 1, json.dumps({"town_ing_noodle": 1, "town_ing_veg": 2}), 30, "town_dish_lv1", 18, 2, 8, 1),
            # 2级菜（Lv10 解锁，1-2级食材）
            ("red_cook", "红烧肉", 2, json.dumps({"town_ing_meat": 2, "town_ing_tofu": 1}), 45, "town_dish_lv2", 36, 4, 12, 10),
            ("egg_noodle", "鸡蛋面", 2, json.dumps({"town_ing_noodle": 1, "town_ing_egg": 2}), 45, "town_dish_lv2", 36, 4, 12, 10),
            # 3级菜（Lv20 解锁，2-3级食材）
            ("mushroom_chicken", "香菇鸡", 3, json.dumps({"town_ing_chicken": 1, "town_ing_mushroom": 2}), 60, "town_dish_lv3", 68, 7, 18, 20),
            ("fish_tofu", "鱼香豆腐", 3, json.dumps({"town_ing_fish": 1, "town_ing_tofu": 2}), 60, "town_dish_lv3", 68, 7, 18, 20),
            # 4级菜（Lv35 解锁，3-4级食材）
            ("beef_burst", "葱爆牛肉", 4, json.dumps({"town_ing_beef": 1, "town_ing_mushroom": 1}), 90, "town_dish_lv4", 118, 11, 26, 35),
            ("shrimp_noodle", "大虾面", 4, json.dumps({"town_ing_shrimp": 2, "town_ing_noodle": 1}), 90, "town_dish_lv4", 118, 11, 26, 35),
            # 5级菜（Lv50 解锁，4-5级食材）
            ("truffle_crab", "松露膏蟹", 5, json.dumps({"town_ing_crab": 1, "town_ing_truffle": 1}), 120, "town_dish_lv5", 198, 16, 36, 50),
            # 6级菜（Lv65 解锁，5-6级/神秘食材）
            ("abalone_feast", "鲍鱼盛宴", 6, json.dumps({"town_ing_abalone": 2, "town_ing_mystery": 1}), 180, "town_dish_lv6", 320, 24, 50, 65),
        ]
        for key, name, rlev, ing, cs, out, bp, be, bo, ul in recipes:
            r = await db.get(models.TownRecipe, key)
            if not r:
                db.add(models.TownRecipe(key=key, name=name, recipe_level=rlev, ingredients=ing,
                                          cook_seconds=cs, output_item_key=out,
                                          base_price=bp, base_exp=be, base_oil=bo, unlock_level=ul,
                                          price=bp, unlock_stars=0))
            else:
                # 升级旧记录到新结构
                r.recipe_level = rlev
                r.cook_seconds = cs
                r.output_item_key = out
                r.base_price = bp
                r.base_exp = be
                r.base_oil = bo
                r.unlock_level = ul
                r.ingredients = ing
        await db.commit()

        # ---------- 花种/花朵/花谱 三概念分离（魔法花园 v0.0.3） ----------
        # 物品等级 Lv1-8 + 稀有度 普通/稀有/史诗/传说 双轴
        # 玩家等级段 vs 物品等级上限：1-10→≤2, 11-20→≤3, 21-30→≤4, 31-40→≤5, 41-50→≤6, 51-65→≤7, 66-80→≤8
        # 花种物品字典（8 个花种，跨 Lv1-8，解锁点对齐段位起始等级 1/6/11/16/21/31/46/66）
        await goods.ensure_item(db, "garden_seed_wild", "野花种子", "flower", "garden", True, 5, "Lv1基础花种，60秒")
        await goods.ensure_item(db, "garden_seed_rose", "玫瑰种子", "flower", "garden", True, 12, "Lv2稀有，需6级")
        await goods.ensure_item(db, "garden_seed_lily", "百合种子", "flower", "garden", True, 18, "Lv3稀有，合成获得")
        await goods.ensure_item(db, "garden_seed_tulip", "郁金香种子", "flower", "garden", True, 28, "Lv4稀有，合成获得")
        await goods.ensure_item(db, "garden_seed_orchid", "兰花种子", "flower", "garden", True, 40, "Lv5史诗，合成获得")
        await goods.ensure_item(db, "garden_seed_lotus", "莲花种子", "flower", "garden", True, 55, "Lv6史诗，合成获得")
        await goods.ensure_item(db, "garden_seed_peony", "牡丹种子", "flower", "garden", True, 80, "Lv7传说，合成获得")
        await goods.ensure_item(db, "garden_seed_legend", "传说花种", "flower", "garden", True, 120, "Lv8传说，兑换获得")
        # 花朵物品字典（收获物，含史诗稀有度）
        await goods.ensure_item(db, "garden_bloom_wild_w", "白色野花", "flower", "garden", True, 8, "野花·白")
        await goods.ensure_item(db, "garden_bloom_wild_r", "红色野花", "flower", "garden", True, 8, "野花·红")
        await goods.ensure_item(db, "garden_bloom_wild_y", "黄色野花", "flower", "garden", True, 8, "野花·黄")
        await goods.ensure_item(db, "garden_bloom_rose_r", "红玫瑰", "flower", "garden", True, 20, "玫瑰·红")
        await goods.ensure_item(db, "garden_bloom_rose_p", "紫玫瑰", "flower", "garden", True, 35, "玫瑰·紫")
        await goods.ensure_item(db, "garden_bloom_lily", "百合花", "flower", "garden", True, 30, "百合·白")
        await goods.ensure_item(db, "garden_bloom_tulip", "郁金香", "flower", "garden", True, 45, "郁金香·黄")
        await goods.ensure_item(db, "garden_bloom_orchid", "兰花", "flower", "garden", True, 60, "兰花·紫")
        await goods.ensure_item(db, "garden_bloom_lotus", "莲花", "flower", "garden", True, 80, "莲花·粉")
        await goods.ensure_item(db, "garden_bloom_peony", "牡丹", "flower", "garden", True, 110, "牡丹·红")
        await goods.ensure_item(db, "garden_bloom_legend", "传说之花", "flower", "garden", True, 200, "传说·金")
        # 合成材料
        await goods.ensure_item(db, "garden_petal_red", "红花瓣", "material", "garden", True, 2, "合成材料")
        await goods.ensure_item(db, "garden_petal_white", "白花瓣", "material", "garden", True, 2, "合成材料")
        await goods.ensure_item(db, "garden_petal_purple", "紫花瓣", "material", "garden", True, 5, "中阶合成材料")
        await goods.ensure_item(db, "garden_dust", "花之粉尘", "material", "garden", True, 8, "高阶合成材料")
        await goods.ensure_item(db, "garden_essence", "花之精华", "material", "garden", True, 15, "兑换/传说合成材料")

        # 花谱项（AlbumEntry）— 按系列分组（野花/玫瑰/百合/郁金香/兰花/莲花/牡丹/传说系列）
        album_entries = [
            ("album_wild_w", "野花系列", "白色野花", "朴素的白色野花", "bloom_wild_w"),
            ("album_wild_r", "野花系列", "红色野花", "热烈的红色野花", "bloom_wild_r"),
            ("album_wild_y", "野花系列", "黄色野花", "明亮的黄色野花", "bloom_wild_y"),
            ("album_rose_r", "玫瑰系列", "红玫瑰", "经典的红玫瑰", "bloom_rose_r"),
            ("album_rose_p", "玫瑰系列", "紫玫瑰", "罕见的紫玫瑰", "bloom_rose_p"),
            ("album_lily", "百合系列", "百合花", "纯洁的百合", "bloom_lily"),
            ("album_tulip", "郁金香系列", "郁金香", "高雅的郁金香", "bloom_tulip"),
            ("album_orchid", "兰花系列", "兰花", "幽谷的兰花", "bloom_orchid"),
            ("album_lotus", "莲花系列", "莲花", "出淤泥的莲花", "bloom_lotus"),
            ("album_peony", "牡丹系列", "牡丹", "富贵的牡丹", "bloom_peony"),
            ("album_legend", "传说系列", "传说之花", "传说中的花朵", "bloom_legend"),
        ]
        for key, series, name, desc, bloom_key in album_entries:
            if not await db.get(models.GardenAlbumEntry, key):
                db.add(models.GardenAlbumEntry(key=key, series=series, name=name, description=desc, bloom_key=bloom_key))
        await db.commit()

        # 花朵定义（Bloom）— (key, name, color, rarity, item_level, sell_price, album_key, item_key, tag)
        blooms = [
            ("bloom_wild_w", "白色野花", "白", "普通", 1, 8, "album_wild_w", "garden_bloom_wild_w", ""),
            ("bloom_wild_r", "红色野花", "红", "普通", 1, 8, "album_wild_r", "garden_bloom_wild_r", ""),
            ("bloom_wild_y", "黄色野花", "黄", "普通", 1, 8, "album_wild_y", "garden_bloom_wild_y", ""),
            ("bloom_rose_r", "红玫瑰", "红", "稀有", 2, 20, "album_rose_r", "garden_bloom_rose_r", ""),
            ("bloom_rose_p", "紫玫瑰", "紫", "稀有", 2, 35, "album_rose_p", "garden_bloom_rose_p", ""),
            ("bloom_lily", "百合花", "白", "稀有", 3, 30, "album_lily", "garden_bloom_lily", ""),
            ("bloom_tulip", "郁金香", "黄", "稀有", 4, 45, "album_tulip", "garden_bloom_tulip", ""),
            ("bloom_orchid", "兰花", "紫", "史诗", 5, 60, "album_orchid", "garden_bloom_orchid", ""),
            ("bloom_lotus", "莲花", "粉", "史诗", 6, 80, "album_lotus", "garden_bloom_lotus", ""),
            ("bloom_peony", "牡丹", "红", "传说", 7, 110, "album_peony", "garden_bloom_peony", ""),
            ("bloom_legend", "传说之花", "金", "传说", 8, 200, "album_legend", "garden_bloom_legend", "活动限定"),
        ]
        for key, name, color, rarity, ilev, price, album_key, item_key, tag in blooms:
            if not await db.get(models.GardenBloom, key):
                db.add(models.GardenBloom(key=key, name=name, color=color, rarity=rarity, item_level=ilev,
                                          sell_price=price, album_entry_key=album_key, item_key=item_key, special_tag=tag))
        await db.commit()

        # 花种定义（Seed）
        # (key, name, min_level, grow_seconds, stages, actions, ymin, ymax, blooms_map, rarity, item_level, sellable, seed_item, sources)
        # 解锁点对齐段位起始等级：1/6/11/16/21/31/46/66
        seeds = [
            ("wild", "野花", 1, 60, 4, {"1": "water", "2": "weed", "3": "debug"}, 1, 2,
             {"bloom_wild_w": 60, "bloom_wild_r": 25, "bloom_wild_y": 15}, "普通", 1, True, "garden_seed_wild", "shop"),
            ("rose", "玫瑰", 6, 90, 4, {"1": "water", "2": "weed", "3": "debug"}, 1, 2,
             {"bloom_rose_r": 70, "bloom_rose_p": 30}, "稀有", 2, True, "garden_seed_rose", "shop"),
            ("lily", "百合", 11, 120, 4, {"1": "water", "2": "weed", "3": "debug"}, 1, 2,
             {"bloom_lily": 100}, "稀有", 3, True, "garden_seed_lily", "craft"),
            ("tulip", "郁金香", 16, 150, 4, {"1": "water", "2": "weed", "3": "debug"}, 1, 2,
             {"bloom_tulip": 100}, "稀有", 4, True, "garden_seed_tulip", "craft"),
            ("orchid", "兰花", 21, 180, 4, {"1": "water", "2": "weed", "3": "debug"}, 1, 2,
             {"bloom_orchid": 100}, "史诗", 5, True, "garden_seed_orchid", "craft"),
            ("lotus", "莲花", 31, 210, 4, {"1": "water", "2": "weed", "3": "debug"}, 1, 2,
             {"bloom_lotus": 100}, "史诗", 6, True, "garden_seed_lotus", "craft"),
            ("peony", "牡丹", 46, 240, 4, {"1": "water", "2": "weed", "3": "debug"}, 1, 1,
             {"bloom_peony": 100}, "传说", 7, True, "garden_seed_peony", "craft"),
            ("legend", "传说花", 66, 300, 4, {"1": "water", "2": "weed", "3": "debug"}, 1, 1,
             {"bloom_legend": 100}, "传说", 8, False, "garden_seed_legend", "exchange"),
        ]
        for key, name, mlvl, gs, st, actions, ymin, ymax, blooms_map, rarity, ilev, sellable, seed_item, sources in seeds:
            if not await db.get(models.GardenSeed, key):
                db.add(models.GardenSeed(key=key, name=name, min_level=mlvl, grow_seconds=gs, stages=st,
                                         stage_actions=json.dumps(actions), yield_min=ymin, yield_max=ymax,
                                         possible_blooms=json.dumps(blooms_map), rarity=rarity, item_level=ilev,
                                         sellable=sellable, seed_item_key=seed_item, obtain_sources=sources))
        await db.commit()

        # 合成配方（Recipe）— 花朵/材料 -> 花种
        # (name, result_key, qty, mats, success_rate, fail_threshold, target_level, require_lock)
        # 成功率随目标等级上升而下降；保底值累计满必成；高阶(≥6)强制操作锁校验
        recipes = [
            ("百合花种配方", "lily", 1, {"garden_petal_red": 2, "garden_petal_white": 2}, 90, 3, 3, False),
            ("郁金香花种配方", "tulip", 1, {"garden_petal_purple": 2, "garden_bloom_lily": 1}, 80, 4, 4, False),
            ("兰花花种配方", "orchid", 1, {"garden_bloom_rose_p": 1, "garden_dust": 2}, 70, 4, 5, False),
            ("莲花花种配方", "lotus", 1, {"garden_bloom_orchid": 1, "garden_dust": 3}, 60, 5, 6, True),
            ("牡丹花种配方", "peony", 1, {"garden_bloom_lotus": 1, "garden_essence": 2}, 50, 5, 7, True),
        ]
        for name, result_key, qty, mats, sr, ft, tl, rl in recipes:
            exists = (await db.execute(select(models.GardenRecipe).where(
                models.GardenRecipe.name == name))).scalar_one_or_none()
            if not exists:
                db.add(models.GardenRecipe(name=name, result_seed_key=result_key, result_qty=qty,
                                           materials=json.dumps(mats), success_rate=sr,
                                           fail_credit_threshold=ft, target_level=tl, require_lock_check=rl))
        await db.commit()

        # 兑换（Exchange）— 活动材料 -> 花种（稳定路径，非纯概率）
        exchanges = [
            ("精华兑换传说花种", "legend", 1, {"garden_essence": 5}, ""),
        ]
        for name, result_key, qty, mats, act in exchanges:
            exists = (await db.execute(select(models.GardenExchange).where(
                models.GardenExchange.name == name))).scalar_one_or_none()
            if not exists:
                db.add(models.GardenExchange(name=name, result_seed_key=result_key, result_qty=qty,
                                             materials=json.dumps(mats), activity_key=act))
        await db.commit()

        # 给 demo 用户一些初始花种和材料，便于体验
        demo_user = (await db.execute(select(models.User).where(models.User.username == "demo"))).scalar_one_or_none()
        if demo_user:
            await goods.add_item(db, demo_user.id, "garden_seed_wild", "garden", 3)
            await goods.add_item(db, demo_user.id, "garden_petal_red", "garden", 4)
            await goods.add_item(db, demo_user.id, "garden_petal_white", "garden", 4)
            await goods.add_item(db, demo_user.id, "garden_petal_purple", "garden", 2)
            await goods.add_item(db, demo_user.id, "garden_dust", "garden", 3)
            await goods.add_item(db, demo_user.id, "garden_essence", "garden", 2)
            # 小镇初始食材（1级食材，便于烹饪 1 级菜）
            await goods.add_item(db, demo_user.id, "town_ing_rice", "town", 6)
            await goods.add_item(db, demo_user.id, "town_ing_egg", "town", 4)
            await goods.add_item(db, demo_user.id, "town_ing_veg", "town", 4)
            await goods.add_item(db, demo_user.id, "town_ing_meat", "town", 2)
            await goods.add_item(db, demo_user.id, "town_ing_noodle", "town", 2)
            # 给 lily 也一些食材，便于 demo 去翻橱柜
            lily_user = (await db.execute(select(models.User).where(models.User.username == "lily"))).scalar_one_or_none()
            if lily_user:
                await goods.add_item(db, lily_user.id, "town_ing_rice", "town", 5)
                await goods.add_item(db, lily_user.id, "town_ing_meat", "town", 3)
                await goods.add_item(db, lily_user.id, "town_ing_mushroom", "town", 2)
                # demo ↔ lily 互为好友，便于体验翻柜/雇佣
                f1 = (await db.execute(select(models.Friend).where(
                    models.Friend.user_id == demo_user.id, models.Friend.friend_id == lily_user.id))).scalar_one_or_none()
                if not f1:
                    db.add(models.Friend(user_id=demo_user.id, friend_id=lily_user.id))
                f2 = (await db.execute(select(models.Friend).where(
                    models.Friend.user_id == lily_user.id, models.Friend.friend_id == demo_user.id))).scalar_one_or_none()
                if not f2:
                    db.add(models.Friend(user_id=lily_user.id, friend_id=demo_user.id))
            # 召唤之王：给 demo 初始捕捉球 + 一只初始幻兽（SZW_0004 岩牙狼）
            await goods.add_item(db, demo_user.id, "IT_BALL_N", "summon", 10)
            await goods.add_item(db, demo_user.id, "IT_BALL_S", "summon", 3)
            existing_pet = (await db.execute(select(models.SummonPet).where(
                models.SummonPet.user_id == demo_user.id))).scalar_one_or_none()
            if not existing_pet:
                from .routers import summon_data as SD
                import json as _json
                stats = SD.roll_pet_stats("SZW_0004", 1, 3)
                aptitudes = stats.pop("aptitudes")  # dict → 转 JSON 字符串
                starter = models.SummonPet(
                    user_id=demo_user.id, species_id="SZW_0004", nickname="小狼",
                    level=1, exp=0, growth_stars=3, team_slot=0,
                    aptitudes=_json.dumps(aptitudes, ensure_ascii=False),
                    skills=_json.dumps(["SK_001", "SK_003"]), **stats)
                db.add(starter)
            # 精武堂：给 demo 初始强化石 + 玄铁精华，便于体验强化与打造
            await goods.add_item(db, demo_user.id, "MT_STRENGTH_STONE", "martial", 5)
            await goods.add_item(db, demo_user.id, "MT_IRON_ESSENCE", "martial", 3)
            await goods.add_item(db, demo_user.id, "MT_SMALL_PILL", "martial", 2)
            # 给 demo 一件初始白品质武器便于上手
            from .routers import martial_data as MD
            import json as _mjson
            existing_weapon = (await db.execute(select(models.MartialEquip).where(
                models.MartialEquip.user_id == demo_user.id,
                models.MartialEquip.slot == "weapon"))).scalar_one_or_none()
            if not existing_weapon:
                db.add(models.MartialEquip(
                    user_id=demo_user.id, slot="weapon", quality="white", strengthen=0,
                    stats=_mjson.dumps(MD.gen_equip_stats("weapon", "white")), equipped=True))
        await db.commit()

        # ---------- 城市 / 航线 ----------
        cities = [
            ("port_a", "启航港", "", 1, "你的起点，宁静的小港"),
            ("reef_b", "珊瑚礁岛", "port_a", 2, "盛产珍珠的岛屿"),
            ("trade_c", "商旅之城", "reef_b", 4, "繁华的贸易港口"),
            ("storm_d", "风暴海域", "trade_c", 7, "只有强者才能穿越"),
        ]
        for key, name, parent, lvl, intro in cities:
            c = await db.get(models.SeaCity, key)
            if not c:
                db.add(models.SeaCity(key=key, name=name, parent_city=parent, unlock_level=lvl, intro=intro))
        await db.commit()
        routes = [
            ("port_a", "reef_b", 2, 30),
            ("reef_b", "trade_c", 4, 45),
            ("trade_c", "storm_d", 7, 60),
        ]
        if not (await db.execute(select(models.SeaRoute))).all():
            for fc, tc, lvl, ts in routes:
                db.add(models.SeaRoute(from_city=fc, to_city=tc, required_level=lvl, travel_seconds=ts))
        await db.commit()

        # 装备字典
        equips = [
            ("sail_basic", "基础船帆", "sail", 5, 100),
            ("cannon_basic", "基础火炮", "cannon", 10, 200),
        ]
        for key, name, slot, stat, price in equips:
            e = await db.get(models.SeaEquipment, key)
            if not e:
                db.add(models.SeaEquipment(key=key, name=name, slot=slot, stat=stat, price=price))
        await db.commit()

        # ---------- 图标定义 ----------
        icon_defs = [
            ("icon_farmer", "勤劳农夫", "收获10次作物", "farm", "harvest_count>=10"),
            ("icon_chef", "星级大厨", "餐厅达到3星", "town", "town_stars>=3"),
            ("icon_gardener", "花谱收藏家", "点亮3种花", "garden", "flower_lit>=3"),
            ("icon_captain", "航海家", "航海等级达到5", "sea", "sea_level>=5"),
            ("icon_martial", "武林高手", "精武堂达到10级", "martial", "martial_level>=10"),
            ("icon_family", "家族之光", "加入家族", "platform", "join_family"),
            ("icon_forum", "论坛达人", "论坛发帖5次", "platform", "forum_post>=5"),
            ("icon_signin", "签到达人", "累计签到", "platform", "signin"),
        ]
        for key, name, desc, source, trig in icon_defs:
            await icons.ensure_icon(db, key, name, desc, source, trig)

        # ---------- 成就定义 ----------
        achv_defs = [
            ("achv_first_harvest", "初次收获", "收获第一棵作物", 1, 50, "farm"),
            ("achv_chef_star2", "二星餐厅", "餐厅升至2星", 1, 100, "town"),
            ("achv_flower_master", "花谱大师", "点亮全部花谱", 2, 200, "garden"),
            ("achv_explorer", "远航者", "到达商旅之城", 1, 150, "sea"),
            ("achv_social", "广交好友", "添加3位好友", 3, 60, "platform"),
            ("achv_martial_arena", "比武新秀", "比武场获胜3场", 3, 100, "martial"),
            ("achv_martial_master", "一代宗师", "精武堂达到30级", 1, 300, "martial"),
        ]
        for key, name, desc, target, reward, source in achv_defs:
            await icons.ensure_achievement(db, key, name, desc, target, reward, source)

        # ---------- 论坛板块 ----------
        if not (await db.execute(select(models.ForumBoard))).all():
            for i, name in enumerate(["家园杂谈", "农场交流", "小镇厨房", "花园图鉴", "航海日志"]):
                db.add(models.ForumBoard(name=name, description=f"{name}板块", sort=i))
        await db.commit()

        # ---------- 聊天室 ----------
        if not (await db.execute(select(models.ChatRoom))).all():
            db.add(models.ChatRoom(name="家园大厅", topic="怀旧老友聚集地"))
            db.add(models.ChatRoom(name="交易茶馆", topic="物品交换与求购"))
        await db.commit()

        # ---------- 活动 ----------
        if not (await db.execute(select(models.Activity))).all():
            db.add(models.Activity(name="每日签到", description="每天签到领金币", type="signin",
                                   start_at=datetime.utcnow(), end_at=datetime.utcnow() + timedelta(days=365)))
        await db.commit()

        print("✅ 种子数据已写入。管理员: admin/admin123  演示: demo/demo123")


if __name__ == "__main__":
    asyncio.run(seed())
