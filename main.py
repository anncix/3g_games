from fastapi import FastAPI, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import json

from models.database import engine, Base, get_db
from models.models import (
    User, Wallet, Forum, IconDef, Achievement, SeaCity, SeaRoute, SeaTask,
    GardenFlower, GardenAlbumEntry, TownRecipe, SeaEquipment,
    ChatRoom, City, HomepageModule, RankDefinition, ShopItem,
    GardenComposeRule, Announcement,
    SummonProfile, SummonMap, SummonBeast, SummonUserBeast,
    SummonSkill, SummonUserBeastSkill, SummonCatchLog,
    SummonBone, SummonUserBone, SummonSoul, SummonUserSoul, SummonSoulHuntLog,
    SummonSpirit, SummonUserSpirit, SummonArenaMatch,
    SummonBattlefield, SummonBattlefieldRecord,
    SummonAlliance, SummonAllianceMember, SummonAllianceDonationLog,
    SummonMasterApprentice,
    FengyunState, FengyunSkill, FengyunUserSkill, FengyunEquip, FengyunUserEquip,
    FengyunDungeon, FengyunLegion, FengyunLegionMember, FengyunTitle,
    FengyunAchievement, FengyunCity, ItemFengyun,
    XyouState, XyouSkill, XyouUserSkill, XyouEquip, XyouUserEquip,
    XyouDungeon, XyouPet, XyouUserPet, XyouScene, XyouMaterial, XyouCoord, ItemXyou
)
from utils.auth import get_current_user, get_password_hash
from routers import auth, home, jingwutang, magic_garden, sunny_farm, delicious_town, zongheng_sihai, admin, summon_king, fengyun, xyou

Base.metadata.create_all(bind=engine)

app = FastAPI(title="QQ家园", version="0.3.2")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(home.router)
app.include_router(jingwutang.router)
app.include_router(magic_garden.router)
app.include_router(sunny_farm.router)
app.include_router(delicious_town.router)
app.include_router(zongheng_sihai.router)
app.include_router(admin.router)
app.include_router(summon_king.router)
app.include_router(fengyun.router)
app.include_router(xyou.router)


def init_default_data(db: Session):
    # 论坛版块
    forums = [
        {"name": "家园公告", "category": "official", "description": "官方公告与活动", "icon": "📢", "sort_order": 0},
        {"name": "新手交流", "category": "communication", "description": "新手指南与问答", "icon": "💬", "sort_order": 1},
        {"name": "精武堂", "category": "game", "description": "江湖儿女聚集地", "icon": "⚔️", "sort_order": 2},
        {"name": "魔法花园", "category": "game", "description": "花友交流区", "icon": "🌸", "sort_order": 3},
        {"name": "阳光牧场", "category": "game", "description": "农牧场主交流", "icon": "🌾", "sort_order": 4},
        {"name": "美味小镇", "category": "game", "description": "厨师们的乐园", "icon": "🍳", "sort_order": 5},
        {"name": "纵横四海", "category": "game", "description": "航海冒险交流", "icon": "⛵", "sort_order": 6},
        {"name": "家族专区", "category": "social", "description": "家族招募与活动", "icon": "🏛️", "sort_order": 7},
        {"name": "灌水闲聊", "category": "chat", "description": "随便聊聊天", "icon": "💧", "sort_order": 99},
    ]
    for f in forums:
        existing = db.query(Forum).filter(Forum.name == f["name"]).first()
        if not existing:
            db.add(Forum(**f))

    # 图标
    icons = [
        {"icon_key": "jingwu_newbie", "name": "精武新人", "icon": "⚔️", "source_module": "jingwutang", "description": "精武堂入门"},
        {"icon_key": "transfer_god", "name": "神", "icon": "👼", "source_module": "jingwutang", "description": "转职为神"},
        {"icon_key": "transfer_devil", "name": "魔", "icon": "😈", "source_module": "jingwutang", "description": "转职为魔"},
        {"icon_key": "transfer_immortal", "name": "仙", "icon": "✨", "source_module": "jingwutang", "description": "转职为仙"},
        {"icon_key": "flower_fairy", "name": "花仙子", "icon": "🌸", "source_module": "garden", "description": "魔法花园达人"},
        {"icon_key": "flower_lover", "name": "花痴", "icon": "🌺", "source_module": "garden", "description": "点亮50种花谱"},
        {"icon_key": "farm_owner", "name": "牧场主", "icon": "🐄", "source_module": "farm", "description": "阳光牧场达人"},
        {"icon_key": "harvest_master", "name": "丰收王", "icon": "🌻", "source_module": "farm", "description": "收获1000次"},
        {"icon_key": "chef_god", "name": "厨神", "icon": "🍳", "source_module": "town", "description": "美味小镇达人"},
        {"icon_key": "five_star", "name": "五星大厨", "icon": "⭐", "source_module": "town", "description": "餐厅达到5星"},
        {"icon_key": "pirate_king", "name": "海贼王", "icon": "⛵", "source_module": "sea", "description": "纵横四海达人"},
        {"icon_key": "explorer", "name": "探险家", "icon": "🗺️", "source_module": "sea", "description": "解锁所有港口"},
        {"icon_key": "vip", "name": "VIP会员", "icon": "💎", "source_module": "platform", "description": "尊贵会员"},
        {"icon_key": "popular", "name": "人气王", "icon": "🔥", "source_module": "platform", "description": "人气值达到10000"},
        {"icon_key": "rich", "name": "大富翁", "icon": "💰", "source_module": "platform", "description": "G币达到100万"},
    ]
    for i in icons:
        existing = db.query(IconDef).filter(IconDef.icon_key == i["icon_key"]).first()
        if not existing:
            db.add(IconDef(**i))

    # 成就
    achievements = [
        {"category": "social", "name": "初入家园", "description": "首次登录QQ家园", "icon": "🏠", "points": 10},
        {"category": "social", "name": "广交好友", "description": "添加10个好友", "icon": "👥", "points": 30},
        {"category": "social", "name": "人气之星", "description": "人气值达到1000", "icon": "⭐", "points": 50},
        {"category": "family", "name": "家族一员", "description": "加入一个家族", "icon": "🏛️", "points": 20},
        {"category": "family", "name": "家族族长", "description": "创建一个家族", "icon": "👑", "points": 100},
        {"category": "jingwutang", "name": "武林新丁", "description": "精武堂达到10级", "icon": "⚡", "points": 20},
        {"category": "jingwutang", "name": "转职成仙", "description": "精武堂完成转职", "icon": "✨", "points": 100},
        {"category": "jingwutang", "name": "百战百胜", "description": "比武胜利100次", "icon": "🏆", "points": 80},
        {"category": "jingwutang", "name": "副本达人", "description": "通关三国副本", "icon": "📜", "points": 150},
        {"category": "garden", "name": "花匠学徒", "description": "点亮10种花谱", "icon": "🌱", "points": 20},
        {"category": "garden", "name": "花之使者", "description": "点亮50种花谱", "icon": "🌷", "points": 80},
        {"category": "garden", "name": "花之女王", "description": "点亮所有花谱", "icon": "👑", "points": 200},
        {"category": "farm", "name": "小农场主", "description": "阳光牧场达到10级", "icon": "🌱", "points": 20},
        {"category": "farm", "name": "农场主", "description": "阳光牧场达到20级", "icon": "🌻", "points": 50},
        {"category": "farm", "name": "养殖大户", "description": "饲养10种动物", "icon": "🐔", "points": 60},
        {"category": "town", "name": "新手厨师", "description": "学会10道菜", "icon": "🍳", "points": 20},
        {"category": "town", "name": "星级厨师", "description": "美味小镇达到3星", "icon": "👨‍🍳", "points": 50},
        {"category": "town", "name": "满汉全席", "description": "学会所有菜系", "icon": "🍽️", "points": 200},
        {"category": "sea", "name": "初次远航", "description": "完成第一次航行", "icon": "⛵", "points": 20},
        {"category": "sea", "name": "航海家", "description": "纵横四海到达10个港口", "icon": "🌊", "points": 50},
        {"category": "sea", "name": "海贼王", "description": "击败所有海盗", "icon": "💀", "points": 200},
    ]
    for a in achievements:
        existing = db.query(Achievement).filter(Achievement.name == a["name"]).first()
        if not existing:
            db.add(Achievement(**a))

    # 聊天室
    chat_rooms = [
        {"room_type": "public", "room_key": "public_main", "name": "家园大厅"},
        {"room_type": "public", "room_key": "public_jingwu", "name": "精武堂聊天室"},
        {"room_type": "public", "room_key": "public_garden", "name": "花友聊天室"},
        {"room_type": "public", "room_key": "public_farm", "name": "牧场聊天室"},
        {"room_type": "public", "room_key": "public_town", "name": "美食聊天室"},
        {"room_type": "public", "room_key": "public_sea", "name": "航海聊天室"},
    ]
    for r in chat_rooms:
        existing = db.query(ChatRoom).filter(ChatRoom.room_key == r["room_key"]).first()
        if not existing:
            db.add(ChatRoom(**r))

    # 同城城市字典
    china_cities = [
        {"code": "beijing", "name": "北京", "province": "北京"},
        {"code": "shanghai", "name": "上海", "province": "上海"},
        {"code": "guangzhou", "name": "广州", "province": "广东"},
        {"code": "shenzhen", "name": "深圳", "province": "广东"},
        {"code": "chengdu", "name": "成都", "province": "四川"},
        {"code": "hangzhou", "name": "杭州", "province": "浙江"},
        {"code": "nanjing", "name": "南京", "province": "江苏"},
        {"code": "wuhan", "name": "武汉", "province": "湖北"},
        {"code": "xian", "name": "西安", "province": "陕西"},
        {"code": "chongqing", "name": "重庆", "province": "重庆"},
    ]
    for c in china_cities:
        existing = db.query(City).filter(City.code == c["code"]).first()
        if not existing:
            db.add(City(**c))

    # 家园模块定义
    homepage_modules = [
        {"module_key": "profile", "name": "个人资料", "type": "display", "icon": "👤", "default_enabled": True},
        {"module_key": "guestbook", "name": "留言板", "type": "function", "icon": "📝", "default_enabled": True},
        {"module_key": "visitors", "name": "最近访客", "type": "display", "icon": "👀", "default_enabled": True},
        {"module_key": "friends", "name": "好友列表", "type": "function", "icon": "👥", "default_enabled": True},
        {"module_key": "music", "name": "音乐盒", "type": "function", "icon": "🎵", "default_enabled": False},
        {"module_key": "album", "name": "相册", "type": "function", "icon": "📷", "default_enabled": False},
    ]
    for m in homepage_modules:
        existing = db.query(HomepageModule).filter(HomepageModule.module_key == m["module_key"]).first()
        if not existing:
            db.add(HomepageModule(**m))

    # 排行榜定义
    ranks = [
        {"rank_key": "home_active", "name": "家园活跃榜", "module_key": "home", "period_type": "week"},
        {"rank_key": "home_popularity", "name": "家园人气榜", "module_key": "home", "period_type": "total"},
        {"rank_key": "home_wealth", "name": "家园财富榜", "module_key": "home", "period_type": "total"},
        {"rank_key": "family_power", "name": "家族实力榜", "module_key": "family", "period_type": "week"},
        {"rank_key": "farm_harvest", "name": "牧场丰收榜", "module_key": "farm", "period_type": "week"},
        {"rank_key": "town_star", "name": "小镇星级榜", "module_key": "town", "period_type": "total"},
        {"rank_key": "garden_album", "name": "花谱点亮榜", "module_key": "garden", "period_type": "total"},
        {"rank_key": "sea_level", "name": "航海等级榜", "module_key": "sea", "period_type": "total"},
        {"rank_key": "jingwu_level", "name": "精武等级榜", "module_key": "jingwutang", "period_type": "total"},
        {"rank_key": "jingwu_win", "name": "精武胜利榜", "module_key": "jingwutang", "period_type": "week"},
    ]
    for r in ranks:
        existing = db.query(RankDefinition).filter(RankDefinition.rank_key == r["rank_key"]).first()
        if not existing:
            db.add(RankDefinition(**r))

    # 纵横四海 - 城市
    sea_cities = [
        {"city_code": "quanzhou", "name": "泉州", "region": "中土", "level_range": "1-10", "description": "航海起点，繁华港口"},
        {"city_code": "hangzhou", "name": "杭州", "region": "中土", "level_range": "5-15", "description": "江南水乡，物产丰富"},
        {"city_code": "ningbo", "name": "宁波", "region": "中土", "level_range": "8-18", "description": "东海明珠"},
        {"city_code": "guangzhou", "name": "广州", "region": "南疆", "level_range": "10-20", "description": "岭南重镇，海贸发达"},
        {"city_code": "haikou", "name": "海口", "region": "南疆", "level_range": "12-22", "description": "琼州门户"},
        {"city_code": "malacca", "name": "马六甲", "region": "南洋", "level_range": "15-25", "description": "南洋咽喉，海盗出没"},
        {"city_code": "manila", "name": "马尼拉", "region": "南洋", "level_range": "18-28", "description": "吕宋岛重镇"},
        {"city_code": "jakarta", "name": "雅加达", "region": "南洋", "level_range": "20-30", "description": "爪哇岛要港"},
        {"city_code": "calicut", "name": "卡利卡特", "region": "西洋", "level_range": "25-35", "description": "印度西海岸贸易中心"},
        {"city_code": "hormuz", "name": "霍尔木兹", "region": "西域", "level_range": "35-45", "description": "波斯湾要道"},
        {"city_code": "aden", "name": "亚丁", "region": "西域", "level_range": "40-50", "description": "红海入口"},
        {"city_code": "alexandria", "name": "亚历山大", "region": "西域", "level_range": "45-55", "description": "地中海明珠"},
    ]
    added_cities = set()
    for c in sea_cities:
        if c["city_code"] in added_cities:
            continue
        added_cities.add(c["city_code"])
        existing = db.query(SeaCity).filter(SeaCity.city_code == c["city_code"]).first()
        if not existing:
            db.add(SeaCity(**c))

    # 纵横四海 - 航线
    sea_routes = [
        {"from_city_code": "quanzhou", "to_city_code": "hangzhou", "danger_level": 1, "travel_time": 30},
        {"from_city_code": "hangzhou", "to_city_code": "ningbo", "danger_level": 1, "travel_time": 20},
        {"from_city_code": "ningbo", "to_city_code": "guangzhou", "danger_level": 2, "travel_time": 60},
        {"from_city_code": "guangzhou", "to_city_code": "haikou", "danger_level": 2, "travel_time": 45},
        {"from_city_code": "haikou", "to_city_code": "malacca", "danger_level": 3, "travel_time": 120},
        {"from_city_code": "malacca", "to_city_code": "manila", "danger_level": 3, "travel_time": 90},
        {"from_city_code": "manila", "to_city_code": "jakarta", "danger_level": 4, "travel_time": 100},
        {"from_city_code": "malacca", "to_city_code": "calicut", "danger_level": 4, "travel_time": 180},
        {"from_city_code": "calicut", "to_city_code": "hormuz", "danger_level": 5, "travel_time": 200},
        {"from_city_code": "hormuz", "to_city_code": "aden", "danger_level": 5, "travel_time": 150},
        {"from_city_code": "aden", "to_city_code": "alexandria", "danger_level": 5, "travel_time": 180},
    ]
    for i, r in enumerate(sea_routes):
        existing = db.query(SeaRoute).filter(
            SeaRoute.from_city_code == r["from_city_code"],
            SeaRoute.to_city_code == r["to_city_code"]
        ).first()
        if not existing:
            db.add(SeaRoute(**r))

    # 纵横四海 - 任务
    sea_tasks = [
        {"task_type": "main", "title": "初次出海", "description": "从泉州出发，到达杭州", "city_code": "quanzhou", "level_required": 1,
         "objective_json": json.dumps({"type": "reach_city", "city_code": "hangzhou"}),
         "reward_json": json.dumps({"silver": 500, "exp": 100})},
        {"task_type": "main", "title": "南下广州", "description": "从杭州航行到广州", "city_code": "hangzhou", "level_required": 5,
         "objective_json": json.dumps({"type": "reach_city", "city_code": "guangzhou"}),
         "reward_json": json.dumps({"silver": 1000, "exp": 200})},
        {"task_type": "main", "title": "南洋冒险", "description": "穿越南海，到达马六甲", "city_code": "guangzhou", "level_required": 15,
         "objective_json": json.dumps({"type": "reach_city", "city_code": "malacca"}),
         "reward_json": json.dumps({"silver": 2000, "exp": 500})},
        {"task_type": "side", "title": "剿灭海盗", "description": "击败5股海盗", "city_code": "malacca", "level_required": 15,
         "objective_json": json.dumps({"type": "defeat_enemy", "enemy_type": "pirate", "count": 5}),
         "reward_json": json.dumps({"silver": 3000, "exp": 800})},
        {"task_type": "trade", "title": "丝绸贸易", "description": "运送丝绸到卡利卡特", "city_code": "quanzhou", "level_required": 20,
         "objective_json": json.dumps({"type": "trade", "item": "silk", "city_code": "calicut"}),
         "reward_json": json.dumps({"silver": 5000, "exp": 1000})},
    ]
    for t in sea_tasks:
        existing = db.query(SeaTask).filter(SeaTask.title == t["title"]).first()
        if not existing:
            db.add(SeaTask(**t))

    # 纵横四海 - 装备
    sea_equipments = [
        {"equip_code": "wooden_sword", "name": "木剑", "slot_type": "weapon", "rarity": "common", "level_required": 1,
         "base_attr_json": json.dumps({"damage": 5}), "icon": "🗡️", "price": 100},
        {"equip_code": "iron_sword", "name": "铁剑", "slot_type": "weapon", "rarity": "common", "level_required": 10,
         "base_attr_json": json.dumps({"damage": 15}), "icon": "⚔️", "price": 500},
        {"equip_code": "steel_sword", "name": "钢剑", "slot_type": "weapon", "rarity": "rare", "level_required": 20,
         "base_attr_json": json.dumps({"damage": 30}), "icon": "⚔️", "price": 2000},
        {"equip_code": "leather_armor", "name": "皮甲", "slot_type": "armor", "rarity": "common", "level_required": 1,
         "base_attr_json": json.dumps({"defense": 5}), "icon": "🥋", "price": 100},
        {"equip_code": "iron_armor", "name": "铁甲", "slot_type": "armor", "rarity": "common", "level_required": 10,
         "base_attr_json": json.dumps({"defense": 15}), "icon": "🛡️", "price": 500},
        {"equip_code": "compass", "name": "罗盘", "slot_type": "accessory", "rarity": "rare", "level_required": 15,
         "base_attr_json": json.dumps({"luck": 10}), "icon": "🧭", "price": 1500},
    ]
    for e in sea_equipments:
        existing = db.query(SeaEquipment).filter(SeaEquipment.equip_code == e["equip_code"]).first()
        if not existing:
            db.add(SeaEquipment(**e))

    # 魔法花园 - 花种
    flowers = [
        {"flower_code": "daisy", "seed_code": "daisy_seed", "name": "雏菊", "rarity": "common",
         "base_colors_json": json.dumps(["white", "yellow", "pink"]), "price": 10, "exp_gain": 5, "grow_time": 300, "album_group": "普通花卉"},
        {"flower_code": "sunflower", "seed_code": "sunflower_seed", "name": "向日葵", "rarity": "common",
         "base_colors_json": json.dumps(["yellow", "golden"]), "price": 15, "exp_gain": 8, "grow_time": 600, "album_group": "普通花卉"},
        {"flower_code": "rose", "seed_code": "rose_seed", "name": "玫瑰", "rarity": "common",
         "base_colors_json": json.dumps(["red", "pink", "white", "yellow"]), "price": 20, "exp_gain": 10, "grow_time": 900, "album_group": "普通花卉"},
        {"flower_code": "tulip", "seed_code": "tulip_seed", "name": "郁金香", "rarity": "rare",
         "base_colors_json": json.dumps(["red", "purple", "yellow", "black"]), "price": 50, "exp_gain": 20, "grow_time": 1800, "album_group": "稀有花卉"},
        {"flower_code": "lily", "seed_code": "lily_seed", "name": "百合", "rarity": "rare",
         "base_colors_json": json.dumps(["white", "pink", "yellow"]), "price": 60, "exp_gain": 25, "grow_time": 2400, "album_group": "稀有花卉"},
        {"flower_code": "peony", "seed_code": "peony_seed", "name": "牡丹", "rarity": "epic",
         "base_colors_json": json.dumps(["red", "pink", "purple", "black"]), "price": 200, "exp_gain": 50, "grow_time": 3600, "album_group": "珍贵花卉"},
        {"flower_code": "lotus", "seed_code": "lotus_seed", "name": "荷花", "rarity": "epic",
         "base_colors_json": json.dumps(["white", "pink", "red"]), "price": 250, "exp_gain": 60, "grow_time": 4500, "album_group": "珍贵花卉"},
        {"flower_code": "plum", "seed_code": "plum_seed", "name": "梅花", "rarity": "legendary",
         "base_colors_json": json.dumps(["red", "white", "pink"]), "price": 500, "exp_gain": 100, "grow_time": 7200, "album_group": "传说花卉"},
        {"flower_code": "orchid", "seed_code": "orchid_seed", "name": "兰花", "rarity": "legendary",
         "base_colors_json": json.dumps(["purple", "white", "green"]), "price": 800, "exp_gain": 150, "grow_time": 10800, "album_group": "传说花卉"},
    ]
    for f in flowers:
        existing = db.query(GardenFlower).filter(GardenFlower.flower_code == f["flower_code"]).first()
        if not existing:
            db.add(GardenFlower(**f))

    # 魔法花园 - 花谱
    album_entries = [
        {"flower_code": "daisy", "flower_name": "雏菊", "color": "white", "category": "普通花卉", "sort_order": 1},
        {"flower_code": "daisy", "flower_name": "雏菊", "color": "yellow", "category": "普通花卉", "sort_order": 2},
        {"flower_code": "daisy", "flower_name": "雏菊", "color": "pink", "category": "普通花卉", "sort_order": 3},
        {"flower_code": "sunflower", "flower_name": "向日葵", "color": "yellow", "category": "普通花卉", "sort_order": 4},
        {"flower_code": "sunflower", "flower_name": "向日葵", "color": "golden", "category": "普通花卉", "sort_order": 5},
        {"flower_code": "rose", "flower_name": "玫瑰", "color": "red", "category": "普通花卉", "sort_order": 6},
        {"flower_code": "rose", "flower_name": "玫瑰", "color": "pink", "category": "普通花卉", "sort_order": 7},
        {"flower_code": "rose", "flower_name": "玫瑰", "color": "white", "category": "普通花卉", "sort_order": 8},
        {"flower_code": "rose", "flower_name": "玫瑰", "color": "yellow", "category": "普通花卉", "sort_order": 9},
        {"flower_code": "tulip", "flower_name": "郁金香", "color": "red", "category": "稀有花卉", "sort_order": 10},
        {"flower_code": "tulip", "flower_name": "郁金香", "color": "purple", "category": "稀有花卉", "sort_order": 11},
        {"flower_code": "tulip", "flower_name": "郁金香", "color": "yellow", "category": "稀有花卉", "sort_order": 12},
        {"flower_code": "tulip", "flower_name": "郁金香", "color": "black", "category": "稀有花卉", "sort_order": 13},
    ]
    for e in album_entries:
        existing = db.query(GardenAlbumEntry).filter(
            GardenAlbumEntry.flower_code == e["flower_code"],
            GardenAlbumEntry.color == e["color"]
        ).first()
        if not existing:
            db.add(GardenAlbumEntry(**e))

    # 魔法花园 - 合成规则
    compose_rules = [
        {"target_seed_code": "tulip_seed", "target_flower_name": "郁金香",
         "cost_json": json.dumps({"daisy": 10, "sunflower": 5, "gold": 100}), "success_rate": 0.8, "gold_cost": 100},
        {"target_seed_code": "lily_seed", "target_flower_name": "百合",
         "cost_json": json.dumps({"rose": 10, "tulip": 5, "gold": 300}), "success_rate": 0.6, "gold_cost": 300},
        {"target_seed_code": "peony_seed", "target_flower_name": "牡丹",
         "cost_json": json.dumps({"lily": 10, "tulip": 10, "gold": 1000}), "success_rate": 0.4, "gold_cost": 1000},
    ]
    for r in compose_rules:
        existing = db.query(GardenComposeRule).filter(GardenComposeRule.target_seed_code == r["target_seed_code"]).first()
        if not existing:
            db.add(GardenComposeRule(**r))

    # 美味小镇 - 菜谱
    recipes = [
        # 中式
        {"recipe_code": "fried_rice", "name": "蛋炒饭", "street_code": "chinese", "level_required": 1, "quality_type": "normal",
         "ingredient_json": json.dumps({"rice": 2, "egg": 1}), "oil_cost": 1, "gold_income": 15, "exp_income": 5},
        {"recipe_code": "tomato_egg", "name": "西红柿炒蛋", "street_code": "chinese", "level_required": 1, "quality_type": "normal",
         "ingredient_json": json.dumps({"tomato": 2, "egg": 2}), "oil_cost": 1, "gold_income": 20, "exp_income": 8},
        {"recipe_code": "kung_pao_chicken", "name": "宫保鸡丁", "street_code": "chinese", "level_required": 5, "quality_type": "normal",
         "ingredient_json": json.dumps({"chicken": 2, "peanut": 1, "chili": 1}), "oil_cost": 2, "gold_income": 50, "exp_income": 15},
        {"recipe_code": "mapo_tofu", "name": "麻婆豆腐", "street_code": "chinese", "level_required": 8, "quality_type": "normal",
         "ingredient_json": json.dumps({"tofu": 2, "pork": 1, "chili": 2}), "oil_cost": 2, "gold_income": 60, "exp_income": 18},
        {"recipe_code": "sweet_sour_pork", "name": "糖醋里脊", "street_code": "chinese", "level_required": 12, "quality_type": "fine",
         "ingredient_json": json.dumps({"pork": 3, "vinegar": 1, "sugar": 1}), "oil_cost": 3, "gold_income": 100, "exp_income": 30},
        # 西式
        {"recipe_code": "steak", "name": "牛排", "street_code": "western", "level_required": 10, "quality_type": "fine",
         "ingredient_json": json.dumps({"beef": 3, "butter": 1, "pepper": 1}), "oil_cost": 3, "gold_income": 120, "exp_income": 35},
        {"recipe_code": "pasta", "name": "意大利面", "street_code": "western", "level_required": 8, "quality_type": "normal",
         "ingredient_json": json.dumps({"noodle": 2, "tomato": 2, "beef": 1}), "oil_cost": 2, "gold_income": 80, "exp_income": 25},
        # 日式
        {"recipe_code": "sushi", "name": "寿司", "street_code": "japanese", "level_required": 10, "quality_type": "fine",
         "ingredient_json": json.dumps({"rice": 2, "fish": 2, "seaweed": 1}), "oil_cost": 1, "gold_income": 90, "exp_income": 28},
        {"recipe_code": "ramen", "name": "拉面", "street_code": "japanese", "level_required": 5, "quality_type": "normal",
         "ingredient_json": json.dumps({"noodle": 2, "pork": 1, "egg": 1}), "oil_cost": 2, "gold_income": 55, "exp_income": 16},
    ]
    for r in recipes:
        existing = db.query(TownRecipe).filter(TownRecipe.recipe_code == r["recipe_code"]).first()
        if not existing:
            db.add(TownRecipe(**r))

    # 商城物品
    shop_items = [
        {"module_key": "common", "item_code": "gcoin_pack_small", "item_name": "小袋G币", "price_currency": "premium_coin", "price_amount": 10, "limit_per_day": 10},
        {"module_key": "common", "item_code": "exp_potion", "item_name": "经验药水", "price_currency": "premium_coin", "price_amount": 50, "limit_per_day": 5},
        {"module_key": "common", "item_code": "vip_day", "item_name": "VIP体验卡(1天)", "price_currency": "premium_coin", "price_amount": 100, "limit_per_day": 1},
        {"module_key": "garden", "item_code": "daisy_seed", "item_name": "雏菊种子", "price_currency": "g_coin", "price_amount": 10, "limit_per_day": 0},
        {"module_key": "garden", "item_code": "sunflower_seed", "item_name": "向日葵种子", "price_currency": "g_coin", "price_amount": 15, "limit_per_day": 0},
        {"module_key": "garden", "item_code": "rose_seed", "item_name": "玫瑰种子", "price_currency": "g_coin", "price_amount": 20, "limit_per_day": 0},
        {"module_key": "garden", "item_code": "fertilizer", "item_name": "肥料", "price_currency": "g_coin", "price_amount": 5, "limit_per_day": 0},
        {"module_key": "farm", "item_code": "wheat_seed", "item_name": "小麦种子", "price_currency": "g_coin", "price_amount": 5, "limit_per_day": 0},
        {"module_key": "farm", "item_code": "cabbage_seed", "item_name": "白菜种子", "price_currency": "g_coin", "price_amount": 8, "limit_per_day": 0},
        {"module_key": "farm", "item_code": "chicken", "item_name": "小鸡", "price_currency": "g_coin", "price_amount": 100, "limit_per_day": 0},
        {"module_key": "jingwutang", "item_code": "hp_potion", "item_name": "金疮药", "price_currency": "g_coin", "price_amount": 50, "limit_per_day": 0},
        {"module_key": "jingwutang", "item_code": "mp_potion", "item_name": "蓝药", "price_currency": "g_coin", "price_amount": 60, "limit_per_day": 0},
        {"module_key": "jingwutang", "item_code": "enhance_talisman", "item_name": "强化符", "price_currency": "premium_coin", "price_amount": 20, "limit_per_day": 0},
        {"module_key": "sea", "item_code": "supply", "item_name": "补给品", "price_currency": "silver_coin", "price_amount": 30, "limit_per_day": 0},
        {"module_key": "sea", "item_code": "repair_kit", "item_name": "修理包", "price_currency": "silver_coin", "price_amount": 100, "limit_per_day": 0},
    ]
    for s in shop_items:
        existing = db.query(ShopItem).filter(ShopItem.item_code == s["item_code"]).first()
        if not existing:
            db.add(ShopItem(**s))

    # 欢迎公告
    welcome_announcement = db.query(Announcement).filter(Announcement.title == "欢迎回到QQ家园").first()
    if not welcome_announcement:
        db.add(Announcement(
            title="欢迎回到QQ家园",
            content="亲爱的玩家，欢迎回到QQ家园！在这里，你可以种花、养宠、经营餐厅、闯荡江湖，找回那些年的美好回忆。精武堂、魔法花园、阳光牧场、美味小镇、纵横四海全部开放，快来体验吧！",
            scope_type="all",
            status=1
        ))

    db.commit()


@app.on_event("startup")
async def startup_event():
    db = next(get_db())
    init_default_data(db)

    # 初始化精武堂基础数据（技能、等级配置、装备模板、头衔等）
    from utils.jingwutang import init_jingwu_data
    init_jingwu_data(db)

    # 魔法花园完整数据（520作物/1024材料/1536配方/3072订单，幂等）
    from seed.seeds_garden import seed_garden_large
    seed_garden_large(db)

    # 纵横四海完整数据（20城市/24套装/60宝石/21卡片/40圣痕/60宠物/12坐骑/8羽翼/
    # 9随从/10副本/14船只/12主线/23技能/34特产/79装备/136物品词典，幂等）
    from seed.seeds_sea import seed_sea_full
    seed_sea_full(db)

    # 阳光牧场完整数据（50作物/100物品字典，幂等）
    from seed.seeds_farm import seed_farm_full
    seed_farm_full(db)

    # 美味小镇完整数据（222食材物品字典，幂等）
    from seed.seeds_town import seed_town_full
    seed_town_full(db)

    # 风云三国完整数据（13城市/30技能/105装备/48系列/11名器/14BOSS/
    # 13副本/15称号/21成就/189物品字典，幂等）
    from seed.seeds_fengyun import seed_fengyun_full
    seed_fengyun_full(db)

    # 幻想西游完整数据（10场景/45技能/108装备/8龙宫叉/22副本/13宠物/
    # 14药品/14扩展药品/19高级材料/12坐标，幂等）
    from seed.seeds_xyou import seed_xyou_full
    seed_xyou_full(db)

    admin_user = db.query(User).filter(User.username == "admin").first()
    if not admin_user:
        admin = User(
            username="admin",
            nickname="管理员",
            password_hash=get_password_hash("admin123"),
            is_admin=True,
            avatar="👑",
            qq_number="100000",
        )
        db.add(admin)
        db.flush()
        wallet = Wallet(user_id=admin.id, g_coin=999999, premium_coin=99999)
        db.add(wallet)
        db.commit()
    db.close()


@app.get("/")
async def root(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    return RedirectResponse(url="/home/", status_code=302)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)