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
    User, GardenProfile, GardenPlot, GardenFlower, GardenUserFlower,
    GardenAlbumEntry, GardenUserAlbum, GardenFriendAction,
    Notification, Wallet
)
from utils.auth import get_current_user
from utils.i18n import t

router = APIRouter(prefix="/magic_garden", tags=["magic_garden"])
templates = Jinja2Templates(directory="templates")

FLOWER_COLORS = {
    "white": "白色",
    "yellow": "黄色",
    "pink": "粉色",
    "red": "红色",
    "purple": "紫色",
    "golden": "金色",
    "black": "黑色",
    "green": "绿色",
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
        "t": lambda key: t(key, lang),
        "unread_count": unread_count,
        "now": datetime.utcnow(),
    }


def init_garden(user: User, db: Session):
    if not user.garden:
        garden = GardenProfile(user_id=user.id)
        db.add(garden)
        db.flush()
        for i in range(6):
            plot = GardenPlot(
                garden_id=garden.id,
                user_id=user.id,
                plot_no=i + 1
            )
            db.add(plot)
        seeds = [
            {"flower_code": "daisy", "flower_name": "雏菊", "quantity": 10, "storage_type": "seed"},
        ]
        for s in seeds:
            db.add(GardenUserFlower(
                garden_id=garden.id,
                user_id=user.id,
                **s
            ))
        db.commit()
        db.refresh(garden)


def process_plots(garden: GardenProfile, db: Session):
    now = datetime.utcnow()
    for plot in garden.plots:
        if plot.seed_code and plot.ready_at and now >= plot.ready_at:
            plot.stage = "mature"


def get_color_name(color_code):
    return FLOWER_COLORS.get(color_code, color_code)


@router.get("", response_class=HTMLResponse)
async def garden_home(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    init_garden(user, db)
    garden = user.garden
    process_plots(garden, db)
    db.commit()
    
    flowers = db.query(GardenFlower).all()
    seed_inventory = db.query(GardenUserFlower).filter(
        GardenUserFlower.user_id == user.id,
        GardenUserFlower.storage_type == "seed"
    ).all()
    flower_inventory = db.query(GardenUserFlower).filter(
        GardenUserFlower.user_id == user.id,
        GardenUserFlower.storage_type == "flower"
    ).all()
    
    ctx.update({
        "garden": garden,
        "plots": sorted(garden.plots, key=lambda p: p.plot_no),
        "flowers": flowers,
        "seed_inventory": seed_inventory,
        "flower_inventory": flower_inventory,
        "color_names": FLOWER_COLORS,
    })
    return templates.TemplateResponse("magic_garden/index.html", ctx)


@router.post("/plant/{plot_no}")
async def plant_seed(
    request: Request,
    plot_no: int,
    seed_code: str = Form(...),
    db: Session = Depends(get_db)
):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    init_garden(user, db)
    garden = user.garden
    
    plot = db.query(GardenPlot).filter(
        GardenPlot.garden_id == garden.id,
        GardenPlot.plot_no == plot_no
    ).first()
    
    if not plot or plot.seed_code:
        return RedirectResponse(url="/magic_garden", status_code=302)
    
    seed = db.query(GardenUserFlower).filter(
        GardenUserFlower.user_id == user.id,
        GardenUserFlower.flower_code == seed_code,
        GardenUserFlower.storage_type == "seed",
        GardenUserFlower.quantity > 0
    ).first()
    
    if not seed:
        return RedirectResponse(url="/magic_garden", status_code=302)
    
    flower_def = db.query(GardenFlower).filter(GardenFlower.flower_code == seed_code).first()
    if not flower_def:
        return RedirectResponse(url="/magic_garden", status_code=302)
    
    seed.quantity -= 1
    if seed.quantity <= 0:
        db.delete(seed)
    
    flower = db.query(GardenFlower).filter(GardenFlower.seed_code == seed_code).first()
    colors = json.loads(flower.base_colors_json) if flower and flower.base_colors_json else ["white"]
    color = random.choice(colors)
    
    plot.seed_code = seed_code
    plot.flower_name = flower.name if flower else seed_code
    plot.stage = "sprout"
    plot.color = color
    plot.planted_at = datetime.utcnow()
    plot.ready_at = datetime.utcnow() + timedelta(seconds=min(flower.grow_time if flower else 300, 60))
    plot.watered = False
    plot.weeded = False
    plot.insect_state = False
    
    db.commit()
    return RedirectResponse(url="/magic_garden", status_code=302)


@router.get("/harvest/{plot_no}")
async def harvest_flower(request: Request, plot_no: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    init_garden(user, db)
    garden = user.garden
    
    plot = db.query(GardenPlot).filter(
        GardenPlot.garden_id == garden.id,
        GardenPlot.plot_no == plot_no
    ).first()
    
    if not plot or plot.stage != "mature":
        return RedirectResponse(url="/magic_garden", status_code=302)
    
    flower_def = db.query(GardenFlower).filter(GardenFlower.flower_code == plot.seed_code).first()
    if flower_def:
        garden.garden_exp += flower_def.exp_gain
        wallet = user.wallet
        if wallet:
            wallet.g_coin += flower_def.price
        
        existing = db.query(GardenUserFlower).filter(
            GardenUserFlower.user_id == user.id,
            GardenUserFlower.flower_code == plot.seed_code,
            GardenUserFlower.color == plot.color,
            GardenUserFlower.storage_type == "flower"
        ).first()
        if existing:
            existing.quantity += 1
        else:
            db.add(GardenUserFlower(
                garden_id=garden.id,
                user_id=user.id,
                flower_code=plot.seed_code,
                flower_name=plot.flower_name,
                color=plot.color,
                quantity=1,
                storage_type="flower"
            ))
        
        album_entry = db.query(GardenAlbumEntry).filter(
            GardenAlbumEntry.flower_code == plot.seed_code,
            GardenAlbumEntry.color == plot.color
        ).first()
        if album_entry:
            user_album = db.query(GardenUserAlbum).filter(
                GardenUserAlbum.user_id == user.id,
                GardenUserAlbum.album_entry_id == album_entry.id
            ).first()
            if not user_album:
                db.add(GardenUserAlbum(
                    user_id=user.id,
                    album_entry_id=album_entry.id,
                    is_lit=True,
                    lit_at=datetime.utcnow()
                ))
                garden.album_lit_count += 1
        
        exp_needed = garden.garden_level * 100
        while garden.garden_exp >= exp_needed:
            garden.garden_exp -= exp_needed
            garden.garden_level += 1
            garden.plot_count = min(6 + garden.garden_level - 1, 18)
            exp_needed = garden.garden_level * 100
    
    plot.seed_code = None
    plot.flower_name = None
    plot.stage = None
    plot.color = None
    plot.planted_at = None
    plot.ready_at = None
    plot.watered = False
    plot.weeded = False
    plot.insect_state = False
    
    db.commit()
    return RedirectResponse(url="/magic_garden", status_code=302)


@router.get("/water/{plot_no}")
async def water_plot(request: Request, plot_no: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    init_garden(user, db)
    garden = user.garden
    
    plot = db.query(GardenPlot).filter(
        GardenPlot.garden_id == garden.id,
        GardenPlot.plot_no == plot_no
    ).first()
    
    if plot and plot.seed_code and not plot.watered:
        plot.watered = True
        if plot.ready_at:
            plot.ready_at -= timedelta(seconds=10)
        db.commit()
    
    return RedirectResponse(url="/magic_garden", status_code=302)


@router.get("/shop")
async def flower_shop(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    flowers = db.query(GardenFlower).all()
    ctx.update({
        "flowers": flowers,
    })
    return templates.TemplateResponse("magic_garden/shop.html", ctx)


@router.post("/buy_seed/{flower_code}")
async def buy_seed(request: Request, flower_code: str, quantity: int = Form(1), db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    flower = db.query(GardenFlower).filter(GardenFlower.flower_code == flower_code).first()
    if not flower:
        return RedirectResponse(url="/magic_garden/shop", status_code=302)
    
    wallet = user.wallet
    total_cost = flower.price * quantity
    if not wallet or wallet.g_coin < total_cost:
        return RedirectResponse(url="/magic_garden/shop", status_code=302)
    
    wallet.g_coin -= total_cost
    
    init_garden(user, db)
    existing = db.query(GardenUserFlower).filter(
        GardenUserFlower.user_id == user.id,
        GardenUserFlower.flower_code == flower_code,
        GardenUserFlower.storage_type == "seed"
    ).first()
    if existing:
        existing.quantity += quantity
    else:
        db.add(GardenUserFlower(
            garden_id=user.garden.id,
            user_id=user.id,
            flower_code=flower_code,
            flower_name=flower.name,
            quantity=quantity,
            storage_type="seed"
        ))
    
    db.commit()
    return RedirectResponse(url="/magic_garden", status_code=302)


@router.get("/album")
async def flower_album(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    init_garden(user, db)
    
    entries = db.query(GardenAlbumEntry).order_by(GardenAlbumEntry.sort_order).all()
    lit_entries = db.query(GardenUserAlbum).filter(
        GardenUserAlbum.user_id == user.id,
        GardenUserAlbum.is_lit == True
    ).all()
    lit_ids = [e.album_entry_id for e in lit_entries]
    
    ctx.update({
        "entries": entries,
        "lit_ids": lit_ids,
        "color_names": FLOWER_COLORS,
    })
    return templates.TemplateResponse("magic_garden/album.html", ctx)