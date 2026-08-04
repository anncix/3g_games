"""美味小镇食材大全（同步 SQLAlchemy 版）

由 /Users/mubai/3g_games/app/seed_town_large.py 迁移改写：
- 异步 `await db.execute(...)` -> 同步 `db.query(...)`
- `goods.ensure_item` -> 落 ItemTown 表
- 模型挂载到 qqgames 新表（ItemTown）

数据量（与 3g_games 保持一致）：
- 具名食材 217：一级22 / 二级65 / 三级50 / 四级30 / 五级30 / 六级神秘10 / 六级其他10
- 万能食材 5（town_wild_ing_1~5，v0.1.1 已有 6 级 town_wild_ing_6，此处补 1-5 级）
- 合计 222

幂等：以 key 存在性判断，已存在则跳过；可断点续跑。
"""
from sqlalchemy.orm import Session

from models.models import ItemTown

BATCH = 100


def seed_town_full(db: Session, log=print):
    """幂等生成美味小镇 222 食材；返回新增计数"""
    stats = {"items": 0}

    # spec 各级具名食材（key 用拼音/英文，避免冲突）
    # 一级 22 种（spec 明确列出）
    lv1 = ["醋", "白菜", "猪肉", "黄瓜", "紫苏", "鸡蛋", "番茄", "茄子", "糯米", "白糖",
           "大蒜", "辣椒", "大葱", "香葱", "生姜", "面粉", "薏仁", "糙米", "土豆", "生菜", "扁豆", "干辣椒"]
    # 二级 ~65 种（spec 列出代表性，补全至 65）
    lv2 = ["鸡肉", "鸭肉", "草鱼", "黄鱼", "鲤鱼", "豆腐", "豆豉", "腐乳", "豆瓣酱", "番茄酱",
           "胡萝卜", "洋葱", "芹菜", "菠菜", "韭菜", "莴笋", "豆角", "豌豆", "绿豆", "红豆",
           "黑豆", "芝麻", "花生", "核桃", "板栗", "莲子", "百合", "银耳", "木耳", "海带",
           "紫菜", "虾皮", "咸鱼", "腊肉", "香肠", "火腿肠", "淀粉", "料酒", "酱油", "醋精",
           "花椒", "八角", "桂皮", "香叶", "丁香", "草果", "白蔻", "陈皮", "枸杞", "当归",
           "党参", "黄芪", "淮山", "茯苓", "麦冬", "莲子心", "桂花", "玫瑰", "茉莉", "蜂蜜",
           "红糖", "冰糖", "麦芽糖", "酵母", "苏打"]
    # 三级 ~50 种（spec 列出代表性，补全至 50）
    lv3 = ["对虾", "桂鱼", "高汤", "瑶柱", "排骨", "鱿鱼", "牛肉", "鲈鱼", "香菇", "蘑菇",
           "火腿", "花雕酒", "小龙虾", "五香料", "鲍菇", "杏鲍菇", "金针菇", "猴头菇", "茶树菇", "口蘑",
           "松茸", "竹荪", "虫草花", "干贝", "海米", "虾仁", "蟹肉", "蚬子", "蛤蜊", "扇贝",
           "青口", "海螺", "海参丁", "鱼丸", "肉丸", "腊肠", "叉烧", "烧肉", "咸蛋黄", "皮蛋",
           "咸肉", "熏肉", "培根", "芝士", "奶油", "黄油", "可可", "咖啡", "抹茶", "可可粉"]
    # 四级 ~30 种（spec 列出代表性，补全至 30）
    lv4 = ["青蟹", "海参", "水鱼", "蛇肉", "石斑", "江团", "雅鱼", "金华火腿", "黄河鲤鱼",
           "松江鲈鱼", "山黑猪肉", "三黄鸡肉", "西湖龙井", "黄山毛峰", "雪花牛肉", "鳗鱼",
           "鲟鱼", "鲑鱼", "金枪鱼", "鲍鱼苗", "干鲍", "鲜鲍", "鱼肚", "花胶", "燕碎",
           "雪蛤", "鹿肉", "鸵鸟肉", "孔雀肉", "鸸鹋蛋"]
    # 五级 ~30 种（spec 列出代表性，补全至 30）
    lv5 = ["鱼翅", "鲍鱼", "鱼肚", "燕窝", "虫草", "辽参", "松茸", "鹿茸", "人参", "熊掌",
           "帝王蟹", "日本和牛", "番红花粉", "澳洲龙虾", "阿拉斯加蟹", "蓝鳍金枪鱼", "白松露",
           "黑松露", "鱼子酱", "鹅肝", "蜗牛", "羊肚菌", "牛肝菌", "鸡油菌", "松露油",
           "藏红花", "天山雪莲", "灵芝", "何首乌", "肉苁蓉"]
    # 六级神秘 10 种（spec 明确列出）
    lv6_mystery = ["神秘九天翅", "神秘九孔鲍", "神秘黄金肚", "神秘高山虫", "神秘金丝盏",
                   "神秘龙涎香", "神秘金蟾菇", "神秘雪川雏", "神秘金钱鳘", "神秘宝田犊"]
    # 六级其他 10 种（spec 列出西式食材）
    lv6_other = ["橄榄油", "三文鱼", "黑胡椒", "迷迭香", "意大利面",
                 "罗勒", "百里香", "牛至", "月桂叶", "藏红花丝"]

    # 售价分级
    prices = {1: 5, 2: 10, 3: 20, 4: 40, 5: 80, 6: 150}

    def _add_ing(name: str, level: int, idx: int, tag: str = ""):
        """落 ItemTown 字典食材，key = town_ing_lv{level}_{idx}"""
        key = f"town_ing_lv{level}_{idx:03d}"
        if db.query(ItemTown).filter(ItemTown.key == key).first():
            return
        price = prices.get(level, 5)
        desc = f"{level}级食材·{tag}" if tag else f"{level}级食材"
        db.add(ItemTown(key=key, name=name, type="ingredient", module_key="town",
                        sell_price=price, description=desc))
        stats["items"] += 1

    # 落各级食材
    for i, name in enumerate(lv1, 1):
        _add_ing(name, 1, i)
    for i, name in enumerate(lv2, 1):
        _add_ing(name, 2, i)
    for i, name in enumerate(lv3, 1):
        _add_ing(name, 3, i)
    for i, name in enumerate(lv4, 1):
        _add_ing(name, 4, i)
    for i, name in enumerate(lv5, 1):
        _add_ing(name, 5, i)
    for i, name in enumerate(lv6_mystery, 1):
        _add_ing(name, 6, i, "神秘")
    for i, name in enumerate(lv6_other, 1):
        _add_ing(name, 6, i + 100, "西式")

    # 万能食材 1-5 级（v0.1.1 已有 6 级 town_wild_ing_6，此处补 1-5 级确保完整）
    wild_price = [30, 50, 80, 120, 180]
    for lvl in range(1, 6):
        key = f"town_wild_ing_{lvl}"
        if db.query(ItemTown).filter(ItemTown.key == key).first():
            continue
        db.add(ItemTown(key=key, name=f"{lvl}级万能食材", type="ingredient", module_key="town",
                        sell_price=wild_price[lvl - 1], description=f"合菜替代位·{lvl}级"))
        stats["items"] += 1

    db.commit()
    log(f"[town-large] 食材物品字典+{stats['items']}（1级22/2级65/3级50/4级30/5级30/6级20/万能5）")
    return stats