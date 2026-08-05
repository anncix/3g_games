"""小轩西游 核心游戏逻辑（移植自 anncix/xiyou 仓库 app/services.py）

与 3g_games 框架对齐：
- 角色使用新模型 XyouCharacter（一个用户可多角色）
- 银两/元宝直接存在角色上，未接入钱包（保持 xiyou 单机口径）
- 所有会话/权限由路由层注入角色，本层只处理纯业务
"""
from __future__ import annotations

import random

from sqlalchemy.orm import Session

from models.models import (
    XyouCharacter, XyouInventory, XyouEquipment, XyouSkill,
    XyouQuest, XyouGuild, XyouGuildMember, XyouWorldMsg, XyouRanking,
)
from utils import xyou_data as gd

# 输入校验常量
CHAR_NAME_MAX = 12
MESSAGE_MAX = 200

# 各阶位初始属性 (hp, mp, atk, dfs)
_RACE_BASE = {"人": (100, 50, 10, 5), "仙": (80, 80, 8, 4), "妖": (120, 40, 12, 6)}


def _validate_char_name(name: str):
    """校验角色名，返回错误信息或 None"""
    if not name.strip():
        return "角色名不能为空"
    if len(name.strip()) > CHAR_NAME_MAX:
        return f"角色名不能超过 {CHAR_NAME_MAX} 个字符"
    return None


# ============ 角色 ============
def create_character(db: Session, user_id: int, name: str, race: str,
                     class_name: str, sex: int):
    err = _validate_char_name(name)
    if err:
        return None, err
    if db.query(XyouCharacter).filter_by(name=name).first():
        return None, "角色名已存在"
    hp, mp, atk, dfs = _RACE_BASE.get(race, (100, 50, 10, 5))
    char = XyouCharacter(
        user_id=user_id, name=name, race=race, class_name=class_name,
        sex=sex, hp=hp, hp_max=hp, mp=mp, mp_max=mp,
        attack=atk, defense=dfs, speed=5, map_id=1,
    )
    db.add(char)
    db.flush()
    # 初始赠送初级装备
    _grant_starter_items(db, char.id)
    db.commit()
    db.refresh(char)
    return char, None


def _grant_starter_items(db: Session, char_id: int):
    db.add(XyouInventory(character_id=char_id, item_id=5, name="铁剑",
                         item_type="装备", count=1, attack=8, level_req=1))
    db.add(XyouInventory(character_id=char_id, item_id=8, name="布衣",
                         item_type="装备", count=1, defense=5, hp_bonus=10, level_req=1))
    db.add(XyouInventory(character_id=char_id, item_id=1, name="金疮药",
                         item_type="药品", count=5, hp_bonus=50, level_req=1))


def get_char_equipment_bonus(db: Session, char_id: int):
    """计算角色装备加成的属性总和"""
    eqs = db.query(XyouEquipment).filter_by(character_id=char_id).all()
    return (sum(e.attack for e in eqs),
            sum(e.defense for e in eqs),
            sum(e.hp_bonus for e in eqs),
            sum(e.mp_bonus for e in eqs))


def get_char_stats(db: Session, char: XyouCharacter):
    """角色总属性（含装备）"""
    eatk, edfs, ehp, emp = get_char_equipment_bonus(db, char.id)
    return {
        "total_attack": char.attack + eatk,
        "total_defense": char.defense + edfs,
        "total_hp_max": char.hp_max + ehp,
        "total_mp_max": char.mp_max + emp,
        "equip_atk": eatk, "equip_def": edfs,
    }


def level_up_exp(level: int) -> int:
    return level * 100 + 50


def add_exp(db: Session, char: XyouCharacter, amount: int):
    """增加经验并处理升级，返回升级次数"""
    char.exp += amount
    leveled = 0
    while char.exp >= level_up_exp(char.level):
        char.exp -= level_up_exp(char.level)
        char.level += 1
        leveled += 1
        _apply_level_up(char)
    db.commit()
    return leveled


def _apply_level_up(char: XyouCharacter):
    char.hp_max += 20
    char.mp_max += 10
    char.attack += 3
    char.defense += 2
    char.hp = char.hp_max
    char.mp = char.mp_max


def add_money(db: Session, char: XyouCharacter, amount: int):
    char.money += amount
    if char.money < 0:
        char.money = 0
    db.commit()


# ============ 背包 ============
def _add_item(db: Session, char_id: int, item_id: int, count: int = 1):
    it = gd.ITEMS[item_id]
    inv = db.query(XyouInventory).filter_by(
        character_id=char_id, item_id=item_id).first()
    if inv:
        inv.count += count
    else:
        inv = XyouInventory(
            character_id=char_id, item_id=item_id, name=it["name"],
            item_type=it["type"], count=count, attack=it["attack"],
            defense=it["defense"], hp_bonus=it["hp"], mp_bonus=it["mp"],
            level_req=it["level_req"], description=it["desc"])
        db.add(inv)
    db.commit()


def _add_item_by_name(db: Session, char_id: int, name: str, count: int = 1):
    """按名称添加物品到背包（用于装备卸下复位）"""
    inv = db.query(XyouInventory).filter_by(character_id=char_id, name=name).first()
    if inv:
        inv.count += count
        db.commit()
        return
    for item_id, it in gd.ITEMS.items():
        if it["name"] == name:
            _add_item(db, char_id, item_id, count)
            return
    db.commit()


def use_item(db: Session, char: XyouCharacter, inv_id: int):
    inv = db.query(XyouInventory).filter_by(id=inv_id, character_id=char.id).first()
    if not inv:
        return None, "没有该物品"
    if inv.item_type != "药品":
        return None, "该物品无法使用"
    stats = get_char_stats(db, char)
    heal, mp = inv.hp_bonus, inv.mp_bonus
    if heal == 0 and mp == 0:
        return None, "该药品没有恢复效果"
    if char.hp >= stats["total_hp_max"] and char.mp >= stats["total_mp_max"]:
        return None, "气血与法力已满，无需使用"
    char.hp = min(stats["total_hp_max"], char.hp + heal)
    if mp > 0:
        char.mp = min(stats["total_mp_max"], char.mp + mp)
    inv.count -= 1
    if inv.count <= 0:
        db.delete(inv)
    db.commit()
    parts = []
    if heal > 0:
        parts.append(f"气血 +{heal}")
    if mp > 0:
        parts.append(f"法力 +{mp}")
    return {"msg": f"使用了【{inv.name}】，{'、'.join(parts)}"}, None


# ============ 战斗 ============
def _battle_victory(db: Session, char: XyouCharacter, m: dict, exp: int, money: int):
    """战斗胜利结算：经验、银两、掉落、任务进度。返回 (升级次数, 掉落物品ID)"""
    leveled = add_exp(db, char, exp)
    add_money(db, char, money)
    drop = None
    for item_id, prob in m["drops"].items():
        if random.randint(1, 100) <= prob:
            drop = item_id
            break
    if drop:
        _add_item(db, char.id, drop)
    _update_quest_kill(db, char.id, m["id"])
    return leveled, drop


def _battle_defeat(db: Session, char: XyouCharacter):
    """战斗失败结算：损失经验并半血，返回损失的经验"""
    lost = int(char.exp * 0.1)
    char.exp = max(0, char.exp - lost)
    char.hp = max(1, char.hp // 2)
    db.commit()
    return lost


def _battle_log_drop(drop: int) -> str:
    return f"掉落物品：【{gd.ITEMS[drop]['name']}】"


def fight_monster(db: Session, char: XyouCharacter, monster_id: int):
    """与怪物战斗，返回战斗结果"""
    m = gd.MONSTERS.get(monster_id)
    if not m:
        return None, "怪物不存在"
    stats = get_char_stats(db, char)
    dmg = max(1, stats["total_attack"] - m["defense"])
    player_hits = max(1, int(m["hp"] / dmg))
    m_dmg = max(1, m["attack"] - stats["total_defense"])
    monster_hits = max(1, int(char.hp / m_dmg))
    win = player_hits <= monster_hits
    log_lines = [f"你遇到了【{m['name']}】(Lv{m['level']})",
                 f"你对其造成 {dmg} 点伤害，需要 {player_hits} 回合击败它"]
    if win:
        exp = m["exp"] + random.randint(0, m["exp"] // 2)
        money = m["money"] + random.randint(0, m["money"])
        leveled, drop = _battle_victory(db, char, m, exp, money)
        log_lines.append(f"你击败了【{m['name']}】！获得 {exp} 经验、{money} 银两")
        if leveled:
            log_lines.append(f"🎉 升级了！当前等级 Lv{char.level}")
        if drop:
            log_lines.append(_battle_log_drop(drop))
        return {"win": True, "log": log_lines, "exp": exp, "money": money,
                "drop": drop, "leveled": leveled}, None
    lost = _battle_defeat(db, char)
    log_lines.append(f"你被【{m['name']}】击败了！损失 {lost} 经验")
    return {"win": False, "log": log_lines, "lost": lost}, None


def use_skill_in_map(db: Session, char: XyouCharacter, monster_id: int, skill_id: int):
    """使用技能打怪（提升伤害）"""
    sk = gd.SKILLS.get(skill_id)
    if not sk:
        return None, "技能不存在"
    have = db.query(XyouSkill).filter_by(
        character_id=char.id, skill_id=skill_id).first()
    if not have:
        return None, "未学会该技能"
    m = gd.MONSTERS.get(monster_id)
    if not m:
        return None, "怪物不存在"
    if char.mp < sk["mp_cost"]:
        return None, "法力不足"
    char.mp -= sk["mp_cost"]
    db.commit()
    stats = get_char_stats(db, char)
    dmg = max(1, int(stats["total_attack"] * sk["damage_mult"]) - m["defense"])
    player_hits = max(1, int(m["hp"] / dmg))
    m_dmg = max(1, m["attack"] - stats["total_defense"])
    monster_hits = max(1, int(char.hp / m_dmg))
    win = player_hits <= monster_hits
    log = [f"你对【{m['name']}】施展了【{sk['name']}】！",
           f"造成 {int(dmg)} 点伤害，需要 {player_hits} 回合击败它"]
    if win:
        exp = int(m["exp"] * 1.2)
        money = m["money"] + random.randint(0, m["money"])
        leveled, drop = _battle_victory(db, char, m, exp, money)
        log.append(f"你击败了【{m['name']}】！获得 {exp} 经验、{money} 银两")
        if leveled:
            log.append(f"🎉 升级了！当前等级 Lv{char.level}")
        if drop:
            log.append(_battle_log_drop(drop))
        return {"win": True, "log": log, "exp": exp, "money": money,
                "drop": drop, "leveled": leveled}, None
    lost = _battle_defeat(db, char)
    log.append(f"你被【{m['name']}】击败了！损失 {lost} 经验")
    return {"win": False, "log": log, "lost": lost}, None


# ============ 任务 ============
def _update_quest_kill(db: Session, char_id: int, monster_id: int):
    quests = db.query(XyouQuest).filter_by(character_id=char_id, status="进行中").all()
    for q in quests:
        qd = gd.QUESTS.get(q.quest_id)
        if qd and qd["type"] == "杀怪" and qd["target"] == monster_id:
            q.progress += 1
            if q.progress >= qd["count"]:
                q.status = "可完成"
    db.commit()


def accept_quest(db: Session, char: XyouCharacter, quest_id: int):
    qd = gd.QUESTS.get(quest_id)
    if not qd:
        return None, "任务不存在"
    if qd.get("map_id") != char.map_id:
        return None, "请前往【{}】再接此任务".format(gd.MAPS[qd["map_id"]]["name"])
    exist = db.query(XyouQuest).filter_by(
        character_id=char.id, quest_id=quest_id).first()
    if exist and exist.status in ("进行中", "可完成"):
        return None, "任务已接取"
    if exist and exist.status == "已完成":
        return None, "任务已完成"
    q = XyouQuest(character_id=char.id, quest_id=quest_id, name=qd["name"],
                  status="进行中", progress=0, target=qd["count"])
    db.add(q)
    db.commit()
    return {"msg": f"接受任务【{qd['name']}】"}, None


def complete_quest(db: Session, char: XyouCharacter, quest_id: int):
    q = db.query(XyouQuest).filter_by(
        character_id=char.id, quest_id=quest_id, status="可完成").first()
    if not q:
        return None, "任务未完成或不存在"
    qd = gd.QUESTS[quest_id]
    q.status = "已完成"
    leveled = add_exp(db, char, qd["reward_exp"])
    add_money(db, char, qd["reward_money"])
    msg = f"完成任务【{qd['name']}】！获得 {qd['reward_exp']} 经验、{qd['reward_money']} 银两"
    if qd["reward_item"]:
        _add_item(db, char.id, qd["reward_item"])
        msg += f"、物品【{gd.ITEMS[qd['reward_item']]['name']}】"
    if leveled:
        msg += f"，升级至 Lv{char.level}！"
    db.commit()
    return {"msg": msg, "leveled": leveled}, None


# ============ 装备 ============
def equip_item(db: Session, char: XyouCharacter, inv_id: int):
    inv = db.query(XyouInventory).filter_by(id=inv_id, character_id=char.id).first()
    if not inv or inv.item_type != "装备":
        return None, "没有该装备"
    if char.level < inv.level_req:
        return None, f"等级不足，需要 Lv{inv.level_req}"
    tmpl = gd.ITEMS.get(inv.item_id)
    slot = tmpl["slot"] if tmpl and tmpl.get("slot") else "armor"
    old = db.query(XyouEquipment).filter_by(character_id=char.id, slot=slot).first()
    if old:
        _add_item_by_name(db, char.id, old.name, 1)
        db.delete(old)
    eq = XyouEquipment(character_id=char.id, slot=slot, name=inv.name,
                       attack=inv.attack, defense=inv.defense,
                       hp_bonus=inv.hp_bonus, mp_bonus=inv.mp_bonus)
    db.add(eq)
    name = inv.name
    inv.count -= 1
    if inv.count <= 0:
        db.delete(inv)
    db.commit()
    return {"msg": f"装备了【{name}】"}, None


def unequip_item(db: Session, char: XyouCharacter, eq_id: int):
    eq = db.query(XyouEquipment).filter_by(id=eq_id, character_id=char.id).first()
    if not eq:
        return None, "没有该装备"
    _add_item_by_name(db, char.id, eq.name, 1)
    db.delete(eq)
    db.commit()
    return {"msg": f"卸下了【{eq.name}】"}, None


# ============ 商店 ============
def buy_item(db: Session, char: XyouCharacter, npc_id: int, item_id: int, count: int = 1):
    if count < 1:
        return None, "购买数量至少为 1"
    npc = gd.NPCS.get(npc_id)
    if not npc or npc["role"] != "商店" or item_id not in npc["shop"]:
        return None, "该NPC不售卖此物品"
    it = gd.ITEMS[item_id]
    cost = it["price"] * count
    if char.money < cost:
        return None, "银两不足"
    char.money -= cost
    _add_item(db, char.id, item_id, count)
    db.commit()
    return {"msg": f"购买了 {count} 个【{it['name']}】，花费 {cost} 银两"}, None


def sell_item(db: Session, char: XyouCharacter, inv_id: int, count: int = 1):
    inv = db.query(XyouInventory).filter_by(id=inv_id, character_id=char.id).first()
    if not inv or inv.count < count:
        return None, "物品不足"
    it = gd.ITEMS.get(inv.item_id)
    price = (it["price"] // 2) if it else 1
    total = price * count
    inv.count -= count
    if inv.count <= 0:
        db.delete(inv)
    char.money += total
    db.commit()
    return {"msg": f"出售了 {count} 个【{inv.name}】，获得 {total} 银两"}, None


# ============ 技能 ============
def learn_skill(db: Session, char: XyouCharacter, npc_id: int, skill_id: int):
    npc = gd.NPCS.get(npc_id)
    if not npc or npc["role"] != "传授":
        return None, "该NPC不能传授技能"
    sk = gd.SKILLS.get(skill_id)
    if not sk:
        return None, "技能不存在"
    exist = db.query(XyouSkill).filter_by(
        character_id=char.id, skill_id=skill_id).first()
    if exist:
        return None, "已学会该技能"
    db.add(XyouSkill(character_id=char.id, skill_id=skill_id, name=sk["name"],
                     description=sk["desc"]))
    db.commit()
    return {"msg": f"学会了技能【{sk['name']}】"}, None


# ============ 移动 ============
def move_map(db: Session, char: XyouCharacter, target_map: int):
    cur = gd.MAPS.get(char.map_id)
    if not cur or target_map not in cur["links"]:
        return None, "无法到达该地图"
    if target_map not in gd.MAPS:
        return None, "地图不存在"
    char.map_id = target_map
    stats = get_char_stats(db, char)
    char.hp = min(stats["total_hp_max"], char.hp + int(stats["total_hp_max"] * 0.3))
    char.mp = min(stats["total_mp_max"], char.mp + int(stats["total_mp_max"] * 0.3))
    db.commit()
    return {"msg": f"你来到了【{gd.MAPS[target_map]['name']}】"}, None


# ============ 帮派 ============
def create_guild(db: Session, char: XyouCharacter, name: str, desc: str = ""):
    if char.money < 1000:
        return None, "创建帮派需要1000银两"
    if db.query(XyouGuild).filter_by(name=name).first():
        return None, "帮派名已存在"
    if char.guild_id != 0:
        return None, "你已有帮派"
    char.money -= 1000
    g = XyouGuild(name=name, leader_id=char.id, leader_name=char.name, description=desc)
    db.add(g)
    db.commit()
    db.refresh(g)
    char.guild_id = g.id
    db.add(XyouGuildMember(guild_id=g.id, character_id=char.id,
                           character_name=char.name, rank="帮主"))
    db.commit()
    return {"msg": f"创建帮派【{name}】成功"}, None


def join_guild(db: Session, char: XyouCharacter, guild_id: int):
    if char.guild_id != 0:
        return None, "你已有帮派"
    g = db.query(XyouGuild).filter_by(id=guild_id).first()
    if not g:
        return None, "帮派不存在"
    char.guild_id = g.id
    db.add(XyouGuildMember(guild_id=g.id, character_id=char.id,
                           character_name=char.name, rank="成员"))
    db.commit()
    return {"msg": f"加入了帮派【{g.name}】"}, None


def leave_guild(db: Session, char: XyouCharacter):
    if char.guild_id == 0:
        return None, "你不在帮派中"
    g = db.query(XyouGuild).filter_by(id=char.guild_id).first()
    if g and g.leader_id == char.id:
        db.query(XyouGuildMember).filter_by(guild_id=g.id).delete()
        db.delete(g)
        char.guild_id = 0
        db.commit()
        return {"msg": "你解散了帮派"}, None
    db.query(XyouGuildMember).filter_by(character_id=char.id).delete()
    char.guild_id = 0
    db.commit()
    return {"msg": "你退出了帮派"}, None


# ============ 聊天 ============
def send_message(db: Session, char: XyouCharacter, content: str):
    if not content.strip():
        return None, "消息不能为空"
    if len(content.strip()) > MESSAGE_MAX:
        return None, f"消息不能超过 {MESSAGE_MAX} 个字符"
    m = XyouWorldMsg(character_name=char.name, content=content.strip())
    db.add(m)
    db.commit()
    return {"msg": "发送成功"}, None


def get_world_messages(db: Session, limit: int = 20):
    return db.query(XyouWorldMsg).order_by(XyouWorldMsg.id.desc()).limit(limit).all()


# ============ 排行榜 ============
def update_ranking(db: Session):
    """更新排行榜（事务内先清空再写入）"""
    chars = db.query(XyouCharacter).order_by(
        XyouCharacter.level.desc(), XyouCharacter.exp.desc()).limit(100).all()
    db.query(XyouRanking).delete()
    for c in chars:
        db.add(XyouRanking(character_id=c.id, character_name=c.name,
                           level=c.level, money=c.money))
    db.commit()