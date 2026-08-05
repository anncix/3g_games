"""小轩西游模块（重构版，移植自 anncix/xiyou 仓库）

- 认证：接入 3g_games JWT（get_current_user），一个用户可多角色
- 路由前缀 /games/xyou
- 数据：utils/xyou_data.py（静态常量）；逻辑：utils/xyou.py（服务层）
- 模板：templates/xyou/*.html（继承 base_wap.html）
"""
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from models.database import get_db
from models.models import (
    User, XyouCharacter, XyouInventory, XyouEquipment, XyouSkill,
    XyouQuest, XyouGuild, XyouGuildMember, XyouWorldMsg, XyouRanking,
)
from utils.auth import get_current_user
from utils import xyou_data as gd
from utils import xyou as svc

router = APIRouter(prefix="/games/xyou", tags=["xyou"])
templates = Jinja2Templates(directory="templates")

# 装备槽位显示文案
SLOT_NAMES = {"weapon": "武器", "armor": "盔甲", "helmet": "头盔", "boots": "靴子"}


def _login_redirect():
    return RedirectResponse(url="/auth/login", status_code=302)


def _get_character(db: Session, user: User):
    return db.query(XyouCharacter).filter(XyouCharacter.user_id == user.id).first()


def _char_context(db: Session, char: XyouCharacter) -> dict:
    """构建角色上下文（地图/属性/装备）"""
    stats = svc.get_char_stats(db, char)
    eqs = db.query(XyouEquipment).filter_by(character_id=char.id).all()
    eq_map = {e.slot: e for e in eqs}
    return {
        "char": char,
        "stats": stats,
        "equipment": eq_map,
        "map": gd.MAPS[char.map_id],
        "slot_names": SLOT_NAMES,
    }


# ============ 首页 / 创建角色 ============
@router.get("", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    ctx = {"request": request, "user": user}
    if not char:
        ctx["need_create"] = True
        return templates.TemplateResponse("xyou/create.html", ctx)
    ctx.update(_char_context(db, char))
    ctx["maps"] = gd.MAPS
    ctx["monsters"] = [m for m in gd.MONSTERS.values() if m["map_id"] == char.map_id]
    ctx["npcs"] = [n for n in gd.NPCS.values() if n["map_id"] == char.map_id]
    ctx["skills"] = db.query(XyouSkill).filter_by(character_id=char.id).all()
    return templates.TemplateResponse("xyou/home.html", ctx)


@router.get("/create", response_class=HTMLResponse)
def create_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if char:
        return RedirectResponse(url="/games/xyou", status_code=302)
    return templates.TemplateResponse("xyou/create.html", {
        "request": request, "user": user, "races": gd.RACES, "classes": gd.CLASSES})


@router.post("/create", response_class=HTMLResponse)
def do_create(request: Request, db: Session = Depends(get_db),
              name: str = Form(...), race: str = Form("人"),
              class_name: str = Form("散仙"), sex: int = Form(1)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if char:
        return RedirectResponse(url="/games/xyou", status_code=302)
    char, err = svc.create_character(db, user.id, name.strip(), race, class_name, sex)
    if err:
        return templates.TemplateResponse("xyou/create.html", {
            "request": request, "user": user, "races": gd.RACES,
            "classes": gd.CLASSES, "error": err})
    return RedirectResponse(url="/games/xyou", status_code=302)


# ============ 地图 ============
@router.get("/map", response_class=HTMLResponse)
def map_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if not char:
        return RedirectResponse(url="/games/xyou/create", status_code=302)
    cur = gd.MAPS[char.map_id]
    ctx = _char_context(db, char)
    ctx.update({"request": request, "user": user, "current": cur,
                "maps": gd.MAPS})
    return templates.TemplateResponse("xyou/map.html", ctx)


@router.post("/move", response_class=HTMLResponse)
def move(request: Request, db: Session = Depends(get_db),
         target: int = Form(...)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if not char:
        return RedirectResponse(url="/games/xyou/create", status_code=302)
    svc.move_map(db, char, target)
    return RedirectResponse(url="/games/xyou", status_code=302)


# ============ 角色 ============
@router.get("/character", response_class=HTMLResponse)
def character_panel(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if not char:
        return RedirectResponse(url="/games/xyou/create", status_code=302)
    ctx = _char_context(db, char)
    ctx.update({"request": request, "user": user,
                "skills": db.query(XyouSkill).filter_by(character_id=char.id).all(),
                "quests": db.query(XyouQuest).filter_by(character_id=char.id).all()})
    return templates.TemplateResponse("xyou/character.html", ctx)


# ============ 背包 / 装备 ============
@router.get("/bag", response_class=HTMLResponse)
def bag(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if not char:
        return RedirectResponse(url="/games/xyou/create", status_code=302)
    items = db.query(XyouInventory).filter_by(character_id=char.id).all()
    for it in items:
        tmpl = gd.ITEMS.get(it.item_id)
        it.slot = tmpl["slot"] if tmpl else ""
    ctx = _char_context(db, char)
    ctx.update({"request": request, "user": user, "items": items})
    return templates.TemplateResponse("xyou/bag.html", ctx)


@router.post("/use", response_class=HTMLResponse)
def use_item(request: Request, db: Session = Depends(get_db),
             inv_id: int = Form(...)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if not char:
        return RedirectResponse(url="/games/xyou/create", status_code=302)
    _, err = svc.use_item(db, char, inv_id)
    url = "/games/xyou/bag"
    if err:
        url += f"?msg={err}"
    return RedirectResponse(url=url, status_code=302)


@router.post("/equip", response_class=HTMLResponse)
def equip_item(request: Request, db: Session = Depends(get_db),
               inv_id: int = Form(...)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if not char:
        return RedirectResponse(url="/games/xyou/create", status_code=302)
    svc.equip_item(db, char, inv_id)
    return RedirectResponse(url="/games/xyou/bag", status_code=302)


@router.post("/unequip", response_class=HTMLResponse)
def unequip_item(request: Request, db: Session = Depends(get_db),
                 eq_id: int = Form(...)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if not char:
        return RedirectResponse(url="/games/xyou/create", status_code=302)
    svc.unequip_item(db, char, eq_id)
    return RedirectResponse(url="/games/xyou/character", status_code=302)


# ============ 商店 ============
@router.get("/shop/{npc_id}", response_class=HTMLResponse)
def shop(request: Request, npc_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if not char:
        return RedirectResponse(url="/games/xyou/create", status_code=302)
    npc = gd.NPCS.get(npc_id)
    if not npc or npc["role"] != "商店":
        return RedirectResponse(url="/games/xyou", status_code=302)
    items = [gd.ITEMS[i] for i in npc["shop"]]
    ctx = _char_context(db, char)
    ctx.update({"request": request, "user": user, "npc": npc, "shop_items": items})
    return templates.TemplateResponse("xyou/shop.html", ctx)


@router.post("/buy", response_class=HTMLResponse)
def buy_item(request: Request, db: Session = Depends(get_db),
             npc_id: int = Form(...), item_id: int = Form(...),
             count: int = Form(1)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if not char:
        return RedirectResponse(url="/games/xyou/create", status_code=302)
    _, err = svc.buy_item(db, char, npc_id, item_id, count)
    url = f"/games/xyou/shop/{npc_id}"
    if err:
        url += f"?msg={err}"
    return RedirectResponse(url=url, status_code=302)


@router.post("/sell", response_class=HTMLResponse)
def sell_item(request: Request, db: Session = Depends(get_db),
              inv_id: int = Form(...)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if not char:
        return RedirectResponse(url="/games/xyou/create", status_code=302)
    svc.sell_item(db, char, inv_id)
    return RedirectResponse(url="/games/xyou/bag", status_code=302)


# ============ 技能 ============
@router.get("/skill/{npc_id}", response_class=HTMLResponse)
def skill_page(request: Request, npc_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if not char:
        return RedirectResponse(url="/games/xyou/create", status_code=302)
    npc = gd.NPCS.get(npc_id)
    if not npc or npc["role"] != "传授":
        return RedirectResponse(url="/games/xyou", status_code=302)
    have = {s.skill_id for s in db.query(XyouSkill).filter_by(
        character_id=char.id).all()}
    skills = [v for k, v in gd.SKILLS.items() if k not in have]
    ctx = _char_context(db, char)
    ctx.update({"request": request, "user": user, "npc": npc, "skills": skills})
    return templates.TemplateResponse("xyou/skill.html", ctx)


@router.post("/learn", response_class=HTMLResponse)
def learn_skill(request: Request, db: Session = Depends(get_db),
                npc_id: int = Form(...), skill_id: int = Form(...)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if not char:
        return RedirectResponse(url="/games/xyou/create", status_code=302)
    _, err = svc.learn_skill(db, char, npc_id, skill_id)
    url = f"/games/xyou/skill/{npc_id}"
    if err:
        url += f"?msg={err}"
    return RedirectResponse(url=url, status_code=302)


# ============ 战斗 ============
@router.post("/fight", response_class=HTMLResponse)
def fight(request: Request, db: Session = Depends(get_db),
          monster_id: int = Form(...)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if not char:
        return RedirectResponse(url="/games/xyou/create", status_code=302)
    result, err = svc.fight_monster(db, char, monster_id)
    return templates.TemplateResponse("xyou/result.html", {
        "request": request, "user": user, "char": char,
        "result": result, "err": err, "back_href": "/games/xyou", "back_text": "返回地图"})


@router.post("/skill_fight", response_class=HTMLResponse)
def skill_fight(request: Request, db: Session = Depends(get_db),
                monster_id: int = Form(...), skill_id: int = Form(...)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if not char:
        return RedirectResponse(url="/games/xyou/create", status_code=302)
    result, err = svc.use_skill_in_map(db, char, monster_id, skill_id)
    return templates.TemplateResponse("xyou/result.html", {
        "request": request, "user": user, "char": char,
        "result": result, "err": err, "back_href": "/games/xyou", "back_text": "返回地图"})


# ============ 任务 ============
@router.get("/quest", response_class=HTMLResponse)
def quest_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if not char:
        return RedirectResponse(url="/games/xyou/create", status_code=302)
    myq = db.query(XyouQuest).filter_by(character_id=char.id).all()
    my_map = {q.quest_id: q for q in myq}
    available = []
    for qid, qd in gd.QUESTS.items():
        if qd.get("map_id") != char.map_id:
            continue
        status = my_map.get(qid)
        if not status:
            available.append({**qd, "id": qid, "status_text": "可接取"})
        elif status.status == "进行中":
            available.append({**qd, "id": qid, "status_text": "进行中",
                              "progress": status.progress})
        elif status.status == "可完成":
            available.append({**qd, "id": qid, "status_text": "可完成",
                              "progress": status.progress})
    done = [q for q in my_map.values() if q.status == "已完成"]
    ctx = _char_context(db, char)
    ctx.update({"request": request, "user": user, "available": available, "done": done})
    return templates.TemplateResponse("xyou/quest.html", ctx)


@router.post("/quest/accept", response_class=HTMLResponse)
def accept_quest(request: Request, db: Session = Depends(get_db),
                 quest_id: int = Form(...)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if not char:
        return RedirectResponse(url="/games/xyou/create", status_code=302)
    svc.accept_quest(db, char, quest_id)
    return RedirectResponse(url="/games/xyou/quest", status_code=302)


@router.post("/quest/complete", response_class=HTMLResponse)
def complete_quest(request: Request, db: Session = Depends(get_db),
                   quest_id: int = Form(...)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if not char:
        return RedirectResponse(url="/games/xyou/create", status_code=302)
    svc.complete_quest(db, char, quest_id)
    return RedirectResponse(url="/games/xyou/quest", status_code=302)


# ============ 帮派 ============
@router.get("/guild", response_class=HTMLResponse)
def guild_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if not char:
        return RedirectResponse(url="/games/xyou/create", status_code=302)
    guilds = db.query(XyouGuild).order_by(XyouGuild.level.desc()).all()
    my_guild = None
    members = []
    if char.guild_id:
        my_guild = db.query(XyouGuild).filter_by(id=char.guild_id).first()
        if my_guild:
            members = db.query(XyouGuildMember).filter_by(guild_id=my_guild.id).all()
    ctx = _char_context(db, char)
    ctx.update({"request": request, "user": user, "guilds": guilds,
                "my_guild": my_guild, "members": members})
    return templates.TemplateResponse("xyou/guild.html", ctx)


@router.post("/guild/create", response_class=HTMLResponse)
def create_guild(request: Request, db: Session = Depends(get_db),
                 name: str = Form(...), description: str = Form("")):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if not char:
        return RedirectResponse(url="/games/xyou/create", status_code=302)
    _, err = svc.create_guild(db, char, name.strip(), description.strip())
    url = "/games/xyou/guild" + (f"?msg={err}" if err else "")
    return RedirectResponse(url=url, status_code=302)


@router.post("/guild/join", response_class=HTMLResponse)
def join_guild(request: Request, db: Session = Depends(get_db),
               guild_id: int = Form(...)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if not char:
        return RedirectResponse(url="/games/xyou/create", status_code=302)
    _, err = svc.join_guild(db, char, guild_id)
    url = "/games/xyou/guild" + (f"?msg={err}" if err else "")
    return RedirectResponse(url=url, status_code=302)


@router.post("/guild/leave", response_class=HTMLResponse)
def leave_guild(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if not char:
        return RedirectResponse(url="/games/xyou/create", status_code=302)
    _, err = svc.leave_guild(db, char)
    url = "/games/xyou/guild" + (f"?msg={err}" if err else "")
    return RedirectResponse(url=url, status_code=302)


# ============ 聊天 ============
@router.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if not char:
        return RedirectResponse(url="/games/xyou/create", status_code=302)
    messages = svc.get_world_messages(db, limit=30)
    messages.reverse()
    ctx = _char_context(db, char)
    ctx.update({"request": request, "user": user, "messages": messages})
    return templates.TemplateResponse("xyou/chat.html", ctx)


@router.post("/chat/send", response_class=HTMLResponse)
def send_chat(request: Request, db: Session = Depends(get_db),
              content: str = Form(...)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if not char:
        return RedirectResponse(url="/games/xyou/create", status_code=302)
    _, err = svc.send_message(db, char, content)
    url = "/games/xyou/chat" + (f"?msg={err}" if err else "")
    return RedirectResponse(url=url, status_code=302)


# ============ 排行榜 ============
@router.get("/ranking", response_class=HTMLResponse)
def ranking_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return _login_redirect()
    char = _get_character(db, user)
    if not char:
        return RedirectResponse(url="/games/xyou/create", status_code=302)
    svc.update_ranking(db)
    rankings = db.query(XyouRanking).order_by(XyouRanking.level.desc()).limit(50).all()
    ctx = _char_context(db, char)
    ctx.update({"request": request, "user": user, "rankings": rankings})
    return templates.TemplateResponse("xyou/ranking.html", ctx)