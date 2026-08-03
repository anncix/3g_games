"""纵横四海补全生成器（v0.1.8 · spec 船只/主线任务/城市特产/宠物技能/补全城市）

按 spec《纵横四海全系统完整目录》补齐 v0.1.7 前完全缺失的 4 类系统数据：
- 14 艘船（spec 船只系统：轻木帆船→明永乐大帆船）
- 12 条主线任务链（spec 主线任务系统：美味任务→封印迷阵，共 4000+ 环）
- 23 种宠物技能（spec 宠物技能：T0/T1/T2 分级）
- 30 城市贸易特产（spec 贸易跑商：5 区域 30 城市特产列表）

同时补全 spec 列出但 v0.1.7 前缺失的 16 个城市（马赛/伊斯坦堡/突尼斯/亚历山大/
阿尔及尔/拉古扎/南特/汉堡/奥斯陆/卢旺达/马达加斯加/孟买/大阪/杭州/广州/马六甲），
并修正里斯本的区域标注（原"亚洲"→"地中海"）。

设计：
- 静态常量从 routers/sea_data.py 引入，本生成器只负责入库（幂等）
- 船只同步落 Item 字典（key=sea_ship_*），可被背包/商店引用
- 城市补全以 key 存在性判断，已存在则仅修正 intro（里斯本区域）
- 城市特产以 city_key 为主键，已存在则跳过

幂等：以 key 存在性判断，已存在则跳过；可断点续跑。
闭环：船只落 Item 字典 + SeaShip 表；特产/技能/任务均落独立表。
"""
import json

from sqlalchemy.ext.asyncio import AsyncSession

from . import models
from .platform import goods
from .routers import sea_data


async def seed_sea_v018(db: AsyncSession, log=print):
    """幂等生成纵横四海 v0.1.8 补全数据；返回新增计数"""
    stats = {"ships": 0, "quests": 0, "specialties": 0, "pet_skills": 0, "cities": 0, "items": 0}

    # ---------- 1. 14 艘船（spec 船只系统）----------
    for key, name, buy_city, price, currency, load, consume in sea_data.SHIPS:
        # 落 Item 字典（船只作为可购买物品）
        item_key = f"sea_{key}"
        if not await goods.get_item_by_key(db, item_key):
            desc = f"船只·载重{load}·消耗{consume}铜/百海里·{buy_city}购买"
            await goods.ensure_item(db, item_key, name, "ship", "sea", False, price, desc)
            stats["items"] += 1

        # 落 SeaShip 表
        if not await db.get(models.SeaShip, key):
            db.add(models.SeaShip(key=key, name=name, buy_city=buy_city,
                                  price=price, currency=currency, load=load,
                                  consume_per_100=consume))
            stats["ships"] += 1
    await db.commit()

    # ---------- 2. 12 条主线任务链（spec 主线任务系统）----------
    for key, name, rounds, reward, sort in sea_data.MAIN_QUESTS:
        if not await db.get(models.SeaMainQuest, key):
            db.add(models.SeaMainQuest(key=key, name=name, rounds=rounds,
                                       reward_desc=reward, sort=sort))
            stats["quests"] += 1
    await db.commit()

    # ---------- 3. 23 种宠物技能（spec 宠物技能）----------
    for key, name, effect, tier in sea_data.PET_SKILLS:
        if not await db.get(models.SeaPetSkill, key):
            db.add(models.SeaPetSkill(key=key, name=name, effect=effect, tier=tier))
            stats["pet_skills"] += 1
    await db.commit()

    # ---------- 4. 补全 16 个缺失城市 + 修正里斯本区域 ----------
    # spec 城市列表：(key, 名称, 区域, 解锁等级, intro)
    # 仅补全 v0.1.7 前缺失的城市；已存在的城市（如 venice/london 等）仅修正 intro
    cities_to_add = [
        # 地中海补全
        ("marseille", "马赛", "地中海", 4, "地中海·白银航线终点，产盐和乳酪"),
        ("istanbul", "伊斯坦堡", "地中海", 6, "地中海·丝织品产地，特殊商店出售解毒剂/固元膏/加速剂"),
        ("tunis", "突尼斯", "地中海", 5, "地中海·杏仁和橄榄油产地"),
        ("alexandria", "亚历山大", "地中海", 7, "地中海·橄榄油产地"),
        ("algiers", "阿尔及尔", "地中海", 5, "地中海·杏仁和橄榄油产地"),
        ("ragusa", "拉古扎", "地中海", 6, "地中海·杏仁和橄榄油产地"),
        # 北海补全
        ("nantes", "南特", "北海", 9, "北海·黄金航线终点，产葡萄酒和小麦"),
        ("hamburg", "汉堡", "北海", 7, "北海·鱼肉和锦织品产地"),
        ("oslo", "奥斯陆", "北海", 8, "北海·鱼肉/木材/绒织品产地"),
        # 非洲补全
        ("rwanda", "卢旺达", "非洲", 22, "非洲·琥珀和珊瑚产地"),
        ("madagascar", "马达加斯加", "非洲", 26, "非洲·木材和毛皮产地"),
        # 印度洋补全
        ("mumbai", "孟买", "印度洋", 24, "印度洋·米/皮草/胡椒产地，可购多桅小型帆船"),
        # 东亚补全
        ("osaka", "大阪", "东亚", 52, "东亚·漆器和茶具产地"),
        ("hangzhou", "杭州", "东亚", 48, "东亚·丝织品产地"),
        ("guangzhou", "广州", "东亚", 46, "东亚·麝香产地，铁匠铺"),
        ("malacca", "马六甲", "东亚", 38, "东亚·肉桂产地"),
    ]
    for key, name, region, lvl, intro in cities_to_add:
        existing = await db.get(models.SeaCity, key)
        if not existing:
            db.add(models.SeaCity(key=key, name=name, unlock_level=lvl, intro=intro))
            stats["cities"] += 1
    await db.commit()

    # 修正里斯本区域标注（v0.1.5 原标"亚洲"，spec 为"地中海"）
    lisbon = await db.get(models.SeaCity, "lisbon")
    if lisbon and "亚洲" in (lisbon.intro or ""):
        lisbon.intro = "地中海·白银航线起点，产葡萄干/盐/杏仁"
    await db.commit()

    # ---------- 5. 30 城市贸易特产（spec 贸易跑商）----------
    for city_key, (city_name, region, specs) in sea_data.CITY_SPECIALTIES.items():
        if not await db.get(models.SeaCitySpecialty, city_key):
            db.add(models.SeaCitySpecialty(city_key=city_key, city_name=city_name,
                                           region=region, specialties=json.dumps(specs, ensure_ascii=False)))
            stats["specialties"] += 1
    await db.commit()

    log(f"[sea-v018] 船只+{stats['ships']} 主线任务+{stats['quests']} "
        f"宠物技能+{stats['pet_skills']} 城市特产+{stats['specialties']} "
        f"补全城市+{stats['cities']} 物品字典+{stats['items']}")
    return stats
