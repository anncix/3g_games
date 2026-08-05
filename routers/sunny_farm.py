"""阳光农场模块（同步 SQLAlchemy 版）

由 v0.3.1 异步版 app/routers/farm.py 移植改写，保留完整玩法：
成长计时 / 护理(浇水·除虫·施肥) / 土地升级 / 作物变异 / 偷菜互助 / 养殖 / 主线任务。
统一使用 v0.3.2 模型（FarmProfile/FarmPlot/FarmAnimal/FarmStorage/FarmFriendAction/Crop/ItemFarm），
作物数据来自 seed/seeds_farm.py 生成的 50 作物字典。
"""
import random
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from models.database import get_db
from models.models import (
    User, FarmProfile, FarmPlot, FarmAnimal, FarmStorage, FarmFriendAction,
    Notification, Wallet, Crop
)
from utils.auth import get_current_user
from utils.i18n import t
from utils.common import change_currency, add_item, remove_item, add_notification

router = APIRouter(prefix="/sunny_farm", tags=["sunny_farm"])
templates = Jinja2Templates(directory="templates")

MODULE_KEY = "farm"

# 土地等级系统（普通→红→金→黑土地）
SOIL_GRADES = {
    "普通": {"next": "红", "min_level": 28, "cost": 200000, "yield_mul": 1.0, "variation_bonus": 0.0},
    "红":   {"next": "金", "min_level": 60, "cost": 2000000, "yield_mul": 1.1, "variation_bonus": 0.05},
    "金":   {"next": "黑", "min_level": 70, "cost": 8000000, "yield_mul": 1.5, "variation_bonus": 0.10},
    "黑":   {"next": "",   "min_level": 99, "cost": 0,         "yield_mul": 2.0, "variation_bonus": 0.15},
}

# 主线任务链（新手引导 + 成长里程碑）
MAIN_QUESTS = [
    (1, "播种希望", 1, "种下第一颗萝卜种子", "经验+50、金币+100"),
    (2, "辛勤浇灌", 3, "完成5次浇水护理", "经验+120、萝卜种子×3"),
    (3, "丰收时刻", 5, "累计收获10次作物", "经验+200、金币+500"),
    (4, "偷菜有道", 8, "去好友家偷菜5次", "经验+150、普通化肥×2"),
    (5, "作物进阶", 12, "种植并收获番茄", "经验+300、番茄种子×5"),
    (6, "红土开荒", 28, "解锁红土地", "经验+1000、金币+2000"),
    (7, "社交达人", 35, "添加10位好友互访", "经验+800、有机化肥×1"),
    (8, "农场大亨", 50, "累计获得10万金币", "经验+5000、高级化肥×1、金土地资格"),
]

# 化肥系统
FERTILIZERS = {
    "normal":  {"name": "普通化肥", "item_key": "farm_fert_normal",  "speedup_sec": 60,  "uses": 1,  "cost": 200},
    "organic": {"name": "有机化肥", "item_key": "farm_fert_organic", "speedup_sec": 30,  "uses": 5,  "cost": 800},
    "premium": {"name": "高级化肥", "item_key": "farm_fert_premium", "speedup_sec": 120, "uses": 3,  "cost": 2000},
}

# 变异系统
VARIATIONS = {
    "爱心": {"yield_mul": 3.0, "price_mul": 1.0, "desc": "产量×3"},
    "湿润": {"yield_mul": 2.0, "price_mul": 1.0, "desc": "产量×2"},
    "暗化": {"yield_mul": 1.0, "price_mul": 2.0, "desc": "售价×2"},
    "冰冻": {"yield_mul": 1.0, "price_mul": 3.0, "desc": "售价×3"},
}

# 起点种子（新玩家初始背包）
STARTER_SEEDS = [
    {"code": "farm_seed_wheat", "name": "小麦种子", "qty": 10},
    {"code": "farm_seed_carrot", "name": "胡萝卜种子", "qty": 5},
]

STAGE_NAMES = ["", "种子", "发芽", "生长", "开花"]


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
    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
    return {
        "request": request,
        "user": user,
        "lang": lang,
        "theme": theme,
        "_": lambda key: t(key, lang),
        "unread_count": unread_count,
        "now": datetime.utcnow(),
        "platform_gcoin": wallet.g_coin if wallet else 0,
    }


def init_farm(user: User, db: Session):
    """确保农场档案与起始地块/种子已初始化"""
    if not user.farm:
        farm = FarmProfile(user_id=user.id)
        db.add(farm)
        db.flush()
        for i in range(6):
            db.add(FarmPlot(farm_id=farm.id, user_id=user.id, plot_no=i + 1))
        for s in STARTER_SEEDS:
            db.add(FarmStorage(
                farm_id=farm.id, user_id=user.id,
                item_code=s["code"], item_name=s["name"], item_type="seed", quantity=s["qty"],
            ))
        db.commit()
        db.refresh(farm)


def process_farm(farm: FarmProfile, db: Session):
    """推进地块 / 动物状态到期判定"""
    now = datetime.utcnow()
    for plot in farm.plots:
        if plot.crop_code and plot.ready_at and now >= plot.ready_at:
            plot.status = "ready"
    for animal in farm.animals:
        if animal.ready_at and now >= animal.ready_at:
            animal.production_ready = True


def get_crop(db: Session, crop_code):
    return db.query(Crop).filter(Crop.key == crop_code).first() if crop_code else None


def plot_stage(plot: FarmPlot, crop, now: datetime) -> str:
    """计算地块作物当前生长阶段"""
    if not plot.crop_code or not plot.planted_at or not crop:
        return "空地"
    if plot.ready_at and now >= plot.ready_at:
        return "成熟"
    total = crop.grow_seconds
    elapsed = (now - plot.planted_at).total_seconds()
    if total <= 0:
        return "成熟"
    idx = min(int(elapsed / (total / crop.stages)) + 1, crop.stages)
    return STAGE_NAMES[min(idx, len(STAGE_NAMES) - 1)] or f"阶段{idx}"


def remain_seconds(plot: FarmPlot, now: datetime) -> int:
    if not plot.crop_code or not plot.ready_at:
        return 0
    return max(0, int((plot.ready_at - now).total_seconds()))


def add_exp(db: Session, farm: FarmProfile, amount: int):
    """增加经验并处理升级（每级需 level*100 经验）"""
    farmland = farm
    farmland.farm_exp = (farmland.farm_exp or 0) + amount
    need = max(1, farmland.farm_level * 100)
    while farmland.farm_exp >= need:
        farmland.farm_exp -= need
        farmland.farm_level += 1
        farmland.land_count = min(6 + farmland.farm_level - 1, 18)
        need = farmland.farm_level * 100


# ============================================================
# 首页 / 列表 / 详情
# ============================================================

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def farm_home(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    init_farm(user, db)
    farm = user.farm
    process_farm(farm, db)
    db.commit()

    now = datetime.utcnow()
    plots = sorted(farm.plots, key=lambda p: p.plot_no)
    plot_info = []
    todo_count = 0
    for p in plots:
        crop = get_crop(db, p.crop_code)
        stage = plot_stage(p, crop, now)
        mature = stage == "成熟"
        if mature:
            todo_count += 1
        if p.insect_state:
            todo_count += 1
        plot_info.append({"plot": p, "crop": crop, "stage": stage,
                          "remain": remain_seconds(p, now), "mature": mature})

    ctx.update({
        "farm": farm,
        "plot_info": plot_info,
        "todo_count": todo_count,
        "animals": farm.animals,
        "storage": db.query(FarmStorage).filter(FarmStorage.user_id == user.id).all(),
    })
    return templates.TemplateResponse("sunny_farm/index.html", ctx)


@router.get("/plots", response_class=HTMLResponse)
def plots_list(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    init_farm(user, db)
    farm = user.farm
    process_farm(farm, db)
    db.commit()

    now = datetime.utcnow()
    plot_info = []
    for p in sorted(farm.plots, key=lambda p: p.plot_no):
        crop = get_crop(db, p.crop_code)
        stage = plot_stage(p, crop, now)
        plot_info.append({"plot": p, "crop": crop, "stage": stage,
                          "remain": remain_seconds(p, now), "mature": stage == "成熟"})
    ctx.update({"farm": farm, "plot_info": plot_info})
    return templates.TemplateResponse("sunny_farm/plots.html", ctx)


@router.get("/plot/{plot_no}", response_class=HTMLResponse)
def plot_detail(plot_no: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    init_farm(user, db)
    farm = user.farm

    plot = db.query(FarmPlot).filter(
        FarmPlot.farm_id == farm.id, FarmPlot.plot_no == plot_no).first()
    if not plot:
        return RedirectResponse(url="/sunny_farm/plots", status_code=302)

    now = datetime.utcnow()
    crop = get_crop(db, plot.crop_code)
    # 可选作物（空地时展示，含已持有种子数量）
    crops = db.query(Crop).order_by(Crop.level_req, Crop.price).all() if not plot.crop_code else []
    seeds = []
    if crops:
        for c in crops:
            item = db.query(FarmStorage).filter(
                FarmStorage.user_id == user.id,
                FarmStorage.item_code == c.seed_item_key,
                FarmStorage.quantity > 0).first()
            if item and item.quantity > 0:
                seeds.append((c, item.quantity))

    ctx.update({
        "farm": farm, "plot": plot, "crop": crop,
        "stage": plot_stage(plot, crop, now), "remain": remain_seconds(plot, now),
        "crops": crops, "seeds": seeds, "fertilizers": FERTILIZERS,
        "soil_grades": SOIL_GRADES,
    })
    return templates.TemplateResponse("sunny_farm/plot_detail.html", ctx)


# ============================================================
# 种植 / 护理 / 收获
# ============================================================

@router.post("/plant/{plot_no}")
def plant_crop(plot_no: int, request: Request, crop_key: str = Form(...),
               db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    init_farm(user, db)
    farm = user.farm

    crop = db.query(Crop).filter(Crop.key == crop_key).first()
    if not crop:
        return RedirectResponse(url=f"/sunny_farm/plot/{plot_no}?msg=作物不存在", status_code=302)

    plot = db.query(FarmPlot).filter(
        FarmPlot.farm_id == farm.id, FarmPlot.plot_no == plot_no).first()
    if not plot or plot.status != "idle":
        return RedirectResponse(url=f"/sunny_farm/plot/{plot_no}?msg=该地块不可种植", status_code=302)

    if farm.farm_level < crop.level_req:
        return RedirectResponse(
            url=f"/sunny_farm/plot/{plot_no}?msg=需达到Lv{crop.level_req}才能种植{crop.name}",
            status_code=302)

    ok = remove_item(user.id, MODULE_KEY, crop.seed_item_key, 1, db=db)
    if not ok:
        return RedirectResponse(url=f"/sunny_farm/plot/{plot_no}?msg=种子不足，去商店购买", status_code=302)

    plot.status = "growing"
    plot.crop_code = crop.key
    plot.crop_name = crop.name
    plot.planted_at = datetime.utcnow()
    plot.ready_at = datetime.utcnow() + timedelta(seconds=crop.grow_seconds)
    plot.stage = "种子"
    plot.water_count = 0
    plot.fertilizer_count = 0
    plot.insect_state = False
    plot.weed_state = False
    plot.variation = ""
    db.commit()
    return RedirectResponse(
        url=f"/sunny_farm/plot/{plot_no}?msg=种下了{crop.name}，约{crop.grow_seconds}秒成熟",
        status_code=302)


@router.post("/water/{plot_no}")
def water_plot(plot_no: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    init_farm(user, db)
    plot = db.query(FarmPlot).filter(
        FarmPlot.farm_id == user.farm.id, FarmPlot.plot_no == plot_no).first()
    if not plot or not plot.crop_code:
        return RedirectResponse(url=f"/sunny_farm/plot/{plot_no}?msg=没有作物可浇水", status_code=302)
    if plot.status == "ready":
        return RedirectResponse(url=f"/sunny_farm/plot/{plot_no}?msg=已成熟无需浇水", status_code=302)
    if plot.water_count >= 3:
        return RedirectResponse(url=f"/sunny_farm/plot/{plot_no}?msg=今天已浇够3次水了", status_code=302)
    plot.water_count += 1
    plot.ready_at -= timedelta(seconds=10)  # 浇水加速10秒
    db.commit()
    return RedirectResponse(url=f"/sunny_farm/plot/{plot_no}?msg=浇水成功，成长加速10秒", status_code=302)


@router.post("/deworm/{plot_no}")
def deworm(plot_no: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    init_farm(user, db)
    plot = db.query(FarmPlot).filter(
        FarmPlot.farm_id == user.farm.id, FarmPlot.plot_no == plot_no).first()
    if not plot or not plot.insect_state:
        return RedirectResponse(url=f"/sunny_farm/plot/{plot_no}?msg=没有虫害", status_code=302)
    plot.insect_state = False
    db.commit()
    return RedirectResponse(url=f"/sunny_farm/plot/{plot_no}?msg=除虫成功", status_code=302)


@router.post("/weed/{plot_no}")
def weed(plot_no: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    init_farm(user, db)
    plot = db.query(FarmPlot).filter(
        FarmPlot.farm_id == user.farm.id, FarmPlot.plot_no == plot_no).first()
    if not plot or not plot.weed_state:
        return RedirectResponse(url=f"/sunny_farm/plot/{plot_no}?msg=没有杂草", status_code=302)
    plot.weed_state = False
    db.commit()
    return RedirectResponse(url=f"/sunny_farm/plot/{plot_no}?msg=除草成功", status_code=302)


@router.post("/fertilize/{plot_no}")
def fertilize(plot_no: int, request: Request, fert_key: str = Form("normal"),
              db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    init_farm(user, db)
    farm = user.farm
    plot = db.query(FarmPlot).filter(
        FarmPlot.farm_id == farm.id, FarmPlot.plot_no == plot_no).first()
    if not plot or not plot.crop_code:
        return RedirectResponse(url=f"/sunny_farm/plot/{plot_no}?msg=没有作物可施肥", status_code=302)

    fert = FERTILIZERS.get(fert_key, FERTILIZERS["normal"])
    ok = remove_item(user.id, MODULE_KEY, fert["item_key"], 1, db=db)
    if not ok:
        return RedirectResponse(url=f"/sunny_farm/plot/{plot_no}?msg={fert['name']}不足，去商店购买", status_code=302)

    plot.ready_at -= timedelta(seconds=fert["speedup_sec"])
    plot.fertilizer_count += 1
    # 施肥概率触发变异（土地等级越高概率越大）
    var_msg = ""
    soil = SOIL_GRADES.get(plot.soil_type, SOIL_GRADES["普通"])
    if not plot.variation and random.random() < soil["variation_bonus"]:
        plot.variation = random.choice(list(VARIATIONS.keys()))
        var_msg = f"！触发了{plot.variation}变异（{VARIATIONS[plot.variation]['desc']}）"
    db.commit()
    return RedirectResponse(
        url=f"/sunny_farm/plot/{plot_no}?msg=施肥成功，加速{fert['speedup_sec']}秒{var_msg}",
        status_code=302)


@router.post("/harvest/{plot_no}")
def harvest(plot_no: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    init_farm(user, db)
    farm = user.farm
    plot = db.query(FarmPlot).filter(
        FarmPlot.farm_id == farm.id, FarmPlot.plot_no == plot_no).first()
    if not plot or not plot.crop_code:
        return RedirectResponse(url=f"/sunny_farm/plot/{plot_no}?msg=没有作物", status_code=302)
    crop = db.query(Crop).filter(Crop.key == plot.crop_code).first()
    if not crop:
        return RedirectResponse(url=f"/sunny_farm/plot/{plot_no}?msg=作物数据缺失", status_code=302)
    if plot.status != "ready":
        return RedirectResponse(url=f"/sunny_farm/plot/{plot_no}?msg=还未成熟", status_code=302)

    # 土地等级产量加成 + 变异产量
    soil = SOIL_GRADES.get(plot.soil_type, SOIL_GRADES["普通"])
    yield_amount = max(1, int(2 * soil["yield_mul"]))
    var_msg = ""
    if plot.variation:
        var = VARIATIONS.get(plot.variation, {"yield_mul": 1.0, "price_mul": 1.0, "desc": ""})
        yield_amount = max(1, int(yield_amount * var["yield_mul"]))
        var_msg = f"（变异·{plot.variation}：{var['desc']}）"

    add_item(user.id, MODULE_KEY, crop.harvest_item_key, crop.name, yield_amount,
             item_type="crop", db=db)
    add_exp(db, farm, crop.harvest_exp)
    add_notification(user.id, "system", "收获成功", f"收获了{crop.name}×{yield_amount}{var_msg}",
                     module_key=MODULE_KEY, db=db)

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
    plot.variation = ""
    db.commit()
    return RedirectResponse(
        url=f"/sunny_farm/plots?msg=收获{crop.name}×{yield_amount}{var_msg}，经验+{crop.harvest_exp}",
        status_code=302)


# ============================================================
# 土地升级 / 上锁 / 虫害演示
# ============================================================

@router.get("/soil", response_class=HTMLResponse)
def soil_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    init_farm(user, db)
    farm = user.farm
    ctx.update({
        "farm": farm,
        "plots": sorted(farm.plots, key=lambda p: p.plot_no),
        "soil_grades": SOIL_GRADES,
        "variations": VARIATIONS,
        "fertilizers": FERTILIZERS,
    })
    return templates.TemplateResponse("sunny_farm/soil.html", ctx)


@router.post("/soil/upgrade/{plot_no}")
def soil_upgrade(plot_no: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    init_farm(user, db)
    farm = user.farm
    plot = db.query(FarmPlot).filter(
        FarmPlot.farm_id == farm.id, FarmPlot.plot_no == plot_no).first()
    if not plot:
        return RedirectResponse(url="/sunny_farm/soil?msg=地块不存在", status_code=302)

    grade = SOIL_GRADES.get(plot.soil_type, SOIL_GRADES["普通"])
    nxt = grade["next"]
    if not nxt:
        return RedirectResponse(url="/sunny_farm/soil?msg=已是最高级黑土地", status_code=302)
    next_grade = SOIL_GRADES[nxt]
    if farm.farm_level < next_grade["min_level"]:
        return RedirectResponse(
            url=f"/sunny_farm/soil?msg=需达到{next_grade['min_level']}级才能升级", status_code=302)
    # 扣金币（金币不足则提示）
    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
    if not wallet or wallet.g_coin < next_grade["cost"]:
        return RedirectResponse(url="/sunny_farm/soil?msg=金币不足", status_code=302)
    change_currency(user.id, "g_coin", -next_grade["cost"], MODULE_KEY,
                    remark=f"地块{plot_no}升级为{nxt}土地", db=db)
    plot.soil_type = nxt
    db.commit()
    return RedirectResponse(
        url=f"/sunny_farm/soil?msg=地块{plot_no}升级为{nxt}土地！产量×{next_grade['yield_mul']}",
        status_code=302)


@router.post("/lock/{plot_no}")
def toggle_lock(plot_no: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    init_farm(user, db)
    plot = db.query(FarmPlot).filter(
        FarmPlot.farm_id == user.farm.id, FarmPlot.plot_no == plot_no).first()
    if plot:
        plot.locked = not plot.locked
        db.commit()
    return RedirectResponse(url=f"/sunny_farm/plot/{plot_no}", status_code=302)


@router.post("/pest/{plot_no}")
def trigger_pest(plot_no: int, request: Request, db: Session = Depends(get_db)):
    """（演示用）随机产生虫害"""
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    init_farm(user, db)
    plot = db.query(FarmPlot).filter(
        FarmPlot.farm_id == user.farm.id, FarmPlot.plot_no == plot_no).first()
    if plot and plot.crop_code:
        plot.insect_state = True
        db.commit()
    return RedirectResponse(url=f"/sunny_farm/plot/{plot_no}", status_code=302)


# ============================================================
# 种子商店 / 仓库出售
# ============================================================

@router.get("/shop", response_class=HTMLResponse)
def shop_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    init_farm(user, db)
    crops = db.query(Crop).order_by(Crop.level_req, Crop.price).all()
    # 玩家已持有的种子数
    seed_counts = {}
    for s in db.query(FarmStorage).filter(
            FarmStorage.user_id == user.id, FarmStorage.item_type == "seed").all():
        seed_counts[s.item_code] = s.quantity
    # 可售仓库物品（作物/产品，附单价）
    sell_map = {c.harvest_item_key: c.sell_price for c in crops}
    sell_items = []
    for s in db.query(FarmStorage).filter(
            FarmStorage.user_id == user.id,
            FarmStorage.item_type.in_(["crop", "product"])).all():
        if sell_map.get(s.item_code, 0) > 0:
            sell_items.append({"item": s, "price": sell_map[s.item_code]})
    ctx.update({"crops": crops, "seed_counts": seed_counts, "farm": user.farm,
                "storage": sell_items})
    return templates.TemplateResponse("sunny_farm/shop.html", ctx)


@router.post("/shop/buy")
def shop_buy(request: Request, crop_key: str = Form(...), quantity: int = Form(1),
             db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    init_farm(user, db)
    crop = db.query(Crop).filter(Crop.key == crop_key).first()
    if not crop:
        return RedirectResponse(url="/sunny_farm/shop?msg=作物不存在", status_code=302)
    quantity = max(1, min(quantity, 99))
    cost = crop.price * quantity
    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
    if not wallet or wallet.g_coin < cost:
        return RedirectResponse(url=f"/sunny_farm/shop?msg=金币不足，需要{cost}", status_code=302)
    change_currency(user.id, "g_coin", -cost, MODULE_KEY,
                    remark=f"购买{crop.name}种子×{quantity}", db=db)
    add_item(user.id, MODULE_KEY, crop.seed_item_key, f"{crop.name}种子", quantity,
             item_type="seed", db=db)
    db.commit()
    return RedirectResponse(url=f"/sunny_farm/shop?msg=购买{crop.name}种子×{quantity}成功", status_code=302)


@router.post("/shop/sell")
def shop_sell(request: Request, item_code: str = Form(...), quantity: int = Form(1),
              db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    init_farm(user, db)
    item = db.query(FarmStorage).filter(
        FarmStorage.user_id == user.id, FarmStorage.item_code == item_code).first()
    if not item or item.quantity <= 0:
        return RedirectResponse(url="/sunny_farm/shop?msg=仓库中没有该物品", status_code=302)
    quantity = max(1, min(quantity, item.quantity))
    # 售价：优先取作物字典 sell_price，否则按收获物 ItemFarm
    crop = db.query(Crop).filter(Crop.harvest_item_key == item_code).first()
    price = crop.sell_price if crop else 0
    if price <= 0:
        return RedirectResponse(url="/sunny_farm/shop?msg=该物品不能出售", status_code=302)
    item.quantity -= quantity
    if item.quantity <= 0:
        db.delete(item)
    change_currency(user.id, "g_coin", price * quantity, MODULE_KEY,
                    remark=f"出售{item.item_name}×{quantity}", db=db)
    db.commit()
    return RedirectResponse(url=f"/sunny_farm/shop?msg=出售{item.item_name}×{quantity}，获得{price * quantity}金币",
                            status_code=302)


# ============================================================
# 养殖（动物）
# ============================================================

ANIMALS = {
    "chicken": {"name": "小鸡", "price": 100, "product": "egg", "product_name": "鸡蛋",
                "product_price": 15, "grow_time": 300},
    "duck": {"name": "小鸭", "price": 150, "product": "duck_egg", "product_name": "鸭蛋",
             "product_price": 20, "grow_time": 360},
    "cow": {"name": "奶牛", "price": 500, "product": "milk", "product_name": "牛奶",
            "product_price": 50, "grow_time": 600},
}


@router.post("/buy_animal")
def buy_animal(request: Request, animal_code: str = Form(...), db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    init_farm(user, db)
    farm = user.farm
    animal_def = ANIMALS.get(animal_code)
    if not animal_def:
        return RedirectResponse(url="/sunny_farm?msg=动物不存在", status_code=302)
    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
    if not wallet or wallet.g_coin < animal_def["price"]:
        return RedirectResponse(url="/sunny_farm?msg=金币不足", status_code=302)
    if len(farm.animals) >= 8:
        return RedirectResponse(url="/sunny_farm?msg=动物栏已满", status_code=302)
    change_currency(user.id, "g_coin", -animal_def["price"], MODULE_KEY,
                    remark=f"购买{animal_def['name']}", db=db)
    db.add(FarmAnimal(
        farm_id=farm.id, user_id=user.id, animal_code=animal_code,
        animal_name=animal_def["name"], status="baby", hunger=100, health=100,
        ready_at=datetime.utcnow() + timedelta(seconds=animal_def["grow_time"]),
        shed_index=len(farm.animals),
    ))
    db.commit()
    return RedirectResponse(url=f"/sunny_farm?msg=购买了{animal_def['name']}", status_code=302)


@router.post("/feed/{animal_id}")
def feed_animal(animal_id: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    animal = db.query(FarmAnimal).filter(
        FarmAnimal.id == animal_id, FarmAnimal.user_id == user.id).first()
    if not animal:
        return RedirectResponse(url="/sunny_farm?msg=动物不存在", status_code=302)
    animal.hunger = min(100, (animal.hunger or 0) + 30)
    animal.health = min(100, (animal.health or 0) + 10)
    db.commit()
    return RedirectResponse(url=f"/sunny_farm?msg=喂养{animal.animal_name}成功", status_code=302)


@router.get("/collect_product/{animal_id}")
def collect_product(animal_id: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    animal = db.query(FarmAnimal).filter(
        FarmAnimal.id == animal_id, FarmAnimal.user_id == user.id).first()
    if not animal or not animal.production_ready:
        return RedirectResponse(url="/sunny_farm?msg=产品还未就绪", status_code=302)
    animal_def = ANIMALS.get(animal.animal_code)
    if animal_def:
        add_item(user.id, MODULE_KEY, animal_def["product"], animal_def["product_name"], 1,
                 item_type="product", db=db)
    animal.production_ready = False
    animal.ready_at = datetime.utcnow() + timedelta(seconds=(animal_def or ANIMALS["chicken"])["grow_time"])
    db.commit()
    if animal_def:
        return RedirectResponse(url=f"/sunny_farm?msg=收取了{animal_def['product_name']}×1", status_code=302)
    return RedirectResponse(url="/sunny_farm", status_code=302)


# ============================================================
# 好友互动：访问 + 偷菜
# ============================================================

def is_blocked(db: Session, target_user_id: int, actor_user_id: int) -> bool:
    """黑名单检查（拉黑彼此不可互访/偷菜）"""
    from models.models import UserBlacklist
    return db.query(UserBlacklist).filter(
        UserBlacklist.user_id == target_user_id,
        UserBlacklist.blocked_user_id == actor_user_id).first() is not None


def already_stolen(db: Session, thief_id: int, plot_id: int) -> bool:
    return db.query(FarmFriendAction).filter(
        FarmFriendAction.actor_user_id == thief_id,
        FarmFriendAction.target_plot_id == plot_id,
        FarmFriendAction.action_type == "steal").first() is not None


@router.get("/visit/{uid}", response_class=HTMLResponse)
def visit_farm(uid: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    if user.id == uid:
        return RedirectResponse(url="/sunny_farm", status_code=302)
    if is_blocked(db, uid, user.id):
        return RedirectResponse(url="/home/friends?msg=对方已拉黑你", status_code=302)
    host = db.query(User).filter(User.id == uid).first()
    if not host or not host.farm:
        return RedirectResponse(url="/home/friends?msg=对方还没有农场", status_code=302)

    now = datetime.utcnow()
    plot_info = []
    for p in sorted(host.farm.plots, key=lambda p: p.plot_no):
        crop = get_crop(db, p.crop_code)
        mature = plot_stage(p, crop, now) == "成熟"
        plot_info.append({"plot": p, "crop": crop, "mature": mature,
                          "locked": p.locked,
                          "already": already_stolen(db, user.id, p.id)})
    ctx.update({"host": host, "plot_info": plot_info})
    return templates.TemplateResponse("sunny_farm/visit.html", ctx)


@router.post("/steal/{plot_id}")
def steal(plot_id: int, request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    plot = db.query(FarmPlot).filter(FarmPlot.id == plot_id).first()
    if not plot:
        return RedirectResponse(url="/home/friends?msg=地块不存在", status_code=302)
    if plot.user_id == user.id:
        return RedirectResponse(url=f"/sunny_farm/visit/{plot.user_id}?msg=不能偷自己的", status_code=302)
    if is_blocked(db, plot.user_id, user.id):
        return RedirectResponse(url=f"/sunny_farm/visit/{plot.user_id}?msg=对方已拉黑你", status_code=302)
    if plot.locked:
        return RedirectResponse(url=f"/sunny_farm/visit/{plot.user_id}?msg=该地块已上锁，无法偷取", status_code=302)
    if already_stolen(db, user.id, plot.id):
        return RedirectResponse(url=f"/sunny_farm/visit/{plot.user_id}?msg=已经偷过这块地了", status_code=302)

    crop = db.query(Crop).filter(Crop.key == plot.crop_code).first() if plot.crop_code else None
    if not crop or plot.status != "ready":
        return RedirectResponse(url=f"/sunny_farm/visit/{plot.user_id}?msg=还没成熟呢", status_code=302)

    add_item(user.id, MODULE_KEY, crop.harvest_item_key, crop.name, 1, item_type="crop", db=db)
    db.add(FarmFriendAction(
        actor_user_id=user.id, target_user_id=plot.user_id, action_type="steal",
        target_plot_id=plot.id, reward_json=json.dumps({"item": crop.harvest_item_key, "amount": 1}),
    ))
    add_notification(plot.user_id, "interact", "被偷菜",
                     f"{user.nickname} 偷了你的 {crop.name} ×1", module_key=MODULE_KEY, db=db)
    db.commit()
    return RedirectResponse(
        url=f"/sunny_farm/visit/{plot.user_id}?msg=偷到{crop.name}×1，快溜！", status_code=302)


# ============================================================
# 规则 / 主线任务
# ============================================================

@router.get("/rules", response_class=HTMLResponse)
def rules(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    return templates.TemplateResponse("sunny_farm/rules.html", ctx)


@router.get("/mainquests", response_class=HTMLResponse)
def mainquests_list(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    user = ctx["user"]
    init_farm(user, db)
    ctx.update({"farm": user.farm, "quests": MAIN_QUESTS})
    return templates.TemplateResponse("sunny_farm/mainquests.html", ctx)