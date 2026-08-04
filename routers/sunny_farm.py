from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc
import random
from datetime import datetime, timedelta

from models.database import get_db
from models.models import (
    User, FarmProfile, FarmPlot, FarmAnimal, FarmStorage, FarmFriendAction,
    Notification, Wallet
)
from utils.auth import get_current_user
from utils.i18n import t

router = APIRouter(prefix="/sunny_farm", tags=["sunny_farm"])
templates = Jinja2Templates(directory="templates")

CROPS = {
    "wheat": {"name": "小麦", "grow_time": 60, "price": 5, "sell_price": 12, "exp": 5},
    "cabbage": {"name": "白菜", "grow_time": 90, "price": 8, "sell_price": 20, "exp": 8},
    "carrot": {"name": "胡萝卜", "grow_time": 120, "price": 12, "sell_price": 30, "exp": 12},
    "corn": {"name": "玉米", "grow_time": 180, "price": 20, "sell_price": 50, "exp": 18},
    "strawberry": {"name": "草莓", "grow_time": 240, "price": 30, "sell_price": 80, "exp": 25},
}

ANIMALS = {
    "chicken": {"name": "小鸡", "price": 100, "product": "egg", "product_name": "鸡蛋", "product_price": 15, "grow_time": 300},
    "duck": {"name": "小鸭", "price": 150, "product": "duck_egg", "product_name": "鸭蛋", "product_price": 20, "grow_time": 360},
    "cow": {"name": "奶牛", "price": 500, "product": "milk", "product_name": "牛奶", "product_price": 50, "grow_time": 600},
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


def init_farm(user: User, db: Session):
    if not user.farm:
        farm = FarmProfile(user_id=user.id)
        db.add(farm)
        db.flush()
        for i in range(6):
            db.add(FarmPlot(
                farm_id=farm.id,
                user_id=user.id,
                plot_no=i + 1
            ))
        seeds = [
            {"item_code": "wheat_seed", "item_name": "小麦种子", "item_type": "seed", "quantity": 10},
        ]
        for s in seeds:
            db.add(FarmStorage(
                farm_id=farm.id,
                user_id=user.id,
                **s
            ))
        db.commit()
        db.refresh(farm)


def process_farm(farm: FarmProfile, db: Session):
    now = datetime.utcnow()
    for plot in farm.plots:
        if plot.crop_code and plot.ready_at and now >= plot.ready_at:
            plot.status = "ready"
    for animal in farm.animals:
        if animal.ready_at and now >= animal.ready_at:
            animal.production_ready = True


@router.get("", response_class=HTMLResponse)
async def farm_home(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    init_farm(user, db)
    farm = user.farm
    process_farm(farm, db)
    db.commit()
    
    storage = db.query(FarmStorage).filter(FarmStorage.user_id == user.id).all()
    
    ctx.update({
        "farm": farm,
        "plots": sorted(farm.plots, key=lambda p: p.plot_no),
        "animals": farm.animals,
        "storage": storage,
        "crops": CROPS,
        "animals_def": ANIMALS,
    })
    return templates.TemplateResponse("sunny_farm/index.html", ctx)


@router.post("/plant/{plot_no}")
async def plant_crop(
    request: Request,
    plot_no: int,
    crop_code: str = Form(...),
    db: Session = Depends(get_db)
):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    init_farm(user, db)
    farm = user.farm
    
    plot = db.query(FarmPlot).filter(
        FarmPlot.farm_id == farm.id,
        FarmPlot.plot_no == plot_no
    ).first()
    
    if not plot or plot.status != "idle":
        return RedirectResponse(url="/sunny_farm", status_code=302)
    
    seed = db.query(FarmStorage).filter(
        FarmStorage.user_id == user.id,
        FarmStorage.item_code == f"{crop_code}_seed",
        FarmStorage.quantity > 0
    ).first()
    
    if not seed:
        return RedirectResponse(url="/sunny_farm", status_code=302)
    
    crop = CROPS.get(crop_code)
    if not crop:
        return RedirectResponse(url="/sunny_farm", status_code=302)
    
    seed.quantity -= 1
    if seed.quantity <= 0:
        db.delete(seed)
    
    plot.status = "growing"
    plot.crop_code = crop_code
    plot.crop_name = crop["name"]
    plot.stage = "sprout"
    plot.planted_at = datetime.utcnow()
    plot.ready_at = datetime.utcnow() + timedelta(seconds=min(crop["grow_time"], 60))
    plot.water_count = 0
    plot.fertilizer_count = 0
    plot.insect_state = False
    plot.weed_state = False
    
    db.commit()
    return RedirectResponse(url="/sunny_farm", status_code=302)


@router.get("/harvest/{plot_no}")
async def harvest_crop(request: Request, plot_no: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    init_farm(user, db)
    farm = user.farm
    
    plot = db.query(FarmPlot).filter(
        FarmPlot.farm_id == farm.id,
        FarmPlot.plot_no == plot_no
    ).first()
    
    if not plot or plot.status != "ready":
        return RedirectResponse(url="/sunny_farm", status_code=302)
    
    crop = CROPS.get(plot.crop_code)
    if crop:
        farm.farm_exp += crop["exp"]
        wallet = user.wallet
        if wallet:
            wallet.g_coin += crop["sell_price"]
        
        existing = db.query(FarmStorage).filter(
            FarmStorage.user_id == user.id,
            FarmStorage.item_code == plot.crop_code
        ).first()
        if existing:
            existing.quantity += 1
        else:
            db.add(FarmStorage(
                farm_id=farm.id,
                user_id=user.id,
                item_code=plot.crop_code,
                item_name=crop["name"],
                item_type="crop",
                quantity=1
            ))
        
        exp_needed = farm.farm_level * 100
        while farm.farm_exp >= exp_needed:
            farm.farm_exp -= exp_needed
            farm.farm_level += 1
            farm.land_count = min(6 + farm.farm_level - 1, 18)
            exp_needed = farm.farm_level * 100
    
    plot.status = "idle"
    plot.crop_code = None
    plot.crop_name = None
    plot.stage = None
    plot.planted_at = None
    plot.ready_at = None
    plot.water_count = 0
    plot.fertilizer_count = 0
    plot.insect_state = False
    plot.weed_state = False
    
    db.commit()
    return RedirectResponse(url="/sunny_farm", status_code=302)


@router.get("/water/{plot_no}")
async def water_plot(request: Request, plot_no: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    init_farm(user, db)
    farm = user.farm
    
    plot = db.query(FarmPlot).filter(
        FarmPlot.farm_id == farm.id,
        FarmPlot.plot_no == plot_no
    ).first()
    
    if plot and plot.status == "growing" and plot.water_count < 3:
        plot.water_count += 1
        if plot.ready_at:
            plot.ready_at -= timedelta(seconds=5)
        db.commit()
    
    return RedirectResponse(url="/sunny_farm", status_code=302)


@router.post("/buy_animal")
async def buy_animal(request: Request, animal_code: str = Form(...), db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    init_farm(user, db)
    farm = user.farm
    
    animal_def = ANIMALS.get(animal_code)
    if not animal_def:
        return RedirectResponse(url="/sunny_farm", status_code=302)
    
    wallet = user.wallet
    if not wallet or wallet.g_coin < animal_def["price"]:
        return RedirectResponse(url="/sunny_farm", status_code=302)
    
    wallet.g_coin -= animal_def["price"]
    
    animal_count = len(farm.animals)
    if animal_count >= 8:
        return RedirectResponse(url="/sunny_farm", status_code=302)
    
    db.add(FarmAnimal(
        farm_id=farm.id,
        user_id=user.id,
        animal_code=animal_code,
        animal_name=animal_def["name"],
        status="baby",
        hunger=100,
        health=100,
        ready_at=datetime.utcnow() + timedelta(seconds=min(animal_def["grow_time"], 120)),
        shed_index=animal_count
    ))
    
    db.commit()
    return RedirectResponse(url="/sunny_farm", status_code=302)


@router.get("/collect_product/{animal_id}")
async def collect_product(request: Request, animal_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    init_farm(user, db)
    
    animal = db.query(FarmAnimal).filter(
        FarmAnimal.id == animal_id,
        FarmAnimal.user_id == user.id
    ).first()
    
    if not animal or not animal.production_ready:
        return RedirectResponse(url="/sunny_farm", status_code=302)
    
    animal_def = ANIMALS.get(animal.animal_code)
    if animal_def:
        wallet = user.wallet
        if wallet:
            wallet.g_coin += animal_def["product_price"]
        
        existing = db.query(FarmStorage).filter(
            FarmStorage.user_id == user.id,
            FarmStorage.item_code == animal_def["product"]
        ).first()
        if existing:
            existing.quantity += 1
        else:
            db.add(FarmStorage(
                farm_id=user.farm.id,
                user_id=user.id,
                item_code=animal_def["product"],
                item_name=animal_def["product_name"],
                item_type="product",
                quantity=1
            ))
    
    animal.production_ready = False
    animal.ready_at = datetime.utcnow() + timedelta(seconds=min(animal_def["grow_time"] if animal_def else 300, 120))
    
    db.commit()
    return RedirectResponse(url="/sunny_farm", status_code=302)