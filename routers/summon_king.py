from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
import random
import json
from datetime import datetime

from models.database import get_db, engine, Base
from models.models import (
    SummonProfile, SummonMap, SummonBeast, SummonUserBeast,
    SummonSkill, SummonUserBeastSkill, SummonCatchLog,
    SummonBone, SummonUserBone, SummonSoul, SummonUserSoul, SummonSoulHuntLog,
    SummonSpirit, SummonUserSpirit, SummonArenaMatch,
    SummonBattlefield, SummonBattlefieldRecord,
    SummonAlliance, SummonAllianceMember, SummonAllianceDonationLog,
    SummonMasterApprentice, User, Wallet, Notification, PlatformEvent,
    InventoryItem
)
from utils.auth import get_current_user
from utils.common import change_currency, add_item, remove_item, add_notification

router = APIRouter(prefix="/summon_king", tags=["summon_king"])
templates = Jinja2Templates(directory="templates")

# ============================================================
# 基础数据初始化
# ============================================================

def init_summon_data(db: Session):
    """初始化召唤之王基础数据"""
    try:
        # 确保表存在
        Base.metadata.create_all(bind=engine)

        # --- 地图 ---
        maps_data = [
            {"map_code": "newbie_village", "name": "新手村", "level_min": 1, "level_max": 10,
             "beast_pool_json": json.dumps(["slime", "rabbit", "cat"]),
             "drop_json": json.dumps({"copper": (10, 30), "ball_normal": (0, 1)}),
             "description": "宁静祥和的小村庄，适合新手召唤师历练。", "vitality_cost": 1},
            {"map_code": "qingfeng_forest", "name": "清风森林", "level_min": 10, "level_max": 20,
             "beast_pool_json": json.dumps(["wolf", "sparrow", "bear"]),
             "drop_json": json.dumps({"copper": (30, 80), "ball_normal": (0, 2), "ball_strong": (0, 1)}),
             "description": "茂密的森林，栖息着各种野兽幻兽。", "vitality_cost": 2},
            {"map_code": "flame_canyon", "name": "烈焰峡谷", "level_min": 20, "level_max": 40,
             "beast_pool_json": json.dumps(["fire_dragon", "flame_bird", "lava_beast"]),
             "drop_json": json.dumps({"copper": (80, 200), "ball_strong": (0, 2), "bone_blue": (0, 1)}),
             "description": "炙热的峡谷，火属性幻兽的领地。", "vitality_cost": 3},
            {"map_code": "nether_abyss", "name": "幽冥深渊", "level_min": 40, "level_max": 100,
             "beast_pool_json": json.dumps(["ghost", "shadow_dragon", "demon_king"]),
             "drop_json": json.dumps({"copper": (200, 500), "ball_super": (0, 1), "bone_purple": (0, 1)}),
             "description": "阴森恐怖的深渊，传说中魔王的居所。", "vitality_cost": 5},
        ]
        for m in maps_data:
            existing = db.query(SummonMap).filter(SummonMap.map_code == m["map_code"]).first()
            if not existing:
                db.add(SummonMap(**m))

        # --- 幻兽 ---
        beasts_data = [
            {"beast_code": "slime", "name": "史莱姆", "race_type": "slime", "map_level_min": 1,
             "rarity": "common", "base_hp": 80, "base_patk": 10, "base_matk": 8,
             "base_pdef": 8, "base_mdef": 8, "base_speed": 5, "growth_min": 1, "growth_max": 3,
             "skill_pool_json": json.dumps(["tackle"]),
             "personality_pool_json": json.dumps(["calm", "brave"]),
             "icon": "🟢", "description": "最常见的软体幻兽，新手练习捕捉的最佳对象。", "catch_rate": 80},
            {"beast_code": "rabbit", "name": "月光兔", "race_type": "beast", "map_level_min": 1,
             "rarity": "common", "base_hp": 70, "base_patk": 12, "base_matk": 15,
             "base_pdef": 6, "base_mdef": 10, "base_speed": 18, "growth_min": 1, "growth_max": 3,
             "skill_pool_json": json.dumps(["tackle", "quick_attack"]),
             "personality_pool_json": json.dumps(["timid", "cheerful"]),
             "icon": "🐰", "description": "速度极快的小兔子，月光下能力增强。", "catch_rate": 70},
            {"beast_code": "cat", "name": "灵猫", "race_type": "beast", "map_level_min": 1,
             "rarity": "uncommon", "base_hp": 75, "base_patk": 18, "base_matk": 12,
             "base_pdef": 8, "base_mdef": 8, "base_speed": 16, "growth_min": 2, "growth_max": 4,
             "skill_pool_json": json.dumps(["scratch", "quick_attack"]),
             "personality_pool_json": json.dumps(["proud", "cunning"]),
             "icon": "🐱", "description": "敏捷的灵猫，攻击力不俗。", "catch_rate": 60},
            {"beast_code": "wolf", "name": "苍狼", "race_type": "beast", "map_level_min": 10,
             "rarity": "uncommon", "base_hp": 120, "base_patk": 25, "base_matk": 10,
             "base_pdef": 15, "base_mdef": 10, "base_speed": 14, "growth_min": 2, "growth_max": 4,
             "skill_pool_json": json.dumps(["bite", "howl"]),
             "personality_pool_json": json.dumps(["brave", "fierce"]),
             "icon": "🐺", "description": "森林中的猎手，物理攻击强大。", "catch_rate": 50},
            {"beast_code": "sparrow", "name": "风雀", "race_type": "flying", "map_level_min": 10,
             "rarity": "common", "base_hp": 90, "base_patk": 15, "base_matk": 22,
             "base_pdef": 8, "base_mdef": 15, "base_speed": 22, "growth_min": 2, "growth_max": 4,
             "skill_pool_json": json.dumps(["wind_blade", "quick_attack"]),
             "personality_pool_json": json.dumps(["cheerful", "timid"]),
             "icon": "🐦", "description": "御风而行的小鸟，魔攻与速度出色。", "catch_rate": 55},
            {"beast_code": "bear", "name": "棕熊王", "race_type": "beast", "map_level_min": 15,
             "rarity": "rare", "base_hp": 200, "base_patk": 35, "base_matk": 10,
             "base_pdef": 25, "base_mdef": 15, "base_speed": 6, "growth_min": 3, "growth_max": 5,
             "skill_pool_json": json.dumps(["heavy_slam", "roar"]),
             "personality_pool_json": json.dumps(["brave", "stubborn"]),
             "icon": "🐻", "description": "森林中的霸主，血量和物理防御极高。", "catch_rate": 30},
            {"beast_code": "fire_dragon", "name": "炎龙幼崽", "race_type": "dragon", "map_level_min": 20,
             "rarity": "rare", "base_hp": 180, "base_patk": 30, "base_matk": 40,
             "base_pdef": 20, "base_mdef": 18, "base_speed": 12, "growth_min": 3, "growth_max": 5,
             "skill_pool_json": json.dumps(["fire_breath", "bite"]),
             "personality_pool_json": json.dumps(["proud", "fierce"]),
             "icon": "🐉", "description": "火龙的幼崽，火属性魔攻极强。", "catch_rate": 20},
            {"beast_code": "flame_bird", "name": "烈焰鸟", "race_type": "flying", "map_level_min": 25,
             "rarity": "epic", "base_hp": 160, "base_patk": 25, "base_matk": 50,
             "base_pdef": 15, "base_mdef": 22, "base_speed": 25, "growth_min": 3, "growth_max": 5,
             "skill_pool_json": json.dumps(["fire_breath", "wind_blade", "rebirth"]),
             "personality_pool_json": json.dumps(["proud", "brave"]),
             "icon": "🔥", "description": "传说中的不死鸟，浴火重生。", "catch_rate": 10},
            {"beast_code": "lava_beast", "name": "熔岩兽", "race_type": "elemental", "map_level_min": 30,
             "rarity": "rare", "base_hp": 220, "base_patk": 40, "base_matk": 25,
             "base_pdef": 30, "base_mdef": 20, "base_speed": 5, "growth_min": 3, "growth_max": 5,
             "skill_pool_json": json.dumps(["heavy_slam", "fire_breath"]),
             "personality_pool_json": json.dumps(["stubborn", "fierce"]),
             "icon": "🌋", "description": "由熔岩构成的巨兽，防御惊人。", "catch_rate": 15},
            {"beast_code": "ghost", "name": "幽灵", "race_type": "undead", "map_level_min": 40,
             "rarity": "rare", "base_hp": 150, "base_patk": 20, "base_matk": 55,
             "base_pdef": 10, "base_mdef": 35, "base_speed": 20, "growth_min": 3, "growth_max": 5,
             "skill_pool_json": json.dumps(["shadow_bolt", "curse"]),
             "personality_pool_json": json.dumps(["cunning", "cold"]),
             "icon": "👻", "description": "飘忽不定的幽灵，魔攻与魔防极高。", "catch_rate": 12},
            {"beast_code": "shadow_dragon", "name": "暗影龙", "race_type": "dragon", "map_level_min": 45,
             "rarity": "legendary", "base_hp": 280, "base_patk": 50, "base_matk": 60,
             "base_pdef": 35, "base_mdef": 30, "base_speed": 18, "growth_min": 4, "growth_max": 5,
             "skill_pool_json": json.dumps(["shadow_bolt", "bite", "dragon_rage"]),
             "personality_pool_json": json.dumps(["proud", "cold", "fierce"]),
             "icon": "🐲", "description": "深渊中的暗影巨龙，全属性优秀。", "catch_rate": 5},
            {"beast_code": "demon_king", "name": "深渊魔王", "race_type": "demon", "map_level_min": 50,
             "rarity": "legendary", "base_hp": 350, "base_patk": 60, "base_matk": 70,
             "base_pdef": 40, "base_mdef": 40, "base_speed": 15, "growth_min": 5, "growth_max": 5,
             "skill_pool_json": json.dumps(["shadow_bolt", "curse", "dragon_rage", "rebirth"]),
             "personality_pool_json": json.dumps(["fierce", "proud", "cold"]),
             "icon": "👹", "description": "深渊的统治者，最强幻兽之一。", "catch_rate": 3},
        ]
        for b in beasts_data:
            existing = db.query(SummonBeast).filter(SummonBeast.beast_code == b["beast_code"]).first()
            if not existing:
                db.add(SummonBeast(**b))

        # --- 技能 ---
        skills_data = [
            {"skill_code": "tackle", "name": "撞击", "skill_type": "active", "category": "patk",
             "damage_formula": "patk*1.0", "base_damage": 10, "trigger_rate": 100, "mp_cost": 0,
             "cooldown": 0, "description": "用身体撞击敌人，造成物理伤害。", "icon": "💥"},
            {"skill_code": "scratch", "name": "抓击", "skill_type": "active", "category": "patk",
             "damage_formula": "patk*1.2", "base_damage": 15, "trigger_rate": 100, "mp_cost": 5,
             "cooldown": 1, "description": "用利爪抓挠敌人，造成较高物理伤害。", "icon": "🐾"},
            {"skill_code": "quick_attack", "name": "电光石火", "skill_type": "active", "category": "patk",
             "damage_formula": "patk*0.8+speed*0.5", "base_damage": 8, "trigger_rate": 100, "mp_cost": 5,
             "cooldown": 2, "description": "以极快速度攻击，必定先出手。", "icon": "⚡"},
            {"skill_code": "bite", "name": "撕咬", "skill_type": "active", "category": "patk",
             "damage_formula": "patk*1.5", "base_damage": 20, "trigger_rate": 100, "mp_cost": 10,
             "cooldown": 2, "description": "用尖牙撕咬敌人，造成高额物理伤害。", "icon": "🦷"},
            {"skill_code": "wind_blade", "name": "风刃", "skill_type": "active", "category": "matk",
             "damage_formula": "matk*1.3", "base_damage": 18, "trigger_rate": 100, "mp_cost": 8,
             "cooldown": 1, "description": "凝聚风之刃攻击敌人，造成魔法伤害。", "icon": "🌪️"},
            {"skill_code": "fire_breath", "name": "火焰吐息", "skill_type": "active", "category": "matk",
             "damage_formula": "matk*1.6", "base_damage": 25, "trigger_rate": 100, "mp_cost": 15,
             "cooldown": 2, "description": "喷出烈焰灼烧敌人，火属性魔法伤害。", "icon": "🔥"},
            {"skill_code": "heavy_slam", "name": "重击", "skill_type": "active", "category": "patk",
             "damage_formula": "patk*1.8+hp*0.1", "base_damage": 30, "trigger_rate": 100, "mp_cost": 15,
             "cooldown": 3, "description": "以全身重量砸向敌人，威力巨大但速度慢。", "icon": "🔨"},
            {"skill_code": "shadow_bolt", "name": "暗影箭", "skill_type": "active", "category": "matk",
             "damage_formula": "matk*1.7", "base_damage": 28, "trigger_rate": 100, "mp_cost": 12,
             "cooldown": 2, "description": "发射暗影能量攻击敌人，暗属性魔法伤害。", "icon": "🌑"},
            {"skill_code": "howl", "name": "嚎叫", "skill_type": "passive", "category": "buff",
             "damage_formula": "", "base_damage": 0, "trigger_rate": 30, "mp_cost": 0,
             "cooldown": 0, "description": "战斗开始时嚎叫，提升己方物攻20%。", "icon": "📢"},
            {"skill_code": "roar", "name": "怒吼", "skill_type": "passive", "category": "debuff",
             "damage_formula": "", "base_damage": 0, "trigger_rate": 25, "mp_cost": 0,
             "cooldown": 0, "description": "怒吼威慑敌人，降低敌方物防20%。", "icon": "🔊"},
            {"skill_code": "curse", "name": "诅咒", "skill_type": "active", "category": "matk",
             "damage_formula": "matk*0.5", "base_damage": 10, "trigger_rate": 100, "mp_cost": 20,
             "cooldown": 4, "description": "诅咒敌人，每回合损失最大HP的10%，持续3回合。", "icon": "💀"},
            {"skill_code": "rebirth", "name": "浴火重生", "skill_type": "passive", "category": "heal",
             "damage_formula": "", "base_damage": 0, "trigger_rate": 100, "mp_cost": 0,
             "cooldown": 0, "description": "HP归零时以50%HP复活一次，每场战斗仅触发一次。", "icon": "🔄"},
            {"skill_code": "dragon_rage", "name": "龙之怒", "skill_type": "active", "category": "matk",
             "damage_formula": "matk*2.5", "base_damage": 50, "trigger_rate": 100, "mp_cost": 30,
             "cooldown": 5, "description": "龙族奥义，对敌人造成毁灭性魔法伤害。", "icon": "🐉"},
        ]
        for s in skills_data:
            existing = db.query(SummonSkill).filter(SummonSkill.skill_code == s["skill_code"]).first()
            if not existing:
                db.add(SummonSkill(**s))

        # --- 战骨 ---
        bones_data = [
            {"bone_code": "skull_common", "name": "兽骨头骨", "slot_type": "skull", "quality": "common",
             "level_required": 1, "hp_bonus": 20, "patk_bonus": 0, "matk_bonus": 5,
             "pdef_bonus": 5, "mdef_bonus": 5, "speed_bonus": 0, "icon": "💀"},
            {"bone_code": "sternum_common", "name": "兽骨胸骨", "slot_type": "sternum", "quality": "common",
             "level_required": 1, "hp_bonus": 40, "patk_bonus": 0, "matk_bonus": 0,
             "pdef_bonus": 10, "mdef_bonus": 10, "speed_bonus": 0, "icon": "🦴"},
            {"bone_code": "arm_bone_common", "name": "兽骨臂骨", "slot_type": "arm", "quality": "common",
             "level_required": 1, "hp_bonus": 10, "patk_bonus": 8, "matk_bonus": 0,
             "pdef_bonus": 5, "mdef_bonus": 0, "speed_bonus": 0, "icon": "🦴"},
            {"bone_code": "leg_bone_common", "name": "兽骨腿骨", "slot_type": "leg", "quality": "common",
             "level_required": 1, "hp_bonus": 15, "patk_bonus": 0, "matk_bonus": 0,
             "pdef_bonus": 8, "mdef_bonus": 5, "speed_bonus": 5, "icon": "🦴"},
            {"bone_code": "hand_bone_common", "name": "兽骨手骨", "slot_type": "hand", "quality": "common",
             "level_required": 1, "hp_bonus": 5, "patk_bonus": 5, "matk_bonus": 5,
             "pdef_bonus": 0, "mdef_bonus": 0, "speed_bonus": 3, "icon": "🦴"},
            {"bone_code": "tail_bone_common", "name": "兽骨尾骨", "slot_type": "tail", "quality": "common",
             "level_required": 1, "hp_bonus": 10, "patk_bonus": 3, "matk_bonus": 3,
             "pdef_bonus": 3, "mdef_bonus": 3, "speed_bonus": 2, "icon": "🦴"},
            {"bone_code": "soul_core_common", "name": "兽魂元魂", "slot_type": "soul_core", "quality": "common",
             "level_required": 1, "hp_bonus": 30, "patk_bonus": 5, "matk_bonus": 5,
             "pdef_bonus": 5, "mdef_bonus": 5, "speed_bonus": 2, "icon": "🔮"},
            {"bone_code": "skull_rare", "name": "精钢头骨", "slot_type": "skull", "quality": "rare",
             "level_required": 20, "hp_bonus": 50, "patk_bonus": 0, "matk_bonus": 15,
             "pdef_bonus": 15, "mdef_bonus": 15, "speed_bonus": 0, "icon": "💀"},
            {"bone_code": "sternum_rare", "name": "精钢胸骨", "slot_type": "sternum", "quality": "rare",
             "level_required": 20, "hp_bonus": 100, "patk_bonus": 0, "matk_bonus": 0,
             "pdef_bonus": 25, "mdef_bonus": 25, "speed_bonus": 0, "icon": "🦴"},
            {"bone_code": "skull_epic", "name": "龙魂头骨", "slot_type": "skull", "quality": "epic",
             "level_required": 40, "hp_bonus": 120, "patk_bonus": 0, "matk_bonus": 40,
             "pdef_bonus": 30, "mdef_bonus": 30, "speed_bonus": 0, "icon": "🐲"},
        ]
        for bn in bones_data:
            existing = db.query(SummonBone).filter(SummonBone.bone_code == bn["bone_code"]).first()
            if not existing:
                db.add(SummonBone(**bn))
        db.flush()  # 刷新基础战骨，确保后续迁移查询立即可见，避免重复插入

        # --- 魔魂 ---
        souls_data = [
            {"soul_code": "waste_soul", "name": "废魂", "quality": "waste", "category": "random",
             "fixed_hp": 5, "fixed_patk": 1, "fixed_matk": 1, "fixed_pdef": 1, "fixed_mdef": 1, "fixed_speed": 1,
             "percent_hp": 0, "percent_patk": 0, "percent_matk": 0, "percent_pdef": 0, "percent_mdef": 0, "percent_speed": 0,
             "icon": "⚪"},
            {"soul_code": "yellow_soul_hp", "name": "黄魂·生命", "quality": "yellow", "category": "hp",
             "fixed_hp": 30, "fixed_patk": 0, "fixed_matk": 0, "fixed_pdef": 5, "fixed_mdef": 5, "fixed_speed": 0,
             "percent_hp": 3, "percent_patk": 0, "percent_matk": 0, "percent_pdef": 0, "percent_mdef": 0, "percent_speed": 0,
             "icon": "🟡"},
            {"soul_code": "yellow_soul_patk", "name": "黄魂·力量", "quality": "yellow", "category": "patk",
             "fixed_hp": 10, "fixed_patk": 8, "fixed_matk": 0, "fixed_pdef": 3, "fixed_mdef": 0, "fixed_speed": 2,
             "percent_hp": 0, "percent_patk": 3, "percent_matk": 0, "percent_pdef": 0, "percent_mdef": 0, "percent_speed": 0,
             "icon": "🟡"},
            {"soul_code": "xuan_soul_matk", "name": "玄魂·智慧", "quality": "xuan", "category": "matk",
             "fixed_hp": 20, "fixed_patk": 0, "fixed_matk": 15, "fixed_pdef": 5, "fixed_mdef": 10, "fixed_speed": 3,
             "percent_hp": 0, "percent_patk": 0, "percent_matk": 5, "percent_pdef": 0, "percent_mdef": 2, "percent_speed": 0,
             "icon": "🟣"},
            {"soul_code": "di_soul_tank", "name": "地魂·守护", "quality": "di", "category": "defense",
             "fixed_hp": 80, "fixed_patk": 5, "fixed_matk": 5, "fixed_pdef": 20, "fixed_mdef": 20, "fixed_speed": 0,
             "percent_hp": 5, "percent_patk": 0, "percent_matk": 0, "percent_pdef": 5, "percent_mdef": 5, "percent_speed": 0,
             "icon": "🟤"},
            {"soul_code": "tian_soul_swift", "name": "天魂·疾风", "quality": "tian", "category": "speed",
             "fixed_hp": 30, "fixed_patk": 10, "fixed_matk": 10, "fixed_pdef": 8, "fixed_mdef": 8, "fixed_speed": 20,
             "percent_hp": 0, "percent_patk": 2, "percent_matk": 2, "percent_pdef": 0, "percent_mdef": 0, "percent_speed": 8,
             "icon": "🔵"},
            {"soul_code": "shen_soul_dragon", "name": "神魂·龙威", "quality": "shen", "category": "all",
             "fixed_hp": 150, "fixed_patk": 30, "fixed_matk": 30, "fixed_pdef": 25, "fixed_mdef": 25, "fixed_speed": 15,
             "percent_hp": 10, "percent_patk": 8, "percent_matk": 8, "percent_pdef": 5, "percent_mdef": 5, "percent_speed": 5,
             "icon": "🌟"},
        ]
        for s in souls_data:
            existing = db.query(SummonSoul).filter(SummonSoul.soul_code == s["soul_code"]).first()
            if not existing:
                db.add(SummonSoul(**s))

        # --- 战场 ---
        battlefields_data = [
            {"battlefield_code": "tiger_battlefield", "name": "猛虎战场", "level_min": 1, "level_max": 40,
             "open_time_start": "06:00", "open_time_end": "24:00",
             "camp_a_name": "猛虎营", "camp_b_name": "飞鹤寨",
             "prestige_reward_win": 50, "prestige_reward_lose": 20, "exp_reward": 100},
            {"battlefield_code": "crane_battlefield", "name": "飞鹤战场", "level_min": 40, "level_max": 100,
             "open_time_start": "06:00", "open_time_end": "24:00",
             "camp_a_name": "天鹤门", "camp_b_name": "幽冥教",
             "prestige_reward_win": 100, "prestige_reward_lose": 40, "exp_reward": 300},
        ]
        for bf in battlefields_data:
            existing = db.query(SummonBattlefield).filter(SummonBattlefield.battlefield_code == bf["battlefield_code"]).first()
            if not existing:
                db.add(SummonBattlefield(**bf))

        # --- 精灵（附属系统基础数据）---
        spirits_data = [
            {"spirit_code": "fire_spirit", "name": "火之精灵", "element_type": "fire", "quality": "common",
             "attr_pool_json": json.dumps({"matk": (5, 15), "patk": (3, 10)}), "icon": "🔥"},
            {"spirit_code": "water_spirit", "name": "水之精灵", "element_type": "water", "quality": "common",
             "attr_pool_json": json.dumps({"mdef": (5, 15), "hp": (20, 50)}), "icon": "💧"},
            {"spirit_code": "wind_spirit", "name": "风之精灵", "element_type": "wind", "quality": "rare",
             "attr_pool_json": json.dumps({"speed": (8, 20), "matk": (5, 12)}), "icon": "🌪️"},
            {"spirit_code": "earth_spirit", "name": "土之精灵", "element_type": "earth", "quality": "rare",
             "attr_pool_json": json.dumps({"pdef": (10, 25), "hp": (30, 80)}), "icon": "🪨"},
        ]
        for sp in spirits_data:
            existing = db.query(SummonSpirit).filter(SummonSpirit.spirit_code == sp["spirit_code"]).first()
            if not existing:
                db.add(SummonSpirit(**sp))

        # --- 迁移补充：地图（来源 3g_games summon_data.py 规格 7 图） ---
        for m in MIGRATED_MAPS:
            existing = db.query(SummonMap).filter(SummonMap.map_code == m["map_code"]).first()
            if not existing:
                db.add(SummonMap(**m))

        # --- 迁移补充：幻兽（120 图鉴） ---
        for b in MIGRATED_BEASTS:
            existing = db.query(SummonBeast).filter(SummonBeast.beast_code == b["beast_code"]).first()
            if not existing:
                db.add(SummonBeast(**b))

        # --- 迁移补充：技能（60 基础技能） ---
        for s in MIGRATED_SKILLS:
            existing = db.query(SummonSkill).filter(SummonSkill.skill_code == s["skill_code"]).first()
            if not existing:
                db.add(SummonSkill(**s))

        # --- 迁移补充：战骨（rare/epic 全部位） ---
        for bn in MIGRATED_BONES:
            existing = db.query(SummonBone).filter(SummonBone.bone_code == bn["bone_code"]).first()
            if not existing:
                db.add(SummonBone(**bn))

        # --- 迁移补充：魔魂（天魂·极品命名魂） ---
        for s in MIGRATED_SOULS:
            existing = db.query(SummonSoul).filter(SummonSoul.soul_code == s["soul_code"]).first()
            if not existing:
                db.add(SummonSoul(**s))

        # --- 迁移补充：战灵（补齐木/金/神 槽位） ---
        for sp in MIGRATED_SPIRITS:
            existing = db.query(SummonSpirit).filter(SummonSpirit.spirit_code == sp["spirit_code"]).first()
            if not existing:
                db.add(SummonSpirit(**sp))

        db.commit()
    except Exception:
        db.rollback()


# ===== 迁移补充数据（来源：3g_games/app/routers/summon_data.py）=====
MIGRATED_MAPS = [
    {'map_code': 'newbie_guide', 'name': '新手村/东村', 'level_min': 1, 'level_max': 9, 'beast_pool_json': '["SZW_0001", "SZW_0002", "SZW_0003", "SZW_0004", "SZW_0005", "SZW_0006", "SZW_0007", "SZW_0008", "SZW_0009", "SZW_0010", "SZW_0011", "SZW_0012", "SZW_0013", "SZW_0014", "SZW_0015"]', 'drop_json': '{"copper": [30, 100], "ball_normal": [0, 1]}', 'description': '新手村/东村（1-9级）', 'vitality_cost': 2},
    {'map_code': 'qingxi_low', 'name': '清溪/低级图', 'level_min': 10, 'level_max': 19, 'beast_pool_json': '["SZW_0001", "SZW_0002", "SZW_0003", "SZW_0004", "SZW_0005", "SZW_0006", "SZW_0007", "SZW_0008", "SZW_0009", "SZW_0010", "SZW_0011", "SZW_0012", "SZW_0013", "SZW_0014", "SZW_0015", "SZW_0016", "SZW_0017", "SZW_0018", "SZW_0019", "SZW_0020", "SZW_0021", "SZW_0022", "SZW_0023", "SZW_0024", "SZW_0025", "SZW_0026", "SZW_0027", "SZW_0028", "SZW_0029", "SZW_0030"]', 'drop_json': '{"copper": [30, 100], "ball_normal": [0, 1]}', 'description': '清溪/低级图（10-19级）', 'vitality_cost': 2},
    {'map_code': 'quarry', 'name': '石工矿场', 'level_min': 20, 'level_max': 29, 'beast_pool_json': '["SZW_0016", "SZW_0017", "SZW_0018", "SZW_0019", "SZW_0020", "SZW_0021", "SZW_0022", "SZW_0023", "SZW_0024", "SZW_0025", "SZW_0026", "SZW_0027", "SZW_0028", "SZW_0029", "SZW_0030"]', 'drop_json': '{"copper": [30, 100], "ball_normal": [0, 1]}', 'description': '石工矿场（20-29级）', 'vitality_cost': 2},
    {'map_code': 'lake', 'name': '湖里', 'level_min': 20, 'level_max': 29, 'beast_pool_json': '["SZW_0016", "SZW_0017", "SZW_0018", "SZW_0019", "SZW_0020", "SZW_0021", "SZW_0022", "SZW_0023", "SZW_0024", "SZW_0025", "SZW_0026", "SZW_0027", "SZW_0028", "SZW_0029", "SZW_0030"]', 'drop_json': '{"copper": [30, 100], "ball_normal": [0, 1]}', 'description': '湖里（20-29级）', 'vitality_cost': 2},
    {'map_code': 'swamp', 'name': '树藤沼泽/黑色荒原', 'level_min': 30, 'level_max': 39, 'beast_pool_json': '["SZW_0031", "SZW_0032", "SZW_0033", "SZW_0034", "SZW_0035", "SZW_0036", "SZW_0037", "SZW_0038", "SZW_0039", "SZW_0040", "SZW_0041", "SZW_0042", "SZW_0043", "SZW_0044", "SZW_0045"]', 'drop_json': '{"copper": [30, 100], "ball_normal": [0, 1]}', 'description': '树藤沼泽/黑色荒原（30-39级）', 'vitality_cost': 2},
    {'map_code': 'desert', 'name': '落日荒漠/雷鸣林地', 'level_min': 40, 'level_max': 49, 'beast_pool_json': '["SZW_0046", "SZW_0047", "SZW_0048", "SZW_0049", "SZW_0050", "SZW_0051", "SZW_0052", "SZW_0053", "SZW_0054", "SZW_0055", "SZW_0056", "SZW_0057", "SZW_0058", "SZW_0059", "SZW_0060"]', 'drop_json': '{"copper": [30, 100], "ball_normal": [0, 1]}', 'description': '落日荒漠/雷鸣林地（40-49级）', 'vitality_cost': 2},
    {'map_code': 'snow_mountain', 'name': '雪山/高级图', 'level_min': 50, 'level_max': 100, 'beast_pool_json': '["SZW_0061", "SZW_0062", "SZW_0063", "SZW_0064", "SZW_0065", "SZW_0066", "SZW_0067", "SZW_0068", "SZW_0069", "SZW_0070", "SZW_0071", "SZW_0072", "SZW_0073", "SZW_0074", "SZW_0075", "SZW_0076", "SZW_0077", "SZW_0078", "SZW_0079", "SZW_0080", "SZW_0081", "SZW_0082", "SZW_0083", "SZW_0084", "SZW_0085", "SZW_0086", "SZW_0087", "SZW_0088", "SZW_0089", "SZW_0090", "SZW_0091", "SZW_0092", "SZW_0093", "SZW_0094", "SZW_0095", "SZW_0096", "SZW_0097", "SZW_0098", "SZW_0099", "SZW_0100", "SZW_0101", "SZW_0102", "SZW_0103", "SZW_0104", "SZW_0105", "SZW_0106", "SZW_0107", "SZW_0108", "SZW_0109", "SZW_0110", "SZW_0111", "SZW_0112", "SZW_0113", "SZW_0114", "SZW_0115", "SZW_0116", "SZW_0117", "SZW_0118", "SZW_0119", "SZW_0120"]', 'drop_json': '{"copper": [30, 100], "ball_normal": [0, 1]}', 'description': '雪山/高级图（50-100级）', 'vitality_cost': 2},
]

MIGRATED_BEASTS = [
    {'beast_code': 'SZW_0001', 'name': '潮芽鱼', 'race_type': 'water', 'map_level_min': 1, 'rarity': 'common', 'base_hp': 202, 'base_patk': 19, 'base_matk': 19, 'base_pdef': 12, 'base_mdef': 12, 'base_speed': 15, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_018", "SK_011", "SK_013", "SK_014"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🌊', 'description': 'T1·N·CTRL 定位：减速', 'catch_rate': 80},
    {'beast_code': 'SZW_0002', 'name': '清泉龟', 'race_type': 'water', 'map_level_min': 1, 'rarity': 'common', 'base_hp': 275, 'base_patk': 19, 'base_matk': 19, 'base_pdef': 16, 'base_mdef': 16, 'base_speed': 12, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_031", "SK_007", "SK_008", "SK_009"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🌊', 'description': 'T1·N·TANK 定位：护盾', 'catch_rate': 80},
    {'beast_code': 'SZW_0003', 'name': '泡泡鲛', 'race_type': 'water', 'map_level_min': 1, 'rarity': 'uncommon', 'base_hp': 202, 'base_patk': 16, 'base_matk': 28, 'base_pdef': 13, 'base_mdef': 13, 'base_speed': 13, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_011", "SK_013", "SK_014", "SK_012"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🌊', 'description': 'T1·R·MAG 定位：法攻叠层', 'catch_rate': 60},
    {'beast_code': 'SZW_0004', 'name': '岩牙狼', 'race_type': 'beast', 'map_level_min': 1, 'rarity': 'common', 'base_hp': 209, 'base_patk': 28, 'base_matk': 16, 'base_pdef': 13, 'base_mdef': 13, 'base_speed': 13, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_003", "SK_001", "SK_002", "SK_034"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐾', 'description': 'T1·N·PHY 定位：流血', 'catch_rate': 80},
    {'beast_code': 'SZW_0005', 'name': '角豚兽', 'race_type': 'beast', 'map_level_min': 1, 'rarity': 'common', 'base_hp': 275, 'base_patk': 19, 'base_matk': 19, 'base_pdef': 16, 'base_mdef': 16, 'base_speed': 12, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_007", "SK_006", "SK_036", "SK_010"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐾', 'description': 'T1·N·TANK 定位：开场减伤', 'catch_rate': 80},
    {'beast_code': 'SZW_0006', 'name': '砂爪猫', 'race_type': 'beast', 'map_level_min': 1, 'rarity': 'uncommon', 'base_hp': 209, 'base_patk': 28, 'base_matk': 16, 'base_pdef': 13, 'base_mdef': 13, 'base_speed': 13, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_004", "SK_001", "SK_002", "SK_003"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐾', 'description': 'T1·R·PHY 定位：连击', 'catch_rate': 60},
    {'beast_code': 'SZW_0007', 'name': '毒针蚁', 'race_type': 'bug', 'map_level_min': 1, 'rarity': 'common', 'base_hp': 231, 'base_patk': 24, 'base_matk': 24, 'base_pdef': 14, 'base_mdef': 14, 'base_speed': 12, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_023", "SK_024", "SK_037", "SK_038"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐛', 'description': 'T1·N·CURSE 定位：叠毒', 'catch_rate': 80},
    {'beast_code': 'SZW_0008', 'name': '蛊壳虫', 'race_type': 'bug', 'map_level_min': 1, 'rarity': 'common', 'base_hp': 275, 'base_patk': 19, 'base_matk': 19, 'base_pdef': 16, 'base_mdef': 16, 'base_speed': 12, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_007", "SK_023", "SK_024", "SK_037"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐛', 'description': 'T1·N·TANK 定位：抗性', 'catch_rate': 80},
    {'beast_code': 'SZW_0009', 'name': '翳雾蛛', 'race_type': 'bug', 'map_level_min': 1, 'rarity': 'uncommon', 'base_hp': 202, 'base_patk': 19, 'base_matk': 19, 'base_pdef': 12, 'base_mdef': 12, 'base_speed': 15, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_028", "SK_039", "SK_018", "SK_019"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐛', 'description': 'T1·R·CTRL 定位：降命中', 'catch_rate': 60},
    {'beast_code': 'SZW_0010', 'name': '风羽雀', 'race_type': 'flying', 'map_level_min': 1, 'rarity': 'common', 'base_hp': 202, 'base_patk': 19, 'base_matk': 19, 'base_pdef': 12, 'base_mdef': 12, 'base_speed': 15, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_017", "SK_018", "SK_042", "SK_016"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🪶', 'description': 'T1·N·CTRL 定位：加速', 'catch_rate': 80},
    {'beast_code': 'SZW_0011', 'name': '雷翎隼', 'race_type': 'flying', 'map_level_min': 1, 'rarity': 'common', 'base_hp': 209, 'base_patk': 28, 'base_matk': 16, 'base_pdef': 13, 'base_mdef': 13, 'base_speed': 13, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_040", "SK_041", "SK_004", "SK_027"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🪶', 'description': 'T1·N·PHY 定位：暴击微增', 'catch_rate': 80},
    {'beast_code': 'SZW_0012', 'name': '飘翼鸢', 'race_type': 'flying', 'map_level_min': 1, 'rarity': 'uncommon', 'base_hp': 202, 'base_patk': 19, 'base_matk': 19, 'base_pdef': 12, 'base_mdef': 12, 'base_speed': 15, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_042", "SK_017", "SK_018", "SK_016"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🪶', 'description': 'T1·R·CTRL 定位：眩晕', 'catch_rate': 60},
    {'beast_code': 'SZW_0013', 'name': '幼炎龙', 'race_type': 'dragon', 'map_level_min': 1, 'rarity': 'rare', 'base_hp': 202, 'base_patk': 16, 'base_matk': 28, 'base_pdef': 13, 'base_mdef': 13, 'base_speed': 13, 'growth_min': 3, 'growth_max': 5, 'skill_pool_json': '["SK_015", "SK_044", "SK_051", "SK_043"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐉', 'description': 'T1·E·MAG 定位：灼烧', 'catch_rate': 30},
    {'beast_code': 'SZW_0014', 'name': '骨灯灵', 'race_type': 'undead', 'map_level_min': 1, 'rarity': 'common', 'base_hp': 231, 'base_patk': 24, 'base_matk': 24, 'base_pdef': 14, 'base_mdef': 14, 'base_speed': 12, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_021", "SK_046", "SK_047", "SK_048"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '💀', 'description': 'T1·N·CURSE 定位：吸血', 'catch_rate': 80},
    {'beast_code': 'SZW_0015', 'name': '幽灯魇', 'race_type': 'undead', 'map_level_min': 1, 'rarity': 'legendary', 'base_hp': 231, 'base_patk': 24, 'base_matk': 24, 'base_pdef': 14, 'base_mdef': 14, 'base_speed': 12, 'growth_min': 4, 'growth_max': 5, 'skill_pool_json': '["SK_025", "SK_046", "SK_047", "SK_048"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '💀', 'description': 'T1·L·CURSE 定位：复生', 'catch_rate': 10},
    {'beast_code': 'SZW_0016', 'name': '冰鳞鲟', 'race_type': 'water', 'map_level_min': 10, 'rarity': 'common', 'base_hp': 387, 'base_patk': 28, 'base_matk': 28, 'base_pdef': 25, 'base_mdef': 25, 'base_speed': 16, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_007", "SK_008", "SK_009", "SK_010"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🌊', 'description': 'T2·N·TANK 定位：物防提升', 'catch_rate': 80},
    {'beast_code': 'SZW_0017', 'name': '寒潮鳗', 'race_type': 'water', 'map_level_min': 10, 'rarity': 'common', 'base_hp': 285, 'base_patk': 23, 'base_matk': 41, 'base_pdef': 20, 'base_mdef': 20, 'base_speed': 17, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_012", "SK_011", "SK_013", "SK_014"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🌊', 'description': 'T2·N·MAG 定位：冰缓', 'catch_rate': 80},
    {'beast_code': 'SZW_0018', 'name': '厚甲龟', 'race_type': 'water', 'map_level_min': 10, 'rarity': 'rare', 'base_hp': 387, 'base_patk': 28, 'base_matk': 28, 'base_pdef': 25, 'base_mdef': 25, 'base_speed': 16, 'growth_min': 3, 'growth_max': 5, 'skill_pool_json': '["SK_031", "SK_007", "SK_008", "SK_009"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🌊', 'description': 'T2·E·TANK 定位：护盾随血增', 'catch_rate': 30},
    {'beast_code': 'SZW_0019', 'name': '赤鬃犬', 'race_type': 'beast', 'map_level_min': 10, 'rarity': 'common', 'base_hp': 294, 'base_patk': 41, 'base_matk': 23, 'base_pdef': 20, 'base_mdef': 20, 'base_speed': 17, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_001", "SK_002", "SK_003", "SK_034"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐾', 'description': 'T2·N·PHY 定位：撕裂', 'catch_rate': 80},
    {'beast_code': 'SZW_0020', 'name': '铜角牛', 'race_type': 'beast', 'map_level_min': 10, 'rarity': 'common', 'base_hp': 387, 'base_patk': 28, 'base_matk': 28, 'base_pdef': 25, 'base_mdef': 25, 'base_speed': 16, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_010", "SK_006", "SK_007", "SK_036"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐾', 'description': 'T2·N·TANK 定位：嘲讽', 'catch_rate': 80},
    {'beast_code': 'SZW_0021', 'name': '采矿猴', 'race_type': 'beast', 'map_level_min': 10, 'rarity': 'uncommon', 'base_hp': 294, 'base_patk': 41, 'base_matk': 23, 'base_pdef': 20, 'base_mdef': 20, 'base_speed': 17, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_002", "SK_001", "SK_003", "SK_034"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐾', 'description': 'T2·R·PHY 定位：破甲', 'catch_rate': 60},
    {'beast_code': 'SZW_0022', 'name': '吞岩兽', 'race_type': 'beast', 'map_level_min': 10, 'rarity': 'rare', 'base_hp': 387, 'base_patk': 28, 'base_matk': 28, 'base_pdef': 25, 'base_mdef': 25, 'base_speed': 16, 'growth_min': 3, 'growth_max': 5, 'skill_pool_json': '["SK_006", "SK_007", "SK_036", "SK_010"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐾', 'description': 'T2·E·TANK 定位：反击强化', 'catch_rate': 30},
    {'beast_code': 'SZW_0023', 'name': '腐沼蝇', 'race_type': 'bug', 'map_level_min': 10, 'rarity': 'common', 'base_hp': 325, 'base_patk': 35, 'base_matk': 35, 'base_pdef': 22, 'base_mdef': 22, 'base_speed': 16, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_023", "SK_024", "SK_037", "SK_038"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐛', 'description': 'T2·N·CURSE 定位：毒扩散', 'catch_rate': 80},
    {'beast_code': 'SZW_0024', 'name': '巢铠甲', 'race_type': 'bug', 'map_level_min': 10, 'rarity': 'common', 'base_hp': 387, 'base_patk': 28, 'base_matk': 28, 'base_pdef': 25, 'base_mdef': 25, 'base_speed': 16, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_008", "SK_023", "SK_024", "SK_037"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐛', 'description': 'T2·N·TANK 定位：减伤', 'catch_rate': 80},
    {'beast_code': 'SZW_0025', 'name': '紫雾虫', 'race_type': 'bug', 'map_level_min': 10, 'rarity': 'uncommon', 'base_hp': 325, 'base_patk': 35, 'base_matk': 35, 'base_pdef': 22, 'base_mdef': 22, 'base_speed': 16, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_021", "SK_023", "SK_024", "SK_037"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐛', 'description': 'T2·R·CURSE 定位：毒吸联动', 'catch_rate': 60},
    {'beast_code': 'SZW_0026', 'name': '翔风雀', 'race_type': 'flying', 'map_level_min': 10, 'rarity': 'common', 'base_hp': 285, 'base_patk': 28, 'base_matk': 28, 'base_pdef': 20, 'base_mdef': 20, 'base_speed': 20, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_017", "SK_018", "SK_042", "SK_016"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🪶', 'description': 'T2·N·CTRL 定位：速度提升', 'catch_rate': 80},
    {'beast_code': 'SZW_0027', 'name': '穿云燕', 'race_type': 'flying', 'map_level_min': 10, 'rarity': 'common', 'base_hp': 294, 'base_patk': 41, 'base_matk': 23, 'base_pdef': 20, 'base_mdef': 20, 'base_speed': 17, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_041", "SK_040", "SK_004", "SK_027"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🪶', 'description': 'T2·N·PHY 定位：连击倾向', 'catch_rate': 80},
    {'beast_code': 'SZW_0028', 'name': '风雷蝶', 'race_type': 'flying', 'map_level_min': 10, 'rarity': 'uncommon', 'base_hp': 285, 'base_patk': 28, 'base_matk': 28, 'base_pdef': 20, 'base_mdef': 20, 'base_speed': 20, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_016", "SK_017", "SK_018", "SK_042"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🪶', 'description': 'T2·R·CTRL 定位：麻痹', 'catch_rate': 60},
    {'beast_code': 'SZW_0029', 'name': '烬息龙', 'race_type': 'dragon', 'map_level_min': 10, 'rarity': 'uncommon', 'base_hp': 285, 'base_patk': 23, 'base_matk': 41, 'base_pdef': 20, 'base_mdef': 20, 'base_speed': 17, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_044", "SK_015", "SK_051", "SK_043"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐉', 'description': 'T2·R·MAG 定位：灼烧爆发', 'catch_rate': 60},
    {'beast_code': 'SZW_0030', 'name': '影缚魂', 'race_type': 'undead', 'map_level_min': 10, 'rarity': 'legendary', 'base_hp': 285, 'base_patk': 28, 'base_matk': 28, 'base_pdef': 20, 'base_mdef': 20, 'base_speed': 20, 'growth_min': 4, 'growth_max': 5, 'skill_pool_json': '["SK_019", "SK_007", "SK_008", "SK_052"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '💀', 'description': 'T2·L·CTRL 定位：开场沉默', 'catch_rate': 10},
    {'beast_code': 'SZW_0031', 'name': '渊潮鲛', 'race_type': 'water', 'map_level_min': 20, 'rarity': 'common', 'base_hp': 386, 'base_patk': 33, 'base_matk': 58, 'base_pdef': 29, 'base_mdef': 29, 'base_speed': 21, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_011", "SK_013", "SK_014", "SK_012"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🌊', 'description': 'T3·N·MAG 定位：冻结概率', 'catch_rate': 80},
    {'beast_code': 'SZW_0032', 'name': '玄水螺', 'race_type': 'water', 'map_level_min': 20, 'rarity': 'uncommon', 'base_hp': 525, 'base_patk': 40, 'base_matk': 40, 'base_pdef': 35, 'base_mdef': 35, 'base_speed': 19, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_031", "SK_007", "SK_008", "SK_009"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🌊', 'description': 'T3·R·TANK 定位：护盾反伤', 'catch_rate': 60},
    {'beast_code': 'SZW_0033', 'name': '狂牙獾', 'race_type': 'beast', 'map_level_min': 20, 'rarity': 'common', 'base_hp': 399, 'base_patk': 58, 'base_matk': 33, 'base_pdef': 29, 'base_mdef': 29, 'base_speed': 22, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_003", "SK_001", "SK_002", "SK_034"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐾', 'description': 'T3·N·PHY 定位：流血延长', 'catch_rate': 80},
    {'beast_code': 'SZW_0034', 'name': '岩背熊', 'race_type': 'beast', 'map_level_min': 20, 'rarity': 'common', 'base_hp': 525, 'base_patk': 40, 'base_matk': 40, 'base_pdef': 35, 'base_mdef': 35, 'base_speed': 19, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_010", "SK_006", "SK_007", "SK_036"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐾', 'description': 'T3·N·TANK 定位：物防壁垒', 'catch_rate': 80},
    {'beast_code': 'SZW_0035', 'name': '赤爪豹', 'race_type': 'beast', 'map_level_min': 20, 'rarity': 'uncommon', 'base_hp': 399, 'base_patk': 58, 'base_matk': 33, 'base_pdef': 29, 'base_mdef': 29, 'base_speed': 22, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_003", "SK_001", "SK_002", "SK_034"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐾', 'description': 'T3·R·PHY 定位：连击+', 'catch_rate': 60},
    {'beast_code': 'SZW_0036', 'name': '獠角豺', 'race_type': 'beast', 'map_level_min': 20, 'rarity': 'common', 'base_hp': 399, 'base_patk': 58, 'base_matk': 33, 'base_pdef': 29, 'base_mdef': 29, 'base_speed': 22, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_003", "SK_001", "SK_002", "SK_034"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐾', 'description': 'T3·N·PHY 定位：破甲', 'catch_rate': 80},
    {'beast_code': 'SZW_0037', 'name': '蛊雾蛛', 'race_type': 'bug', 'map_level_min': 20, 'rarity': 'common', 'base_hp': 386, 'base_patk': 40, 'base_matk': 40, 'base_pdef': 28, 'base_mdef': 28, 'base_speed': 25, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_039", "SK_018", "SK_019", "SK_016"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐛', 'description': 'T3·N·CTRL 定位：降速', 'catch_rate': 80},
    {'beast_code': 'SZW_0038', 'name': '噬心蠹', 'race_type': 'bug', 'map_level_min': 20, 'rarity': 'common', 'base_hp': 441, 'base_patk': 50, 'base_matk': 50, 'base_pdef': 31, 'base_mdef': 31, 'base_speed': 19, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_023", "SK_024", "SK_037", "SK_038"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐛', 'description': 'T3·N·CURSE 定位：DOT叠层', 'catch_rate': 80},
    {'beast_code': 'SZW_0039', 'name': '毒巢后', 'race_type': 'bug', 'map_level_min': 20, 'rarity': 'uncommon', 'base_hp': 441, 'base_patk': 50, 'base_matk': 50, 'base_pdef': 31, 'base_mdef': 31, 'base_speed': 19, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_023", "SK_024", "SK_037", "SK_038"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐛', 'description': 'T3·R·CURSE 定位：毒伤窗口', 'catch_rate': 60},
    {'beast_code': 'SZW_0040', 'name': '断翼鸦', 'race_type': 'flying', 'map_level_min': 20, 'rarity': 'common', 'base_hp': 386, 'base_patk': 40, 'base_matk': 40, 'base_pdef': 28, 'base_mdef': 28, 'base_speed': 25, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_042", "SK_017", "SK_018", "SK_016"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🪶', 'description': 'T3·N·CTRL 定位：降命中', 'catch_rate': 80},
    {'beast_code': 'SZW_0041', 'name': '雷隼骑', 'race_type': 'flying', 'map_level_min': 20, 'rarity': 'uncommon', 'base_hp': 399, 'base_patk': 58, 'base_matk': 33, 'base_pdef': 29, 'base_mdef': 29, 'base_speed': 22, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_040", "SK_041", "SK_004", "SK_027"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🪶', 'description': 'T3·R·PHY 定位：先手暴击', 'catch_rate': 60},
    {'beast_code': 'SZW_0042', 'name': '云刃鹫', 'race_type': 'flying', 'map_level_min': 20, 'rarity': 'common', 'base_hp': 399, 'base_patk': 58, 'base_matk': 33, 'base_pdef': 29, 'base_mdef': 29, 'base_speed': 22, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_040", "SK_041", "SK_004", "SK_027"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🪶', 'description': 'T3·N·PHY 定位：穿透', 'catch_rate': 80},
    {'beast_code': 'SZW_0043', 'name': '苍焰幼龙', 'race_type': 'dragon', 'map_level_min': 20, 'rarity': 'rare', 'base_hp': 399, 'base_patk': 58, 'base_matk': 33, 'base_pdef': 29, 'base_mdef': 29, 'base_speed': 22, 'growth_min': 3, 'growth_max': 5, 'skill_pool_json': '["SK_043", "SK_001", "SK_002", "SK_005"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐉', 'description': 'T3·E·PHY 定位：威压降防', 'catch_rate': 30},
    {'beast_code': 'SZW_0044', 'name': '冥骨犬', 'race_type': 'undead', 'map_level_min': 20, 'rarity': 'uncommon', 'base_hp': 441, 'base_patk': 50, 'base_matk': 50, 'base_pdef': 31, 'base_mdef': 31, 'base_speed': 19, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_021", "SK_046", "SK_047", "SK_048"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '💀', 'description': 'T3·R·CURSE 定位：吸血流血', 'catch_rate': 60},
    {'beast_code': 'SZW_0045', 'name': '咒墓王', 'race_type': 'undead', 'map_level_min': 20, 'rarity': 'legendary', 'base_hp': 441, 'base_patk': 50, 'base_matk': 50, 'base_pdef': 31, 'base_mdef': 31, 'base_speed': 19, 'growth_min': 4, 'growth_max': 5, 'skill_pool_json': '["SK_048", "SK_046", "SK_047", "SK_021"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '💀', 'description': 'T3·L·CURSE 定位：诅咒回血', 'catch_rate': 10},
    {'beast_code': 'SZW_0046', 'name': '海潮鲸', 'race_type': 'water', 'map_level_min': 30, 'rarity': 'common', 'base_hp': 687, 'base_patk': 56, 'base_matk': 56, 'base_pdef': 48, 'base_mdef': 48, 'base_speed': 23, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_031", "SK_007", "SK_008", "SK_009"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🌊', 'description': 'T4·N·TANK 定位：高血抗压', 'catch_rate': 80},
    {'beast_code': 'SZW_0047', 'name': '冰壳蟹', 'race_type': 'water', 'map_level_min': 30, 'rarity': 'uncommon', 'base_hp': 687, 'base_patk': 56, 'base_matk': 56, 'base_pdef': 48, 'base_mdef': 48, 'base_speed': 23, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_031", "SK_007", "SK_008", "SK_009"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🌊', 'description': 'T4·R·TANK 定位：双防提升', 'catch_rate': 60},
    {'beast_code': 'SZW_0048', 'name': '海龙鱼', 'race_type': 'water', 'map_level_min': 30, 'rarity': 'rare', 'base_hp': 506, 'base_patk': 46, 'base_matk': 80, 'base_pdef': 39, 'base_mdef': 39, 'base_speed': 25, 'growth_min': 3, 'growth_max': 5, 'skill_pool_json': '["SK_011", "SK_013", "SK_014", "SK_012"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🌊', 'description': 'T4·E·MAG 定位：冰潮AOE', 'catch_rate': 30},
    {'beast_code': 'SZW_0049', 'name': '砂暴獾', 'race_type': 'beast', 'map_level_min': 30, 'rarity': 'common', 'base_hp': 522, 'base_patk': 80, 'base_matk': 46, 'base_pdef': 39, 'base_mdef': 39, 'base_speed': 26, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_003", "SK_001", "SK_002", "SK_034"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐾', 'description': 'T4·N·PHY 定位：暴击提升', 'catch_rate': 80},
    {'beast_code': 'SZW_0050', 'name': '铁骨犀', 'race_type': 'beast', 'map_level_min': 30, 'rarity': 'uncommon', 'base_hp': 687, 'base_patk': 56, 'base_matk': 56, 'base_pdef': 48, 'base_mdef': 48, 'base_speed': 23, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_010", "SK_006", "SK_007", "SK_036"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐾', 'description': 'T4·R·TANK 定位：嘲讽减伤', 'catch_rate': 60},
    {'beast_code': 'SZW_0051', 'name': '落魂兽', 'race_type': 'beast', 'map_level_min': 30, 'rarity': 'rare', 'base_hp': 522, 'base_patk': 80, 'base_matk': 46, 'base_pdef': 39, 'base_mdef': 39, 'base_speed': 26, 'growth_min': 3, 'growth_max': 5, 'skill_pool_json': '["SK_003", "SK_001", "SK_002", "SK_034"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐾', 'description': 'T4·E·PHY 定位：斩杀增伤', 'catch_rate': 30},
    {'beast_code': 'SZW_0052', 'name': '穿刺蝎', 'race_type': 'bug', 'map_level_min': 30, 'rarity': 'common', 'base_hp': 522, 'base_patk': 80, 'base_matk': 46, 'base_pdef': 39, 'base_mdef': 39, 'base_speed': 26, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_002", "SK_023", "SK_024", "SK_037"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐛', 'description': 'T4·N·PHY 定位：破甲', 'catch_rate': 80},
    {'beast_code': 'SZW_0053', 'name': '腐翳蜂', 'race_type': 'bug', 'map_level_min': 30, 'rarity': 'common', 'base_hp': 577, 'base_patk': 69, 'base_matk': 69, 'base_pdef': 42, 'base_mdef': 42, 'base_speed': 23, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_023", "SK_024", "SK_037", "SK_038"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐛', 'description': 'T4·N·CURSE 定位：DOT扩散', 'catch_rate': 80},
    {'beast_code': 'SZW_0054', 'name': '毒母蛛', 'race_type': 'bug', 'map_level_min': 30, 'rarity': 'uncommon', 'base_hp': 506, 'base_patk': 56, 'base_matk': 56, 'base_pdef': 38, 'base_mdef': 38, 'base_speed': 30, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_039", "SK_018", "SK_019", "SK_016"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐛', 'description': 'T4·R·CTRL 定位：网缚', 'catch_rate': 60},
    {'beast_code': 'SZW_0055', 'name': '落日雕', 'race_type': 'flying', 'map_level_min': 30, 'rarity': 'common', 'base_hp': 506, 'base_patk': 56, 'base_matk': 56, 'base_pdef': 38, 'base_mdef': 38, 'base_speed': 30, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_042", "SK_017", "SK_018", "SK_016"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🪶', 'description': 'T4·N·CTRL 定位：速度爆发', 'catch_rate': 80},
    {'beast_code': 'SZW_0056', 'name': '风刃鸢', 'race_type': 'flying', 'map_level_min': 30, 'rarity': 'common', 'base_hp': 522, 'base_patk': 80, 'base_matk': 46, 'base_pdef': 39, 'base_mdef': 39, 'base_speed': 26, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_040", "SK_041", "SK_004", "SK_027"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🪶', 'description': 'T4·N·PHY 定位：连击', 'catch_rate': 80},
    {'beast_code': 'SZW_0057', 'name': '雷鸣隼', 'race_type': 'flying', 'map_level_min': 30, 'rarity': 'uncommon', 'base_hp': 506, 'base_patk': 56, 'base_matk': 56, 'base_pdef': 38, 'base_mdef': 38, 'base_speed': 30, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_042", "SK_017", "SK_018", "SK_016"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🪶', 'description': 'T4·R·CTRL 定位：麻痹控制', 'catch_rate': 60},
    {'beast_code': 'SZW_0058', 'name': '霜息龙', 'race_type': 'dragon', 'map_level_min': 30, 'rarity': 'uncommon', 'base_hp': 506, 'base_patk': 46, 'base_matk': 80, 'base_pdef': 39, 'base_mdef': 39, 'base_speed': 25, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_044", "SK_015", "SK_051", "SK_043"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐉', 'description': 'T4·R·MAG 定位：冻结窗口', 'catch_rate': 60},
    {'beast_code': 'SZW_0059', 'name': '冥甲尸', 'race_type': 'undead', 'map_level_min': 30, 'rarity': 'common', 'base_hp': 687, 'base_patk': 56, 'base_matk': 56, 'base_pdef': 48, 'base_mdef': 48, 'base_speed': 23, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_052", "SK_007", "SK_008", "SK_050"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '💀', 'description': 'T4·N·TANK 定位：抗性', 'catch_rate': 80},
    {'beast_code': 'SZW_0060', 'name': '幽王骸', 'race_type': 'undead', 'map_level_min': 30, 'rarity': 'legendary', 'base_hp': 687, 'base_patk': 56, 'base_matk': 56, 'base_pdef': 48, 'base_mdef': 48, 'base_speed': 23, 'growth_min': 4, 'growth_max': 5, 'skill_pool_json': '["SK_052", "SK_007", "SK_008", "SK_050"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '💀', 'description': 'T4·L·TANK 定位：回魂护盾', 'catch_rate': 10},
    {'beast_code': 'SZW_0061', 'name': '深渊鲛', 'race_type': 'water', 'map_level_min': 40, 'rarity': 'common', 'base_hp': 644, 'base_patk': 61, 'base_matk': 107, 'base_pdef': 52, 'base_mdef': 52, 'base_speed': 29, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_011", "SK_013", "SK_014", "SK_012"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🌊', 'description': 'T5·N·MAG 定位：冰缓连锁', 'catch_rate': 80},
    {'beast_code': 'SZW_0062', 'name': '潮汐螺皇', 'race_type': 'water', 'map_level_min': 40, 'rarity': 'uncommon', 'base_hp': 875, 'base_patk': 74, 'base_matk': 74, 'base_pdef': 63, 'base_mdef': 63, 'base_speed': 27, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_031", "SK_007", "SK_008", "SK_009"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🌊', 'description': 'T5·R·TANK 定位：护盾强化', 'catch_rate': 60},
    {'beast_code': 'SZW_0063', 'name': '玄海龙鳝', 'race_type': 'water', 'map_level_min': 40, 'rarity': 'rare', 'base_hp': 644, 'base_patk': 74, 'base_matk': 74, 'base_pdef': 50, 'base_mdef': 50, 'base_speed': 34, 'growth_min': 3, 'growth_max': 5, 'skill_pool_json': '["SK_032", "SK_011", "SK_013", "SK_014"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🌊', 'description': 'T5·E·CTRL 定位：冻结降速', 'catch_rate': 30},
    {'beast_code': 'SZW_0064', 'name': '狂角狮', 'race_type': 'beast', 'map_level_min': 40, 'rarity': 'common', 'base_hp': 665, 'base_patk': 107, 'base_matk': 61, 'base_pdef': 52, 'base_mdef': 52, 'base_speed': 30, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_003", "SK_001", "SK_002", "SK_034"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐾', 'description': 'T5·N·PHY 定位：斩击增伤', 'catch_rate': 80},
    {'beast_code': 'SZW_0065', 'name': '岩背巨熊', 'race_type': 'beast', 'map_level_min': 40, 'rarity': 'uncommon', 'base_hp': 875, 'base_patk': 74, 'base_matk': 74, 'base_pdef': 63, 'base_mdef': 63, 'base_speed': 27, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_010", "SK_006", "SK_007", "SK_036"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐾', 'description': 'T5·R·TANK 定位：反伤', 'catch_rate': 60},
    {'beast_code': 'SZW_0066', 'name': '群噬蠊', 'race_type': 'bug', 'map_level_min': 40, 'rarity': 'common', 'base_hp': 735, 'base_patk': 92, 'base_matk': 92, 'base_pdef': 55, 'base_mdef': 55, 'base_speed': 27, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_023", "SK_024", "SK_037", "SK_038"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐛', 'description': 'T5·N·CURSE 定位：叠毒加速', 'catch_rate': 80},
    {'beast_code': 'SZW_0067', 'name': '蛊巢将', 'race_type': 'bug', 'map_level_min': 40, 'rarity': 'uncommon', 'base_hp': 644, 'base_patk': 74, 'base_matk': 74, 'base_pdef': 50, 'base_mdef': 50, 'base_speed': 34, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_039", "SK_018", "SK_019", "SK_016"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐛', 'description': 'T5·R·CTRL 定位：降命中降速', 'catch_rate': 60},
    {'beast_code': 'SZW_0068', 'name': '腐王蛛', 'race_type': 'bug', 'map_level_min': 40, 'rarity': 'common', 'base_hp': 735, 'base_patk': 92, 'base_matk': 92, 'base_pdef': 55, 'base_mdef': 55, 'base_speed': 27, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_023", "SK_024", "SK_037", "SK_038"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐛', 'description': 'T5·N·CURSE 定位：吸血放大', 'catch_rate': 80},
    {'beast_code': 'SZW_0069', 'name': '风雷鹰', 'race_type': 'flying', 'map_level_min': 40, 'rarity': 'common', 'base_hp': 644, 'base_patk': 74, 'base_matk': 74, 'base_pdef': 50, 'base_mdef': 50, 'base_speed': 34, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_042", "SK_017", "SK_018", "SK_016"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🪶', 'description': 'T5·N·CTRL 定位：先手优势', 'catch_rate': 80},
    {'beast_code': 'SZW_0070', 'name': '云刃隼王', 'race_type': 'flying', 'map_level_min': 40, 'rarity': 'uncommon', 'base_hp': 665, 'base_patk': 107, 'base_matk': 61, 'base_pdef': 52, 'base_mdef': 52, 'base_speed': 30, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_040", "SK_041", "SK_004", "SK_027"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🪶', 'description': 'T5·R·PHY 定位：追击', 'catch_rate': 60},
    {'beast_code': 'SZW_0071', 'name': '飓翼鹫', 'race_type': 'flying', 'map_level_min': 40, 'rarity': 'common', 'base_hp': 665, 'base_patk': 107, 'base_matk': 61, 'base_pdef': 52, 'base_mdef': 52, 'base_speed': 30, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_040", "SK_041", "SK_004", "SK_027"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🪶', 'description': 'T5·N·PHY 定位：穿透', 'catch_rate': 80},
    {'beast_code': 'SZW_0072', 'name': '苍炎龙', 'race_type': 'dragon', 'map_level_min': 40, 'rarity': 'common', 'base_hp': 644, 'base_patk': 61, 'base_matk': 107, 'base_pdef': 52, 'base_mdef': 52, 'base_speed': 29, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_044", "SK_015", "SK_051", "SK_043"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐉', 'description': 'T5·N·MAG 定位：灼烧', 'catch_rate': 80},
    {'beast_code': 'SZW_0073', 'name': '星纹龙', 'race_type': 'dragon', 'map_level_min': 40, 'rarity': 'rare', 'base_hp': 665, 'base_patk': 107, 'base_matk': 61, 'base_pdef': 52, 'base_mdef': 52, 'base_speed': 30, 'growth_min': 3, 'growth_max': 5, 'skill_pool_json': '["SK_043", "SK_001", "SK_002", "SK_005"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐉', 'description': 'T5·E·PHY 定位：威压破防', 'catch_rate': 30},
    {'beast_code': 'SZW_0074', 'name': '影咒僧', 'race_type': 'undead', 'map_level_min': 40, 'rarity': 'common', 'base_hp': 644, 'base_patk': 74, 'base_matk': 74, 'base_pdef': 50, 'base_mdef': 50, 'base_speed': 34, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_019", "SK_007", "SK_008", "SK_052"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '💀', 'description': 'T5·N·CTRL 定位：沉默', 'catch_rate': 80},
    {'beast_code': 'SZW_0075', 'name': '冥渊王座', 'race_type': 'undead', 'map_level_min': 40, 'rarity': 'legendary', 'base_hp': 735, 'base_patk': 92, 'base_matk': 92, 'base_pdef': 55, 'base_mdef': 55, 'base_speed': 27, 'growth_min': 4, 'growth_max': 5, 'skill_pool_json': '["SK_048", "SK_046", "SK_047", "SK_021"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '💀', 'description': 'T5·L·CURSE 定位：群诅咒', 'catch_rate': 10},
    {'beast_code': 'SZW_0076', 'name': '寒渊鲸', 'race_type': 'water', 'map_level_min': 50, 'rarity': 'common', 'base_hp': 1087, 'base_patk': 96, 'base_matk': 96, 'base_pdef': 80, 'base_mdef': 80, 'base_speed': 31, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_031", "SK_007", "SK_008", "SK_009"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🌊', 'description': 'T6·N·TANK 定位：高血护盾', 'catch_rate': 80},
    {'beast_code': 'SZW_0077', 'name': '冰潮鲛王', 'race_type': 'water', 'map_level_min': 50, 'rarity': 'uncommon', 'base_hp': 800, 'base_patk': 79, 'base_matk': 139, 'base_pdef': 66, 'base_mdef': 66, 'base_speed': 33, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_011", "SK_013", "SK_014", "SK_012"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🌊', 'description': 'T6·R·MAG 定位：冻结+', 'catch_rate': 60},
    {'beast_code': 'SZW_0078', 'name': '玄潮龙鱼', 'race_type': 'water', 'map_level_min': 50, 'rarity': 'rare', 'base_hp': 800, 'base_patk': 79, 'base_matk': 139, 'base_pdef': 66, 'base_mdef': 66, 'base_speed': 33, 'growth_min': 3, 'growth_max': 5, 'skill_pool_json': '["SK_011", "SK_013", "SK_014", "SK_012"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🌊', 'description': 'T6·E·MAG 定位：法穿增益', 'catch_rate': 30},
    {'beast_code': 'SZW_0079', 'name': '狂獠虎机', 'race_type': 'beast', 'map_level_min': 50, 'rarity': 'common', 'base_hp': 826, 'base_patk': 139, 'base_matk': 79, 'base_pdef': 66, 'base_mdef': 66, 'base_speed': 34, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_003", "SK_001", "SK_002", "SK_034"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐾', 'description': 'T6·N·PHY 定位：暴击提升', 'catch_rate': 80},
    {'beast_code': 'SZW_0080', 'name': '铁角巨犀', 'race_type': 'beast', 'map_level_min': 50, 'rarity': 'uncommon', 'base_hp': 1087, 'base_patk': 96, 'base_matk': 96, 'base_pdef': 80, 'base_mdef': 80, 'base_speed': 31, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_010", "SK_006", "SK_007", "SK_036"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐾', 'description': 'T6·R·TANK 定位：嘲讽减伤', 'catch_rate': 60},
    {'beast_code': 'SZW_0081', 'name': '霸爪王豹', 'race_type': 'beast', 'map_level_min': 50, 'rarity': 'rare', 'base_hp': 826, 'base_patk': 139, 'base_matk': 79, 'base_pdef': 66, 'base_mdef': 66, 'base_speed': 34, 'growth_min': 3, 'growth_max': 5, 'skill_pool_json': '["SK_003", "SK_001", "SK_002", "SK_034"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐾', 'description': 'T6·E·PHY 定位：斩杀强化', 'catch_rate': 30},
    {'beast_code': 'SZW_0082', 'name': '毒云蜂后', 'race_type': 'bug', 'map_level_min': 50, 'rarity': 'common', 'base_hp': 913, 'base_patk': 119, 'base_matk': 119, 'base_pdef': 70, 'base_mdef': 70, 'base_speed': 31, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_023", "SK_024", "SK_037", "SK_038"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐛', 'description': 'T6·N·CURSE 定位：DOT扩散', 'catch_rate': 80},
    {'beast_code': 'SZW_0083', 'name': '腐化螳', 'race_type': 'bug', 'map_level_min': 50, 'rarity': 'uncommon', 'base_hp': 826, 'base_patk': 139, 'base_matk': 79, 'base_pdef': 66, 'base_mdef': 66, 'base_speed': 34, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_002", "SK_023", "SK_024", "SK_037"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐛', 'description': 'T6·R·PHY 定位：破甲流血', 'catch_rate': 60},
    {'beast_code': 'SZW_0084', 'name': '蛊皇', 'race_type': 'bug', 'map_level_min': 50, 'rarity': 'common', 'base_hp': 800, 'base_patk': 96, 'base_matk': 96, 'base_pdef': 64, 'base_mdef': 64, 'base_speed': 39, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_039", "SK_018", "SK_019", "SK_016"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐛', 'description': 'T6·N·CTRL 定位：降速降防', 'catch_rate': 80},
    {'beast_code': 'SZW_0085', 'name': '风暴隼', 'race_type': 'flying', 'map_level_min': 50, 'rarity': 'common', 'base_hp': 800, 'base_patk': 96, 'base_matk': 96, 'base_pdef': 64, 'base_mdef': 64, 'base_speed': 39, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_042", "SK_017", "SK_018", "SK_016"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🪶', 'description': 'T6·N·CTRL 定位：先手爆发', 'catch_rate': 80},
    {'beast_code': 'SZW_0086', 'name': '雷翼鸢王', 'race_type': 'flying', 'map_level_min': 50, 'rarity': 'uncommon', 'base_hp': 826, 'base_patk': 139, 'base_matk': 79, 'base_pdef': 66, 'base_mdef': 66, 'base_speed': 34, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_040", "SK_041", "SK_004", "SK_027"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🪶', 'description': 'T6·R·PHY 定位：连击追击', 'catch_rate': 60},
    {'beast_code': 'SZW_0087', 'name': '天翔鹫', 'race_type': 'flying', 'map_level_min': 50, 'rarity': 'common', 'base_hp': 800, 'base_patk': 96, 'base_matk': 96, 'base_pdef': 64, 'base_mdef': 64, 'base_speed': 39, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_042", "SK_017", "SK_018", "SK_016"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🪶', 'description': 'T6·N·CTRL 定位：闪避提升', 'catch_rate': 80},
    {'beast_code': 'SZW_0088', 'name': '烬星龙', 'race_type': 'dragon', 'map_level_min': 50, 'rarity': 'uncommon', 'base_hp': 800, 'base_patk': 79, 'base_matk': 139, 'base_pdef': 66, 'base_mdef': 66, 'base_speed': 33, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_044", "SK_015", "SK_051", "SK_043"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐉', 'description': 'T6·R·MAG 定位：灼烧转爆', 'catch_rate': 60},
    {'beast_code': 'SZW_0089', 'name': '冥炎龙裔', 'race_type': 'dragon', 'map_level_min': 50, 'rarity': 'legendary', 'base_hp': 826, 'base_patk': 139, 'base_matk': 79, 'base_pdef': 66, 'base_mdef': 66, 'base_speed': 34, 'growth_min': 4, 'growth_max': 5, 'skill_pool_json': '["SK_043", "SK_001", "SK_002", "SK_005"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐉', 'description': 'T6·L·PHY 定位：威压灼烧', 'catch_rate': 10},
    {'beast_code': 'SZW_0090', 'name': '骸骨将', 'race_type': 'undead', 'map_level_min': 50, 'rarity': 'common', 'base_hp': 1087, 'base_patk': 96, 'base_matk': 96, 'base_pdef': 80, 'base_mdef': 80, 'base_speed': 31, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_052", "SK_007", "SK_008", "SK_050"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '💀', 'description': 'T6·N·TANK 定位：抗性', 'catch_rate': 80},
    {'beast_code': 'SZW_0091', 'name': '玄冰螺皇', 'race_type': 'water', 'map_level_min': 60, 'rarity': 'common', 'base_hp': 1325, 'base_patk': 122, 'base_matk': 122, 'base_pdef': 100, 'base_mdef': 100, 'base_speed': 35, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_031", "SK_007", "SK_008", "SK_009"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🌊', 'description': 'T7·N·TANK 定位：护盾增强', 'catch_rate': 80},
    {'beast_code': 'SZW_0092', 'name': '深海龙鲛', 'race_type': 'water', 'map_level_min': 60, 'rarity': 'uncommon', 'base_hp': 975, 'base_patk': 100, 'base_matk': 175, 'base_pdef': 82, 'base_mdef': 82, 'base_speed': 37, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_011", "SK_013", "SK_014", "SK_012"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🌊', 'description': 'T7·R·MAG 定位：冻结法穿', 'catch_rate': 60},
    {'beast_code': 'SZW_0093', 'name': '潮汐霸主', 'race_type': 'water', 'map_level_min': 60, 'rarity': 'legendary', 'base_hp': 1325, 'base_patk': 122, 'base_matk': 122, 'base_pdef': 100, 'base_mdef': 100, 'base_speed': 35, 'growth_min': 4, 'growth_max': 5, 'skill_pool_json': '["SK_031", "SK_007", "SK_008", "SK_009"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🌊', 'description': 'T7·L·TANK 定位：群体护盾', 'catch_rate': 10},
    {'beast_code': 'SZW_0094', 'name': '狂岩狮王', 'race_type': 'beast', 'map_level_min': 60, 'rarity': 'common', 'base_hp': 1007, 'base_patk': 175, 'base_matk': 100, 'base_pdef': 82, 'base_mdef': 82, 'base_speed': 38, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_003", "SK_001", "SK_002", "SK_034"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐾', 'description': 'T7·N·PHY 定位：暴击提升', 'catch_rate': 80},
    {'beast_code': 'SZW_0095', 'name': '铁背蛮熊', 'race_type': 'beast', 'map_level_min': 60, 'rarity': 'uncommon', 'base_hp': 1325, 'base_patk': 122, 'base_matk': 122, 'base_pdef': 100, 'base_mdef': 100, 'base_speed': 35, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_010", "SK_006", "SK_007", "SK_036"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐾', 'description': 'T7·R·TANK 定位：反伤强化', 'catch_rate': 60},
    {'beast_code': 'SZW_0096', 'name': '兽神角斗', 'race_type': 'beast', 'map_level_min': 60, 'rarity': 'rare', 'base_hp': 1007, 'base_patk': 175, 'base_matk': 100, 'base_pdef': 82, 'base_mdef': 82, 'base_speed': 38, 'growth_min': 3, 'growth_max': 5, 'skill_pool_json': '["SK_003", "SK_001", "SK_002", "SK_034"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐾', 'description': 'T7·E·PHY 定位：破甲斩杀', 'catch_rate': 30},
    {'beast_code': 'SZW_0097', 'name': '毒巢女皇', 'race_type': 'bug', 'map_level_min': 60, 'rarity': 'common', 'base_hp': 1113, 'base_patk': 151, 'base_matk': 151, 'base_pdef': 87, 'base_mdef': 87, 'base_speed': 35, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_023", "SK_024", "SK_037", "SK_038"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐛', 'description': 'T7·N·CURSE 定位：毒扩散', 'catch_rate': 80},
    {'beast_code': 'SZW_0098', 'name': '蛊翼皇蜂', 'race_type': 'bug', 'map_level_min': 60, 'rarity': 'uncommon', 'base_hp': 975, 'base_patk': 122, 'base_matk': 122, 'base_pdef': 80, 'base_mdef': 80, 'base_speed': 44, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_039", "SK_018", "SK_019", "SK_016"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐛', 'description': 'T7·R·CTRL 定位：麻痹降命中', 'catch_rate': 60},
    {'beast_code': 'SZW_0099', 'name': '腐渊蠹王', 'race_type': 'bug', 'map_level_min': 60, 'rarity': 'rare', 'base_hp': 1113, 'base_patk': 151, 'base_matk': 151, 'base_pdef': 87, 'base_mdef': 87, 'base_speed': 35, 'growth_min': 3, 'growth_max': 5, 'skill_pool_json': '["SK_023", "SK_024", "SK_037", "SK_038"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐛', 'description': 'T7·E·CURSE 定位：吸血放大', 'catch_rate': 30},
    {'beast_code': 'SZW_0100', 'name': '风雷天隼', 'race_type': 'flying', 'map_level_min': 60, 'rarity': 'common', 'base_hp': 975, 'base_patk': 122, 'base_matk': 122, 'base_pdef': 80, 'base_mdef': 80, 'base_speed': 44, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_042", "SK_017", "SK_018", "SK_016"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🪶', 'description': 'T7·N·CTRL 定位：先手压制', 'catch_rate': 80},
    {'beast_code': 'SZW_0101', 'name': '云裂鸢', 'race_type': 'flying', 'map_level_min': 60, 'rarity': 'uncommon', 'base_hp': 1007, 'base_patk': 175, 'base_matk': 100, 'base_pdef': 82, 'base_mdef': 82, 'base_speed': 38, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_040", "SK_041", "SK_004", "SK_027"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🪶', 'description': 'T7·R·PHY 定位：追击强化', 'catch_rate': 60},
    {'beast_code': 'SZW_0102', 'name': '雷霆鹫王', 'race_type': 'flying', 'map_level_min': 60, 'rarity': 'rare', 'base_hp': 975, 'base_patk': 122, 'base_matk': 122, 'base_pdef': 80, 'base_mdef': 80, 'base_speed': 44, 'growth_min': 3, 'growth_max': 5, 'skill_pool_json': '["SK_042", "SK_017", "SK_018", "SK_016"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🪶', 'description': 'T7·E·CTRL 定位：群麻痹', 'catch_rate': 30},
    {'beast_code': 'SZW_0103', 'name': '苍穹龙', 'race_type': 'dragon', 'map_level_min': 60, 'rarity': 'common', 'base_hp': 1007, 'base_patk': 175, 'base_matk': 100, 'base_pdef': 82, 'base_mdef': 82, 'base_speed': 38, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_043", "SK_001", "SK_002", "SK_005"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐉', 'description': 'T7·N·PHY 定位：威压破防', 'catch_rate': 80},
    {'beast_code': 'SZW_0104', 'name': '星辉龙', 'race_type': 'dragon', 'map_level_min': 60, 'rarity': 'uncommon', 'base_hp': 975, 'base_patk': 100, 'base_matk': 175, 'base_pdef': 82, 'base_mdef': 82, 'base_speed': 37, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_044", "SK_015", "SK_051", "SK_043"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐉', 'description': 'T7·R·MAG 定位：星火灼烧', 'catch_rate': 60},
    {'beast_code': 'SZW_0105', 'name': '冥主骸王', 'race_type': 'undead', 'map_level_min': 60, 'rarity': 'common', 'base_hp': 1325, 'base_patk': 122, 'base_matk': 122, 'base_pdef': 100, 'base_mdef': 100, 'base_speed': 35, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_052", "SK_007", "SK_008", "SK_050"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '💀', 'description': 'T7·N·TANK 定位：抗性高', 'catch_rate': 80},
    {'beast_code': 'SZW_0106', 'name': '深渊鲸皇', 'race_type': 'water', 'map_level_min': 70, 'rarity': 'common', 'base_hp': 1600, 'base_patk': 153, 'base_matk': 153, 'base_pdef': 123, 'base_mdef': 123, 'base_speed': 38, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_031", "SK_007", "SK_008", "SK_009"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🌊', 'description': 'T8·N·TANK 定位：高血护盾', 'catch_rate': 80},
    {'beast_code': 'SZW_0107', 'name': '冰海圣鲛', 'race_type': 'water', 'map_level_min': 70, 'rarity': 'uncommon', 'base_hp': 1177, 'base_patk': 125, 'base_matk': 219, 'base_pdef': 101, 'base_mdef': 101, 'base_speed': 41, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_011", "SK_013", "SK_014", "SK_012"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🌊', 'description': 'T8·R·MAG 定位：冻结稳定', 'catch_rate': 60},
    {'beast_code': 'SZW_0108', 'name': '潮冕龙鲛', 'race_type': 'water', 'map_level_min': 70, 'rarity': 'rare', 'base_hp': 1177, 'base_patk': 153, 'base_matk': 153, 'base_pdef': 98, 'base_mdef': 98, 'base_speed': 49, 'growth_min': 3, 'growth_max': 5, 'skill_pool_json': '["SK_032", "SK_011", "SK_013", "SK_014"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🌊', 'description': 'T8·E·CTRL 定位：冻结驱散', 'catch_rate': 30},
    {'beast_code': 'SZW_0109', 'name': '霸爪战王', 'race_type': 'beast', 'map_level_min': 70, 'rarity': 'common', 'base_hp': 1216, 'base_patk': 219, 'base_matk': 125, 'base_pdef': 101, 'base_mdef': 101, 'base_speed': 43, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_003", "SK_001", "SK_002", "SK_034"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐾', 'description': 'T8·N·PHY 定位：斩杀强化', 'catch_rate': 80},
    {'beast_code': 'SZW_0110', 'name': '岩甲巨兽', 'race_type': 'beast', 'map_level_min': 70, 'rarity': 'uncommon', 'base_hp': 1600, 'base_patk': 153, 'base_matk': 153, 'base_pdef': 123, 'base_mdef': 123, 'base_speed': 38, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_010", "SK_006", "SK_007", "SK_036"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐾', 'description': 'T8·R·TANK 定位：嘲讽减伤', 'catch_rate': 60},
    {'beast_code': 'SZW_0111', 'name': '蛊渊皇', 'race_type': 'bug', 'map_level_min': 70, 'rarity': 'common', 'base_hp': 1344, 'base_patk': 189, 'base_matk': 189, 'base_pdef': 107, 'base_mdef': 107, 'base_speed': 38, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_023", "SK_024", "SK_037", "SK_038"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐛', 'description': 'T8·N·CURSE 定位：DOT扩散', 'catch_rate': 80},
    {'beast_code': 'SZW_0112', 'name': '腐天女皇', 'race_type': 'bug', 'map_level_min': 70, 'rarity': 'uncommon', 'base_hp': 1177, 'base_patk': 153, 'base_matk': 153, 'base_pdef': 98, 'base_mdef': 98, 'base_speed': 49, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_039", "SK_018", "SK_019", "SK_016"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐛', 'description': 'T8·R·CTRL 定位：降命中降速', 'catch_rate': 60},
    {'beast_code': 'SZW_0113', 'name': '虫巢灾主', 'race_type': 'bug', 'map_level_min': 70, 'rarity': 'rare', 'base_hp': 1344, 'base_patk': 189, 'base_matk': 189, 'base_pdef': 107, 'base_mdef': 107, 'base_speed': 38, 'growth_min': 3, 'growth_max': 5, 'skill_pool_json': '["SK_023", "SK_024", "SK_037", "SK_038"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐛', 'description': 'T8·E·CURSE 定位：吸血爆发', 'catch_rate': 30},
    {'beast_code': 'SZW_0114', 'name': '天风神隼', 'race_type': 'flying', 'map_level_min': 70, 'rarity': 'common', 'base_hp': 1177, 'base_patk': 153, 'base_matk': 153, 'base_pdef': 98, 'base_mdef': 98, 'base_speed': 49, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_042", "SK_017", "SK_018", "SK_016"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🪶', 'description': 'T8·N·CTRL 定位：先手压制', 'catch_rate': 80},
    {'beast_code': 'SZW_0115', 'name': '雷羽王', 'race_type': 'flying', 'map_level_min': 70, 'rarity': 'uncommon', 'base_hp': 1216, 'base_patk': 219, 'base_matk': 125, 'base_pdef': 101, 'base_mdef': 101, 'base_speed': 43, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_040", "SK_041", "SK_004", "SK_027"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🪶', 'description': 'T8·R·PHY 定位：追击连击', 'catch_rate': 60},
    {'beast_code': 'SZW_0116', 'name': '苍穹翼圣', 'race_type': 'flying', 'map_level_min': 70, 'rarity': 'common', 'base_hp': 1177, 'base_patk': 153, 'base_matk': 153, 'base_pdef': 98, 'base_mdef': 98, 'base_speed': 49, 'growth_min': 1, 'growth_max': 3, 'skill_pool_json': '["SK_042", "SK_017", "SK_018", "SK_016"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🪶', 'description': 'T8·N·CTRL 定位：闪避提升', 'catch_rate': 80},
    {'beast_code': 'SZW_0117', 'name': '星烬龙王', 'race_type': 'dragon', 'map_level_min': 70, 'rarity': 'uncommon', 'base_hp': 1216, 'base_patk': 219, 'base_matk': 125, 'base_pdef': 101, 'base_mdef': 101, 'base_speed': 43, 'growth_min': 2, 'growth_max': 4, 'skill_pool_json': '["SK_043", "SK_001", "SK_002", "SK_005"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐉', 'description': 'T8·R·PHY 定位：威压破防', 'catch_rate': 60},
    {'beast_code': 'SZW_0118', 'name': '霜烬龙皇', 'race_type': 'dragon', 'map_level_min': 70, 'rarity': 'rare', 'base_hp': 1177, 'base_patk': 125, 'base_matk': 219, 'base_pdef': 101, 'base_mdef': 101, 'base_speed': 41, 'growth_min': 3, 'growth_max': 5, 'skill_pool_json': '["SK_044", "SK_015", "SK_051", "SK_043"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐉', 'description': 'T8·E·MAG 定位：冻灼双态', 'catch_rate': 30},
    {'beast_code': 'SZW_0119', 'name': '幽冥龙祖', 'race_type': 'dragon', 'map_level_min': 70, 'rarity': 'legendary', 'base_hp': 1216, 'base_patk': 219, 'base_matk': 125, 'base_pdef': 101, 'base_mdef': 101, 'base_speed': 43, 'growth_min': 4, 'growth_max': 5, 'skill_pool_json': '["SK_043", "SK_001", "SK_002", "SK_005"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '🐉', 'description': 'T8·L·PHY 定位：双威压', 'catch_rate': 10},
    {'beast_code': 'SZW_0120', 'name': '归墟死王', 'race_type': 'undead', 'map_level_min': 70, 'rarity': 'legendary', 'base_hp': 1344, 'base_patk': 189, 'base_matk': 189, 'base_pdef': 107, 'base_mdef': 107, 'base_speed': 38, 'growth_min': 4, 'growth_max': 5, 'skill_pool_json': '["SK_048", "SK_046", "SK_047", "SK_021"]', 'personality_pool_json': '["brave", "calm", "timid", "cheerful", "proud", "cunning", "fierce", "stubborn", "cold"]', 'icon': '💀', 'description': 'T8·L·CURSE 定位：群诅咒复生', 'catch_rate': 10},
]

MIGRATED_SKILLS = [
    {'skill_code': 'SK_001', 'name': '利爪斩', 'skill_type': 'active', 'category': 'patk', 'damage_formula': 'PHY*1.10', 'base_damage': 22, 'trigger_rate': 100, 'mp_cost': 5, 'cooldown': 1, 'description': '单体物伤', 'icon': '⚔️'},
    {'skill_code': 'SK_002', 'name': '破甲击', 'skill_type': 'active', 'category': 'patk', 'damage_formula': 'PHY*0.95', 'base_damage': 19, 'trigger_rate': 100, 'mp_cost': 10, 'cooldown': 2, 'description': '降DEF_PHY', 'icon': '⚔️'},
    {'skill_code': 'SK_003', 'name': '撕裂', 'skill_type': 'active', 'category': 'patk', 'damage_formula': 'PHY*0.90', 'base_damage': 18, 'trigger_rate': 100, 'mp_cost': 10, 'cooldown': 2, 'description': '流血2回合', 'icon': '⚔️'},
    {'skill_code': 'SK_004', 'name': '连环突袭', 'skill_type': 'active', 'category': 'patk', 'damage_formula': 'PHY*0.65', 'base_damage': 13, 'trigger_rate': 100, 'mp_cost': 15, 'cooldown': 3, 'description': '随机2-3段', 'icon': '⚔️'},
    {'skill_code': 'SK_005', 'name': '斩杀线', 'skill_type': 'passive', 'category': 'patk', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 20, 'mp_cost': 0, 'cooldown': 0, 'description': '目标低血增伤', 'icon': '⚔️'},
    {'skill_code': 'SK_006', 'name': '反击姿态', 'skill_type': 'passive', 'category': 'buff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 18, 'mp_cost': 0, 'cooldown': 0, 'description': '受击反击概率', 'icon': '🛡️'},
    {'skill_code': 'SK_007', 'name': '坚甲', 'skill_type': 'passive', 'category': 'buff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 12, 'mp_cost': 0, 'cooldown': 0, 'description': 'DEF_PHY%提升', 'icon': '🛡️'},
    {'skill_code': 'SK_008', 'name': '法抗', 'skill_type': 'passive', 'category': 'buff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 12, 'mp_cost': 0, 'cooldown': 0, 'description': 'DEF_MAG%提升', 'icon': '🛡️'},
    {'skill_code': 'SK_009', 'name': '护盾术', 'skill_type': 'active', 'category': 'buff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 15, 'cooldown': 3, 'description': '按HP生成盾', 'icon': '🛡️'},
    {'skill_code': 'SK_010', 'name': '嘲讽', 'skill_type': 'active', 'category': 'buff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 20, 'cooldown': 4, 'description': '强制目标1回合', 'icon': '🛡️'},
    {'skill_code': 'SK_011', 'name': '潮汐箭', 'skill_type': 'active', 'category': 'matk', 'damage_formula': 'MAG*1.10', 'base_damage': 22, 'trigger_rate': 100, 'mp_cost': 5, 'cooldown': 1, 'description': '单体法伤', 'icon': '🔮'},
    {'skill_code': 'SK_012', 'name': '冰封', 'skill_type': 'active', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 20, 'cooldown': 4, 'description': '冻结1回合', 'icon': '🌀'},
    {'skill_code': 'SK_013', 'name': '寒潮', 'skill_type': 'active', 'category': 'matk', 'damage_formula': 'MAG*0.85', 'base_damage': 17, 'trigger_rate': 100, 'mp_cost': 15, 'cooldown': 3, 'description': '群体法伤', 'icon': '🔮'},
    {'skill_code': 'SK_014', 'name': '法穿印记', 'skill_type': 'active', 'category': 'matk', 'damage_formula': 'MAG*0.00', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 15, 'cooldown': 3, 'description': '降DEF_MAG', 'icon': '🔮'},
    {'skill_code': 'SK_015', 'name': '灼烧', 'skill_type': 'active', 'category': 'matk', 'damage_formula': 'MAG*0.70', 'base_damage': 14, 'trigger_rate': 100, 'mp_cost': 10, 'cooldown': 2, 'description': '灼烧2回合', 'icon': '🔮'},
    {'skill_code': 'SK_016', 'name': '雷击', 'skill_type': 'active', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 10, 'cooldown': 2, 'description': '小概率麻痹', 'icon': '🌀'},
    {'skill_code': 'SK_017', 'name': '加速', 'skill_type': 'active', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 15, 'cooldown': 3, 'description': '己方速度提升', 'icon': '🌀'},
    {'skill_code': 'SK_018', 'name': '减速', 'skill_type': 'active', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 10, 'cooldown': 2, 'description': '敌方速度下降', 'icon': '🌀'},
    {'skill_code': 'SK_019', 'name': '沉默咒', 'skill_type': 'active', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 20, 'cooldown': 4, 'description': '沉默1回合', 'icon': '🌀'},
    {'skill_code': 'SK_020', 'name': '驱散', 'skill_type': 'active', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 20, 'cooldown': 4, 'description': '驱散1个减益', 'icon': '🌀'},
    {'skill_code': 'SK_021', 'name': '吸血咒', 'skill_type': 'active', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 10, 'cooldown': 2, 'description': '造成伤害并回血', 'icon': '💀'},
    {'skill_code': 'SK_022', 'name': '诅咒', 'skill_type': 'active', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 15, 'cooldown': 3, 'description': '受伤加深', 'icon': '💀'},
    {'skill_code': 'SK_023', 'name': '中毒', 'skill_type': 'active', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 10, 'cooldown': 2, 'description': '毒2回合', 'icon': '💀'},
    {'skill_code': 'SK_024', 'name': '腐蚀', 'skill_type': 'active', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 15, 'cooldown': 3, 'description': '降双防', 'icon': '💀'},
    {'skill_code': 'SK_025', 'name': '复生印记', 'skill_type': 'passive', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 20, 'mp_cost': 0, 'cooldown': 0, 'description': '濒死免死一次', 'icon': '💀'},
    {'skill_code': 'SK_026', 'name': '先手压制', 'skill_type': 'passive', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 10, 'mp_cost': 0, 'cooldown': 0, 'description': '首回合增伤', 'icon': '🌀'},
    {'skill_code': 'SK_027', 'name': '暴击训练', 'skill_type': 'passive', 'category': 'patk', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 10, 'mp_cost': 0, 'cooldown': 0, 'description': '暴击%提升', 'icon': '⚔️'},
    {'skill_code': 'SK_028', 'name': '命中校准', 'skill_type': 'passive', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 10, 'mp_cost': 0, 'cooldown': 0, 'description': '命中%提升', 'icon': '🌀'},
    {'skill_code': 'SK_029', 'name': '闪避身法', 'skill_type': 'passive', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 10, 'mp_cost': 0, 'cooldown': 0, 'description': '闪避%提升', 'icon': '🌀'},
    {'skill_code': 'SK_030', 'name': '抗暴甲', 'skill_type': 'passive', 'category': 'buff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 10, 'mp_cost': 0, 'cooldown': 0, 'description': '抗暴%提升', 'icon': '🛡️'},
    {'skill_code': 'SK_031', 'name': '水盾', 'skill_type': 'active', 'category': 'buff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 15, 'cooldown': 3, 'description': '水族专属护盾', 'icon': '🛡️'},
    {'skill_code': 'SK_032', 'name': '冻结潮', 'skill_type': 'active', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 25, 'cooldown': 5, 'description': '群体小概率冻结', 'icon': '🌀'},
    {'skill_code': 'SK_033', 'name': '深海回响', 'skill_type': 'passive', 'category': 'matk', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 12, 'mp_cost': 0, 'cooldown': 0, 'description': '法伤增幅', 'icon': '🔮'},
    {'skill_code': 'SK_034', 'name': '兽怒', 'skill_type': 'active', 'category': 'patk', 'damage_formula': 'PHY*0.00', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 20, 'cooldown': 4, 'description': '自增伤+自减防', 'icon': '⚔️'},
    {'skill_code': 'SK_035', 'name': '冲撞', 'skill_type': 'active', 'category': 'patk', 'damage_formula': 'PHY*1.05', 'base_damage': 21, 'trigger_rate': 100, 'mp_cost': 10, 'cooldown': 2, 'description': '附带眩晕概率', 'icon': '⚔️'},
    {'skill_code': 'SK_036', 'name': '野性再生', 'skill_type': 'active', 'category': 'buff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 20, 'cooldown': 4, 'description': '按HP回血', 'icon': '🛡️'},
    {'skill_code': 'SK_037', 'name': '虫群', 'skill_type': 'active', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 15, 'cooldown': 3, 'description': '多段DOT', 'icon': '💀'},
    {'skill_code': 'SK_038', 'name': '毒扩散', 'skill_type': 'passive', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 25, 'mp_cost': 0, 'cooldown': 0, 'description': '毒可扩散', 'icon': '💀'},
    {'skill_code': 'SK_039', 'name': '网缚', 'skill_type': 'active', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 20, 'cooldown': 4, 'description': '定身1回合', 'icon': '🌀'},
    {'skill_code': 'SK_040', 'name': '风刃', 'skill_type': 'active', 'category': 'patk', 'damage_formula': 'PHY*1.00', 'base_damage': 20, 'trigger_rate': 100, 'mp_cost': 5, 'cooldown': 1, 'description': '羽族物伤', 'icon': '⚔️'},
    {'skill_code': 'SK_041', 'name': '追击', 'skill_type': 'passive', 'category': 'patk', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 18, 'mp_cost': 0, 'cooldown': 0, 'description': '击杀后追击', 'icon': '⚔️'},
    {'skill_code': 'SK_042', 'name': '雷翼麻痹', 'skill_type': 'active', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 20, 'cooldown': 4, 'description': '麻痹1回合', 'icon': '🌀'},
    {'skill_code': 'SK_043', 'name': '龙威', 'skill_type': 'active', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 20, 'cooldown': 4, 'description': '群体降攻', 'icon': '🌀'},
    {'skill_code': 'SK_044', 'name': '龙炎吐息', 'skill_type': 'active', 'category': 'matk', 'damage_formula': 'MAG*0.90', 'base_damage': 18, 'trigger_rate': 100, 'mp_cost': 15, 'cooldown': 3, 'description': '群体灼烧', 'icon': '🔮'},
    {'skill_code': 'SK_045', 'name': '霜息', 'skill_type': 'active', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 20, 'cooldown': 4, 'description': '单体冻结', 'icon': '🌀'},
    {'skill_code': 'SK_046', 'name': '亡灵虹吸', 'skill_type': 'active', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 10, 'cooldown': 2, 'description': '吸血+降速', 'icon': '💀'},
    {'skill_code': 'SK_047', 'name': '冥火', 'skill_type': 'active', 'category': 'matk', 'damage_formula': 'MAG*1.05', 'base_damage': 21, 'trigger_rate': 100, 'mp_cost': 10, 'cooldown': 2, 'description': '法伤附灼烧', 'icon': '🔮'},
    {'skill_code': 'SK_048', 'name': '群体诅咒', 'skill_type': 'active', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 25, 'cooldown': 5, 'description': '群体受伤加深', 'icon': '💀'},
    {'skill_code': 'SK_049', 'name': '净化之风', 'skill_type': 'active', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 20, 'cooldown': 4, 'description': '驱散1个增益', 'icon': '🌀'},
    {'skill_code': 'SK_050', 'name': '护主', 'skill_type': 'passive', 'category': 'buff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 15, 'mp_cost': 0, 'cooldown': 0, 'description': '为队友分摊伤害', 'icon': '🛡️'},
    {'skill_code': 'SK_051', 'name': '破魔', 'skill_type': 'active', 'category': 'matk', 'damage_formula': 'MAG*1.00', 'base_damage': 20, 'trigger_rate': 100, 'mp_cost': 10, 'cooldown': 2, 'description': '对护盾增伤', 'icon': '🔮'},
    {'skill_code': 'SK_052', 'name': '反伤结界', 'skill_type': 'active', 'category': 'buff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 25, 'cooldown': 5, 'description': '反伤2回合', 'icon': '🛡️'},
    {'skill_code': 'SK_053', 'name': '血祭', 'skill_type': 'active', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 25, 'cooldown': 5, 'description': '自损换高伤', 'icon': '💀'},
    {'skill_code': 'SK_054', 'name': '怒火连击', 'skill_type': 'active', 'category': 'patk', 'damage_formula': 'PHY*0.60', 'base_damage': 12, 'trigger_rate': 100, 'mp_cost': 20, 'cooldown': 4, 'description': '三段随机', 'icon': '⚔️'},
    {'skill_code': 'SK_055', 'name': '风暴降临', 'skill_type': 'active', 'category': 'matk', 'damage_formula': 'MAG*0.80', 'base_damage': 16, 'trigger_rate': 100, 'mp_cost': 20, 'cooldown': 4, 'description': '群体+降速', 'icon': '🔮'},
    {'skill_code': 'SK_056', 'name': '绝对零度', 'skill_type': 'active', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 30, 'cooldown': 6, 'description': '冻结+降防', 'icon': '🌀'},
    {'skill_code': 'SK_057', 'name': '天魔降伏', 'skill_type': 'passive', 'category': 'patk', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 0, 'cooldown': 0, 'description': '对应天魂模板', 'icon': '⚔️'},
    {'skill_code': 'SK_058', 'name': '守护之魂', 'skill_type': 'passive', 'category': 'buff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 0, 'cooldown': 0, 'description': '对应天魂模板', 'icon': '🛡️'},
    {'skill_code': 'SK_059', 'name': '蹑影逐日', 'skill_type': 'passive', 'category': 'debuff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 100, 'mp_cost': 0, 'cooldown': 0, 'description': '对应天魂模板', 'icon': '🌀'},
    {'skill_code': 'SK_060', 'name': '极寿无疆', 'skill_type': 'passive', 'category': 'buff', 'damage_formula': '', 'base_damage': 0, 'trigger_rate': 6, 'mp_cost': 0, 'cooldown': 0, 'description': 'HP%提升', 'icon': '🛡️'},
]

MIGRATED_BONES = [
    {'bone_code': 'skull_rare', 'name': '精钢头骨', 'slot_type': 'skull', 'quality': 'rare', 'level_required': 20, 'hp_bonus': 60, 'patk_bonus': 0, 'matk_bonus': 0, 'pdef_bonus': 0, 'mdef_bonus': 20, 'speed_bonus': 0, 'icon': '🦴'},
    {'bone_code': 'skull_epic', 'name': '龙魂头骨', 'slot_type': 'skull', 'quality': 'epic', 'level_required': 40, 'hp_bonus': 90, 'patk_bonus': 0, 'matk_bonus': 0, 'pdef_bonus': 0, 'mdef_bonus': 30, 'speed_bonus': 0, 'icon': '🦴'},
    {'bone_code': 'sternum_rare', 'name': '精钢胸骨', 'slot_type': 'sternum', 'quality': 'rare', 'level_required': 20, 'hp_bonus': 80, 'patk_bonus': 0, 'matk_bonus': 0, 'pdef_bonus': 20, 'mdef_bonus': 20, 'speed_bonus': 0, 'icon': '🦴'},
    {'bone_code': 'sternum_epic', 'name': '龙魂胸骨', 'slot_type': 'sternum', 'quality': 'epic', 'level_required': 40, 'hp_bonus': 120, 'patk_bonus': 0, 'matk_bonus': 0, 'pdef_bonus': 30, 'mdef_bonus': 30, 'speed_bonus': 0, 'icon': '🦴'},
    {'bone_code': 'arm_rare', 'name': '精钢臂骨', 'slot_type': 'arm', 'quality': 'rare', 'level_required': 20, 'hp_bonus': 0, 'patk_bonus': 16, 'matk_bonus': 16, 'pdef_bonus': 0, 'mdef_bonus': 0, 'speed_bonus': 0, 'icon': '🦴'},
    {'bone_code': 'arm_epic', 'name': '龙魂臂骨', 'slot_type': 'arm', 'quality': 'epic', 'level_required': 40, 'hp_bonus': 0, 'patk_bonus': 24, 'matk_bonus': 24, 'pdef_bonus': 0, 'mdef_bonus': 0, 'speed_bonus': 0, 'icon': '🦴'},
    {'bone_code': 'leg_rare', 'name': '精钢腿骨', 'slot_type': 'leg', 'quality': 'rare', 'level_required': 20, 'hp_bonus': 0, 'patk_bonus': 0, 'matk_bonus': 0, 'pdef_bonus': 16, 'mdef_bonus': 0, 'speed_bonus': 10, 'icon': '🦴'},
    {'bone_code': 'leg_epic', 'name': '龙魂腿骨', 'slot_type': 'leg', 'quality': 'epic', 'level_required': 40, 'hp_bonus': 0, 'patk_bonus': 0, 'matk_bonus': 0, 'pdef_bonus': 24, 'mdef_bonus': 0, 'speed_bonus': 15, 'icon': '🦴'},
    {'bone_code': 'hand_rare', 'name': '精钢手骨', 'slot_type': 'hand', 'quality': 'rare', 'level_required': 20, 'hp_bonus': 0, 'patk_bonus': 10, 'matk_bonus': 10, 'pdef_bonus': 0, 'mdef_bonus': 0, 'speed_bonus': 6, 'icon': '🦴'},
    {'bone_code': 'hand_epic', 'name': '龙魂手骨', 'slot_type': 'hand', 'quality': 'epic', 'level_required': 40, 'hp_bonus': 0, 'patk_bonus': 15, 'matk_bonus': 15, 'pdef_bonus': 0, 'mdef_bonus': 0, 'speed_bonus': 9, 'icon': '🦴'},
    {'bone_code': 'tail_rare', 'name': '精钢尾骨', 'slot_type': 'tail', 'quality': 'rare', 'level_required': 20, 'hp_bonus': 0, 'patk_bonus': 6, 'matk_bonus': 6, 'pdef_bonus': 0, 'mdef_bonus': 0, 'speed_bonus': 6, 'icon': '🦴'},
    {'bone_code': 'tail_epic', 'name': '龙魂尾骨', 'slot_type': 'tail', 'quality': 'epic', 'level_required': 40, 'hp_bonus': 0, 'patk_bonus': 9, 'matk_bonus': 9, 'pdef_bonus': 0, 'mdef_bonus': 0, 'speed_bonus': 9, 'icon': '🦴'},
    {'bone_code': 'soul_core_rare', 'name': '精钢元魂', 'slot_type': 'soul_core', 'quality': 'rare', 'level_required': 20, 'hp_bonus': 60, 'patk_bonus': 10, 'matk_bonus': 10, 'pdef_bonus': 0, 'mdef_bonus': 0, 'speed_bonus': 0, 'icon': '🦴'},
    {'bone_code': 'soul_core_epic', 'name': '龙魂元魂', 'slot_type': 'soul_core', 'quality': 'epic', 'level_required': 40, 'hp_bonus': 90, 'patk_bonus': 15, 'matk_bonus': 15, 'pdef_bonus': 0, 'mdef_bonus': 0, 'speed_bonus': 0, 'icon': '🦴'},
]

MIGRATED_SOULS = [
    {'soul_code': 'tian_天魔降伏', 'name': '天魂·天魔降伏', 'quality': 'tian', 'category': 'special', 'fixed_hp': 0, 'fixed_patk': 120, 'fixed_matk': 0, 'fixed_pdef': 0, 'fixed_mdef': 0, 'fixed_speed': 0, 'percent_hp': 0, 'percent_patk': 0, 'percent_matk': 0, 'percent_pdef': 0, 'percent_mdef': 0, 'percent_speed': 0, 'icon': '🔵'},
    {'soul_code': 'tian_日月乾坤', 'name': '天魂·日月乾坤', 'quality': 'tian', 'category': 'special', 'fixed_hp': 0, 'fixed_patk': 0, 'fixed_matk': 0, 'fixed_pdef': 60, 'fixed_mdef': 0, 'fixed_speed': 0, 'percent_hp': 0, 'percent_patk': 0, 'percent_matk': 0, 'percent_pdef': 0, 'percent_mdef': 0, 'percent_speed': 0, 'icon': '🔵'},
    {'soul_code': 'tian_万龙朝圣', 'name': '天魂·万龙朝圣', 'quality': 'tian', 'category': 'special', 'fixed_hp': 0, 'fixed_patk': 0, 'fixed_matk': 120, 'fixed_pdef': 0, 'fixed_mdef': 0, 'fixed_speed': 0, 'percent_hp': 0, 'percent_patk': 0, 'percent_matk': 0, 'percent_pdef': 0, 'percent_mdef': 0, 'percent_speed': 0, 'icon': '🔵'},
    {'soul_code': 'tian_绝对零度', 'name': '天魂·绝对零度', 'quality': 'tian', 'category': 'special', 'fixed_hp': 0, 'fixed_patk': 0, 'fixed_matk': 0, 'fixed_pdef': 0, 'fixed_mdef': 60, 'fixed_speed': 0, 'percent_hp': 0, 'percent_patk': 0, 'percent_matk': 0, 'percent_pdef': 0, 'percent_mdef': 0, 'percent_speed': 0, 'icon': '🔵'},
    {'soul_code': 'tian_守护之魂', 'name': '天魂·守护之魂', 'quality': 'tian', 'category': 'special', 'fixed_hp': 150, 'fixed_patk': 0, 'fixed_matk': 0, 'fixed_pdef': 0, 'fixed_mdef': 0, 'fixed_speed': 0, 'percent_hp': 0, 'percent_patk': 0, 'percent_matk': 0, 'percent_pdef': 0, 'percent_mdef': 0, 'percent_speed': 0, 'icon': '🔵'},
    {'soul_code': 'tian_蹑影逐日', 'name': '天魂·蹑影逐日', 'quality': 'tian', 'category': 'special', 'fixed_hp': 0, 'fixed_patk': 0, 'fixed_matk': 0, 'fixed_pdef': 0, 'fixed_mdef': 0, 'fixed_speed': 8, 'percent_hp': 0, 'percent_patk': 0, 'percent_matk': 0, 'percent_pdef': 0, 'percent_mdef': 0, 'percent_speed': 0, 'icon': '🔵'},
    {'soul_code': 'tian_无人能挡', 'name': '天魂·无人能挡', 'quality': 'tian', 'category': 'special', 'fixed_hp': 0, 'fixed_patk': 0, 'fixed_matk': 0, 'fixed_pdef': 0, 'fixed_mdef': 0, 'fixed_speed': 0, 'percent_hp': 0, 'percent_patk': 8, 'percent_matk': 0, 'percent_pdef': 0, 'percent_mdef': 0, 'percent_speed': 0, 'icon': '🔵'},
    {'soul_code': 'tian_逢凶化吉', 'name': '天魂·逢凶化吉', 'quality': 'tian', 'category': 'special', 'fixed_hp': 0, 'fixed_patk': 0, 'fixed_matk': 0, 'fixed_pdef': 0, 'fixed_mdef': 0, 'fixed_speed': 0, 'percent_hp': 0, 'percent_patk': 0, 'percent_matk': 0, 'percent_pdef': 6, 'percent_mdef': 0, 'percent_speed': 0, 'icon': '🔵'},
    {'soul_code': 'tian_天绝地灭', 'name': '天魂·天绝地灭', 'quality': 'tian', 'category': 'special', 'fixed_hp': 0, 'fixed_patk': 0, 'fixed_matk': 0, 'fixed_pdef': 0, 'fixed_mdef': 0, 'fixed_speed': 0, 'percent_hp': 0, 'percent_patk': 0, 'percent_matk': 8, 'percent_pdef': 0, 'percent_mdef': 0, 'percent_speed': 0, 'icon': '🔵'},
    {'soul_code': 'tian_冰霜之心', 'name': '天魂·冰霜之心', 'quality': 'tian', 'category': 'special', 'fixed_hp': 0, 'fixed_patk': 0, 'fixed_matk': 0, 'fixed_pdef': 0, 'fixed_mdef': 0, 'fixed_speed': 0, 'percent_hp': 0, 'percent_patk': 0, 'percent_matk': 0, 'percent_pdef': 0, 'percent_mdef': 6, 'percent_speed': 0, 'icon': '🔵'},
    {'soul_code': 'tian_极寿无疆', 'name': '天魂·极寿无疆', 'quality': 'tian', 'category': 'special', 'fixed_hp': 0, 'fixed_patk': 0, 'fixed_matk': 0, 'fixed_pdef': 0, 'fixed_mdef': 0, 'fixed_speed': 0, 'percent_hp': 6, 'percent_patk': 0, 'percent_matk': 0, 'percent_pdef': 0, 'percent_mdef': 0, 'percent_speed': 0, 'icon': '🔵'},
    {'soul_code': 'tian_流星赶月', 'name': '天魂·流星赶月', 'quality': 'tian', 'category': 'special', 'fixed_hp': 0, 'fixed_patk': 0, 'fixed_matk': 0, 'fixed_pdef': 0, 'fixed_mdef': 0, 'fixed_speed': 0, 'percent_hp': 0, 'percent_patk': 0, 'percent_matk': 0, 'percent_pdef': 0, 'percent_mdef': 0, 'percent_speed': 6, 'icon': '🔵'},
]

MIGRATED_SPIRITS = [
    {'spirit_code': 'water_spirit', 'name': '水之战灵', 'element_type': 'water', 'quality': 'rare', 'attr_pool_json': '{"hp": [30, 80], "mdef": [5, 15]}', 'icon': '💧'},
    {'spirit_code': 'earth_spirit', 'name': '土之战灵', 'element_type': 'earth', 'quality': 'rare', 'attr_pool_json': '{"pdef": [10, 25], "hp": [30, 80]}', 'icon': '🪨'},
    {'spirit_code': 'fire_spirit', 'name': '火之战灵', 'element_type': 'fire', 'quality': 'rare', 'attr_pool_json': '{"matk": [5, 15], "patk": [3, 10]}', 'icon': '🔥'},
    {'spirit_code': 'wood_spirit', 'name': '木之战灵', 'element_type': 'wood', 'quality': 'rare', 'attr_pool_json': '{"hp": [40, 100], "speed": [3, 8]}', 'icon': '🌿'},
    {'spirit_code': 'metal_spirit', 'name': '金之战灵', 'element_type': 'metal', 'quality': 'rare', 'attr_pool_json': '{"patk": [8, 20], "matk": [8, 20]}', 'icon': '⚜️'},
    {'spirit_code': 'god_spirit', 'name': '神之战灵', 'element_type': 'god', 'quality': 'legendary', 'attr_pool_json': '{"hp": [60, 150], "patk": [10, 25], "matk": [10, 25], "speed": [5, 12]}', 'icon': '✨'},
]


# ============================================================
# 工具函数
# ============================================================

RARITY_NAMES = {
    "common": "普通", "uncommon": "优秀", "rare": "稀有",
    "epic": "史诗", "legendary": "传说"
}
RARITY_COLORS = {
    "common": "#888", "uncommon": "#2e8b57", "rare": "#4169e1",
    "epic": "#9932cc", "legendary": "#ff8c00"
}
SOUL_QUALITY_NAMES = {
    "waste": "废", "yellow": "黄", "xuan": "玄", "di": "地", "tian": "天", "shen": "神"
}
SOUL_QUALITY_COLORS = {
    "waste": "#999", "yellow": "#daa520", "xuan": "#9370db",
    "di": "#8b4513", "tian": "#4169e1", "shen": "#ff4500"
}
PERSONALITY_NAMES = {
    "brave": "勇敢", "calm": "冷静", "timid": "胆小", "cheerful": "开朗",
    "proud": "骄傲", "cunning": "狡猾", "fierce": "凶猛", "stubborn": "固执", "cold": "冷酷"
}
SLOT_NAMES = {
    "skull": "头骨", "sternum": "胸骨", "arm": "臂骨", "leg": "腿骨",
    "hand": "手骨", "tail": "尾骨", "soul_core": "元魂"
}
QUALITY_NAMES_BONE = {
    "common": "普通", "rare": "精良", "epic": "史诗", "legendary": "传说"
}


def get_common_context(request: Request, db: Session):
    user = get_current_user(request, db)
    if not user:
        return None
    unread_count = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == False
    ).count()
    return {
        "request": request,
        "user": user,
        "lang": "zh",
        "theme": "light",
        "unread_count": unread_count,
        "now": datetime.utcnow(),
    }


def get_or_create_profile(db: Session, user: User) -> SummonProfile:
    """获取或创建召唤师档案"""
    profile = db.query(SummonProfile).filter(SummonProfile.user_id == user.id).first()
    if not profile:
        # 获取初始幻兽：史莱姆
        starter_beast = db.query(SummonBeast).filter(SummonBeast.beast_code == "slime").first()
        starter_skill = db.query(SummonSkill).filter(SummonSkill.skill_code == "tackle").first()

        profile = SummonProfile(
            user_id=user.id,
            summoner_name=user.nickname or "召唤师",
            level=1,
            exp=0,
            vitality=100,
            max_vitality=100,
            copper_coin=1000,
            yuanbao=0,
            prestige=0,
            catch_ball_normal=20,
            catch_ball_strong=5,
            catch_ball_super=0,
        )
        db.add(profile)
        db.flush()

        # 发放初始幻兽
        if starter_beast:
            ub = SummonUserBeast(
                profile_id=profile.id,
                user_id=user.id,
                beast_id=starter_beast.id,
                nickname="初始史莱姆",
                level=1,
                exp=0,
                growth_star=random.randint(1, 3),
                personality="calm",
                quality="normal",
                hp=starter_beast.base_hp,
                max_hp=starter_beast.base_hp,
                patk=starter_beast.base_patk,
                matk=starter_beast.base_matk,
                pdef=starter_beast.base_pdef,
                mdef=starter_beast.base_mdef,
                speed=starter_beast.base_speed,
                status="battle",
            )
            db.add(ub)
            db.flush()

            # 学习初始技能
            if starter_skill:
                us = SummonUserBeastSkill(
                    beast_id=ub.id,
                    skill_id=starter_skill.id,
                    skill_level=1,
                    slot_position=0,
                )
                db.add(us)

            # 发放一套初始战骨
            starter_bones = db.query(SummonBone).filter(SummonBone.quality == "common").all()
            for bone in starter_bones:
                ub_bone = SummonUserBone(
                    beast_id=ub.id,
                    user_id=user.id,
                    bone_id=bone.id,
                    slot_type=bone.slot_type,
                    quality=bone.quality,
                    enhance_level=0,
                    hp_bonus=bone.hp_bonus,
                    patk_bonus=bone.patk_bonus,
                    matk_bonus=bone.matk_bonus,
                    pdef_bonus=bone.pdef_bonus,
                    mdef_bonus=bone.mdef_bonus,
                    speed_bonus=bone.speed_bonus,
                    equipped=True,
                )
                db.add(ub_bone)

        db.commit()
        db.refresh(profile)
    return profile


def exp_for_level(level: int) -> int:
    """计算升级所需经验"""
    return int(50 * (level ** 1.5))


def calculate_beast_stats(ub: SummonUserBeast, beast_def: SummonBeast) -> dict:
    """计算幻兽最终属性（含战骨加成）"""
    growth_mult = 1 + (ub.growth_star - 1) * 0.1
    level_mult = 1 + (ub.level - 1) * 0.08

    hp = int(beast_def.base_hp * level_mult * growth_mult)
    patk = int(beast_def.base_patk * level_mult * growth_mult)
    matk = int(beast_def.base_matk * level_mult * growth_mult)
    pdef = int(beast_def.base_pdef * level_mult * growth_mult)
    mdef = int(beast_def.base_mdef * level_mult * growth_mult)
    speed = int(beast_def.base_speed * level_mult * growth_mult)

    # 战骨加成
    for bone in ub.bones:
        if bone.equipped:
            enh_mult = 1 + bone.enhance_level * 0.1
            hp += int(bone.hp_bonus * enh_mult)
            patk += int(bone.patk_bonus * enh_mult)
            matk += int(bone.matk_bonus * enh_mult)
            pdef += int(bone.pdef_bonus * enh_mult)
            mdef += int(bone.mdef_bonus * enh_mult)
            speed += int(bone.speed_bonus * enh_mult)

    # 魔魂加成
    for soul in ub.souls:
        if soul.equipped:
            soul_def = soul.soul
            if soul_def:
                hp += soul_def.fixed_hp + int(hp * soul_def.percent_hp / 100)
                patk += soul_def.fixed_patk + int(patk * soul_def.percent_patk / 100)
                matk += soul_def.fixed_matk + int(matk * soul_def.percent_matk / 100)
                pdef += soul_def.fixed_pdef + int(pdef * soul_def.percent_pdef / 100)
                mdef += soul_def.fixed_mdef + int(mdef * soul_def.percent_mdef / 100)
                speed += soul_def.fixed_speed + int(speed * soul_def.percent_speed / 100)

    return {"hp": hp, "max_hp": hp, "patk": patk, "matk": matk, "pdef": pdef, "mdef": mdef, "speed": speed}


def recalc_profile_exp(profile: SummonProfile, db: Session):
    """重新计算召唤师等级"""
    while profile.exp >= exp_for_level(profile.level):
        profile.exp -= exp_for_level(profile.level)
        profile.level += 1
        profile.max_vitality += 5
        profile.vitality = profile.max_vitality


def simulate_beast_battle(attacker_ub, attacker_def, attacker_stats,
                          defender_ub, defender_def, defender_stats):
    """模拟两只幻兽的战斗，返回战斗日志和胜负"""
    logs = []
    a_hp = attacker_stats["hp"]
    d_hp = defender_stats["hp"]
    a_max_hp = attacker_stats["max_hp"]
    d_max_hp = defender_stats["max_hp"]
    round_num = 0

    # 获取技能
    a_skills = []
    for us in attacker_ub.skills:
        sk = us.skill
        if sk and sk.skill_type == "active":
            a_skills.append(sk)
    d_skills = []
    for us in defender_ub.skills:
        sk = us.skill
        if sk and sk.skill_type == "active":
            d_skills.append(sk)

    # 被动buff处理
    a_patk_buff = 0
    d_pdef_debuff = 0
    a_rebirth = False
    d_rebirth = False

    for us in attacker_ub.skills:
        sk = us.skill
        if sk and sk.skill_type == "passive":
            if sk.skill_code == "howl" and random.randint(1, 100) <= sk.trigger_rate:
                a_patk_buff = 0.2
                logs.append(f"⚡ {attacker_def.name}发出嚎叫，物攻提升20%！")
            if sk.skill_code == "rebirth":
                a_rebirth = True

    for us in defender_ub.skills:
        sk = us.skill
        if sk and sk.skill_type == "passive":
            if sk.skill_code == "roar" and random.randint(1, 100) <= sk.trigger_rate:
                d_pdef_debuff = 0.2
                logs.append(f"⚡ {defender_def.name}发出怒吼，敌方物防降低20%！")
            if sk.skill_code == "rebirth":
                d_rebirth = True

    a_patk = int(attacker_stats["patk"] * (1 + a_patk_buff))
    d_pdef = int(defender_stats["pdef"] * (1 - d_pdef_debuff))
    d_patk = defender_stats["patk"]
    a_pdef = attacker_stats["pdef"]
    a_matk = attacker_stats["matk"]
    d_mdef = defender_stats["mdef"]
    d_matk = defender_stats["matk"]
    a_mdef = attacker_stats["mdef"]

    while a_hp > 0 and d_hp > 0 and round_num < 20:
        round_num += 1
        logs.append(f"—— 第{round_num}回合 ——")

        # 攻击方出手
        a_skill = random.choice(a_skills) if a_skills else None
        if a_skill:
            if a_skill.category == "patk":
                dmg = max(1, a_patk + a_skill.base_damage - d_pdef)
                logs.append(f"🔹 {attacker_def.name}使用【{a_skill.name}】，对{defender_def.name}造成{dmg}点伤害！")
            elif a_skill.category == "matk":
                dmg = max(1, a_matk + a_skill.base_damage - d_mdef)
                logs.append(f"🔹 {attacker_def.name}使用【{a_skill.name}】，对{defender_def.name}造成{dmg}点魔法伤害！")
            else:
                dmg = max(1, a_patk - d_pdef)
                logs.append(f"🔹 {attacker_def.name}攻击{defender_def.name}，造成{dmg}点伤害！")
            d_hp -= dmg
        else:
            dmg = max(1, a_patk - d_pdef)
            logs.append(f"🔹 {attacker_def.name}攻击{defender_def.name}，造成{dmg}点伤害！")
            d_hp -= dmg

        if d_hp <= 0:
            if d_rebirth:
                d_hp = d_max_hp // 2
                d_rebirth = False
                logs.append(f"✨ {defender_def.name}触发【浴火重生】，以{d_hp}HP复活！")
            else:
                logs.append(f"💥 {defender_def.name}被击败了！")
                break

        # 防守方反击
        d_skill = random.choice(d_skills) if d_skills else None
        if d_skill:
            if d_skill.category == "patk":
                dmg = max(1, d_patk + d_skill.base_damage - a_pdef)
                logs.append(f"🔸 {defender_def.name}使用【{d_skill.name}】，对{attacker_def.name}造成{dmg}点伤害！")
            elif d_skill.category == "matk":
                dmg = max(1, d_matk + d_skill.base_damage - a_mdef)
                logs.append(f"🔸 {defender_def.name}使用【{d_skill.name}】，对{attacker_def.name}造成{dmg}点魔法伤害！")
            else:
                dmg = max(1, d_patk - a_pdef)
                logs.append(f"🔸 {defender_def.name}攻击{attacker_def.name}，造成{dmg}点伤害！")
            a_hp -= dmg
        else:
            dmg = max(1, d_patk - a_pdef)
            logs.append(f"🔸 {defender_def.name}攻击{attacker_def.name}，造成{dmg}点伤害！")
            a_hp -= dmg

        if a_hp <= 0:
            if a_rebirth:
                a_hp = a_max_hp // 2
                a_rebirth = False
                logs.append(f"✨ {attacker_def.name}触发【浴火重生】，以{a_hp}HP复活！")
            else:
                logs.append(f"💥 {attacker_def.name}被击败了！")
                break

    winner = "attacker" if d_hp <= 0 else "defender" if a_hp <= 0 else "draw"
    if winner == "draw" and a_hp < d_hp:
        winner = "defender"
    elif winner == "draw":
        winner = "attacker"

    return logs, winner


# ============================================================
# 路由：首页/初始化
# ============================================================

@router.get("", response_class=HTMLResponse)
async def summon_king_home(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    init_summon_data(db)
    profile = get_or_create_profile(db, ctx["user"])

    # 恢复体力（每3分钟恢复1点）
    now = datetime.utcnow()
    # 简单恢复：每次访问最多恢复满
    if profile.vitality < profile.max_vitality:
        profile.vitality = min(profile.max_vitality, profile.vitality + 10)

    # 获取出战幻兽
    battle_beast = db.query(SummonUserBeast).filter(
        SummonUserBeast.profile_id == profile.id,
        SummonUserBeast.status == "battle"
    ).first()

    beasts_count = db.query(SummonUserBeast).filter(
        SummonUserBeast.profile_id == profile.id
    ).count()

    # 获取联盟信息
    alliance = None
    if profile.alliance_id:
        alliance = db.query(SummonAlliance).filter(SummonAlliance.id == profile.alliance_id).first()

    # 最近捕捉记录
    recent_catches = db.query(SummonCatchLog).filter(
        SummonCatchLog.user_id == ctx["user"].id
    ).order_by(desc(SummonCatchLog.created_at)).limit(5).all()

    # 擂台排名
    rank_subq = db.query(
        SummonProfile.user_id,
        SummonProfile.prestige,
        func.row_number().over(order_by=desc(SummonProfile.prestige)).label("rnk")
    ).subquery()
    my_rank = db.query(rank_subq.c.rnk).filter(rank_subq.c.user_id == ctx["user"].id).scalar()

    ctx.update({
        "profile": profile,
        "battle_beast": battle_beast,
        "beasts_count": beasts_count,
        "alliance": alliance,
        "recent_catches": recent_catches,
        "my_rank": my_rank or "未上榜",
        "exp_needed": exp_for_level(profile.level),
        "rarity_names": RARITY_NAMES,
        "rarity_colors": RARITY_COLORS,
    })
    db.commit()
    return templates.TemplateResponse("summon_king/index.html", ctx)


@router.post("/create")
async def create_summoner(
    request: Request,
    summoner_name: str = Form(...),
    db: Session = Depends(get_db)
):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    init_summon_data(db)
    profile = get_or_create_profile(db, ctx["user"])
    if summoner_name.strip():
        profile.summoner_name = summoner_name.strip()
        db.commit()
    return RedirectResponse(url="/summon_king", status_code=302)


# ============================================================
# 路由：地图系统
# ============================================================

@router.get("/maps", response_class=HTMLResponse)
async def maps_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    init_summon_data(db)
    profile = get_or_create_profile(db, ctx["user"])

    maps = db.query(SummonMap).all()

    ctx.update({
        "profile": profile,
        "maps": maps,
    })
    return templates.TemplateResponse("summon_king/map.html", ctx)


@router.get("/explore/{map_id}")
async def explore_map(request: Request, map_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])
    map_obj = db.query(SummonMap).filter(SummonMap.id == map_id).first()
    if not map_obj:
        return RedirectResponse(url="/summon_king/maps?msg=地图不存在", status_code=302)

    # 等级限制检查（宽松）
    if profile.level < map_obj.level_min - 5:
        return RedirectResponse(url=f"/summon_king/maps?msg=等级不足，需要{map_obj.level_min}级", status_code=302)

    if profile.vitality < map_obj.vitality_cost:
        return RedirectResponse(url=f"/summon_king/maps?msg=体力不足", status_code=302)

    profile.vitality -= map_obj.vitality_cost

    # 随机遇怪
    beast_pool = json.loads(map_obj.beast_pool_json) if map_obj.beast_pool_json else []
    if not beast_pool:
        profile.exp += 10
        profile.copper_coin += 5
        recalc_profile_exp(profile, db)
        db.commit()
        return RedirectResponse(url=f"/summon_king/maps?msg=探索了{map_obj.name}，获得10经验和5铜币", status_code=302)

    # 遇怪逻辑：70%遇怪
    if random.randint(1, 100) <= 70:
        beast_code = random.choice(beast_pool)
        beast = db.query(SummonBeast).filter(SummonBeast.beast_code == beast_code).first()
        if beast:
            # 掉落铜钱
            import ast
            try:
                drops = json.loads(map_obj.drop_json) if map_obj.drop_json else {}
            except:
                drops = {}
            copper_range = drops.get("copper", (5, 15))
            copper_gain = random.randint(copper_range[0], copper_range[1])
            profile.copper_coin += copper_gain
            profile.exp += 15 + beast.map_level_min * 2
            recalc_profile_exp(profile, db)
            db.commit()
            # 跳转到捕捉页面
            return RedirectResponse(url=f"/summon_king/catch/{map_id}/{beast.id}?copper={copper_gain}", status_code=302)

    # 没遇到怪，获得少量奖励
    profile.exp += 5
    profile.copper_coin += random.randint(5, 15)
    recalc_profile_exp(profile, db)
    db.commit()
    return RedirectResponse(url=f"/summon_king/maps?msg=探索了{map_obj.name}，没有遇到幻兽", status_code=302)


# ============================================================
# 路由：捕捉系统
# ============================================================

@router.get("/catch/{map_id}/{beast_id}", response_class=HTMLResponse)
async def catch_page(request: Request, map_id: int, beast_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])
    map_obj = db.query(SummonMap).filter(SummonMap.id == map_id).first()
    beast = db.query(SummonBeast).filter(SummonBeast.id == beast_id).first()

    if not map_obj or not beast:
        return RedirectResponse(url="/summon_king/maps", status_code=302)

    copper_gain = request.query_params.get("copper", "0")

    ctx.update({
        "profile": profile,
        "map": map_obj,
        "beast": beast,
        "copper_gain": copper_gain,
        "rarity_names": RARITY_NAMES,
        "rarity_colors": RARITY_COLORS,
    })
    return templates.TemplateResponse("summon_king/catch.html", ctx)


@router.post("/catch/{map_id}/{beast_id}")
async def do_catch(
    request: Request,
    map_id: int,
    beast_id: int,
    ball_type: str = Form("normal"),
    db: Session = Depends(get_db)
):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])
    map_obj = db.query(SummonMap).filter(SummonMap.id == map_id).first()
    beast = db.query(SummonBeast).filter(SummonBeast.id == beast_id).first()
    if not map_obj or not beast:
        return RedirectResponse(url="/summon_king/maps", status_code=302)

    # 检查捕捉球
    ball_field = f"catch_ball_{ball_type}"
    ball_count = getattr(profile, ball_field, 0)
    if ball_count <= 0:
        return RedirectResponse(url=f"/summon_king/catch/{map_id}/{beast_id}?msg=捕捉球不足", status_code=302)

    setattr(profile, ball_field, ball_count - 1)

    # 计算捕捉概率
    ball_mult = {"normal": 1.0, "strong": 1.8, "super": 3.0}.get(ball_type, 1.0)
    base_rate = beast.catch_rate / 100.0
    catch_prob = min(0.95, base_rate * ball_mult)

    success = random.random() < catch_prob
    user_beast_id = None

    if success:
        # 创建用户幻兽
        growth = random.randint(beast.growth_min, beast.growth_max)
        personality_pool = json.loads(beast.personality_pool_json) if beast.personality_pool_json else ["brave"]
        personality = random.choice(personality_pool)

        # 品质判定：成长星越高品质越好
        quality = "normal"
        if growth >= beast.growth_max:
            quality = random.choice(["good", "excellent", "perfect"])
        elif growth >= beast.growth_max - 1:
            quality = random.choice(["normal", "good"])

        ub = SummonUserBeast(
            profile_id=profile.id,
            user_id=ctx["user"].id,
            beast_id=beast.id,
            nickname=beast.name,
            level=max(1, map_obj.level_min),
            exp=0,
            growth_star=growth,
            personality=personality,
            quality=quality,
            hp=beast.base_hp,
            max_hp=beast.base_hp,
            patk=beast.base_patk,
            matk=beast.base_matk,
            pdef=beast.base_pdef,
            mdef=beast.base_mdef,
            speed=beast.base_speed,
            status="rest",
        )
        db.add(ub)
        db.flush()
        user_beast_id = ub.id

        # 自动学习第一个技能
        skill_pool = json.loads(beast.skill_pool_json) if beast.skill_pool_json else []
        if skill_pool:
            for i, sk_code in enumerate(skill_pool[:2]):
                skill = db.query(SummonSkill).filter(SummonSkill.skill_code == sk_code).first()
                if skill:
                    us = SummonUserBeastSkill(
                        beast_id=ub.id,
                        skill_id=skill.id,
                        skill_level=1,
                        slot_position=i,
                    )
                    db.add(us)

        add_notification(ctx["user"].id, "game", "捕捉成功",
                         f"恭喜你成功捕捉了{beast.name}！", "summon_king", db)

    # 记录
    log = SummonCatchLog(
        user_id=ctx["user"].id,
        map_id=map_id,
        beast_id=beast.id,
        beast_name=beast.name,
        ball_type=ball_type,
        success=success,
        user_beast_id=user_beast_id,
    )
    db.add(log)

    profile.exp += 10
    recalc_profile_exp(profile, db)
    db.commit()

    if success:
        return RedirectResponse(url=f"/summon_king/beasts?msg=捕捉成功！获得了{beast.name}", status_code=302)
    else:
        return RedirectResponse(url=f"/summon_king/maps?msg=捕捉失败，{beast.name}逃跑了", status_code=302)


# ============================================================
# 路由：幻兽系统
# ============================================================

@router.get("/beasts", response_class=HTMLResponse)
async def beasts_list(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])
    user_beasts = db.query(SummonUserBeast).filter(
        SummonUserBeast.profile_id == profile.id
    ).all()

    # 为每个幻兽加载基础数据
    beasts_data = []
    for ub in user_beasts:
        bdef = db.query(SummonBeast).filter(SummonBeast.id == ub.beast_id).first()
        if bdef:
            stats = calculate_beast_stats(ub, bdef)
            beasts_data.append({"ub": ub, "bdef": bdef, "stats": stats})

    ctx.update({
        "profile": profile,
        "beasts_data": beasts_data,
        "rarity_names": RARITY_NAMES,
        "rarity_colors": RARITY_COLORS,
        "personality_names": PERSONALITY_NAMES,
    })
    return templates.TemplateResponse("summon_king/beasts.html", ctx)


@router.get("/beast/{beast_id}", response_class=HTMLResponse)
async def beast_detail(request: Request, beast_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])
    ub = db.query(SummonUserBeast).filter(
        SummonUserBeast.id == beast_id,
        SummonUserBeast.profile_id == profile.id
    ).first()
    if not ub:
        return RedirectResponse(url="/summon_king/beasts?msg=幻兽不存在", status_code=302)

    bdef = db.query(SummonBeast).filter(SummonBeast.id == ub.beast_id).first()
    stats = calculate_beast_stats(ub, bdef)

    # 所有可用技能（从技能池）
    available_skills = []
    skill_pool = json.loads(bdef.skill_pool_json) if bdef.skill_pool_json else []
    learned_skill_ids = {us.skill_id for us in ub.skills}
    for sk_code in skill_pool:
        sk = db.query(SummonSkill).filter(SummonSkill.skill_code == sk_code).first()
        if sk and sk.id not in learned_skill_ids:
            available_skills.append(sk)

    # 装备的战骨
    equipped_bones = {b.slot_type: b for b in ub.bones if b.equipped}
    bone_defs = {}
    for slot_type, ub_bone in equipped_bones.items():
        bone_defs[slot_type] = db.query(SummonBone).filter(SummonBone.id == ub_bone.bone_id).first()

    # 装备的魔魂
    equipped_souls = [s for s in ub.souls if s.equipped]

    # 等级所需经验
    level_exp = int(30 * (ub.level ** 1.3))

    ctx.update({
        "profile": profile,
        "ub": ub,
        "bdef": bdef,
        "stats": stats,
        "available_skills": available_skills,
        "equipped_bones": equipped_bones,
        "bone_defs": bone_defs,
        "equipped_souls": equipped_souls,
        "level_exp": level_exp,
        "rarity_names": RARITY_NAMES,
        "rarity_colors": RARITY_COLORS,
        "personality_names": PERSONALITY_NAMES,
        "slot_names": SLOT_NAMES,
        "quality_names_bone": QUALITY_NAMES_BONE,
        "soul_quality_names": SOUL_QUALITY_NAMES,
        "soul_quality_colors": SOUL_QUALITY_COLORS,
    })
    return templates.TemplateResponse("summon_king/beast_detail.html", ctx)


@router.post("/beast/{beast_id}/set_battle")
async def set_battle_beast(request: Request, beast_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])
    ub = db.query(SummonUserBeast).filter(
        SummonUserBeast.id == beast_id,
        SummonUserBeast.profile_id == profile.id
    ).first()
    if not ub:
        return RedirectResponse(url="/summon_king/beasts", status_code=302)

    # 取消其他出战
    db.query(SummonUserBeast).filter(
        SummonUserBeast.profile_id == profile.id,
        SummonUserBeast.status == "battle"
    ).update({"status": "rest"})

    ub.status = "battle"
    db.commit()
    return RedirectResponse(url=f"/summon_king/beast/{beast_id}?msg=已设为出战", status_code=302)


@router.post("/beast/{beast_id}/rest")
async def rest_beast(request: Request, beast_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])
    ub = db.query(SummonUserBeast).filter(
        SummonUserBeast.id == beast_id,
        SummonUserBeast.profile_id == profile.id
    ).first()
    if ub:
        ub.status = "rest"
        db.commit()
    return RedirectResponse(url=f"/summon_king/beast/{beast_id}?msg=已休息", status_code=302)


@router.post("/beast/{beast_id}/train")
async def train_beast(request: Request, beast_id: int, db: Session = Depends(get_db)):
    """训练幻兽升级（消耗铜币）"""
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])
    ub = db.query(SummonUserBeast).filter(
        SummonUserBeast.id == beast_id,
        SummonUserBeast.profile_id == profile.id
    ).first()
    if not ub:
        return RedirectResponse(url="/summon_king/beasts", status_code=302)

    cost = ub.level * 20
    if profile.copper_coin < cost:
        return RedirectResponse(url=f"/summon_king/beast/{beast_id}?msg=铜币不足，需要{cost}", status_code=302)

    profile.copper_coin -= cost
    ub.exp += int(30 * (ub.level ** 1.3))

    # 升级
    level_exp = int(30 * (ub.level ** 1.3))
    leveled = False
    while ub.exp >= level_exp and ub.level < 100:
        ub.exp -= level_exp
        ub.level += 1
        bdef = db.query(SummonBeast).filter(SummonBeast.id == ub.beast_id).first()
        growth_mult = 1 + (ub.growth_star - 1) * 0.1
        ub.max_hp = int(bdef.base_hp * (1 + (ub.level - 1) * 0.08) * growth_mult)
        ub.hp = ub.max_hp
        ub.patk = int(bdef.base_patk * (1 + (ub.level - 1) * 0.08) * growth_mult)
        ub.matk = int(bdef.base_matk * (1 + (ub.level - 1) * 0.08) * growth_mult)
        ub.pdef = int(bdef.base_pdef * (1 + (ub.level - 1) * 0.08) * growth_mult)
        ub.mdef = int(bdef.base_mdef * (1 + (ub.level - 1) * 0.08) * growth_mult)
        ub.speed = int(bdef.base_speed * (1 + (ub.level - 1) * 0.08) * growth_mult)
        level_exp = int(30 * (ub.level ** 1.3))
        leveled = True

    db.commit()
    msg = f"训练完成，消耗{cost}铜币"
    if leveled:
        msg += f"，幻兽升级到{ub.level}级！"
    return RedirectResponse(url=f"/summon_king/beast/{beast_id}?msg={msg}", status_code=302)


@router.post("/beast/{beast_id}/learn_skill/{skill_id}")
async def learn_skill(request: Request, beast_id: int, skill_id: int, db: Session = Depends(get_db)):
    """学习技能"""
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])
    ub = db.query(SummonUserBeast).filter(
        SummonUserBeast.id == beast_id,
        SummonUserBeast.profile_id == profile.id
    ).first()
    skill = db.query(SummonSkill).filter(SummonSkill.id == skill_id).first()
    if not ub or not skill:
        return RedirectResponse(url="/summon_king/beasts", status_code=302)

    # 检查是否已学
    existing = db.query(SummonUserBeastSkill).filter(
        SummonUserBeastSkill.beast_id == beast_id,
        SummonUserBeastSkill.skill_id == skill_id
    ).first()
    if existing:
        return RedirectResponse(url=f"/summon_king/beast/{beast_id}?msg=已经学会此技能", status_code=302)

    # 检查技能栏位（最多4个）
    current_skills = db.query(SummonUserBeastSkill).filter(
        SummonUserBeastSkill.beast_id == beast_id
    ).count()
    if current_skills >= 4:
        return RedirectResponse(url=f"/summon_king/beast/{beast_id}?msg=技能栏已满", status_code=302)

    # 学习费用
    cost = 200
    if profile.copper_coin < cost:
        return RedirectResponse(url=f"/summon_king/beast/{beast_id}?msg=铜币不足", status_code=302)

    profile.copper_coin -= cost
    us = SummonUserBeastSkill(
        beast_id=beast_id,
        skill_id=skill_id,
        skill_level=1,
        slot_position=current_skills,
    )
    db.add(us)
    db.commit()
    return RedirectResponse(url=f"/summon_king/beast/{beast_id}?msg=学会了{skill.name}", status_code=302)


@router.post("/beast/{beast_id}/release")
async def release_beast(request: Request, beast_id: int, db: Session = Depends(get_db)):
    """放生幻兽"""
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])
    ub = db.query(SummonUserBeast).filter(
        SummonUserBeast.id == beast_id,
        SummonUserBeast.profile_id == profile.id
    ).first()
    if not ub:
        return RedirectResponse(url="/summon_king/beasts", status_code=302)
    if ub.status == "battle":
        return RedirectResponse(url=f"/summon_king/beast/{beast_id}?msg=出战中幻兽无法放生", status_code=302)

    bdef = db.query(SummonBeast).filter(SummonBeast.id == ub.beast_id).first()
    copper_back = ub.level * 10
    profile.copper_coin += copper_back
    db.delete(ub)
    db.commit()
    return RedirectResponse(url=f"/summon_king/beasts?msg=放生了{bdef.name}，获得{copper_back}铜币", status_code=302)


# ============================================================
# 路由：战骨系统
# ============================================================

@router.get("/bones", response_class=HTMLResponse)
async def bones_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])

    # 获取当前出战幻兽的战骨
    battle_beast = db.query(SummonUserBeast).filter(
        SummonUserBeast.profile_id == profile.id,
        SummonUserBeast.status == "battle"
    ).first()

    user_bones = []
    bdef = None
    if battle_beast:
        bdef = db.query(SummonBeast).filter(SummonBeast.id == battle_beast.beast_id).first()
        user_bones = db.query(SummonUserBone).filter(
            SummonUserBone.beast_id == battle_beast.id
        ).all()
        for ub in user_bones:
            ub.bone_def = db.query(SummonBone).filter(SummonBone.id == ub.bone_id).first()

    # 背包中未装备的战骨
    all_user_bones = db.query(SummonUserBone).filter(
        SummonUserBone.user_id == ctx["user"].id,
        SummonUserBone.equipped == False
    ).all() if False else []

    ctx.update({
        "profile": profile,
        "battle_beast": battle_beast,
        "bdef": bdef,
        "user_bones": user_bones,
        "slot_names": SLOT_NAMES,
        "quality_names_bone": QUALITY_NAMES_BONE,
    })
    return templates.TemplateResponse("summon_king/bones.html", ctx)


@router.post("/bone/{user_bone_id}/enhance")
async def enhance_bone(request: Request, user_bone_id: int, db: Session = Depends(get_db)):
    """强化战骨"""
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])
    ub = db.query(SummonUserBone).filter(SummonUserBone.id == user_bone_id).first()
    if not ub or ub.user_id != ctx["user"].id:
        return RedirectResponse(url="/summon_king/bones", status_code=302)

    cost = (ub.enhance_level + 1) * 100
    if profile.copper_coin < cost:
        return RedirectResponse(url="/summon_king/bones?msg=铜币不足", status_code=302)

    # 强化成功率：等级越高越低
    success_rate = max(0.2, 1.0 - ub.enhance_level * 0.1)
    profile.copper_coin -= cost

    if random.random() < success_rate:
        ub.enhance_level += 1
        bone_def = db.query(SummonBone).filter(SummonBone.id == ub.bone_id).first()
        if bone_def:
            enh_mult = 1 + ub.enhance_level * 0.1
            ub.hp_bonus = int(bone_def.hp_bonus * enh_mult)
            ub.patk_bonus = int(bone_def.patk_bonus * enh_mult)
            ub.matk_bonus = int(bone_def.matk_bonus * enh_mult)
            ub.pdef_bonus = int(bone_def.pdef_bonus * enh_mult)
            ub.mdef_bonus = int(bone_def.mdef_bonus * enh_mult)
            ub.speed_bonus = int(bone_def.speed_bonus * enh_mult)
        db.commit()
        return RedirectResponse(url="/summon_king/bones?msg=强化成功！", status_code=302)
    else:
        db.commit()
        return RedirectResponse(url="/summon_king/bones?msg=强化失败", status_code=302)


# ============================================================
# 路由：魔魂系统
# ============================================================

@router.get("/souls", response_class=HTMLResponse)
async def souls_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])

    # 用户所有魔魂
    user_souls = db.query(SummonUserSoul).filter(
        SummonUserSoul.user_id == ctx["user"].id
    ).all()
    for us in user_souls:
        us.soul_def = db.query(SummonSoul).filter(SummonSoul.id == us.soul_id).first()
        if us.beast_id:
            us.beast_obj = db.query(SummonUserBeast).filter(SummonUserBeast.id == us.beast_id).first()
            if us.beast_obj:
                us.beast_bdef = db.query(SummonBeast).filter(SummonBeast.id == us.beast_obj.beast_id).first()

    # 出战幻兽
    battle_beast = db.query(SummonUserBeast).filter(
        SummonUserBeast.profile_id == profile.id,
        SummonUserBeast.status == "battle"
    ).first()

    # 猎魂记录
    hunt_logs = db.query(SummonSoulHuntLog).filter(
        SummonSoulHuntLog.user_id == ctx["user"].id
    ).order_by(desc(SummonSoulHuntLog.created_at)).limit(10).all()

    ctx.update({
        "profile": profile,
        "user_souls": user_souls,
        "battle_beast": battle_beast,
        "hunt_logs": hunt_logs,
        "soul_quality_names": SOUL_QUALITY_NAMES,
        "soul_quality_colors": SOUL_QUALITY_COLORS,
    })
    return templates.TemplateResponse("summon_king/souls.html", ctx)


@router.post("/souls/hunt")
async def hunt_soul(request: Request, hunt_type: str = Form("copper"), db: Session = Depends(get_db)):
    """猎魂"""
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])

    if hunt_type == "copper":
        cost = 500
        if profile.copper_coin < cost:
            return RedirectResponse(url="/summon_king/souls?msg=铜币不足", status_code=302)
        profile.copper_coin -= cost
        # 概率分布：废60%、黄25%、玄10%、地4%、天0.9%、神0.1%
        roll = random.random() * 100
        if roll < 60:
            quality = "waste"
        elif roll < 85:
            quality = "yellow"
        elif roll < 95:
            quality = "xuan"
        elif roll < 99:
            quality = "di"
        elif roll < 99.9:
            quality = "tian"
        else:
            quality = "shen"
    else:
        cost = 10
        if profile.yuanbao < cost:
            return RedirectResponse(url="/summon_king/souls?msg=元宝不足", status_code=302)
        profile.yuanbao -= cost
        # 元宝猎魂：概率更高
        roll = random.random() * 100
        if roll < 20:
            quality = "waste"
        elif roll < 50:
            quality = "yellow"
        elif roll < 75:
            quality = "xuan"
        elif roll < 92:
            quality = "di"
        elif roll < 99:
            quality = "tian"
        else:
            quality = "shen"

    # 随机选取对应品质的魔魂
    candidates = db.query(SummonSoul).filter(SummonSoul.quality == quality).all()
    if not candidates:
        candidates = db.query(SummonSoul).filter(SummonSoul.quality == "waste").all()
    soul = random.choice(candidates) if candidates else None

    if soul:
        us = SummonUserSoul(
            user_id=ctx["user"].id,
            soul_id=soul.id,
            level=1,
            soul_power=10 if quality == "waste" else 20 if quality == "yellow" else 50 if quality == "xuan" else 100 if quality == "di" else 200 if quality == "tian" else 500,
            equipped=False,
        )
        db.add(us)
        log = SummonSoulHuntLog(
            user_id=ctx["user"].id,
            hunter_level=1,
            cost_copper=cost if hunt_type == "copper" else 0,
            cost_yuanbao=0 if hunt_type == "copper" else cost,
            soul_id=soul.id,
            soul_quality=quality,
        )
        db.add(log)
        db.commit()
        return RedirectResponse(url=f"/summon_king/souls?msg=猎魂成功！获得{soul.name}", status_code=302)

    db.commit()
    return RedirectResponse(url="/summon_king/souls?msg=猎魂失败", status_code=302)


@router.post("/soul/{user_soul_id}/equip/{beast_id}")
async def equip_soul(request: Request, user_soul_id: int, beast_id: int, db: Session = Depends(get_db)):
    """装备魔魂"""
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])
    us = db.query(SummonUserSoul).filter(SummonUserSoul.id == user_soul_id).first()
    ub = db.query(SummonUserBeast).filter(SummonUserBeast.id == beast_id).first()
    if not us or us.user_id != ctx["user"].id or not ub or ub.profile_id != profile.id:
        return RedirectResponse(url="/summon_king/souls", status_code=302)

    # 每个幻兽最多装备3个魔魂
    equipped_count = db.query(SummonUserSoul).filter(
        SummonUserSoul.beast_id == beast_id,
        SummonUserSoul.equipped == True
    ).count()
    if equipped_count >= 3:
        return RedirectResponse(url="/summon_king/souls?msg=魔魂栏已满（最多3个）", status_code=302)

    us.beast_id = beast_id
    us.equipped = True
    us.slot_position = equipped_count
    db.commit()
    return RedirectResponse(url="/summon_king/souls?msg=装备成功", status_code=302)


@router.post("/soul/{user_soul_id}/unequip")
async def unequip_soul(request: Request, user_soul_id: int, db: Session = Depends(get_db)):
    """卸下魔魂"""
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    us = db.query(SummonUserSoul).filter(SummonUserSoul.id == user_soul_id).first()
    if us and us.user_id == ctx["user"].id:
        us.equipped = False
        us.beast_id = None
        db.commit()
    return RedirectResponse(url="/summon_king/souls?msg=已卸下", status_code=302)


# ============================================================
# 路由：擂台系统
# ============================================================

@router.get("/arena", response_class=HTMLResponse)
async def arena_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])

    # 我的出战幻兽
    my_beast = db.query(SummonUserBeast).filter(
        SummonUserBeast.profile_id == profile.id,
        SummonUserBeast.status == "battle"
    ).first()

    # 匹配对手（声望相近的玩家）
    opponents_profiles = db.query(SummonProfile).filter(
        SummonProfile.user_id != ctx["user"].id,
        SummonProfile.prestige >= profile.prestige - 200,
        SummonProfile.prestige <= profile.prestige + 300
    ).order_by(func.random()).limit(5).all()

    if len(opponents_profiles) < 3:
        opponents_profiles = db.query(SummonProfile).filter(
            SummonProfile.user_id != ctx["user"].id
        ).order_by(func.random()).limit(5).all()

    opponents = []
    for op in opponents_profiles:
        op_user = db.query(User).filter(User.id == op.user_id).first()
        op_beast = db.query(SummonUserBeast).filter(
            SummonUserBeast.profile_id == op.id,
            SummonUserBeast.status == "battle"
        ).first()
        op_bdef = None
        op_stats = None
        if op_beast:
            op_bdef = db.query(SummonBeast).filter(SummonBeast.id == op_beast.beast_id).first()
            if op_bdef:
                op_stats = calculate_beast_stats(op_beast, op_bdef)
        opponents.append({
            "profile": op, "user": op_user, "beast": op_beast,
            "bdef": op_bdef, "stats": op_stats
        })

    # 排行榜（前10名）
    rank_subq = db.query(
        SummonProfile,
        User,
        func.row_number().over(order_by=desc(SummonProfile.prestige)).label("rnk")
    ).join(User, User.id == SummonProfile.user_id).subquery()

    top_rankings = db.query(rank_subq).order_by(rank_subq.c.rnk).limit(10).all()

    # 我的排名
    my_rank = db.query(rank_subq.c.rnk).filter(rank_subq.c.user_id == ctx["user"].id).scalar()

    # 最近战报
    recent_matches = db.query(SummonArenaMatch).filter(
        (SummonArenaMatch.attacker_id == ctx["user"].id) |
        (SummonArenaMatch.defender_id == ctx["user"].id)
    ).order_by(desc(SummonArenaMatch.created_at)).limit(10).all()

    ctx.update({
        "profile": profile,
        "my_beast": my_beast,
        "my_bdef": db.query(SummonBeast).filter(SummonBeast.id == my_beast.beast_id).first() if my_beast else None,
        "my_stats": calculate_beast_stats(my_beast, db.query(SummonBeast).filter(SummonBeast.id == my_beast.beast_id).first()) if my_beast else None,
        "opponents": opponents,
        "top_rankings": top_rankings,
        "my_rank": my_rank or "未上榜",
        "recent_matches": recent_matches,
        "rarity_names": RARITY_NAMES,
        "rarity_colors": RARITY_COLORS,
    })
    return templates.TemplateResponse("summon_king/arena.html", ctx)


@router.post("/arena/challenge/{opponent_user_id}")
async def arena_challenge(request: Request, opponent_user_id: int, db: Session = Depends(get_db)):
    """挑战对手"""
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])

    if profile.vitality < 5:
        return RedirectResponse(url="/summon_king/arena?msg=体力不足（需要5点）", status_code=302)

    my_beast = db.query(SummonUserBeast).filter(
        SummonUserBeast.profile_id == profile.id,
        SummonUserBeast.status == "battle"
    ).first()
    if not my_beast:
        return RedirectResponse(url="/summon_king/arena?msg=请先设置出战幻兽", status_code=302)

    opponent_profile = db.query(SummonProfile).filter(SummonProfile.user_id == opponent_user_id).first()
    if not opponent_profile:
        return RedirectResponse(url="/summon_king/arena?msg=对手不存在", status_code=302)

    opponent_user = db.query(User).filter(User.id == opponent_user_id).first()
    opponent_beast = db.query(SummonUserBeast).filter(
        SummonUserBeast.profile_id == opponent_profile.id,
        SummonUserBeast.status == "battle"
    ).first()
    if not opponent_beast:
        # 对手没有出战幻兽，直接获胜
        profile.prestige += 20
        profile.vitality -= 5
        profile.copper_coin += 50
        db.commit()
        return RedirectResponse(url="/summon_king/arena?msg=对手没有出战幻兽，不战而胜！", status_code=302)

    # 模拟战斗
    my_bdef = db.query(SummonBeast).filter(SummonBeast.id == my_beast.beast_id).first()
    opp_bdef = db.query(SummonBeast).filter(SummonBeast.id == opponent_beast.beast_id).first()
    my_stats = calculate_beast_stats(my_beast, my_bdef)
    opp_stats = calculate_beast_stats(opponent_beast, opp_bdef)

    logs, winner = simulate_beast_battle(
        my_beast, my_bdef, my_stats,
        opponent_beast, opp_bdef, opp_stats
    )

    prestige_gain = 0
    prestige_loss = 0
    result = "win"

    if winner == "attacker":
        # 我方胜利
        prestige_gain = min(50, max(10, int((opponent_profile.prestige - profile.prestige) / 10) + 25))
        profile.prestige += prestige_gain
        profile.copper_coin += 100
        profile.exp += 50
        result = "win"
    else:
        # 我方失败
        prestige_loss = min(30, max(5, int((profile.prestige - opponent_profile.prestige) / 10) + 10))
        profile.prestige = max(0, profile.prestige - prestige_loss)
        profile.copper_coin += 20
        profile.exp += 15
        result = "lose"

    profile.vitality -= 5
    recalc_profile_exp(profile, db)

    # 记录战报
    match = SummonArenaMatch(
        attacker_id=ctx["user"].id,
        defender_id=opponent_user_id,
        attacker_nickname=profile.summoner_name,
        defender_nickname=opponent_profile.summoner_name or opponent_user.nickname if opponent_user else "未知",
        tier=profile.arena_tier,
        result=result,
        attacker_rank_change=prestige_gain if result == "win" else -prestige_loss,
        defender_rank_change=-prestige_gain // 2 if result == "win" else prestige_loss // 2,
        prestige_change=prestige_gain if result == "win" else -prestige_loss,
        battle_log=json.dumps(logs, ensure_ascii=False),
    )
    db.add(match)
    db.commit()

    msg = "挑战胜利！" if result == "win" else "挑战失败"
    return RedirectResponse(url=f"/summon_king/arena?msg={msg}", status_code=302)


@router.get("/arena/match/{match_id}", response_class=HTMLResponse)
async def match_detail(request: Request, match_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    match = db.query(SummonArenaMatch).filter(SummonArenaMatch.id == match_id).first()
    if not match:
        return RedirectResponse(url="/summon_king/arena", status_code=302)

    battle_log = json.loads(match.battle_log) if match.battle_log else []

    ctx.update({
        "match": match,
        "battle_log": battle_log,
    })
    # 直接返回简单页面
    from fastapi.responses import HTMLResponse as HTMLResp
    html = f"""
    <!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>战报详情</title>
    <style>body{{font-family:sans-serif;max-width:480px;margin:0 auto;padding:10px;background:#e8eef7;}}
    .log{{background:white;padding:10px;border:1px solid #b8ccea;margin:10px 0;}}
    .win{{color:#3ac840;font-weight:bold;}}.lose{{color:#e8403a;font-weight:bold;}}
    a{{color:#1a5dc7;}}</style></head><body>
    <h3>战报详情</h3>
    <p><a href="/summon_king/arena">← 返回擂台</a></p>
    <div class="log">
    <p><b>{match.attacker_nickname}</b> VS <b>{match.defender_nickname}</b></p>
    <p>结果：<span class="{'win' if match.result=='win' else 'lose'}">{'胜利' if match.result=='win' else '失败'}</span>
    （声望{match.prestige_change:+d}）</p>
    <hr>
    {''.join(f'<p>{line}</p>' for line in battle_log)}
    </div></body></html>
    """
    return HTMLResp(content=html)


# ============================================================
# 路由：联盟系统
# ============================================================

@router.get("/alliance", response_class=HTMLResponse)
async def alliance_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])

    my_alliance = None
    my_membership = None
    members = []
    donation_logs = []

    if profile.alliance_id:
        my_alliance = db.query(SummonAlliance).filter(SummonAlliance.id == profile.alliance_id).first()
        if my_alliance:
            my_membership = db.query(SummonAllianceMember).filter(
                SummonAllianceMember.alliance_id == my_alliance.id,
                SummonAllianceMember.user_id == ctx["user"].id
            ).first()
            members = db.query(SummonAllianceMember).filter(
                SummonAllianceMember.alliance_id == my_alliance.id
            ).order_by(SummonAllianceMember.contribution.desc()).all()
            donation_logs = db.query(SummonAllianceDonationLog).filter(
                SummonAllianceDonationLog.alliance_id == my_alliance.id
            ).order_by(desc(SummonAllianceDonationLog.created_at)).limit(20).all()

    # 联盟列表
    alliances = db.query(SummonAlliance).filter(SummonAlliance.status == 1).order_by(desc(SummonAlliance.level), desc(SummonAlliance.funds)).limit(20).all()

    ctx.update({
        "profile": profile,
        "my_alliance": my_alliance,
        "my_membership": my_membership,
        "members": members,
        "donation_logs": donation_logs,
        "alliances": alliances,
    })
    return templates.TemplateResponse("summon_king/alliance.html", ctx)


@router.post("/alliance/create")
async def create_alliance(request: Request, name: str = Form(...), db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])
    if profile.alliance_id:
        return RedirectResponse(url="/summon_king/alliance?msg=你已在联盟中", status_code=302)

    if profile.copper_coin < 5000:
        return RedirectResponse(url="/summon_king/alliance?msg=创建联盟需要5000铜币", status_code=302)

    existing = db.query(SummonAlliance).filter(SummonAlliance.name == name.strip()).first()
    if existing:
        return RedirectResponse(url="/summon_king/alliance?msg=联盟名称已存在", status_code=302)

    profile.copper_coin -= 5000

    alliance = SummonAlliance(
        name=name.strip(),
        leader_user_id=ctx["user"].id,
        leader_nickname=profile.summoner_name,
        notice="欢迎加入联盟！",
        description="新建联盟",
        level=1,
        funds=0,
        member_count=1,
        skill_level_json=json.dumps({"atk": 1, "def": 1, "hp": 1}),
    )
    db.add(alliance)
    db.flush()

    member = SummonAllianceMember(
        alliance_id=alliance.id,
        user_id=ctx["user"].id,
        user_nickname=profile.summoner_name,
        role="leader",
        contribution=0,
    )
    db.add(member)

    profile.alliance_id = alliance.id
    db.commit()
    return RedirectResponse(url="/summon_king/alliance?msg=联盟创建成功", status_code=302)


@router.post("/alliance/join/{alliance_id}")
async def join_alliance(request: Request, alliance_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])
    if profile.alliance_id:
        return RedirectResponse(url="/summon_king/alliance?msg=你已在联盟中", status_code=302)

    alliance = db.query(SummonAlliance).filter(SummonAlliance.id == alliance_id).first()
    if not alliance:
        return RedirectResponse(url="/summon_king/alliance?msg=联盟不存在", status_code=302)
    if alliance.member_count >= alliance.member_limit:
        return RedirectResponse(url="/summon_king/alliance?msg=联盟人数已满", status_code=302)

    member = SummonAllianceMember(
        alliance_id=alliance.id,
        user_id=ctx["user"].id,
        user_nickname=profile.summoner_name,
        role="member",
    )
    db.add(member)
    alliance.member_count += 1
    profile.alliance_id = alliance.id
    db.commit()
    return RedirectResponse(url="/summon_king/alliance?msg=加入联盟成功", status_code=302)


@router.post("/alliance/leave")
async def leave_alliance(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])
    if not profile.alliance_id:
        return RedirectResponse(url="/summon_king/alliance", status_code=302)

    membership = db.query(SummonAllianceMember).filter(
        SummonAllianceMember.alliance_id == profile.alliance_id,
        SummonAllianceMember.user_id == ctx["user"].id
    ).first()
    if membership and membership.role == "leader":
        return RedirectResponse(url="/summon_king/alliance?msg=会长不能退出联盟，请先转让", status_code=302)

    if membership:
        db.delete(membership)
    alliance = db.query(SummonAlliance).filter(SummonAlliance.id == profile.alliance_id).first()
    if alliance:
        alliance.member_count = max(0, alliance.member_count - 1)
    profile.alliance_id = None
    db.commit()
    return RedirectResponse(url="/summon_king/alliance?msg=已退出联盟", status_code=302)


@router.post("/alliance/donate")
async def donate_alliance(
    request: Request,
    donate_type: str = Form("copper"),
    amount: int = Form(1000),
    db: Session = Depends(get_db)
):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])
    if not profile.alliance_id:
        return RedirectResponse(url="/summon_king/alliance?msg=你还没有联盟", status_code=302)

    if donate_type == "copper":
        if profile.copper_coin < amount:
            return RedirectResponse(url="/summon_king/alliance?msg=铜币不足", status_code=302)
        profile.copper_coin -= amount
        contribution = amount // 100
    else:
        if profile.yuanbao < amount:
            return RedirectResponse(url="/summon_king/alliance?msg=元宝不足", status_code=302)
        profile.yuanbao -= amount
        contribution = amount * 10

    alliance = db.query(SummonAlliance).filter(SummonAlliance.id == profile.alliance_id).first()
    if alliance:
        alliance.funds += amount
        alliance.contribution_total += contribution

    membership = db.query(SummonAllianceMember).filter(
        SummonAllianceMember.alliance_id == profile.alliance_id,
        SummonAllianceMember.user_id == ctx["user"].id
    ).first()
    if membership:
        membership.contribution += contribution
        membership.total_donation += amount

    log = SummonAllianceDonationLog(
        alliance_id=profile.alliance_id,
        user_id=ctx["user"].id,
        user_nickname=profile.summoner_name,
        donation_type=donate_type,
        amount=amount,
        contribution_reward=contribution,
    )
    db.add(log)
    db.commit()
    return RedirectResponse(url=f"/summon_king/alliance?msg=捐献成功，贡献+{contribution}", status_code=302)


# ============================================================
# 路由：背包系统
# ============================================================

@router.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])

    # 从 InventoryItem 获取 summon_king 模块的道具
    items = db.query(InventoryItem).filter(
        InventoryItem.user_id == ctx["user"].id,
        InventoryItem.module_key == "summon_king"
    ).all()

    # 分类整理
    balls = []
    potions = []
    materials = []
    other_items = []
    for item in items:
        if item.item_type == "ball":
            balls.append(item)
        elif item.item_type == "potion":
            potions.append(item)
        elif item.item_type == "material":
            materials.append(item)
        else:
            other_items.append(item)

    ctx.update({
        "profile": profile,
        "balls": balls,
        "potions": potions,
        "materials": materials,
        "other_items": other_items,
    })
    return templates.TemplateResponse("summon_king/inventory.html", ctx)


@router.post("/buy_balls")
async def buy_balls(request: Request, ball_type: str = Form("normal"), count: int = Form(1), db: Session = Depends(get_db)):
    """购买捕捉球"""
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])

    prices = {"normal": 50, "strong": 200, "super": 1000}
    ball_names = {"normal": "普球", "strong": "强力球", "super": "超级球"}
    price = prices.get(ball_type, 50) * count

    if profile.copper_coin < price:
        return RedirectResponse(url="/summon_king/inventory?msg=铜币不足", status_code=302)

    profile.copper_coin -= price
    field = f"catch_ball_{ball_type}"
    setattr(profile, field, getattr(profile, field, 0) + count)
    db.commit()
    return RedirectResponse(url=f"/summon_king/inventory?msg=购买了{count}个{ball_names.get(ball_type, '捕捉球')}", status_code=302)


@router.post("/heal")
async def heal_all_beasts(request: Request, db: Session = Depends(get_db)):
    """治疗所有幻兽（消耗铜币）"""
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)

    profile = get_or_create_profile(db, ctx["user"])
    beasts = db.query(SummonUserBeast).filter(SummonUserBeast.profile_id == profile.id).all()

    total_cost = 0
    for ub in beasts:
        bdef = db.query(SummonBeast).filter(SummonBeast.id == ub.beast_id).first()
        stats = calculate_beast_stats(ub, bdef)
        missing_hp = stats["max_hp"] - ub.hp
        if missing_hp > 0:
            cost = max(10, missing_hp // 2)
            total_cost += cost

    if total_cost == 0:
        return RedirectResponse(url="/summon_king/inventory?msg=所有幻兽已满血", status_code=302)
    if profile.copper_coin < total_cost:
        return RedirectResponse(url=f"/summon_king/inventory?msg=治疗需要{total_cost}铜币，余额不足", status_code=302)

    profile.copper_coin -= total_cost
    for ub in beasts:
        bdef = db.query(SummonBeast).filter(SummonBeast.id == ub.beast_id).first()
        stats = calculate_beast_stats(ub, bdef)
        ub.hp = stats["max_hp"]
    db.commit()
    return RedirectResponse(url=f"/summon_king/inventory?msg=治疗完成，消耗{total_cost}铜币", status_code=302)
