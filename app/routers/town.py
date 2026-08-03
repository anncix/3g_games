"""美味小镇模块

老味道点：食材短缺驱动互动 / 翻好友橱柜 / 添油维持营业 / 升星与挑剔客人
"""
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from ..platform import goods, icons, events, locks, friends as fsvc, log
from .views import render

router = APIRouter(prefix="/games/town")
MODULE_KEY = "town"


async def get_state(db: AsyncSession, user_id: int) -> models.TownState:
    st = await db.get(models.TownState, user_id)
    if not st:
        st = models.TownState(user_id=user_id)
        db.add(st)
        await db.commit()
        await db.refresh(st)
    return st


async def _drain_oil(db: AsyncSession, st: models.TownState):
    """油量随时间消耗"""
    elapsed = (datetime.utcnow() - st.last_oil_drain).total_seconds()
    drained = int(elapsed / 60) * 5  # 每分钟-5
    if drained > 0:
        st.oil = max(0, st.oil - drained)
        st.last_oil_drain = datetime.utcnow()


async def _cook_done(st: models.TownState, recipe: models.TownRecipe) -> bool:
    return st.cooking_recipe and (datetime.utcnow() - st.cooking_started_at).total_seconds() >= recipe.cook_seconds


@router.get("")
async def town_home(request: Request, db: AsyncSession = Depends(get_db)):
    """模块首页"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    await _drain_oil(db, st)
    await db.commit()
    # 当前烹饪
    cooking_recipe = None
    cook_remain = 0
    if st.cooking_recipe:
        cooking_recipe = await db.get(models.TownRecipe, st.cooking_recipe)
        if cooking_recipe:
            cook_remain = max(0, int(cooking_recipe.cook_seconds - (datetime.utcnow() - st.cooking_started_at).total_seconds()))
    # 可做菜谱
    recipes = (await db.execute(select(models.TownRecipe).where(models.TownRecipe.unlock_stars <= st.stars))).scalars().all()
    todo = 0
    if st.oil < 30: todo += 1
    if cooking_recipe and cook_remain == 0: todo += 1
    return await render(request, "town/home.html", db, user=user, st=st,
                        cooking_recipe=cooking_recipe, cook_remain=cook_remain, recipes=recipes, todo=todo)


@router.get("/recipes")
async def recipes_list(request: Request, db: AsyncSession = Depends(get_db)):
    """列表页：菜谱"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    recipes = (await db.execute(select(models.TownRecipe))).scalars().all()
    info = []
    for r in recipes:
        ing = json.loads(r.ingredients)
        can = r.unlock_stars <= st.stars
        ings = []
        enough = True
        for k, n in ing.items():
            cnt = await goods.count_item(db, user.id, k, MODULE_KEY)
            ings.append((k, n, cnt))
            if cnt < n: enough = False
        info.append({"r": r, "ings": ings, "can": can, "enough": enough})
    return await render(request, "town/recipes.html", db, user=user, st=st, info=info)


@router.post("/cook/{key}")
async def cook(key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """操作页：烹饪"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if st.cooking_recipe:
        return await render(request, "result.html", db, user=user, ok=False, msg="正在烹饪中，先完成当前的", back_href="/games/town", back_text="返回")
    recipe = await db.get(models.TownRecipe, key)
    if not recipe or recipe.unlock_stars > st.stars:
        return await render(request, "result.html", db, user=user, ok=False, msg="菜谱未解锁", back_href="/games/town/recipes", back_text="返回菜谱")
    if st.oil < 10:
        return await render(request, "result.html", db, user=user, ok=False, msg="油量不足10，请先添油", back_href="/games/town", back_text="返回")
    ing = json.loads(recipe.ingredients)
    for k, n in ing.items():
        if await goods.count_item(db, user.id, k, MODULE_KEY) < n:
            return await render(request, "result.html", db, user=user, ok=False, msg=f"食材不足：{k}", back_href="/games/town/recipes", back_text="返回菜谱")
    for k, n in ing.items():
        await goods.remove_item(db, user.id, k, MODULE_KEY, n)
    st.cooking_recipe = key
    st.cooking_started_at = datetime.utcnow()
    st.oil -= 10
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "cook", key)
    return await render(request, "result.html", db, user=user, ok=True, msg=f"开始烹饪{recipe.name}，约{recipe.cook_seconds}秒", back_href="/games/town", back_text="返回首页")


@router.post("/finish")
async def finish_cook(request: Request, db: AsyncSession = Depends(get_db)):
    """完成烹饪（结果页）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if not st.cooking_recipe:
        return await render(request, "result.html", db, user=user, ok=False, msg="没有在烹饪", back_href="/games/town", back_text="返回")
    recipe = await db.get(models.TownRecipe, st.cooking_recipe)
    if not recipe or (datetime.utcnow() - st.cooking_started_at).total_seconds() < recipe.cook_seconds:
        return await render(request, "result.html", db, user=user, ok=False, msg="还没烹饪完成", back_href="/games/town", back_text="返回")
    await goods.add_item(db, user.id, recipe.output_item_key, MODULE_KEY, 1)
    user.coins += recipe.price
    st.dishes_served += 1
    st.exp += 20
    st.cooking_recipe = ""
    st.cooking_started_at = None
    # 升星：每50份升1星，上限5
    if st.dishes_served >= st.stars * 50 and st.stars < 5:
        st.stars += 1
        await events.emit(db, user.id, MODULE_KEY, "interact_notify",
                          {"to_id": user.id, "title": "餐厅升星", "content": f"恭喜！餐厅升至{st.stars}星"})
        if st.stars >= 2:
            await events.emit(db, user.id, MODULE_KEY, "achievement", {"key": "achv_chef_star2"})
        if st.stars >= 3:
            await events.emit(db, user.id, MODULE_KEY, "icon_light", {"icon_key": "icon_chef"})
    await events.emit(db, user.id, MODULE_KEY, "ranking", {"metric": "dishes", "score": 1})
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "finish_cook", recipe.key)
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"完成{recipe.name}×1，售价{recipe.price}金币，经验+20", back_href="/games/town", back_text="返回首页")


@router.post("/addoil")
async def add_oil(request: Request, db: AsyncSession = Depends(get_db)):
    """添油维持营业（消耗食材油，+30油量）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    if await goods.count_item(db, user.id, "town_ingredient_oil", MODULE_KEY) < 1:
        return await render(request, "result.html", db, user=user, ok=False, msg="没有食用油，去商店买", back_href="/shop?m=town", back_text="去商店")
    await goods.remove_item(db, user.id, "town_ingredient_oil", MODULE_KEY, 1)
    st.oil = min(100, st.oil + 30)
    st.last_oil_drain = datetime.utcnow()
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "addoil", "+30")
    return await render(request, "result.html", db, user=user, ok=True, msg=f"添油成功，油量{st.oil}/100", back_href="/games/town", back_text="返回首页")


# ---------------- 翻好友橱柜 ----------------
@router.get("/visit/{uid}")
async def visit_town(uid: int, request: Request, db: AsyncSession = Depends(get_db)):
    """翻好友橱柜：从好友食材中翻一件"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if await fsvc.is_blocked(db, uid, user.id):
        return await render(request, "result.html", db, user=user, ok=False, msg="对方已拉黑你", back_href="/friends", back_text="返回好友")
    host = await db.get(models.User, uid)
    # 好友的食材（非上锁）
    invs = await goods.list_inventory(db, uid, MODULE_KEY)
    items = []
    for inv, item in invs:
        if item.type == "ingredient" and inv.quantity > 0:
            locked = await locks.is_item_locked(db, uid, MODULE_KEY, item.key)
            already = await _already_raided(db, user.id, uid, item.key)
            items.append({"inv": inv, "item": item, "locked": locked, "already": already})
    return await render(request, "town/visit.html", db, user=user, host=host, items=items)


async def _already_raided(db: AsyncSession, thief_id: int, host_id: int, item_key: str) -> bool:
    from sqlalchemy import select as sel
    res = await db.execute(sel(models.OperationLog).where(
        models.OperationLog.user_id == thief_id, models.OperationLog.module_key == MODULE_KEY,
        models.OperationLog.action == "raid", models.OperationLog.detail == f"{host_id}:{item_key}"))
    return res.scalar_one_or_none() is not None


@router.post("/raid/{uid}/{item_key}")
async def raid(uid: int, item_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """翻橱柜（受物品锁约束）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if await locks.is_item_locked(db, uid, MODULE_KEY, item_key):
        return await render(request, "result.html", db, user=user, ok=False, msg="🔒 食材已上锁", back_href=f"/games/town/visit/{uid}", back_text="返回")
    if await _already_raided(db, user.id, uid, item_key):
        return await render(request, "result.html", db, user=user, ok=False, msg="已经翻过这个了", back_href=f"/games/town/visit/{uid}", back_text="返回")
    ok = await goods.remove_item(db, uid, item_key, MODULE_KEY, 1)
    if not ok:
        return await render(request, "result.html", db, user=user, ok=False, msg="对方没有这种食材了", back_href=f"/games/town/visit/{uid}", back_text="返回")
    await goods.add_item(db, user.id, item_key, MODULE_KEY, 1)
    item = await goods.get_item_by_key(db, item_key)
    await events.emit(db, user.id, MODULE_KEY, "interact_notify",
                      {"to_id": uid, "title": "被翻橱柜", "content": f"{user.nickname} 翻走了你的 {item.name} ×1"})
    await log.record(db, user.id, MODULE_KEY, "raid", f"{uid}:{item_key}")
    await db.commit()
    return await render(request, "result.html", db, user=user, ok=True, msg=f"翻到{item.name}×1", back_href=f"/games/town/visit/{uid}", back_text="继续翻")


@router.get("/rules")
async def rules(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return await render(request, "town/rules.html", db, user=user)
