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
        # 小镇食材
        await goods.ensure_item(db, "town_ingredient_rice", "大米", "ingredient", "town", True, 5, "基础食材")
        await goods.ensure_item(db, "town_ingredient_meat", "猪肉", "ingredient", "town", True, 8, "基础食材")
        await goods.ensure_item(db, "town_ingredient_oil", "食用油", "ingredient", "town", True, 6, "添油用")
        await goods.ensure_item(db, "town_dish_fried_rice", "蛋炒饭", "ingredient", "town", True, 30, "招牌菜")
        await goods.ensure_item(db, "town_dish_red_cook", "红烧肉", "ingredient", "town", True, 60, "高星菜")
        # 花园
        await goods.ensure_item(db, "garden_seed_rose", "玫瑰种子", "flower", "garden", True, 10, "种下60秒盛开")
        await goods.ensure_item(db, "garden_rose", "玫瑰", "flower", "garden", True, 20, "可送可展示")
        await goods.ensure_item(db, "garden_seed_lily", "百合种子", "flower", "garden", True, 15, "需合成")
        await goods.ensure_item(db, "garden_lily", "百合", "flower", "garden", True, 30, "高级花")
        await goods.ensure_item(db, "garden_petal_red", "红花瓣", "material", "garden", True, 2, "合成材料")
        await goods.ensure_item(db, "garden_petal_white", "白花瓣", "material", "garden", True, 2, "合成材料")
        # 航海装备
        await goods.ensure_item(db, "sea_equip_sail", "船帆", "equip", "sea", False, 50, "提升战力")
        await goods.ensure_item(db, "sea_equip_cannon", "火炮", "equip", "sea", False, 80, "大幅战力")

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

        # ---------- 菜谱字典 ----------
        recipes = [
            ("fried_rice", "蛋炒饭", json.dumps({"town_ingredient_rice": 2}), 30, "town_dish_fried_rice", 20, 1),
            ("red_cook", "红烧肉", json.dumps({"town_ingredient_meat": 2, "town_ingredient_oil": 1}), 60, "town_dish_red_cook", 50, 2),
        ]
        for key, name, ing, cs, out, price, stars in recipes:
            r = await db.get(models.TownRecipe, key)
            if not r:
                db.add(models.TownRecipe(key=key, name=name, ingredients=ing, cook_seconds=cs,
                                         output_item_key=out, price=price, unlock_stars=stars))
        await db.commit()

        # ---------- 花种字典 ----------
        flowers = [
            ("rose", "玫瑰", 60, 4, "garden_seed_rose", "garden_rose", ""),
            ("lily", "百合", 90, 4, "garden_seed_lily", "garden_lily",
             json.dumps({"garden_petal_red": 1, "garden_petal_white": 1})),
        ]
        for key, name, gs, st, seed, harvest, recipe in flowers:
            f = await db.get(models.Flower, key)
            if not f:
                db.add(models.Flower(key=key, name=name, grow_seconds=gs, stages=st,
                                      seed_item_key=seed, harvest_item_key=harvest, recipe=recipe))
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
