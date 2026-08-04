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
    User, TownProfile, TownTable, TownRecipe, TownUserRecipe, TownIngredient,
    TownOrder, TownFriendAction, Notification, Wallet
)
from utils.auth import get_current_user
from utils.i18n import t

router = APIRouter(prefix="/delicious_town", tags=["delicious_town"])
templates = Jinja2Templates(directory="templates")

INGREDIENTS = {
    "rice": {"name": "大米", "price": 2},
    "egg": {"name": "鸡蛋", "price": 3},
    "tomato": {"name": "西红柿", "price": 3},
    "chicken": {"name": "鸡肉", "price": 8},
    "pork": {"name": "猪肉", "price": 10},
    "beef": {"name": "牛肉", "price": 15},
    "tofu": {"name": "豆腐", "price": 4},
    "noodle": {"name": "面条", "price": 5},
    "fish": {"name": "鱼", "price": 12},
    "seaweed": {"name": "紫菜", "price": 5},
    "peanut": {"name": "花生", "price": 4},
    "chili": {"name": "辣椒", "price": 3},
    "vinegar": {"name": "醋", "price": 2},
    "sugar": {"name": "糖", "price": 2},
    "butter": {"name": "黄油", "price": 8},
    "pepper": {"name": "胡椒", "price": 5},
}

STREETS = {
    "chinese": {"name": "中华街", "unlock_level": 1},
    "western": {"name": "西洋街", "unlock_level": 10},
    "japanese": {"name": "日式街", "unlock_level": 5},
}


def get_common_context(request: Request, db: Session):
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


def init_town(user: User, db: Session):
    if not user.town:
        town = TownProfile(user_id=user.id)
        db.add(town)
        db.flush()
        for i in range(4):
            db.add(TownTable(
                town_id=town.id,
                user_id=user.id,
                table_no=i + 1
            ))
        starter_ingredients = [
            {"ingredient_code": "rice", "ingredient_name": "大米", "quantity": 20},
            {"ingredient_code": "egg", "ingredient_name": "鸡蛋", "quantity": 20},
            {"ingredient_code": "tomato", "ingredient_name": "西红柿", "quantity": 20},
        ]
        for ing in starter_ingredients:
            db.add(TownIngredient(
                town_id=town.id,
                user_id=user.id,
                **ing
            ))
        db.commit()
        db.refresh(town)


def process_town(town: TownProfile, db: Session):
    now = datetime.utcnow()
    for table in town.tables:
        if table.status == "occupied":
            orders = db.query(TownOrder).filter(
                TownOrder.table_id == table.id,
                TownOrder.status == "waiting"
            ).all()
            for order in orders:
                if now >= order.created_at + timedelta(seconds=30):
                    order.status = "completed"
                    if order.reward_gold > 0:
                        town.gold += order.reward_gold
                    if order.reward_exp > 0:
                        town.restaurant_exp += order.reward_exp
                    table.status = "dirty"


def generate_customer(town: TownProfile, table: TownTable, db: Session):
    available_recipes = db.query(TownRecipe).filter(
        TownRecipe.street_code == town.street_code,
        TownRecipe.level_required <= town.restaurant_level
    ).all()
    
    learned_recipe_ids = [r.recipe_id for r in town.recipes]
    cookable_recipes = [r for r in available_recipes if r.id in learned_recipe_ids]
    
    if not cookable_recipes:
        cookable_recipes = available_recipes[:3] if available_recipes else []
    
    if not cookable_recipes:
        return None
    
    recipe = random.choice(cookable_recipes)
    
    customer_type = "picky" if random.random() < 0.2 else "normal"
    reward_mult = 1.5 if customer_type == "picky" else 1.0
    
    order = TownOrder(
        town_id=town.id,
        user_id=town.user_id,
        table_id=table.id,
        customer_type=customer_type,
        recipe_id=recipe.id,
        recipe_name=recipe.name,
        status="waiting",
        reward_gold=int(recipe.gold_income * reward_mult),
        reward_exp=int(recipe.exp_income * reward_mult),
        created_at=datetime.utcnow()
    )
    db.add(order)
    table.status = "occupied"
    return order


@router.get("", response_class=HTMLResponse)
async def town_home(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    init_town(user, db)
    town = user.town
    process_town(town, db)
    
    idle_tables = [t for t in town.tables if t.status == "idle"]
    if idle_tables and town.oil_amount > 0:
        for table in idle_tables[:2]:
            generate_customer(town, table, db)
    
    db.commit()
    
    recipes = db.query(TownRecipe).filter(TownRecipe.street_code == town.street_code).all()
    ingredients = db.query(TownIngredient).filter(TownIngredient.user_id == user.id).all()
    orders = db.query(TownOrder).filter(
        TownOrder.user_id == user.id,
        TownOrder.status.in_(["waiting", "completed"])
    ).order_by(desc(TownOrder.created_at)).limit(10).all()
    
    ctx.update({
        "town": town,
        "tables": sorted(town.tables, key=lambda t: t.table_no),
        "recipes": recipes,
        "ingredients": ingredients,
        "orders": orders,
        "streets": STREETS,
        "ingredients_def": INGREDIENTS,
    })
    return templates.TemplateResponse("delicious_town/index.html", ctx)


@router.get("/learn/{recipe_id}")
async def learn_recipe(request: Request, recipe_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    init_town(user, db)
    town = user.town
    
    recipe = db.query(TownRecipe).filter(TownRecipe.id == recipe_id).first()
    if not recipe:
        return RedirectResponse(url="/delicious_town", status_code=302)
    
    existing = db.query(TownUserRecipe).filter(
        TownUserRecipe.town_id == town.id,
        TownUserRecipe.recipe_id == recipe_id
    ).first()
    if existing:
        return RedirectResponse(url="/delicious_town", status_code=302)
    
    if town.gold < 100 * recipe.level_required:
        return RedirectResponse(url="/delicious_town", status_code=302)
    
    ingredients_needed = json.loads(recipe.ingredient_json) if recipe.ingredient_json else {}
    for ing_code, qty in ingredients_needed.items():
        ing = db.query(TownIngredient).filter(
            TownIngredient.user_id == user.id,
            TownIngredient.ingredient_code == ing_code
        ).first()
        if not ing or ing.quantity < qty:
            return RedirectResponse(url="/delicious_town", status_code=302)
    
    town.gold -= 100 * recipe.level_required
    for ing_code, qty in ingredients_needed.items():
        ing = db.query(TownIngredient).filter(
            TownIngredient.user_id == user.id,
            TownIngredient.ingredient_code == ing_code
        ).first()
        ing.quantity -= qty
        if ing.quantity <= 0:
            db.delete(ing)
    
    db.add(TownUserRecipe(
        town_id=town.id,
        user_id=user.id,
        recipe_id=recipe_id,
        quality_level="normal"
    ))
    
    town.restaurant_exp += 20
    exp_needed = town.restaurant_level * 100
    while town.restaurant_exp >= exp_needed:
        town.restaurant_exp -= exp_needed
        town.restaurant_level += 1
        if town.restaurant_level in [3, 5, 8, 10]:
            town.star_level = min(town.star_level + 1, 5)
            town.seats += 1
        exp_needed = town.restaurant_level * 100
    
    db.commit()
    return RedirectResponse(url="/delicious_town", status_code=302)


@router.post("/add_oil")
async def add_oil(request: Request, amount: int = Form(10), db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    init_town(user, db)
    town = user.town
    
    cost = amount * 10
    wallet = user.wallet
    if not wallet or wallet.g_coin < cost:
        return RedirectResponse(url="/delicious_town", status_code=302)
    
    wallet.g_coin -= cost
    town.oil_amount = min(town.oil_amount + amount, 1000)
    
    db.commit()
    return RedirectResponse(url="/delicious_town", status_code=302)


@router.post("/buy_ingredient")
async def buy_ingredient(
    request: Request,
    ingredient_code: str = Form(...),
    quantity: int = Form(10),
    db: Session = Depends(get_db)
):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    init_town(user, db)
    town = user.town
    
    ing_def = INGREDIENTS.get(ingredient_code)
    if not ing_def:
        return RedirectResponse(url="/delicious_town", status_code=302)
    
    total_cost = ing_def["price"] * quantity
    if town.gold < total_cost:
        return RedirectResponse(url="/delicious_town", status_code=302)
    
    town.gold -= total_cost
    
    existing = db.query(TownIngredient).filter(
        TownIngredient.user_id == user.id,
        TownIngredient.ingredient_code == ingredient_code
    ).first()
    if existing:
        existing.quantity += quantity
    else:
        db.add(TownIngredient(
            town_id=town.id,
            user_id=user.id,
            ingredient_code=ingredient_code,
            ingredient_name=ing_def["name"],
            quantity=quantity
        ))
    
    db.commit()
    return RedirectResponse(url="/delicious_town", status_code=302)


@router.get("/clean_table/{table_id}")
async def clean_table(request: Request, table_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    init_town(user, db)
    town = user.town
    
    table = db.query(TownTable).filter(
        TownTable.id == table_id,
        TownTable.town_id == town.id
    ).first()
    
    if table and table.status == "dirty":
        table.status = "idle"
        db.commit()
    
    return RedirectResponse(url="/delicious_town", status_code=302)