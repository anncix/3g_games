"""JSON API 规范实现 (/api/*)

统一规范：
- 认证：Bearer Token（登录返回），放入 Authorization 头；模块事件上报可带 X-Module-Key
- 响应格式：{ "code": 0, "msg": "ok", "data": {...} }；code!=0 表示错误
- 模块事件上报：POST /api/events/emit —— 模块只能通过此接口上报事件（5.5）
- 所有写操作幂等校验，返回结果对象
"""
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models, config
from ..database import get_db
from ..deps import hash_password, verify_password, create_session
from ..platform import friends as fsvc, goods, icons, events, locks, ranking, log

router = APIRouter(prefix="/api", tags=["API"])


def ok(data: Any = None, msg: str = "ok"):
    return {"code": 0, "msg": msg, "data": data}


def err(msg: str, code: int = 1):
    return {"code": code, "msg": msg, "data": None}


async def _auth(request: Request, db: AsyncSession) -> models.User:
    auth = request.headers.get("authorization", "")
    token = ""
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    elif auth:
        token = auth.strip()
    if not token:
        token = request.cookies.get(config.SESSION_COOKIE, "")
    if not token:
        raise HTTPException(401, "未登录")
    sess = await db.get(models.Session, token)
    if not sess or sess.expires_at < datetime.utcnow():
        raise HTTPException(401, "登录已过期")
    user = await db.get(models.User, sess.user_id)
    if not user:
        raise HTTPException(401, "用户不存在")
    return user


def _user_dict(u: models.User) -> dict:
    return {"id": u.id, "username": u.username, "nickname": u.nickname,
            "signature": u.signature, "city": u.city, "gender": u.gender,
            "coins": u.coins, "is_admin": u.is_admin}


# ===================== 认证 =====================
class LoginIn(BaseModel):
    username: str
    password: str


class RegisterIn(BaseModel):
    username: str
    password: str
    nickname: str = ""
    city: str = ""


@router.post("/login")
async def api_login(body: LoginIn, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(models.User).where(models.User.username == body.username))
    user = res.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        return err("用户名或密码错误")
    token = await create_session(db, user.id)
    return ok({"token": token, "user": _user_dict(user)})


@router.post("/register")
async def api_register(body: RegisterIn, db: AsyncSession = Depends(get_db)):
    if len(body.username) < 3 or len(body.password) < 4:
        return err("用户名≥3位，密码≥4位")
    res = await db.execute(select(models.User).where(models.User.username == body.username))
    if res.scalar_one_or_none():
        return err("用户名已存在")
    user = models.User(username=body.username, password_hash=hash_password(body.password),
                       nickname=body.nickname or body.username, city=body.city)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = await create_session(db, user.id)
    return ok({"token": token, "user": _user_dict(user)})


@router.get("/me")
async def api_me(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _auth(request, db)
    return ok(_user_dict(user))


# ===================== 平台公共能力 =====================
@router.get("/friends")
async def api_friends(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _auth(request, db)
    frs = await fsvc.list_friends(db, user.id)
    out = []
    for f in frs:
        u = await db.get(models.User, f.friend_id)
        if u:
            out.append({"user": _user_dict(u), "group": f.group_name})
    return ok(out)


class FriendOp(BaseModel):
    friend_id: int


@router.post("/friends/add")
async def api_add_friend(body: FriendOp, request: Request, db: AsyncSession = Depends(get_db)):
    user = await _auth(request, db)
    ok_, msg = await fsvc.add_friend(db, user.id, body.friend_id)
    return ok({"success": ok_}, msg) if ok_ else err(msg)


@router.post("/friends/remove")
async def api_remove_friend(body: FriendOp, request: Request, db: AsyncSession = Depends(get_db)):
    user = await _auth(request, db)
    await fsvc.remove_friend(db, user.id, body.friend_id)
    return ok(None, "已删除")


@router.get("/inventory")
async def api_inventory(request: Request, m: str = "platform", db: AsyncSession = Depends(get_db)):
    user = await _auth(request, db)
    rows = await goods.list_inventory(db, user.id, m)
    return ok([{"item_id": inv.item_id, "key": item.key, "name": item.name,
                "type": item.type, "quantity": inv.quantity, "locked": inv.locked,
                "sell_price": item.sell_price} for inv, item in rows])


class BuyIn(BaseModel):
    item_key: str
    module_key: str = "platform"
    quantity: int = 1


@router.post("/shop/buy")
async def api_buy(body: BuyIn, request: Request, db: AsyncSession = Depends(get_db)):
    """通用购买：按物品字典 key 购买（价格取 sell_price*2）"""
    user = await _auth(request, db)
    item = await goods.get_item_by_key(db, body.item_key)
    if not item:
        return err("物品不存在")
    price = max(1, item.sell_price * 2) * body.quantity
    if user.coins < price:
        return err("金币不足")
    user.coins -= price
    await goods.add_item(db, user.id, item.key, body.module_key, body.quantity)
    await db.commit()
    return ok({"coins": user.coins}, "购买成功")


@router.get("/messages")
async def api_messages(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _auth(request, db)
    res = await db.execute(select(models.Message).where(
        models.Message.user_id == user.id).order_by(models.Message.created_at.desc()).limit(50))
    return ok([{"id": m.id, "type": m.type, "title": m.title, "content": m.content,
                "module": m.module_key, "read": m.is_read,
                "time": m.created_at.isoformat()} for m in res.scalars().all()])


@router.get("/ranking")
async def api_ranking(request: Request, m: str = "farm", metric: str = "harvest",
                      period: str = "total", n: int = 20, db: AsyncSession = Depends(get_db)):
    await _auth(request, db)
    rows = await ranking.top_n(db, m, metric, period, n)
    return ok([{"rank": i + 1, "user_id": u.id, "nickname": u.nickname, "score": re.score}
               for i, (re, u) in enumerate(rows)])


@router.get("/icons")
async def api_icons(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _auth(request, db)
    ics = (await db.execute(select(models.Icon).order_by(models.Icon.id))).scalars().all()
    lit_ids = set()
    res = await db.execute(select(models.UserIcon).where(
        models.UserIcon.user_id == user.id, models.UserIcon.lit.is_(True)))
    for ui in res.scalars().all():
        lit_ids.add(ui.icon_id)
    return ok([{"key": i.key, "name": i.name, "description": i.description,
                "source": i.source, "lit": i.id in lit_ids} for i in ics])


# ===================== 模块事件上报（5.5 核心规范）=====================
class EmitIn(BaseModel):
    event: str
    payload: dict = {}


@router.post("/events/emit")
async def api_emit(body: EmitIn, request: Request, db: AsyncSession = Depends(get_db),
                   x_module_key: str = Header(default="platform", alias="X-Module-Key")):
    """模块事件上报入口。模块只能上报事件，不可直接修改平台数据。

    event: message / icon_light / achievement / ranking / activity_progress / interact_notify
    """
    user = await _auth(request, db)
    await events.emit(db, user.id, x_module_key, body.event, body.payload)
    return ok(None, "事件已上报")


# ===================== 模块状态查询 =====================
@router.get("/farm/state")
async def api_farm_state(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _auth(request, db)
    st = await db.get(models.FarmState, user.id)
    return ok({"level": st.level if st else 1, "exp": st.exp if st else 0,
               "plot_count": st.plot_count if st else 6})


@router.get("/town/state")
async def api_town_state(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _auth(request, db)
    st = await db.get(models.TownState, user.id)
    if not st:
        return ok({"stars": 0, "oil": 3000, "oil_cap": 3000, "coins": 10000,
                   "dishes_served": 0, "level": 1, "exp": 0, "exp_needed": 200,
                   "total_service": 0, "total_revenue": 0, "fame": 0, "table_count": 3})
    from ..routers.town import exp_needed, star_info, calc_serving_tables, get_active_waiters, get_active_cockroaches
    waiters = await get_active_waiters(db, user.id)
    roaches = await get_active_cockroaches(db, user.id)
    table_cap, waiter_total, cabinet_cap, facility_slots, picky_pct, rare_pct, revenue_coef = star_info(st.stars)
    serving_tables = calc_serving_tables(st.table_count, len(waiters) + 1, len(roaches))
    return ok({
        "stars": st.stars, "level": st.level, "exp": st.exp,
        "exp_needed": exp_needed(st.level),
        "oil": st.oil, "oil_cap": st.oil_cap,
        "coins": st.coins, "dishes_served": st.dishes_served,
        "total_service": st.total_service, "total_revenue": st.total_revenue,
        "fame": st.fame, "table_count": st.table_count,
        "table_cap": table_cap, "waiter_total": waiter_total,
        "cabinet_cap": cabinet_cap, "facility_slots": facility_slots,
        "picky_pct": picky_pct, "rare_pct": rare_pct,
        "revenue_coef": revenue_coef, "serving_tables": serving_tables,
        "active_waiters": len(waiters), "active_roaches": len(roaches),
        "oil_pct": int(st.oil / st.oil_cap * 100) if st.oil_cap > 0 else 0,
    })


@router.get("/garden/state")
async def api_garden_state(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _auth(request, db)
    st = await db.get(models.GardenState, user.id)
    res = await db.execute(select(models.GardenCollection).where(models.GardenCollection.user_id == user.id))
    lit = sum(1 for c in res.scalars().all() if c.lit)
    level = st.level if st else 1
    # v0.1.3：订单统计（活跃数 + 累计交付金币）
    active_orders = 0
    total_order_coin = 0
    if st:
        o_res = await db.execute(select(models.GardenOrder).where(
            models.GardenOrder.user_id == user.id, models.GardenOrder.delivered.is_(False)))
        active_orders = len([o for o in o_res.scalars().all() if not o.expire_at or o.expire_at > datetime.utcnow()])
        l_res = await db.execute(select(models.GardenOrderLog).where(
            models.GardenOrderLog.user_id == user.id))
        total_order_coin = sum(l.coin_gain for l in l_res.scalars().all())
    # 魔法师称号 + 物品等级上限（v0.0.3）
    from ..routers.garden import magician_title, item_level_cap, exp_needed
    title, tier_range = magician_title(level)
    return ok({
        "level": level,
        "exp": st.exp if st else 0,
        "exp_needed": exp_needed(level),
        "coins": st.coins if st else 0,
        "pot_count": st.pot_count if st else 4,
        "flower_lit": lit,
        "title": title,
        "tier_range": list(tier_range),
        "item_level_cap": item_level_cap(level),
        "active_orders": active_orders,        # v0.1.3
        "total_order_coin": total_order_coin,  # v0.1.3
    })


@router.get("/sea/state")
async def api_sea_state(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _auth(request, db)
    st = await db.get(models.SeaState, user.id)
    return ok({"level": st.level if st else 1, "power": st.power if st else 10,
               "current_city": st.current_city if st else "port_a",
               "traveling_to": st.traveling_to if st else ""})


@router.get("/summon/state")
async def api_summon_state(request: Request, db: AsyncSession = Depends(get_db)):
    """v0.1.2：补齐召唤之王状态接口（之前仅 farm/town/garden/sea 四个，缺 summon）"""
    user = await _auth(request, db)
    st = await db.get(models.SummonState, user.id)
    # 统计队伍中的幻兽数量与最高等级
    pets_res = await db.execute(select(models.SummonPet).where(
        models.SummonPet.user_id == user.id))
    pets = pets_res.scalars().all()
    in_team = sum(1 for p in pets if p.team_slot is not None and p.team_slot >= 0)
    max_pet_level = max((p.level for p in pets), default=0)
    return ok({
        "level": st.level if st else 1,
        "exp": st.exp if st else 0,
        "energy": st.energy if st else 120,
        "coins": st.coins if st else 5000,         # 铜钱
        "gems": st.gems if st else 100,            # 元宝
        "prestige": st.prestige if st else 0,      # 声望
        "arena_coin": st.arena_coin if st else 0,
        "current_map": st.current_map if st else "T1",
        "stage_cleared": st.stage_cleared if st else 0,
        "pet_total": len(pets),
        "pet_in_team": in_team,
        "max_pet_level": max_pet_level,
    })

