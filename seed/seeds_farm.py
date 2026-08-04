"""阳光牧场完整数据生成器（同步 SQLAlchemy 版）

由 /Users/mubai/3g_games/app/seed_farm_large.py 迁移改写：
- 异步 `await db.get(...)` -> 同步 `db.query(...).filter(...).first()`
- 模型挂载到 qqgames 新表（Crop/ItemFarm）
- 幂等：以 key 存在性判断，已存在则跳过；可断点续跑

数据量（与 3g_games 保持一致）：
- 作物 50（Crop 字典）
- 物品字典 ItemFarm：50 种子 + 50 收获物 = 100
"""
from sqlalchemy.orm import Session

from models.models import Crop, ItemFarm

BATCH = 20

# spec 作物数据表：(key, 名称, 等级, 单价, 最低产量, 成熟h, 再熟h, 售价)
# 来源：spec《阳光牧场作物数据表》2011年整理
CROPS_SPEC = [
    ("bamboo", "竹子", 0, 225, 15, 9.4, 0, 432),
    ("carrot", "胡萝卜", 0, 120, 25, 8, 0, 140),
    ("pumpkin", "南瓜", 1, 130, 25, 8, 0, 312),
    ("barley", "大麦", 1, 150, 25, 8, 0, 280),
    ("grass", "牧草", 1, 140, 25, 9, 0, 280),
    ("corn", "玉米", 2, 145, 25, 8.5, 0, 312),
    ("tomato", "西红柿", 3, 155, 25, 9.5, 0, 416),
    ("eggplant", "茄子", 4, 143, 25, 10.5, 0, 416),
    ("apple", "苹果", 5, 279, 25, 13.5, 8.4, 432),
    ("cantaloupe", "哈密瓜", 6, 166, 25, 15, 0, 624),
    ("strawberry", "草莓", 7, 315, 25, 18.5, 11.5, 560),
    ("grape", "葡萄", 8, 210, 25, 20.5, 12.5, 648),
    ("goldmelon", "黄金瓜", 9, 313, 25, 22.5, 14, 672),
    ("pea", "豌豆", 10, 215, 25, 25, 15.5, 864),
    ("mango", "芒果", 11, 324, 25, 25.5, 15.5, 896),
    ("mulberry", "桑葚", 12, 218, 25, 26, 16, 972),
    ("lemon", "柠檬", 13, 330, 25, 26.5, 16.5, 1080),
    ("lychee", "荔枝", 14, 221, 25, 27, 16.5, 1080),
    ("cactus", "仙人掌", 15, 323, 25, 27.5, 17.5, 1080),
    ("jackfruit", "木菠萝", 16, 224, 25, 28, 17, 1188),
    ("persimmon", "柿子", 17, 329, 25, 28.5, 17.5, 1200),
    ("catchfly", "捕蚊草", 18, 226, 25, 29, 18, 1296),
    ("peach", "水蜜桃", 19, 333, 25, 30, 18.5, 1320),
    ("banana", "香蕉", 20, 222, 25, 30.5, 19, 1296),
    ("cherry", "樱桃", 21, 327, 25, 31, 19, 1320),
    ("orange", "橘子", 22, 226, 25, 31.5, 19.5, 1304),
    ("longan", "桂圆", 23, 331, 25, 32.5, 20, 1440),
    ("jujube", "红枣", 24, 228, 25, 33, 20.5, 1401),
    ("sugarcane", "甘蔗", 25, 337, 25, 33.5, 20.5, 1560),
    ("blueberry", "蓝莓", 26, 482, 25, 34.5, 21, 1600),
    ("kiwi", "猕猴桃", 27, 494, 25, 35, 21.5, 1625),
    ("sesame", "黑芝麻", 28, 410, 25, 35.5, 22, 1727),
    ("woodear", "木耳", 29, 411, 25, 36.5, 22.5, 1828),
    ("durian", "榴莲", 30, 412, 25, 37, 23, 1930),
    ("starfruit", "杨桃", 31, 528, 25, 27, 10, 2040),
    ("greentea", "绿茶", 32, 446, 25, 27.5, 10.5, 1440),
    ("ginseng", "人参", 33, 530, 25, 28, 10.5, 2140),
    ("chili", "红辣椒", 34, 456, 25, 28.5, 10.5, 1600),
    ("gourd", "葫芦", 35, 530, 25, 29, 11.5, 2440),
    ("mushroom", "蘑菇", 36, 464, 25, 29.5, 11.5, 1760),
    ("coconut", "椰子", 37, 533, 25, 30, 12, 2460),
    ("sunflower", "向日葵", 38, 466, 25, 30.5, 12, 1760),
    ("dragonfruit", "火龙果", 39, 533, 25, 31, 13, 2448),
    ("fig", "无花果", 40, 465, 25, 31.5, 13, 1920),
    ("guava", "番石榴", 41, 534, 25, 32, 13.5, 2550),
    ("rambutan", "红毛丹", 50, 415, 25, 37, 17, 2032),
    ("yam", "山药", 51, 415, 25, 37.5, 17.5, 2133),
    ("artocarpus", "菠萝蜜", 52, 416, 25, 38, 17.5, 2235),
    ("mint", "薄荷", 53, 417, 25, 38.5, 18, 2336),
    ("blackcurrant", "黑加仑", 54, 418, 25, 34.5, 16.5, 2438),
]


def _ensure_item(db: Session, key: str, name: str, type_: str, price: int, desc: str) -> bool:
    """幂等写入 ItemFarm 物品字典；返回是否新增"""
    if not db.query(ItemFarm).filter(ItemFarm.key == key).first():
        db.add(ItemFarm(key=key, name=name, type=type_, module_key="farm",
                        sell_price=price, description=desc))
        return True
    return False


def seed_farm_full(db: Session, log=print):
    """幂等生成阳光牧场 50 作物；返回新增计数"""
    stats = {"crops": 0, "items": 0}

    for idx, (key, name, lvl, unit_price, min_yield, grow_h, regrow_h, sell) in enumerate(CROPS_SPEC):
        grow_seconds = int(grow_h * 3600)
        regrow_seconds = int(regrow_h * 3600) if regrow_h > 0 else 0
        crop_type = "多季" if regrow_seconds > 0 else "一季"
        seed_key = f"farm_seed_{key}"
        harvest_key = f"farm_{key}"
        # 经验：售价 / 10（spec 无明确经验值，按售价比例估算）
        exp = max(10, sell // 10)

        # 落 Item 字典（种子 + 收获物）
        if _ensure_item(db, seed_key, f"{name}种子", "crop", unit_price,
                        f"等级{lvl}·{crop_type}·成熟{grow_h}h"):
            stats["items"] += 1
        if _ensure_item(db, harvest_key, name, "crop", sell,
                        f"{crop_type}作物·最低产量{min_yield}·售价{sell}"):
            stats["items"] += 1

        # 落 Crop 字典
        existing = db.query(Crop).filter(Crop.key == key).first()
        if not existing:
            db.add(Crop(key=key, name=name, grow_seconds=grow_seconds, stages=4,
                        seed_item_key=seed_key, harvest_item_key=harvest_key,
                        harvest_exp=exp, price=unit_price, level_req=lvl,
                        crop_type=crop_type, min_yield=min_yield,
                        regrow_seconds=regrow_seconds, sell_price=sell))
            stats["crops"] += 1

        # 分批提交：每 BATCH 条 commit 一次，可断点续跑
        if (idx + 1) % BATCH == 0:
            db.commit()
    db.commit()

    log(f"[farm-full] 作物+{stats['crops']}（共{len(CROPS_SPEC)}种，含种子/收获物 Item 字典同步，ItemFarm+{stats['items']}）")
    return stats