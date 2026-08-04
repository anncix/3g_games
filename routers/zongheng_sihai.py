from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc
import random
import json
from datetime import datetime, timedelta

from models.database import get_db
from models.models import (
    User, SeaProfile, SeaCity, SeaUserCity, SeaRoute, SeaTask, SeaUserTask,
    SeaEvent, SeaBattle, SeaEquipment, SeaUserEquipment,
    SeaPet, SeaUserPet, SeaMount, SeaUserMount, SeaWing, SeaUserWing,
    SeaFollower, SeaUserFollower, SeaGem, SeaUserGem, SeaCard, SeaUserCard,
    SeaStigmata, SeaUserStigmata, SeaHideout, SeaHideoutPlot, SeaTrainingRoom,
    SeaGoods, SeaUserGoods, Wallet, Notification, PlatformEvent
)
from utils.auth import get_current_user
from utils.i18n import t

router = APIRouter(prefix="/zongheng_sihai", tags=["zongheng_sihai"])
templates = Jinja2Templates(directory="templates")

# ==================== 游戏常量 ====================
PIRATE_NAMES = ["小海盗", "海狼", "南洋海盗", "东海倭寇", "西洋舰队", "皇家海军", "黑帆海盗团", "骷髅旗舰队"]
MONSTER_NAMES = ["巨型章鱼", "海怪克拉肯", "深海巨鲨", "幽灵船", "美人鱼塞壬"]
EVENT_TYPES = ["pirate", "storm", "treasure", "adventure", "merchant", "calm"]
EVENT_WEIGHTS = [25, 15, 12, 10, 18, 20]

EQUIPMENT_SLOTS = ["weapon", "armor", "helmet", "boots", "ring", "necklace"]
SLOT_NAMES = {
    "weapon": "武器",
    "armor": "铠甲",
    "helmet": "头盔",
    "boots": "战靴",
    "ring": "戒指",
    "necklace": "项链",
}

CROPS = {
    "rice": {"name": "水稻", "grow_time": 300, "reward": 50},
    "wheat": {"name": "小麦", "grow_time": 600, "reward": 120},
    "herb": {"name": "草药", "grow_time": 900, "reward": 200},
    "ginseng": {"name": "人参", "grow_time": 1800, "reward": 500},
}

# ==================== 基础数据初始化 ====================

def init_base_data(db: Session):
    """初始化基础游戏数据（城市、航线、任务、装备、宠物、商品）"""
    # 城市
    cities_data = [
        {"city_code": "quanzhou", "name": "泉州", "region": "大明东南", "level_range": "1-10",
         "description": "东方第一大港，海上丝绸之路起点，商贾云集之地。"},
        {"city_code": "hangzhou", "name": "杭州", "region": "大明江南", "level_range": "5-15",
         "description": "人间天堂，西湖美景闻名天下，丝绸茶叶远销海外。"},
        {"city_code": "guangzhou", "name": "广州", "region": "大明岭南", "level_range": "10-20",
         "description": "岭南重镇，西洋商船汇聚之地，香料宝石贸易中心。"},
        {"city_code": "yangzhou", "name": "扬州", "region": "大明江淮", "level_range": "3-12",
         "description": "淮左名都，竹西佳处，盐商巨贾聚居之地，繁华富庶。"},
        {"city_code": "lisbon", "name": "里斯本", "region": "欧罗巴", "level_range": "20-30",
         "description": "葡萄牙首都，大航海时代的起点，探险家的摇篮。"},
    ]
    for cd in cities_data:
        if not db.query(SeaCity).filter(SeaCity.city_code == cd["city_code"]).first():
            db.add(SeaCity(**cd))
    db.flush()

    # 航线
    routes_data = [
        {"from_city_code": "quanzhou", "to_city_code": "hangzhou", "danger_level": 1, "travel_time": 30,
         "event_pool_json": json.dumps(["pirate", "storm", "merchant", "calm", "treasure"])},
        {"from_city_code": "hangzhou", "to_city_code": "yangzhou", "danger_level": 1, "travel_time": 20,
         "event_pool_json": json.dumps(["calm", "merchant", "storm"])},
        {"from_city_code": "quanzhou", "to_city_code": "guangzhou", "danger_level": 2, "travel_time": 45,
         "event_pool_json": json.dumps(["pirate", "storm", "treasure", "merchant", "calm", "adventure"])},
        {"from_city_code": "guangzhou", "to_city_code": "lisbon", "danger_level": 5, "travel_time": 120,
         "event_pool_json": json.dumps(["pirate", "storm", "treasure", "adventure", "monster"])},
        {"from_city_code": "hangzhou", "to_city_code": "quanzhou", "danger_level": 1, "travel_time": 30,
         "event_pool_json": json.dumps(["pirate", "storm", "merchant", "calm", "treasure"])},
        {"from_city_code": "yangzhou", "to_city_code": "hangzhou", "danger_level": 1, "travel_time": 20,
         "event_pool_json": json.dumps(["calm", "merchant", "storm"])},
        {"from_city_code": "guangzhou", "to_city_code": "quanzhou", "danger_level": 2, "travel_time": 45,
         "event_pool_json": json.dumps(["pirate", "storm", "treasure", "merchant", "calm", "adventure"])},
        {"from_city_code": "lisbon", "to_city_code": "guangzhou", "danger_level": 5, "travel_time": 120,
         "event_pool_json": json.dumps(["pirate", "storm", "treasure", "adventure", "monster"])},
    ]
    for rd in routes_data:
        existing = db.query(SeaRoute).filter(
            SeaRoute.from_city_code == rd["from_city_code"],
            SeaRoute.to_city_code == rd["to_city_code"]
        ).first()
        if not existing:
            db.add(SeaRoute(**rd))
    db.flush()

    # 主线任务
    tasks_data = [
        {"task_type": "main", "title": "初出茅庐", "description": "你是一名年轻的水手，从泉州港出发，开始你的航海生涯。先在泉州港熟悉一下环境吧。",
         "city_code": "quanzhou", "level_required": 1,
         "objective_json": json.dumps({"type": "reach_level", "target": 2}),
         "reward_json": json.dumps({"silver": 500, "exp": 100, "items": [{"code": "supply_small", "name": "小型补给包", "qty": 3}]})},
        {"task_type": "main", "title": "首航杭州", "description": "从泉州航行至杭州，见识一下江南的繁华。",
         "city_code": "quanzhou", "level_required": 2,
         "objective_json": json.dumps({"type": "visit_city", "target": "hangzhou"}),
         "reward_json": json.dumps({"silver": 800, "exp": 200, "items": [{"code": "iron_sword", "name": "铁剑", "qty": 1}]})},
        {"task_type": "main", "title": "扬州盐商", "description": "从杭州前往扬州，帮助当地盐商运送一批货物。",
         "city_code": "hangzhou", "level_required": 3,
         "objective_json": json.dumps({"type": "visit_city", "target": "yangzhou"}),
         "reward_json": json.dumps({"silver": 1200, "exp": 300, "items": [{"code": "leather_armor", "name": "皮甲", "qty": 1}]})},
        {"task_type": "main", "title": "岭南风云", "description": "南下广州，调查南洋海盗的动向。击败至少3波海盗。",
         "city_code": "yangzhou", "level_required": 5,
         "objective_json": json.dumps({"type": "defeat_enemy", "target": "pirate", "count": 3}),
         "reward_json": json.dumps({"silver": 2000, "exp": 500, "items": [{"code": "steel_sword", "name": "钢剑", "qty": 1}]})},
        {"task_type": "main", "title": "远航西洋", "description": "从广州出发，远航至里斯本，成为真正的航海家！",
         "city_code": "guangzhou", "level_required": 10,
         "objective_json": json.dumps({"type": "visit_city", "target": "lisbon"}),
         "reward_json": json.dumps({"silver": 5000, "exp": 1000, "items": [{"code": "captain_sword", "name": "船长佩剑", "qty": 1}]})},
        {"task_type": "side", "title": "补给采购", "description": "购买100单位补给，确保航行安全。",
         "city_code": "quanzhou", "level_required": 1,
         "objective_json": json.dumps({"type": "buy_supplies", "target": 100}),
         "reward_json": json.dumps({"silver": 200, "exp": 50})},
        {"task_type": "side", "title": "海盗猎人", "description": "击败5个海盗，保护海上商船。",
         "city_code": "hangzhou", "level_required": 3,
         "objective_json": json.dumps({"type": "defeat_enemy", "target": "pirate", "count": 5}),
         "reward_json": json.dumps({"silver": 1000, "exp": 300})},
    ]
    for td in tasks_data:
        if not db.query(SeaTask).filter(SeaTask.title == td["title"]).first():
            db.add(SeaTask(**td))
    db.flush()

    # 装备
    equipments_data = [
        {"equip_code": "wooden_sword", "name": "木剑", "slot_type": "weapon", "rarity": "common",
         "level_required": 1, "base_attr_json": json.dumps({"atk": 5}), "icon": "🗡️", "price": 100},
        {"equip_code": "iron_sword", "name": "铁剑", "slot_type": "weapon", "rarity": "common",
         "level_required": 3, "base_attr_json": json.dumps({"atk": 12}), "icon": "⚔️", "price": 300},
        {"equip_code": "steel_sword", "name": "钢剑", "slot_type": "weapon", "rarity": "uncommon",
         "level_required": 5, "base_attr_json": json.dumps({"atk": 22}), "icon": "⚔️", "price": 800},
        {"equip_code": "captain_sword", "name": "船长佩剑", "slot_type": "weapon", "rarity": "rare",
         "level_required": 10, "base_attr_json": json.dumps({"atk": 40}), "icon": "🗡️", "price": 2000},
        {"equip_code": "leather_armor", "name": "皮甲", "slot_type": "armor", "rarity": "common",
         "level_required": 1, "base_attr_json": json.dumps({"def": 8, "hp": 20}), "icon": "🥋", "price": 200},
        {"equip_code": "chain_armor", "name": "锁子甲", "slot_type": "armor", "rarity": "uncommon",
         "level_required": 5, "base_attr_json": json.dumps({"def": 18, "hp": 50}), "icon": "🛡️", "price": 600},
        {"equip_code": "sailor_ring", "name": "水手戒指", "slot_type": "ring", "rarity": "common",
         "level_required": 1, "base_attr_json": json.dumps({"atk": 3, "def": 2}), "icon": "💍", "price": 150},
        {"equip_code": "captain_necklace", "name": "船长项链", "slot_type": "necklace", "rarity": "rare",
         "level_required": 8, "base_attr_json": json.dumps({"atk": 10, "def": 8, "hp": 30}), "icon": "📿", "price": 1500},
        {"equip_code": "sailor_hat", "name": "水手帽", "slot_type": "helmet", "rarity": "common",
         "level_required": 1, "base_attr_json": json.dumps({"def": 3}), "icon": "🎩", "price": 80},
        {"equip_code": "sea_boots", "name": "航海靴", "slot_type": "boots", "rarity": "common",
         "level_required": 2, "base_attr_json": json.dumps({"def": 4, "agi": 3}), "icon": "👢", "price": 120},
    ]
    for ed in equipments_data:
        if not db.query(SeaEquipment).filter(SeaEquipment.equip_code == ed["equip_code"]).first():
            db.add(SeaEquipment(**ed))
    db.flush()

    # 宠物
    pets_data = [
        {"pet_code": "parrot", "name": "航海鹦鹉", "category": "normal", "rarity": "common",
         "level_required": 1, "base_hp": 50, "base_atk": 8, "base_def": 3, "base_agi": 15,
         "skill_pool_json": json.dumps([{"name": "警觉", "desc": "提前发现危险"}]),
         "icon": "🦜", "description": "聪明的鹦鹉，能提前发现危险，是航海者的好伙伴。"},
        {"pet_code": "monkey", "name": "灵猴", "category": "normal", "rarity": "common",
         "level_required": 3, "base_hp": 60, "base_atk": 10, "base_def": 5, "base_agi": 20,
         "skill_pool_json": json.dumps([{"name": "攀爬", "desc": "战斗中闪避率提升"}]),
         "icon": "🐒", "description": "机灵的猴子，动作敏捷，擅长在桅杆间穿梭。"},
        {"pet_code": "sea_turtle", "name": "海龟", "category": "rare", "rarity": "uncommon",
         "level_required": 5, "base_hp": 150, "base_atk": 5, "base_def": 20, "base_agi": 3,
         "skill_pool_json": json.dumps([{"name": "龟甲防御", "desc": "减少受到的伤害"}]),
         "icon": "🐢", "description": "千年海龟，防御惊人，能在战斗中保护主人。"},
    ]
    for pd in pets_data:
        if not db.query(SeaPet).filter(SeaPet.pet_code == pd["pet_code"]).first():
            db.add(SeaPet(**pd))
    db.flush()

    # 商品（补给、炮弹、药品等）
    goods_data = [
        {"goods_code": "supply_bread", "name": "干粮", "category": "supply",
         "buy_price": 2, "sell_price": 1, "level_required": 1,
         "description": "航海必备的干粮，恢复10点补给。", "icon": "🍞"},
        {"goods_code": "supply_water", "name": "淡水", "category": "supply",
         "buy_price": 1, "sell_price": 1, "level_required": 1,
         "description": "淡水是生命之源，恢复5点补给。", "icon": "💧"},
        {"goods_code": "cannon_ball", "name": "炮弹", "category": "ammo",
         "buy_price": 5, "sell_price": 2, "level_required": 1,
         "description": "海战必需品，提升战斗伤害。", "icon": "💣"},
        {"goods_code": "medicine", "name": "金疮药", "category": "medicine",
         "buy_price": 20, "sell_price": 10, "level_required": 1,
         "description": "治疗伤口，恢复50点船只耐久。", "icon": "🧪"},
        {"goods_code": "repair_wood", "name": "修船木料", "category": "material",
         "buy_price": 15, "sell_price": 8, "level_required": 1,
         "description": "修理船只的木材，恢复30点船只耐久。", "icon": "🪵"},
        {"goods_code": "rum", "name": "朗姆酒", "category": "supply",
         "buy_price": 10, "sell_price": 5, "level_required": 3,
         "description": "水手们最爱的朗姆酒，恢复体力。", "icon": "🍶"},
        {"goods_code": "spice", "name": "香料", "category": "trade",
         "buy_price": 50, "sell_price": 80, "level_required": 5,
         "description": "珍贵的东方香料，可以卖到好价钱。", "icon": "🌶️"},
        {"goods_code": "silk", "name": "丝绸", "category": "trade",
         "buy_price": 80, "sell_price": 120, "level_required": 5,
         "description": "上等丝绸，西洋贵族争相购买。", "icon": "🧣"},
    ]
    for gd in goods_data:
        if not db.query(SeaGoods).filter(SeaGoods.goods_code == gd["goods_code"]).first():
            db.add(SeaGoods(**gd))
    db.flush()

    db.commit()


# ==================== 公共工具函数 ====================

def get_common_context(request: Request, db: Session):
    """获取公共上下文"""
    user = get_current_user(request, db)
    if not user:
        return None
    lang = user.language or "zh"
    theme = user.theme or "light"
    unread_count = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == False
    ).count()
    return {
        "request": request,
        "user": user,
        "lang": lang,
        "theme": theme,
        "_": lambda key: t(key, lang),
        "unread_count": unread_count,
        "now": datetime.utcnow(),
    }


def get_city_by_code(db: Session, city_code: str):
    """根据city_code获取城市"""
    return db.query(SeaCity).filter(SeaCity.city_code == city_code).first()


def get_city_name(db: Session, city_code: str):
    """获取城市名称"""
    city = get_city_by_code(db, city_code)
    return city.name if city else city_code


def calculate_sea_stats(sea: SeaProfile, db: Session):
    """计算航海角色的战斗属性（含装备加成）"""
    base_atk = sea.ship_damage
    base_def = sea.ship_defense
    base_hp = sea.ship_max_hp
    base_agi = 10

    equipped_items = db.query(SeaUserEquipment).filter(
        SeaUserEquipment.user_id == sea.user_id,
        SeaUserEquipment.equipped == True
    ).all()

    for ue in equipped_items:
        equip = db.query(SeaEquipment).filter(SeaEquipment.id == ue.equip_id).first()
        if equip:
            try:
                attrs = json.loads(equip.base_attr_json) if equip.base_attr_json else {}
            except:
                attrs = {}
            enhance_bonus = 1 + ue.enhance_level * 0.1
            base_atk += int(attrs.get("atk", 0) * enhance_bonus)
            base_def += int(attrs.get("def", 0) * enhance_bonus)
            base_hp += int(attrs.get("hp", 0) * enhance_bonus)
            base_agi += int(attrs.get("agi", 0) * enhance_bonus)

    return {
        "atk": base_atk,
        "def": base_def,
        "max_hp": base_hp,
        "hp": min(sea.ship_hp, base_hp),
        "agi": base_agi,
    }


def level_up_check(sea: SeaProfile):
    """检查并处理升级"""
    leveled_up = False
    while sea.exp >= sea.level * 200:
        sea.exp -= sea.level * 200
        sea.level += 1
        sea.max_power += 10
        sea.power = sea.max_power
        sea.ship_max_hp += 20
        sea.ship_hp = sea.ship_max_hp
        sea.ship_damage += 2
        sea.ship_defense += 1
        sea.max_supplies += 10
        leveled_up = True
    return leveled_up


def give_initial_equipment(user: User, db: Session):
    """发放初始装备"""
    starter_equips = ["wooden_sword", "leather_armor", "sailor_hat"]
    for code in starter_equips:
        equip = db.query(SeaEquipment).filter(SeaEquipment.equip_code == code).first()
        if equip:
            existing = db.query(SeaUserEquipment).filter(
                SeaUserEquipment.user_id == user.id,
                SeaUserEquipment.equip_id == equip.id
            ).first()
            if not existing:
                ue = SeaUserEquipment(
                    user_id=user.id,
                    equip_id=equip.id,
                    enhance_level=0,
                    equipped=True
                )
                db.add(ue)


def give_initial_goods(user: User, db: Session):
    """发放初始物品"""
    starter_goods = [
        ("supply_bread", "干粮", 20, "supply"),
        ("supply_water", "淡水", 20, "supply"),
        ("cannon_ball", "炮弹", 10, "ammo"),
        ("medicine", "金疮药", 3, "medicine"),
    ]
    for code, name, qty, cat in starter_goods:
        existing = db.query(SeaUserGoods).filter(
            SeaUserGoods.user_id == user.id,
            SeaUserGoods.goods_code == code
        ).first()
        if existing:
            existing.quantity += qty
        else:
            db.add(SeaUserGoods(
                user_id=user.id,
                goods_code=code,
                goods_name=name,
                quantity=qty,
                category=cat
            ))


def init_sea_character(user: User, db: Session):
    """初始化航海角色"""
    init_base_data(db)

    if not user.sea:
        sea = SeaProfile(
            user_id=user.id,
            ship_name="起航号",
            current_city_code="quanzhou",
            silver_coin=1000,
            level=1,
            exp=0,
            power=100,
            max_power=100,
            ship_hp=100,
            ship_max_hp=100,
            ship_damage=10,
            ship_defense=5,
            ship_capacity=50,
            supplies=100,
            max_supplies=100,
        )
        db.add(sea)
        db.flush()

        # 解锁初始城市泉州
        quanzhou = get_city_by_code(db, "quanzhou")
        if quanzhou:
            db.add(SeaUserCity(
                user_id=user.id,
                city_id=quanzhou.id,
                unlocked=True,
                unlocked_at=datetime.utcnow()
            ))

        # 创建山寨
        db.add(SeaHideout(user_id=user.id))

        db.flush()

        # 发放初始装备和物品
        give_initial_equipment(user, db)
        give_initial_goods(user, db)

        # 发放初始宠物
        parrot = db.query(SeaPet).filter(SeaPet.pet_code == "parrot").first()
        if parrot:
            db.add(SeaUserPet(
                user_id=user.id,
                pet_id=parrot.id,
                nickname="波利",
                level=1,
                hp=parrot.base_hp,
                atk=parrot.base_atk,
                def_=parrot.base_def,
                agi=parrot.base_agi,
            ))

        # 接取初始任务
        starter_tasks = db.query(SeaTask).filter(SeaTask.level_required <= 1).all()
        for task in starter_tasks:
            db.add(SeaUserTask(
                sea_id=sea.id,
                user_id=user.id,
                task_id=task.id,
                status="accepted",
                accepted_at=datetime.utcnow(),
                progress_json=json.dumps({})
            ))

        db.commit()
        db.refresh(sea)
    else:
        # 确保山寨存在
        hideout = db.query(SeaHideout).filter(SeaHideout.user_id == user.id).first()
        if not hideout:
            db.add(SeaHideout(user_id=user.id))
            db.commit()


def simulate_sea_battle(sea: SeaProfile, enemy_name: str, enemy_level: int, enemy_type: str, db: Session):
    """模拟海战回合制战斗"""
    player_stats = calculate_sea_stats(sea, db)
    enemy_hp = 80 + enemy_level * 30
    enemy_max_hp = enemy_hp
    enemy_atk = 8 + enemy_level * 3
    enemy_def = 3 + enemy_level * 2

    battle_log = []
    round_num = 1
    player_hp = player_stats["hp"]
    player_max_hp = player_stats["max_hp"]

    battle_log.append(f"⚔️ 遭遇{enemy_name}（Lv.{enemy_level}）！战斗开始！")

    while player_hp > 0 and enemy_hp > 0 and round_num <= 20:
        # 玩家攻击
        import random as _r
        crit = _r.random() < 0.15
        dodge = _r.random() < 0.1
        if dodge:
            battle_log.append(f"第{round_num}回合：{enemy_name}闪避了你的攻击！")
        else:
            dmg = max(1, player_stats["atk"] - enemy_def + _r.randint(-3, 5))
            if crit:
                dmg = int(dmg * 1.8)
                battle_log.append(f"第{round_num}回合：你发动暴击！对{enemy_name}造成{dmg}点伤害！")
            else:
                battle_log.append(f"第{round_num}回合：你攻击{enemy_name}，造成{dmg}点伤害。")
            enemy_hp -= dmg

        if enemy_hp <= 0:
            break

        # 敌人攻击
        crit_e = _r.random() < 0.1
        dodge_e = _r.random() < 0.1
        if dodge_e:
            battle_log.append(f"第{round_num}回合：你闪避了{enemy_name}的攻击！")
        else:
            edmg = max(1, enemy_atk - player_stats["def"] + _r.randint(-2, 4))
            if crit_e:
                edmg = int(edmg * 1.5)
                battle_log.append(f"第{round_num}回合：{enemy_name}暴击！对你造成{edmg}点伤害！")
            else:
                battle_log.append(f"第{round_num}回合：{enemy_name}攻击你，造成{edmg}点伤害。")
            player_hp -= edmg

        round_num += 1

    win = player_hp > 0
    if win:
        silver_reward = _r.randint(30, 100) * enemy_level
        exp_reward = _r.randint(15, 40) * enemy_level
        battle_log.append(f"🎉 战斗胜利！获得{silver_reward}银两，{exp_reward}经验！")
        sea.silver_coin += silver_reward
        sea.exp += exp_reward
        sea.ship_hp = max(1, player_hp)
        result = "win"
    else:
        silver_loss = _r.randint(10, 50) * enemy_level
        sea.silver_coin = max(0, sea.silver_coin - silver_loss)
        sea.ship_hp = max(10, player_max_hp // 4)
        battle_log.append(f"💀 战斗失败！损失{silver_loss}银两，船只严重受损！")
        result = "lose"

    # 记录战斗
    db.add(SeaBattle(
        user_id=sea.user_id,
        enemy_type=enemy_type,
        enemy_name=enemy_name,
        battle_result=result,
        reward_json=json.dumps({"silver": silver_reward if win else -silver_loss, "exp": exp_reward if win else 0}),
        log="\n".join(battle_log)
    ))

    return {
        "win": win,
        "log": battle_log,
        "silver": silver_reward if win else -silver_loss,
        "exp": exp_reward if win else 0,
        "enemy_name": enemy_name,
        "enemy_level": enemy_level,
        "player_hp_remaining": max(1, player_hp) if win else max(10, player_max_hp // 4),
    }


def update_task_progress(user: User, sea: SeaProfile, prog_type: str, target: str = None, count: int = 1, db: Session = None):
    """更新任务进度"""
    user_tasks = db.query(SeaUserTask).filter(
        SeaUserTask.user_id == user.id,
        SeaUserTask.status == "accepted"
    ).all()

    for ut in user_tasks:
        task = db.query(SeaTask).filter(SeaTask.id == ut.task_id).first()
        if not task:
            continue
        try:
            obj = json.loads(task.objective_json) if task.objective_json else {}
        except:
            obj = {}

        try:
            progress = json.loads(ut.progress_json) if ut.progress_json else {}
        except:
            progress = {}

        if obj.get("type") == prog_type:
            if prog_type == "reach_level":
                if sea.level >= obj.get("target", 999):
                    ut.status = "completed"
                    ut.completed_at = datetime.utcnow()
            elif prog_type == "visit_city":
                if target == obj.get("target"):
                    ut.status = "completed"
                    ut.completed_at = datetime.utcnow()
            elif prog_type == "defeat_enemy":
                if target == obj.get("target"):
                    progress["count"] = progress.get("count", 0) + count
                    ut.progress_json = json.dumps(progress)
                    if progress["count"] >= obj.get("count", 1):
                        ut.status = "completed"
                        ut.completed_at = datetime.utcnow()
            elif prog_type == "buy_supplies":
                progress["amount"] = progress.get("amount", 0) + count
                ut.progress_json = json.dumps(progress)
                if progress["amount"] >= obj.get("target", 0):
                    ut.status = "completed"
                    ut.completed_at = datetime.utcnow()


# ==================== 路由：角色首页 ====================

@router.get("", response_class=HTMLResponse)
async def sea_home(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)
    sea = user.sea

    current_city = get_city_by_code(db, sea.current_city_code)
    stats = calculate_sea_stats(sea, db)

    # 可用航线
    available_routes = db.query(SeaRoute).filter(
        SeaRoute.from_city_code == sea.current_city_code
    ).all()

    # 当前任务
    my_tasks = db.query(SeaUserTask).filter(
        SeaUserTask.user_id == user.id,
        SeaUserTask.status.in_(["accepted", "completed"])
    ).all()
    task_details = []
    for ut in my_tasks:
        task = db.query(SeaTask).filter(SeaTask.id == ut.task_id).first()
        if task:
            task_details.append({"user_task": ut, "task": task})

    # 已解锁城市
    unlocked_cities = db.query(SeaUserCity).filter(
        SeaUserCity.user_id == user.id,
        SeaUserCity.unlocked == True
    ).all()

    # 最近事件
    recent_events = db.query(SeaEvent).filter(
        SeaEvent.user_id == user.id
    ).order_by(desc(SeaEvent.created_at)).limit(5).all()

    # 最近战斗
    recent_battles = db.query(SeaBattle).filter(
        SeaBattle.user_id == user.id
    ).order_by(desc(SeaBattle.created_at)).limit(3).all()

    # 装备信息
    equipped = {}
    for ue in db.query(SeaUserEquipment).filter(
        SeaUserEquipment.user_id == user.id,
        SeaUserEquipment.equipped == True
    ).all():
        eq = db.query(SeaEquipment).filter(SeaEquipment.id == ue.equip_id).first()
        if eq:
            equipped[eq.slot_type] = {"ue": ue, "equip": eq}

    ctx.update({
        "sea": sea,
        "stats": stats,
        "current_city": current_city,
        "available_routes": available_routes,
        "task_details": task_details,
        "unlocked_cities": unlocked_cities,
        "recent_events": recent_events,
        "recent_battles": recent_battles,
        "equipped": equipped,
        "slot_names": SLOT_NAMES,
        "get_city_name": lambda code: get_city_name(db, code),
        "message": request.query_params.get("msg"),
        "error": request.query_params.get("error"),
    })
    return templates.TemplateResponse("zongheng_sihai/index.html", ctx)


# ==================== 路由：角色创建（名字设置） ====================

@router.post("/set_ship_name")
async def set_ship_name(request: Request, ship_name: str = Form("起航号"), db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)
    sea = user.sea

    if ship_name.strip():
        sea.ship_name = ship_name.strip()[:20]
        db.commit()

    return RedirectResponse(url="/zongheng_sihai", status_code=302)


# ==================== 路由：休息恢复 ====================

@router.get("/rest")
async def rest(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)
    sea = user.sea

    sea.power = sea.max_power
    sea.ship_hp = sea.ship_max_hp
    db.commit()

    return RedirectResponse(url="/zongheng_sihai?msg=休息完毕，体力和船只耐久已完全恢复！", status_code=302)


# ==================== 路由：城市系统 ====================

@router.get("/city", response_class=HTMLResponse)
async def city_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)
    sea = user.sea

    current_city = get_city_by_code(db, sea.current_city_code)

    # 可接任务
    available_tasks = db.query(SeaTask).filter(
        SeaTask.city_code == sea.current_city_code,
        SeaTask.level_required <= sea.level
    ).all()

    accepted_task_ids = [ut.task_id for ut in db.query(SeaUserTask).filter(
        SeaUserTask.user_id == user.id
    ).all()]

    # 可用航线
    routes = db.query(SeaRoute).filter(
        SeaRoute.from_city_code == sea.current_city_code
    ).all()
    route_info = []
    for r in routes:
        to_city = get_city_by_code(db, r.to_city_code)
        route_info.append({"route": r, "to_city": to_city})

    # 该城市商店装备
    shop_equipments = db.query(SeaEquipment).filter(
        SeaEquipment.level_required <= sea.level + 5
    ).order_by(SeaEquipment.level_required).limit(12).all()

    ctx.update({
        "sea": sea,
        "current_city": current_city,
        "available_tasks": available_tasks,
        "accepted_task_ids": accepted_task_ids,
        "route_info": route_info,
        "shop_equipments": shop_equipments,
        "message": request.query_params.get("msg"),
    })
    return templates.TemplateResponse("zongheng_sihai/city.html", ctx)


# ==================== 路由：航线与航行 ====================

@router.get("/sail", response_class=HTMLResponse)
async def sail_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)
    sea = user.sea

    routes = db.query(SeaRoute).filter(
        SeaRoute.from_city_code == sea.current_city_code
    ).all()
    route_info = []
    for r in routes:
        to_city = get_city_by_code(db, r.to_city_code)
        danger_names = {1: "安全", 2: "轻微", 3: "中等", 4: "危险", 5: "极险"}
        route_info.append({
            "route": r,
            "to_city": to_city,
            "danger_name": danger_names.get(r.danger_level, "未知"),
            "supplies_needed": r.travel_time // 5 + 10,
        })

    ctx.update({
        "sea": sea,
        "current_city": get_city_by_code(db, sea.current_city_code),
        "route_info": route_info,
        "error": request.query_params.get("error"),
    })
    return templates.TemplateResponse("zongheng_sihai/sail.html", ctx)


@router.get("/sail/start/{route_id}", response_class=HTMLResponse)
async def do_sail(request: Request, route_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)
    sea = user.sea

    route = db.query(SeaRoute).filter(SeaRoute.id == route_id).first()
    if not route:
        return RedirectResponse(url="/zongheng_sihai/sail?error=航线不存在", status_code=302)

    if route.from_city_code != sea.current_city_code:
        return RedirectResponse(url="/zongheng_sihai/sail?error=你不在该航线的起始港口", status_code=302)

    supplies_needed = route.travel_time // 5 + 10
    if sea.supplies < supplies_needed:
        return RedirectResponse(url=f"/zongheng_sihai/sail?error=补给不足！需要{supplies_needed}单位补给", status_code=302)

    if sea.power < 20:
        return RedirectResponse(url="/zongheng_sihai/sail?error=体力不足，请先休息", status_code=302)

    sea.supplies -= supplies_needed
    sea.power -= 20

    # 航行中随机事件
    event_type = random.choices(EVENT_TYPES, weights=EVENT_WEIGHTS, k=1)[0]

    event_result = {}
    battle_result_data = None

    if event_type == "pirate":
        pirate_name = random.choice(PIRATE_NAMES)
        pirate_level = max(1, sea.level + random.randint(-2, route.danger_level))
        battle_result_data = simulate_sea_battle(sea, pirate_name, pirate_level, "pirate", db)
        event_result = {"pirate": pirate_name, "battle": battle_result_data}
        if battle_result_data["win"]:
            update_task_progress(user, sea, "defeat_enemy", "pirate", 1, db)

        db.add(SeaEvent(
            user_id=user.id,
            route_id=route_id,
            event_type="pirate",
            result_json=json.dumps({"pirate": pirate_name, "result": battle_result_data["win"]})
        ))

    elif event_type == "storm":
        damage = random.randint(10, 15) + route.danger_level * 5
        sea.ship_hp = max(10, sea.ship_hp - damage)
        event_result = {"damage": damage, "message": f"遭遇暴风雨，船只受损{damage}点！"}
        db.add(SeaEvent(
            user_id=user.id, route_id=route_id, event_type="storm",
            result_json=json.dumps(event_result)
        ))

    elif event_type == "treasure":
        silver_found = random.randint(100, 300) * sea.level
        sea.silver_coin += silver_found
        event_result = {"silver": silver_found, "message": f"发现漂浮的宝箱！获得{silver_found}银两！"}
        db.add(SeaEvent(
            user_id=user.id, route_id=route_id, event_type="treasure",
            result_json=json.dumps(event_result)
        ))

    elif event_type == "adventure":
        adv_type = random.choice(["mermaid", "ghost_ship", "floating_island", "ancient_map"])
        adv_messages = {
            "mermaid": "遇到了善良的美人鱼，她为你指引方向，船只恢复了一些耐久！",
            "ghost_ship": "发现了一艘幽灵船残骸，搜出了一些物资！",
            "floating_island": "发现了一座神秘的浮岛，岛上有珍贵的补给！",
            "ancient_map": "捞到了一张古老的海图，获得了额外经验！",
        }
        if adv_type == "mermaid":
            heal = random.randint(20, 50)
            sea.ship_hp = min(sea.ship_max_hp, sea.ship_hp + heal)
            event_result = {"message": adv_messages[adv_type], "heal": heal}
        elif adv_type == "ghost_ship":
            silver = random.randint(200, 500) * sea.level
            sea.silver_coin += silver
            event_result = {"message": adv_messages[adv_type], "silver": silver}
        elif adv_type == "floating_island":
            sup = random.randint(20, 50)
            sea.supplies = min(sea.max_supplies, sea.supplies + sup)
            event_result = {"message": adv_messages[adv_type], "supplies": sup}
        else:
            exp_gain = random.randint(50, 150)
            sea.exp += exp_gain
            event_result = {"message": adv_messages[adv_type], "exp": exp_gain}

        db.add(SeaEvent(
            user_id=user.id, route_id=route_id, event_type="adventure",
            result_json=json.dumps(event_result)
        ))

    elif event_type == "merchant":
        profit = random.randint(50, 200) * sea.level
        sea.silver_coin += profit
        event_result = {"profit": profit, "message": f"途中遇到友好的商船，进行了一笔小交易，赚了{profit}银两！"}
        db.add(SeaEvent(
            user_id=user.id, route_id=route_id, event_type="merchant",
            result_json=json.dumps(event_result)
        ))

    else:  # calm
        event_result = {"message": "一路顺风，平安抵达目的地。"}
        db.add(SeaEvent(
            user_id=user.id, route_id=route_id, event_type="calm",
            result_json=json.dumps(event_result)
        ))

    # 到达目的城市
    to_city = get_city_by_code(db, route.to_city_code)
    arrived_city_name = to_city.name if to_city else route.to_city_code

    if to_city:
        old_city = sea.current_city_code
        sea.current_city_code = route.to_city_code

        user_city = db.query(SeaUserCity).filter(
            SeaUserCity.user_id == user.id,
            SeaUserCity.city_id == to_city.id
        ).first()
        newly_unlocked = False
        if not user_city:
            db.add(SeaUserCity(
                user_id=user.id,
                city_id=to_city.id,
                unlocked=True,
                unlocked_at=datetime.utcnow()
            ))
            sea.exp += 100
            newly_unlocked = True

        update_task_progress(user, sea, "visit_city", route.to_city_code, 1, db)
        event_result["arrived_city"] = arrived_city_name
        event_result["newly_unlocked"] = newly_unlocked

    # 升级检查
    level_up_check(sea)
    update_task_progress(user, sea, "reach_level", db=db)

    db.commit()

    ctx.update({
        "sea": sea,
        "route": route,
        "from_city": get_city_by_code(db, route.from_city_code),
        "to_city": to_city,
        "event_type": event_type,
        "event_result": event_result,
        "battle_result": battle_result_data,
    })
    return templates.TemplateResponse("zongheng_sihai/sail.html", ctx)


# ==================== 路由：战斗系统 ====================

@router.get("/battle", response_class=HTMLResponse)
async def battle_page(request: Request, enemy_type: str = "pirate", db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)
    sea = user.sea

    if enemy_type == "pirate":
        enemy_name = random.choice(PIRATE_NAMES)
        enemy_level = max(1, sea.level + random.randint(-2, 2))
    elif enemy_type == "monster":
        enemy_name = random.choice(MONSTER_NAMES)
        enemy_level = max(1, sea.level + random.randint(0, 3))
    else:
        enemy_name = "小海盗"
        enemy_level = max(1, sea.level)

    ctx.update({
        "sea": sea,
        "stats": calculate_sea_stats(sea, db),
        "enemy_name": enemy_name,
        "enemy_level": enemy_level,
        "enemy_type": enemy_type,
    })
    return templates.TemplateResponse("zongheng_sihai/battle.html", ctx)


@router.get("/battle/fight", response_class=HTMLResponse)
async def do_battle(request: Request, enemy_type: str = "pirate", enemy_level: int = 1, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)
    sea = user.sea

    if sea.power < 10:
        return RedirectResponse(url="/zongheng_sihai/battle?error=体力不足，请先休息", status_code=302)

    sea.power -= 10

    if enemy_type == "pirate":
        enemy_name = random.choice(PIRATE_NAMES)
    else:
        enemy_name = random.choice(MONSTER_NAMES)

    enemy_level = max(1, min(enemy_level, sea.level + 5))
    result = simulate_sea_battle(sea, enemy_name, enemy_level, enemy_type, db)

    if result["win"]:
        update_task_progress(user, sea, "defeat_enemy", enemy_type, 1, db)

    level_up_check(sea)
    update_task_progress(user, sea, "reach_level", db=db)
    db.commit()

    ctx.update({
        "sea": sea,
        "stats": calculate_sea_stats(sea, db),
        "result": result,
        "enemy_type": enemy_type,
    })
    return templates.TemplateResponse("zongheng_sihai/battle.html", ctx)


# ==================== 路由：任务系统 ====================

@router.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)
    sea = user.sea

    # 我的任务
    my_tasks = db.query(SeaUserTask).filter(
        SeaUserTask.user_id == user.id
    ).all()

    task_list = []
    for ut in my_tasks:
        task = db.query(SeaTask).filter(SeaTask.id == ut.task_id).first()
        if task:
            try:
                progress = json.loads(ut.progress_json) if ut.progress_json else {}
            except:
                progress = {}
            try:
                reward = json.loads(task.reward_json) if task.reward_json else {}
            except:
                reward = {}
            try:
                objective = json.loads(task.objective_json) if task.objective_json else {}
            except:
                objective = {}
            task_list.append({
                "user_task": ut,
                "task": task,
                "progress": progress,
                "reward": reward,
                "objective": objective,
            })

    # 可接任务
    accepted_ids = [ut.task_id for ut in my_tasks]
    available_tasks = db.query(SeaTask).filter(
        SeaTask.level_required <= sea.level,
        ~SeaTask.id.in_(accepted_ids) if accepted_ids else True
    ).all()

    ctx.update({
        "sea": sea,
        "task_list": task_list,
        "available_tasks": available_tasks,
        "message": request.query_params.get("msg"),
    })
    return templates.TemplateResponse("zongheng_sihai/tasks.html", ctx)


@router.get("/tasks/accept/{task_id}")
async def accept_task(request: Request, task_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)
    sea = user.sea

    task = db.query(SeaTask).filter(SeaTask.id == task_id).first()
    if not task:
        return RedirectResponse(url="/zongheng_sihai/tasks", status_code=302)

    existing = db.query(SeaUserTask).filter(
        SeaUserTask.user_id == user.id,
        SeaUserTask.task_id == task_id
    ).first()
    if existing:
        return RedirectResponse(url="/zongheng_sihai/tasks", status_code=302)

    db.add(SeaUserTask(
        sea_id=sea.id,
        user_id=user.id,
        task_id=task_id,
        status="accepted",
        accepted_at=datetime.utcnow(),
        progress_json=json.dumps({})
    ))
    db.commit()

    return RedirectResponse(url="/zongheng_sihai/tasks?msg=已接取任务", status_code=302)


@router.get("/tasks/claim/{task_id}")
async def claim_task_reward(request: Request, task_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)
    sea = user.sea

    ut = db.query(SeaUserTask).filter(
        SeaUserTask.user_id == user.id,
        SeaUserTask.task_id == task_id,
        SeaUserTask.status == "completed"
    ).first()
    if not ut:
        return RedirectResponse(url="/zongheng_sihai/tasks", status_code=302)

    task = db.query(SeaTask).filter(SeaTask.id == task_id).first()
    if not task:
        return RedirectResponse(url="/zongheng_sihai/tasks", status_code=302)

    try:
        reward = json.loads(task.reward_json) if task.reward_json else {}
    except:
        reward = {}

    # 发放奖励
    silver = reward.get("silver", 0)
    exp = reward.get("exp", 0)
    sea.silver_coin += silver
    sea.exp += exp

    # 发放物品奖励
    items = reward.get("items", [])
    for item in items:
        # 检查是否是装备
        equip = db.query(SeaEquipment).filter(SeaEquipment.equip_code == item.get("code", "")).first()
        if equip:
            existing_ue = db.query(SeaUserEquipment).filter(
                SeaUserEquipment.user_id == user.id,
                SeaUserEquipment.equip_id == equip.id
            ).first()
            if not existing_ue:
                db.add(SeaUserEquipment(
                    user_id=user.id,
                    equip_id=equip.id,
                    enhance_level=0,
                    equipped=False
                ))
        else:
            # 商品类物品
            goods = db.query(SeaGoods).filter(SeaGoods.goods_code == item.get("code", "")).first()
            if goods:
                existing_g = db.query(SeaUserGoods).filter(
                    SeaUserGoods.user_id == user.id,
                    SeaUserGoods.goods_code == goods.goods_code
                ).first()
                if existing_g:
                    existing_g.quantity += item.get("qty", 1)
                else:
                    db.add(SeaUserGoods(
                        user_id=user.id,
                        goods_code=goods.goods_code,
                        goods_name=goods.name,
                        quantity=item.get("qty", 1),
                        category=goods.category
                    ))

    ut.status = "claimed"
    level_up_check(sea)
    db.commit()

    msg = f"领取奖励成功！获得{silver}银两，{exp}经验"
    if items:
        item_names = [i.get("name", "") for i in items]
        msg += f"，物品：{'、'.join(item_names)}"

    return RedirectResponse(url=f"/zongheng_sihai/tasks?msg={msg}", status_code=302)


# ==================== 路由：装备系统 ====================

@router.get("/equipment", response_class=HTMLResponse)
async def equipment_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)
    sea = user.sea

    # 已装备
    equipped = {}
    unequipped = []
    all_ue = db.query(SeaUserEquipment).filter(SeaUserEquipment.user_id == user.id).all()
    for ue in all_ue:
        eq = db.query(SeaEquipment).filter(SeaEquipment.id == ue.equip_id).first()
        if eq:
            try:
                attrs = json.loads(eq.base_attr_json) if eq.base_attr_json else {}
            except:
                attrs = {}
            eq_info = {"ue": ue, "equip": eq, "attrs": attrs}
            if ue.equipped:
                equipped[eq.slot_type] = eq_info
            else:
                unequipped.append(eq_info)

    stats = calculate_sea_stats(sea, db)

    ctx.update({
        "sea": sea,
        "equipped": equipped,
        "unequipped": unequipped,
        "stats": stats,
        "slot_names": SLOT_NAMES,
        "message": request.query_params.get("msg"),
    })
    return templates.TemplateResponse("zongheng_sihai/equipment.html", ctx)


@router.get("/equipment/equip/{ue_id}")
async def do_equip(request: Request, ue_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)

    ue = db.query(SeaUserEquipment).filter(
        SeaUserEquipment.id == ue_id,
        SeaUserEquipment.user_id == user.id
    ).first()
    if not ue:
        return RedirectResponse(url="/zongheng_sihai/equipment", status_code=302)

    eq = db.query(SeaEquipment).filter(SeaEquipment.id == ue.equip_id).first()
    if not eq:
        return RedirectResponse(url="/zongheng_sihai/equipment", status_code=302)

    # 卸下同槽位装备
    old_equip = db.query(SeaUserEquipment).filter(
        SeaUserEquipment.user_id == user.id,
        SeaUserEquipment.equipped == True
    ).all()
    for old in old_equip:
        old_eq = db.query(SeaEquipment).filter(SeaEquipment.id == old.equip_id).first()
        if old_eq and old_eq.slot_type == eq.slot_type and old.id != ue.id:
            old.equipped = False

    ue.equipped = True
    db.commit()

    return RedirectResponse(url="/zongheng_sihai/equipment?msg=装备成功", status_code=302)


@router.get("/equipment/unequip/{ue_id}")
async def do_unequip(request: Request, ue_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)

    ue = db.query(SeaUserEquipment).filter(
        SeaUserEquipment.id == ue_id,
        SeaUserEquipment.user_id == user.id
    ).first()
    if not ue:
        return RedirectResponse(url="/zongheng_sihai/equipment", status_code=302)

    ue.equipped = False
    db.commit()

    return RedirectResponse(url="/zongheng_sihai/equipment?msg=已卸下装备", status_code=302)


@router.get("/equipment/enhance/{ue_id}")
async def do_enhance(request: Request, ue_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)
    sea = user.sea

    ue = db.query(SeaUserEquipment).filter(
        SeaUserEquipment.id == ue_id,
        SeaUserEquipment.user_id == user.id
    ).first()
    if not ue:
        return RedirectResponse(url="/zongheng_sihai/equipment", status_code=302)

    cost = (ue.enhance_level + 1) * 200
    if sea.silver_coin < cost:
        return RedirectResponse(url=f"/zongheng_sihai/equipment?msg=强化失败，银两不足（需要{cost}）", status_code=302)

    sea.silver_coin -= cost
    success_rate = max(0.2, 1.0 - ue.enhance_level * 0.1)
    if random.random() < success_rate:
        ue.enhance_level += 1
        msg = f"强化成功！装备强化等级+{ue.enhance_level}"
    else:
        msg = "强化失败！银两已消耗"

    db.commit()
    return RedirectResponse(url=f"/zongheng_sihai/equipment?msg={msg}", status_code=302)


# ==================== 路由：背包系统 ====================

@router.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request, category: str = "all", db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)
    sea = user.sea

    categories = {
        "all": "全部",
        "supply": "补给",
        "ammo": "弹药",
        "medicine": "药品",
        "material": "材料",
        "trade": "贸易品",
    }

    goods_query = db.query(SeaUserGoods).filter(SeaUserGoods.user_id == user.id)
    if category != "all":
        goods_query = goods_query.filter(SeaUserGoods.category == category)
    goods = goods_query.all()

    # 获取商品详情
    goods_info = []
    for g in goods:
        goods_def = db.query(SeaGoods).filter(SeaGoods.goods_code == g.goods_code).first()
        goods_info.append({"user_goods": g, "goods": goods_def})

    ctx.update({
        "sea": sea,
        "goods_info": goods_info,
        "categories": categories,
        "current_category": category,
        "message": request.query_params.get("msg"),
    })
    return templates.TemplateResponse("zongheng_sihai/inventory.html", ctx)


@router.get("/inventory/use/{goods_id}")
async def use_goods(request: Request, goods_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)
    sea = user.sea

    ug = db.query(SeaUserGoods).filter(
        SeaUserGoods.id == goods_id,
        SeaUserGoods.user_id == user.id
    ).first()
    if not ug:
        return RedirectResponse(url="/zongheng_sihai/inventory", status_code=302)

    goods_def = db.query(SeaGoods).filter(SeaGoods.goods_code == ug.goods_code).first()
    msg = ""

    if ug.goods_code == "supply_bread":
        sea.supplies = min(sea.max_supplies, sea.supplies + 10)
        msg = "食用干粮，补给+10"
    elif ug.goods_code == "supply_water":
        sea.supplies = min(sea.max_supplies, sea.supplies + 5)
        msg = "补充淡水，补给+5"
    elif ug.goods_code == "medicine":
        sea.ship_hp = min(sea.ship_max_hp, sea.ship_hp + 50)
        msg = "使用金疮药，船只耐久+50"
    elif ug.goods_code == "repair_wood":
        sea.ship_hp = min(sea.ship_max_hp, sea.ship_hp + 30)
        msg = "使用木料修船，船只耐久+30"
    elif ug.goods_code == "rum":
        sea.power = min(sea.max_power, sea.power + 30)
        msg = "喝了朗姆酒，体力+30"
    else:
        msg = "该物品无法直接使用"

    if goods_def and goods_def.category in ["supply", "medicine", "ammo"]:
        if ug.quantity <= 1:
            db.delete(ug)
        else:
            ug.quantity -= 1
        update_task_progress(user, sea, "buy_supplies", count=1, db=db)

    db.commit()
    return RedirectResponse(url=f"/zongheng_sihai/inventory?msg={msg}", status_code=302)


# ==================== 路由：山寨系统 ====================

@router.get("/hideout", response_class=HTMLResponse)
async def hideout_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)
    sea = user.sea

    hideout = db.query(SeaHideout).filter(SeaHideout.user_id == user.id).first()
    if not hideout:
        hideout = SeaHideout(user_id=user.id)
        db.add(hideout)
        db.flush()
        db.commit()
        db.refresh(hideout)

    # 农田
    plots = db.query(SeaHideoutPlot).filter(SeaHideoutPlot.hideout_id == hideout.id).all()
    existing_plot_nos = {p.plot_no for p in plots}
    for i in range(1, hideout.farm_plots_count + 1):
        if i not in existing_plot_nos:
            db.add(SeaHideoutPlot(
                hideout_id=hideout.id,
                plot_no=i,
                status="idle"
            ))
    db.commit()
    plots = db.query(SeaHideoutPlot).filter(SeaHideoutPlot.hideout_id == hideout.id).order_by(SeaHideoutPlot.plot_no).all()

    # 计算作物状态
    plot_info = []
    now = datetime.utcnow()
    for p in plots:
        info = {"plot": p, "crop": None, "ready": False, "remaining": 0}
        if p.status == "growing" and p.crop_code:
            crop = CROPS.get(p.crop_code, {})
            info["crop"] = crop
            if p.ready_at and now >= p.ready_at:
                info["ready"] = True
            elif p.ready_at:
                info["remaining"] = int((p.ready_at - now).total_seconds())
        plot_info.append(info)

    # 练功房
    training_room = db.query(SeaTrainingRoom).filter(SeaTrainingRoom.hideout_id == hideout.id).first()
    if not training_room:
        training_room = SeaTrainingRoom(hideout_id=hideout.id)
        db.add(training_room)
        db.commit()
        db.refresh(training_room)

    training_remaining = 0
    if training_room.is_training and training_room.training_start:
        elapsed = (now - training_room.training_start).total_seconds()
        training_room.accumulated_exp = int(elapsed / 3600 * training_room.exp_per_hour)
        training_remaining = -1  # 正在训练中
    db.commit()

    ctx.update({
        "sea": sea,
        "hideout": hideout,
        "plot_info": plot_info,
        "crops": CROPS,
        "training_room": training_room,
        "training_remaining": training_remaining,
        "message": request.query_params.get("msg"),
    })
    return templates.TemplateResponse("zongheng_sihai/hideout.html", ctx)


@router.get("/hideout/plant/{plot_no}/{crop_code}")
async def plant_crop(request: Request, plot_no: int, crop_code: str, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)

    hideout = db.query(SeaHideout).filter(SeaHideout.user_id == user.id).first()
    if not hideout:
        return RedirectResponse(url="/zongheng_sihai/hideout", status_code=302)

    plot = db.query(SeaHideoutPlot).filter(
        SeaHideoutPlot.hideout_id == hideout.id,
        SeaHideoutPlot.plot_no == plot_no
    ).first()
    if not plot:
        return RedirectResponse(url="/zongheng_sihai/hideout", status_code=302)

    crop = CROPS.get(crop_code)
    if not crop:
        return RedirectResponse(url="/zongheng_sihai/hideout?msg=未知作物", status_code=302)

    if plot.status == "growing":
        return RedirectResponse(url="/zongheng_sihai/hideout?msg=该地块已有作物", status_code=302)

    seed_cost = crop["reward"] // 5
    if user.sea.silver_coin < seed_cost:
        return RedirectResponse(url=f"/zongheng_sihai/hideout?msg=银两不足，需要{seed_cost}银两购买种子", status_code=302)

    user.sea.silver_coin -= seed_cost
    plot.crop_code = crop_code
    plot.crop_name = crop["name"]
    plot.planted_at = datetime.utcnow()
    plot.ready_at = datetime.utcnow() + timedelta(seconds=crop["grow_time"])
    plot.status = "growing"
    plot.silver_reward = crop["reward"]

    db.commit()
    return RedirectResponse(url=f"/zongheng_sihai/hideout?msg=种植{crop['name']}成功！", status_code=302)


@router.get("/hideout/harvest/{plot_no}")
async def harvest_crop(request: Request, plot_no: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)
    sea = user.sea

    hideout = db.query(SeaHideout).filter(SeaHideout.user_id == user.id).first()
    if not hideout:
        return RedirectResponse(url="/zongheng_sihai/hideout", status_code=302)

    plot = db.query(SeaHideoutPlot).filter(
        SeaHideoutPlot.hideout_id == hideout.id,
        SeaHideoutPlot.plot_no == plot_no
    ).first()
    if not plot or plot.status != "growing":
        return RedirectResponse(url="/zongheng_sihai/hideout", status_code=302)

    now = datetime.utcnow()
    if not plot.ready_at or now < plot.ready_at:
        return RedirectResponse(url="/zongheng_sihai/hideout?msg=作物尚未成熟", status_code=302)

    reward = plot.silver_reward
    sea.silver_coin += reward
    sea.exp += 20

    plot.crop_code = None
    plot.crop_name = None
    plot.planted_at = None
    plot.ready_at = None
    plot.status = "idle"
    plot.silver_reward = 0

    hideout.last_farm_harvest = now
    level_up_check(sea)
    db.commit()

    return RedirectResponse(url=f"/zongheng_sihai/hideout?msg=收获成功！获得{reward}银两，20经验", status_code=302)


@router.get("/hideout/training/start")
async def start_training(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)

    hideout = db.query(SeaHideout).filter(SeaHideout.user_id == user.id).first()
    if not hideout:
        return RedirectResponse(url="/zongheng_sihai/hideout", status_code=302)

    training_room = db.query(SeaTrainingRoom).filter(SeaTrainingRoom.hideout_id == hideout.id).first()
    if not training_room:
        training_room = SeaTrainingRoom(hideout_id=hideout.id)
        db.add(training_room)
        db.flush()

    if training_room.is_training:
        return RedirectResponse(url="/zongheng_sihai/hideout?msg=你已经在练功中了", status_code=302)

    training_room.is_training = True
    training_room.training_start = datetime.utcnow()
    training_room.accumulated_exp = 0
    db.commit()

    return RedirectResponse(url="/zongheng_sihai/hideout?msg=开始练功！", status_code=302)


@router.get("/hideout/training/stop")
async def stop_training(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)
    sea = user.sea

    hideout = db.query(SeaHideout).filter(SeaHideout.user_id == user.id).first()
    if not hideout:
        return RedirectResponse(url="/zongheng_sihai/hideout", status_code=302)

    training_room = db.query(SeaTrainingRoom).filter(SeaTrainingRoom.hideout_id == hideout.id).first()
    if not training_room or not training_room.is_training:
        return RedirectResponse(url="/zongheng_sihai/hideout", status_code=302)

    now = datetime.utcnow()
    if training_room.training_start:
        elapsed_hours = (now - training_room.training_start).total_seconds() / 3600
        exp_gained = int(elapsed_hours * training_room.exp_per_hour)
        exp_gained = min(exp_gained, 5000)
    else:
        exp_gained = 0

    sea.exp += exp_gained
    training_room.is_training = False
    training_room.training_start = None
    training_room.accumulated_exp = 0
    hideout.last_training_reward = now

    level_up_check(sea)
    db.commit()

    return RedirectResponse(url=f"/zongheng_sihai/hideout?msg=练功结束，获得{exp_gained}经验！", status_code=302)


# ==================== 路由：商店系统 ====================

@router.get("/shop", response_class=HTMLResponse)
async def shop_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)
    sea = user.sea

    # 商品分类
    all_goods = db.query(SeaGoods).filter(SeaGoods.level_required <= sea.level).all()
    goods_by_cat = {}
    for g in all_goods:
        cat = g.category
        if cat not in goods_by_cat:
            goods_by_cat[cat] = []
        goods_by_cat[cat].append(g)

    # 装备
    equipments = db.query(SeaEquipment).filter(
        SeaEquipment.level_required <= sea.level + 5
    ).order_by(SeaEquipment.price).all()

    # 已拥有的装备
    my_equip_ids = [ue.equip_id for ue in db.query(SeaUserEquipment).filter(
        SeaUserEquipment.user_id == user.id
    ).all()]

    ctx.update({
        "sea": sea,
        "goods_by_cat": goods_by_cat,
        "equipments": equipments,
        "my_equip_ids": my_equip_ids,
        "cat_names": {"supply": "补给品", "ammo": "弹药", "medicine": "药品", "material": "材料", "trade": "贸易品"},
        "message": request.query_params.get("msg"),
        "error": request.query_params.get("error"),
    })
    return templates.TemplateResponse("zongheng_sihai/shop.html", ctx)


@router.post("/shop/buy_supplies")
async def buy_supplies(request: Request, amount: int = Form(50), db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)
    sea = user.sea

    cost = amount * 2
    if sea.silver_coin < cost:
        return RedirectResponse(url="/zongheng_sihai/shop?error=银两不足", status_code=302)

    sea.silver_coin -= cost
    sea.supplies = min(sea.supplies + amount, sea.max_supplies)
    update_task_progress(user, sea, "buy_supplies", count=amount, db=db)

    db.commit()
    return RedirectResponse(url=f"/zongheng_sihai/shop?msg=购买{amount}单位补给成功，花费{cost}银两", status_code=302)


@router.get("/shop/buy_goods/{goods_code}")
async def buy_goods(request: Request, goods_code: str, qty: int = 1, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)
    sea = user.sea

    goods = db.query(SeaGoods).filter(SeaGoods.goods_code == goods_code).first()
    if not goods:
        return RedirectResponse(url="/zongheng_sihai/shop?error=商品不存在", status_code=302)

    cost = goods.buy_price * qty
    if sea.silver_coin < cost:
        return RedirectResponse(url="/zongheng_sihai/shop?error=银两不足", status_code=302)

    sea.silver_coin -= cost

    existing = db.query(SeaUserGoods).filter(
        SeaUserGoods.user_id == user.id,
        SeaUserGoods.goods_code == goods_code
    ).first()
    if existing:
        existing.quantity += qty
    else:
        db.add(SeaUserGoods(
            user_id=user.id,
            goods_code=goods.goods_code,
            goods_name=goods.name,
            quantity=qty,
            category=goods.category
        ))

    db.commit()
    return RedirectResponse(url=f"/zongheng_sihai/shop?msg=购买{goods.name}x{qty}成功，花费{cost}银两", status_code=302)


@router.get("/shop/buy_equipment/{equip_id}")
async def buy_equipment(request: Request, equip_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)
    sea = user.sea

    equip = db.query(SeaEquipment).filter(SeaEquipment.id == equip_id).first()
    if not equip:
        return RedirectResponse(url="/zongheng_sihai/shop?error=装备不存在", status_code=302)

    if sea.silver_coin < equip.price:
        return RedirectResponse(url="/zongheng_sihai/shop?error=银两不足", status_code=302)

    # 检查是否已拥有
    existing = db.query(SeaUserEquipment).filter(
        SeaUserEquipment.user_id == user.id,
        SeaUserEquipment.equip_id == equip_id
    ).first()
    if existing:
        return RedirectResponse(url="/zongheng_sihai/shop?error=你已拥有该装备", status_code=302)

    sea.silver_coin -= equip.price
    db.add(SeaUserEquipment(
        user_id=user.id,
        equip_id=equip_id,
        enhance_level=0,
        equipped=False
    ))

    db.commit()
    return RedirectResponse(url=f"/zongheng_sihai/shop?msg=购买{equip.name}成功！", status_code=302)


@router.get("/shop/sell/{goods_id}")
async def sell_goods(request: Request, goods_id: int, qty: int = 1, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    user = ctx["user"]
    init_sea_character(user, db)
    sea = user.sea

    ug = db.query(SeaUserGoods).filter(
        SeaUserGoods.id == goods_id,
        SeaUserGoods.user_id == user.id
    ).first()
    if not ug:
        return RedirectResponse(url="/zongheng_sihai/shop", status_code=302)

    goods_def = db.query(SeaGoods).filter(SeaGoods.goods_code == ug.goods_code).first()
    if not goods_def:
        return RedirectResponse(url="/zongheng_sihai/shop", status_code=302)

    sell_qty = min(qty, ug.quantity)
    earn = goods_def.sell_price * sell_qty
    sea.silver_coin += earn

    ug.quantity -= sell_qty
    if ug.quantity <= 0:
        db.delete(ug)

    db.commit()
    return RedirectResponse(url=f"/zongheng_sihai/shop?msg=出售{goods_def.name}x{sell_qty}，获得{earn}银两", status_code=302)
