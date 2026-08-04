"""魔法花园完整数据生成器（同步 SQLAlchemy 版）

由 /Users/mubai/3g_games/app/seed_garden_large.py 迁移改写：
- 异步 `await db.execute(...)` -> 同步 `db.query(...)`
- `db.add_all(...)` -> 分批 `db.add_all(...) + db.commit()`
- 模型挂载到 qqgames 新表（ItemGarden/GardenSeed/GardenBloom/GardenAlbumEntryFull/
  GardenRecipe/GardenOrderTemplate）

数据量（与 3g_games 保持一致）：
- 作物 520（seed + bloom + album + item 各 520，8 tier × 65）
- 材料 1024（item 字典，8 tier × 128）
- 配方 1536（GardenRecipe，target tier 2-8）
- 订单模板 3072（GardenOrderTemplate，按 level 分层 pool(L)）

幂等：以 key 前缀/名称计数，已达标则跳过；可断点续跑。
"""
import json
import random

from sqlalchemy.orm import Session

from models.models import (
    ItemGarden, GardenSeed, GardenBloom, GardenAlbumEntryFull,
    GardenRecipe, GardenOrderTemplate,
)

# ---------- tier 配置 ----------
TIERS = list(range(1, 9))  # T1-T8
TIER_UNLOCK_LEVEL = {1: 1, 2: 6, 3: 11, 4: 16, 5: 21, 6: 31, 7: 46, 8: 66}
TIER_GROW_SECONDS = {1: 60, 2: 90, 3: 150, 4: 240, 5: 360, 6: 540, 7: 780, 8: 1080}
TIER_RARITY = {1: "普通", 2: "普通", 3: "稀有", 4: "稀有",
               5: "史诗", 6: "史诗", 7: "传说", 8: "传说"}
TIER_SELL_BASE = {1: 8, 2: 14, 3: 24, 4: 40, 5: 65, 6: 100, 7: 150, 8: 220}

CROP_PER_TIER = 65        # 8 × 65 = 520
MAT_PER_TIER = 128        # 8 × 128 = 1024
RECIPE_TARGET = 1536
TEMPLATE_TARGET = 3072

# 名字池（13×5=65 / 16×8=128）
CROP_BASES = ["薄荷", "雏菊", "星草", "露兰", "苔藓", "风信", "甘菊", "铃草",
              "樱草", "蒲公英", "勿忘", "银莲", "月见"]
CROP_COLORS = ["白", "红", "黄", "粉", "蓝"]
MAT_BASES = ["花粉", "露珠", "孢子", "星尘", "精油", "结晶", "花瓣", "藤蔓",
             "蕊心", "根须", "叶片", "汁液", "灵灰", "珀片", "砂砾", "魂核"]
MAT_SUFFIX = ["碎", "晶", "露", "粉", "核", "珀", "砂", "魄"]

QUALITY_POOL = {
    "normal": ["N", "G"],
    "premium": ["N", "G", "R"],
    "limited": ["N", "G", "R", "E"],
}
BATCH = 500


def _value_coin(sell_price: int) -> int:
    """非成长物 value_coin = max(sell,1)*4"""
    return max(sell_price, 1) * 4


def seed_garden_large(db: Session, log=print):
    """幂等生成超大数据；返回各分类新增计数"""
    stats = {"crops": 0, "materials": 0, "recipes": 0, "templates": 0}

    # ---------- 1. 作物 520（bloom + seed + album + item）----------
    bloom_cnt = db.query(GardenBloom).filter(GardenBloom.key.like("gbloom_t%")).count()
    if bloom_cnt < CROP_PER_TIER * len(TIERS):
        # 已存在的 key 集合（避免重复）
        ex_bloom = {r[0] for r in db.query(GardenBloom.key).filter(
            GardenBloom.key.like("gbloom_t%")).all()}
        ex_seed = {r[0] for r in db.query(GardenSeed.key).filter(
            GardenSeed.key.like("gseed_t%")).all()}
        ex_album = {r[0] for r in db.query(GardenAlbumEntryFull.key).filter(
            GardenAlbumEntryFull.key.like("galbum_t%")).all()}
        ex_item = {r[0] for r in db.query(ItemGarden.key).filter(
            ItemGarden.key.like("garden_bloom_t%")).all()}
        ex_seed_item = {r[0] for r in db.query(ItemGarden.key).filter(
            ItemGarden.key.like("garden_seed_t%")).all()}

        add_items, add_blooms, add_seeds, add_albums = [], [], [], []
        for tier in TIERS:
            rarity = TIER_RARITY[tier]
            ilev = tier
            grow = TIER_GROW_SECONDS[tier]
            sell = TIER_SELL_BASE[tier]
            minlvl = TIER_UNLOCK_LEVEL[tier]
            series = f"星辉系列T{tier}"
            for i in range(CROP_PER_TIER):
                base = CROP_BASES[i % len(CROP_BASES)]
                color = CROP_COLORS[i // len(CROP_BASES)]
                idx = f"{i:03d}"
                bkey = f"gbloom_t{tier}_{idx}"
                skey = f"gseed_t{tier}_{idx}"
                akey = f"galbum_t{tier}_{idx}"
                bitem = f"garden_bloom_t{tier}_{idx}"
                sitem = f"garden_seed_t{tier}_{idx}"
                name = f"{base}{color}"

                if bitem not in ex_item:
                    add_items.append(ItemGarden(key=bitem, name=name, type="flower",
                                                module_key="garden", sell_price=sell,
                                                description=f"T{tier}作物·{rarity}"))
                if sitem not in ex_seed_item:
                    add_items.append(ItemGarden(key=sitem, name=f"{name}种子", type="flower",
                                                module_key="garden", sell_price=max(1, sell // 3),
                                                description=f"T{tier}花种·{rarity}"))
                if bkey not in ex_bloom:
                    add_blooms.append(GardenBloom(
                        key=bkey, name=name, color=color, rarity=rarity, item_level=ilev,
                        sell_price=sell, album_entry_key=akey, item_key=bitem, special_tag=""))
                if akey not in ex_album:
                    add_albums.append(GardenAlbumEntryFull(
                        key=akey, series=series, name=name,
                        description=f"{rarity}·{color}色·T{tier}", bloom_key=bkey))
                if skey not in ex_seed:
                    add_seeds.append(GardenSeed(
                        key=skey, name=name, min_level=minlvl, grow_seconds=grow, stages=4,
                        stage_actions=json.dumps({"1": "water", "2": "weed", "3": "debug"}),
                        yield_min=1, yield_max=2,
                        possible_blooms=json.dumps({bkey: 100}),
                        rarity=rarity, item_level=ilev,
                        sellable=(tier <= 2), seed_item_key=sitem,
                        obtain_sources="shop" if tier == 1 else "craft"))
        _bulk(db, add_items)
        _bulk(db, add_albums)
        _bulk(db, add_blooms)
        _bulk(db, add_seeds)
        stats["crops"] = len(add_blooms)
        log(f"[garden-large] 作物 +{len(add_blooms)} (bloom/seed/album/item 同步)")

    # ---------- 2. 材料 1024（item 字典）----------
    mat_cnt = db.query(ItemGarden).filter(ItemGarden.key.like("garden_mat_t%")).count()
    if mat_cnt < MAT_PER_TIER * len(TIERS):
        ex_mat = {r[0] for r in db.query(ItemGarden.key).filter(
            ItemGarden.key.like("garden_mat_t%")).all()}
        add_items = []
        for tier in TIERS:
            sell = max(2, TIER_SELL_BASE[tier] // 4)
            for i in range(MAT_PER_TIER):
                base = MAT_BASES[i % len(MAT_BASES)]
                suf = MAT_SUFFIX[i // len(MAT_BASES)]
                key = f"garden_mat_t{tier}_{i:04d}"
                if key in ex_mat:
                    continue
                add_items.append(ItemGarden(key=key, name=f"{base}{suf}·T{tier}",
                                            type="material", module_key="garden",
                                            sell_price=sell, description=f"T{tier}合成材料"))
        _bulk(db, add_items)
        stats["materials"] = len(add_items)
        log(f"[garden-large] 材料 +{len(add_items)}")

    # ---------- 收集可用 item 池（bloom + material）供配方/订单引用 ----------
    bloom_rows = db.query(GardenBloom).filter(GardenBloom.key.like("gbloom_t%")).all()
    mat_rows = db.query(ItemGarden).filter(ItemGarden.key.like("garden_mat_t%")).all()
    seed_rows = db.query(GardenSeed).filter(GardenSeed.key.like("gseed_t%")).all()
    # 按 tier 分桶
    bloom_by_tier = {t: [] for t in TIERS}
    for b in bloom_rows:
        bloom_by_tier[b.item_level].append(b)
    mat_by_tier = {t: [] for t in TIERS}
    for m in mat_rows:
        # key: garden_mat_t{tier}_xxxx
        try:
            t = int(m.key.split("_t")[1].split("_")[0])
            mat_by_tier[t].append(m)
        except Exception:
            pass
    seed_by_tier = {t: [] for t in TIERS}
    for s in seed_rows:
        seed_by_tier[s.item_level].append(s)

    # ---------- 3. 配方 1536（target tier 2-8，填至目标）----------
    recipe_cnt = db.query(GardenRecipe).filter(GardenRecipe.name.like("配方#R%")).count()
    need_recipes = RECIPE_TARGET - recipe_cnt
    if need_recipes > 0 and seed_rows:
        target_tiers = list(range(2, 9))  # T2-T8 有产出
        add_recipes = []
        rid = recipe_cnt + 1
        made = 0
        # 循环分配直到填满 need
        while made < need_recipes:
            tt = target_tiers[made % len(target_tiers)]
            seeds_t = seed_by_tier.get(tt, [])
            if not seeds_t:
                made += 1
                continue
            seed = random.choice(seeds_t)
            mats = {}
            n_mat = random.randint(2, 3)
            for _ in range(n_mat):
                src_t = random.choice([tt, max(1, tt - 1)])
                pool = mat_by_tier.get(src_t) or mat_rows
                if not pool:
                    break
                m = random.choice(pool)
                mats[m.key] = mats.get(m.key, 0) + random.randint(1, 3)
            if random.random() < 0.5:
                low_t = max(1, tt - 1)
                bpool = bloom_by_tier.get(low_t) or bloom_rows
                if bpool:
                    b = random.choice(bpool)
                    mats[b.item_key] = mats.get(b.item_key, 0) + 1
            if not mats:
                made += 1
                continue
            sr = max(30, 92 - (tt - 1) * 8)
            add_recipes.append(GardenRecipe(
                name=f"配方#R{rid:04d}", result_seed_key=seed.key, result_qty=1,
                materials=json.dumps(mats), success_rate=sr,
                fail_credit_threshold=3 + tt, target_level=tt,
                require_lock_check=(tt >= 6)))
            rid += 1
            made += 1
        _bulk(db, add_recipes)
        stats["recipes"] = len(add_recipes)
        log(f"[garden-large] 配方 +{len(add_recipes)}")

    # ---------- 4. 订单模板 3072（按 level 分层 pool(L)，填至目标）----------
    tpl_cnt = db.query(GardenOrderTemplate).count()
    need_tpls = TEMPLATE_TARGET - tpl_cnt
    if need_tpls > 0 and (bloom_rows or mat_rows):
        add_tpls = []
        # 按 tier 权重循环分配直到填满 need
        tier_weights = {1: 20, 2: 18, 3: 16, 4: 14, 5: 12, 6: 10, 7: 6, 8: 4}
        weighted_tiers = []
        for t, w in tier_weights.items():
            weighted_tiers.extend([t] * w)
        made = 0
        while made < need_tpls:
            tier = weighted_tiers[made % len(weighted_tiers)]
            # 该 tier 可引用的 item：<= tier 的 bloom 与 material（分池）
            bloom_pool = []
            mat_pool = []
            for t in range(1, tier + 1):
                bloom_pool.extend([(b.item_key, b.name, b.item_level, b.rarity, b.sell_price)
                                   for b in bloom_by_tier.get(t, [])])
                mat_pool.extend([(m.key, m.name, t, TIER_RARITY[t], m.sell_price)
                                 for m in mat_by_tier.get(t, [])])
            if not bloom_pool and not mat_pool:
                made += 1
                continue
            r = random.random()
            if r < 0.12:
                otype = "limited"
            elif r < 0.40:
                otype = "premium"
            else:
                otype = "normal"
            n_items = random.randint(1, 3)
            reqs = []
            used_keys = set()
            for _ in range(n_items):
                # 订单以收获产出(bloom)为主，材料为辅(70/30)
                if bloom_pool and (not mat_pool or random.random() < 0.7):
                    pool = bloom_pool
                else:
                    pool = mat_pool
                pick = random.choice(pool)
                if pick[0] in used_keys:
                    continue
                used_keys.add(pick[0])
                ikey, iname, ilev, rar, sell = pick
                qty = random.randint(1, 3)
                quality = random.choice(QUALITY_POOL[otype])
                reqs.append({"item_key": ikey, "name": iname, "qty": qty,
                             "quality": quality, "value_coin": _value_coin(sell),
                             "item_level": ilev, "rarity": rar})
            if not reqs:
                made += 1
                continue
            level_min = TIER_UNLOCK_LEVEL[tier]
            weight = 60 if otype == "limited" else (80 if otype == "premium" else 100)
            add_tpls.append(GardenOrderTemplate(
                order_type=otype, requirements=json.dumps(reqs, ensure_ascii=False),
                level_min=level_min, level_max=99, weight=weight))
            made += 1
        _bulk(db, add_tpls)
        stats["templates"] = len(add_tpls)
        log(f"[garden-large] 订单模板 +{len(add_tpls)}")

    return stats


def _bulk(db: Session, objs: list):
    """分批 add_all + commit"""
    if not objs:
        return
    for i in range(0, len(objs), BATCH):
        db.add_all(objs[i:i + BATCH])
        db.commit()