"""阳光农场模块

老味道点：成长计时 / 护理(浇水除虫施肥) / 偷菜互助 / 回访节奏
对应规范：模块首页必备(进度/待办/快捷入口) / 页面树约束 / 背包分页 / 事件上报 / 消息模板 / 排行 / 安全风控
"""
from datetime import datetime, timedelta
import json

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from ..platform import goods, icons, events, locks, friends as fsvc, log, ranking
from .views import render

router = APIRouter(prefix="/games/farm", tags=["阳光农场"])
MODULE_KEY = "farm"

# v0.2.1：土地等级系统（spec：普通→红→金→黑土地，来源 baike.com 红土地百科 + youxiabc.com 攻略）
# 普通(基础) → 红土地(28级,普通作物+10%) → 金土地(60级,+50%) → 黑土地(+100%)
SOIL_GRADES = {
    "普通": {"next": "红", "min_level": 28, "cost": 200000, "yield_mul": 1.0, "variation_bonus": 0.0},
    "红":   {"next": "金", "min_level": 60, "cost": 2000000, "yield_mul": 1.1, "variation_bonus": 0.05},
    "金":   {"next": "黑", "min_level": 70, "cost": 8000000, "yield_mul": 1.5, "variation_bonus": 0.10},
    "黑":   {"next": "",   "min_level": 99, "cost": 0,         "yield_mul": 2.0, "variation_bonus": 0.15},
}

# v0.2.6 主线任务链（新手引导 + 成长里程碑，来源：阳光农场原版玩法 + baike.com 词条）
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

# 化肥系统（spec：普通化肥缩短成熟时间/有机化肥多次使用，来源 youxiabc.com 攻略）
FERTILIZERS = {
    "normal":  {"name": "普通化肥", "item_key": "farm_fert_normal",  "speedup_sec": 60,  "uses": 1,  "cost": 200},
    "organic": {"name": "有机化肥", "item_key": "farm_fert_organic", "speedup_sec": 30,  "uses": 5,  "cost": 800},
    "premium": {"name": "高级化肥", "item_key": "farm_fert_premium", "speedup_sec": 120, "uses": 3,  "cost": 2000},
}

# 变异系统（spec：4种变异效果，可叠加双变异，来源 QQ经典农场频道攻略）
VARIATIONS = {
    "爱心": {"yield_mul": 3.0, "price_mul": 1.0, "desc": "产量×3"},
    "湿润": {"yield_mul": 2.0, "price_mul": 1.0, "desc": "产量×2"},
    "暗化": {"yield_mul": 1.0, "price_mul": 2.0, "desc": "售价×2"},
    "冰冻": {"yield_mul": 1.0, "price_mul": 3.0, "desc": "售价×3"},
}


async def get_state(db: AsyncSession, user_id: int) -> models.FarmState:
    st = await db.get(models.FarmState, user_id)
    if not st:
        st = models.FarmState(user_id=user_id)
        db.add(st)
        await db.flush()  # 应用默认值
        # 初始化地块
        for i in range(st.plot_count):
            db.add(models.FarmPlot(user_id=user_id, slot=i))
        await db.commit()
        await db.refresh(st)
    return st


def crop_stage(plot: models.FarmPlot, crop: models.Crop | None) -> str:
    """计算当前阶段名称"""
    if not plot.crop_key or not plot.planted_at or not crop:
        return "空地"
    elapsed = (datetime.utcnow() - plot.planted_at).total_seconds()
    if elapsed >= crop.grow_seconds:
        return "成熟"
    stage_idx = min(int(elapsed / (crop.grow_seconds / crop.stages)) + 1, crop.stages)
    names = ["", "种子", "发芽", "生长", "开花"]
    return names[min(stage_idx, len(names)-1)] or f"阶段{stage_idx}"


def remain_seconds(plot: models.FarmPlot, crop: models.Crop | None) -> int:
    if not plot.crop_key or not plot.planted_at or not crop:
        return 0
    elapsed = (datetime.utcnow() - plot.planted_at).total_seconds()
    return max(0, int(crop.grow_seconds - elapsed))


@router.get("")
async def farm_home(request: Request, db: AsyncSession = Depends(get_db)):
    """模块首页：进度 / 今日待办 / 快捷入口"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    plots = (await db.execute(
        select(models.FarmPlot).where(models.FarmPlot.user_id == user.id).order_by(models.FarmPlot.slot)
    )).scalars().all()
    # 组装地块信息
    plot_info = []
    todo_count = 0
    for p in plots:
        crop = await db.get(models.Crop, p.crop_key) if p.crop_key else None
        stage = crop_stage(p, crop)
        rem = remain_seconds(p, crop)
        mature = stage == "成熟"
        if mature:
            todo_count += 1
        if p.pest:
            todo_count += 1
        plot_info.append({"plot": p, "crop": crop, "stage": stage, "remain": rem, "mature": mature})
    return await render(request, "farm/home.html", db, user=user, st=st, plot_info=plot_info, todo_count=todo_count)


@router.get("/plots")
async def plots_list(request: Request, db: AsyncSession = Depends(get_db)):
    """列表页：我的农田"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    plots = (await db.execute(
        select(models.FarmPlot).where(models.FarmPlot.user_id == user.id).order_by(models.FarmPlot.slot)
    )).scalars().all()
    plot_info = []
    for p in plots:
        crop = await db.get(models.Crop, p.crop_key) if p.crop_key else None
        locked = await locks.is_item_locked(db, user.id, MODULE_KEY, f"plot_{p.slot}")
        plot_info.append({"plot": p, "crop": crop, "stage": crop_stage(p, crop),
                          "remain": remain_seconds(p, crop), "locked": locked})
    crops = (await db.execute(select(models.Crop))).scalars().all()
    return await render(request, "farm/plots.html", db, user=user, st=st, plot_info=plot_info, crops=crops)


@router.get("/plot/{slot}")
async def plot_detail(slot: int, request: Request, db: AsyncSession = Depends(get_db)):
    """详情页：单块地"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    res = await db.execute(
        select(models.FarmPlot).where(models.FarmPlot.user_id == user.id, models.FarmPlot.slot == slot))
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "地块不存在")
    crop = await db.get(models.Crop, p.crop_key) if p.crop_key else None
    locked = await locks.is_item_locked(db, user.id, MODULE_KEY, f"plot_{p.slot}")
    crops = (await db.execute(select(models.Crop))).scalars().all() if not p.crop_key else []
    # 库存种子数
    seeds = []
    for c in (crops if crops else []):
        n = await goods.count_item(db, user.id, c.seed_item_key, MODULE_KEY)
        if n > 0:
            seeds.append((c, n))
    return await render(request, "farm/plot_detail.html", db, user=user, plot=p, crop=crop,
                        stage=crop_stage(p, crop), remain=remain_seconds(p, crop),
                        locked=locked, crops=crops, seeds=seeds)


@router.post("/plant/{slot}")
async def plant(slot: int, request: Request, db: AsyncSession = Depends(get_db)):
    """操作页：种植"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    await get_state(db, user.id)  # 确保地块已初始化
    form = await request.form()
    crop_key = form.get("crop_key")
    crop = await db.get(models.Crop, crop_key)
    if not crop:
        return await render(request, "result.html", db, user=user, ok=False, msg="作物不存在", back_href=f"/games/farm/plot/{slot}", back_text="返回地块")
    ok = await goods.remove_item(db, user.id, crop.seed_item_key, MODULE_KEY, 1)
    if not ok:
        return await render(request, "result.html", db, user=user, ok=False, msg="种子不足，去商店购买", back_href="/shop", back_text="去商店")
    res = await db.execute(select(models.FarmPlot).where(
        models.FarmPlot.user_id == user.id, models.FarmPlot.slot == slot))
    p = res.scalar_one_or_none()
    if not p:
        return await render(request, "result.html", db, user=user, ok=False, msg="地块不存在", back_href="/games/farm/plots", back_text="返回农田")
    p.crop_key = crop_key
    p.planted_at = datetime.utcnow()
    p.watered = False
    p.pest = False
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "plant", f"slot{slot}:{crop_key}")
    return await render(request, "result.html", db, user=user, ok=True, msg=f"种下了{crop.name}，约{crop.grow_seconds}秒成熟", back_href=f"/games/farm/plot/{slot}", back_text="返回地块")


@router.post("/water/{slot}")
async def water(slot: int, request: Request, db: AsyncSession = Depends(get_db)):
    """护理：浇水（加速成长，简化为缩短时间）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    res = await db.execute(select(models.FarmPlot).where(
        models.FarmPlot.user_id == user.id, models.FarmPlot.slot == slot))
    p = res.scalar_one_or_none()
    if not p or not p.crop_key:
        return await render(request, "result.html", db, user=user, ok=False, msg="没有作物可浇水", back_href="/games/farm/plots", back_text="返回农田")
    if p.watered:
        return await render(request, "result.html", db, user=user, ok=False, msg="已经浇过水了", back_href=f"/games/farm/plot/{slot}", back_text="返回地块")
    p.watered = True
    # 浇水加速10秒
    p.planted_at = p.planted_at - timedelta(seconds=10)
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "water", f"slot{slot}")
    return await render(request, "result.html", db, user=user, ok=True, msg="浇水成功，成长加速10秒", back_href=f"/games/farm/plot/{slot}", back_text="返回地块")


@router.post("/deworm/{slot}")
async def deworm(slot: int, request: Request, db: AsyncSession = Depends(get_db)):
    """护理：除虫"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    res = await db.execute(select(models.FarmPlot).where(
        models.FarmPlot.user_id == user.id, models.FarmPlot.slot == slot))
    p = res.scalar_one_or_none()
    if not p or not p.pest:
        return await render(request, "result.html", db, user=user, ok=False, msg="没有虫害", back_href=f"/games/farm/plot/{slot}", back_text="返回地块")
    p.pest = False
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "deworm", f"slot{slot}")
    return await render(request, "result.html", db, user=user, ok=True, msg="除虫成功", back_href=f"/games/farm/plot/{slot}", back_text="返回地块")


@router.post("/harvest/{slot}")
async def harvest(slot: int, request: Request, db: AsyncSession = Depends(get_db)):
    """操作页：收获（v0.2.1：土地等级加成 + 变异效果）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    res = await db.execute(select(models.FarmPlot).where(
        models.FarmPlot.user_id == user.id, models.FarmPlot.slot == slot))
    p = res.scalar_one_or_none()
    if not p or not p.crop_key:
        return await render(request, "result.html", db, user=user, ok=False, msg="没有作物", back_href="/games/farm/plots", back_text="返回农田")
    crop = await db.get(models.Crop, p.crop_key)
    if crop_stage(p, crop) != "成熟":
        return await render(request, "result.html", db, user=user, ok=False, msg="还未成熟", back_href=f"/games/farm/plot/{slot}", back_text="返回地块")
    # v0.2.1：土地等级产量加成
    soil = SOIL_GRADES.get(p.soil_type, SOIL_GRADES["普通"])
    base_yield = 2
    yield_amount = max(1, int(base_yield * soil["yield_mul"]))
    # v0.2.1：变异效果
    var_msg = ""
    if p.variation:
        var = VARIATIONS.get(p.variation, {"yield_mul": 1.0, "price_mul": 1.0, "desc": ""})
        yield_amount = max(1, int(yield_amount * var["yield_mul"]))
        var_msg = f"（变异·{p.variation}：{var['desc']}）"
    await goods.add_item(db, user.id, crop.harvest_item_key, MODULE_KEY, yield_amount)
    st = await get_state(db, user.id)
    st.exp += crop.harvest_exp
    need = st.level * 100
    if st.exp >= need:
        st.exp -= need
        st.level += 1
    st.harvest_count += 1  # v0.1.2：真实收获计数（图标触发用）
    p.crop_key = ""
    p.planted_at = None
    p.watered = False
    p.pest = False
    p.variation = ""  # 收获后变异清空
    await db.commit()
    # 事件上报：图标/成就/排行
    await events.emit(db, user.id, MODULE_KEY, "achievement", {"key": "achv_first_harvest", "delta": 1})
    # v0.1.2：累计收获达10次点亮"勤劳农夫"图标（spec：收获10次作物）
    if st.harvest_count >= 10:
        await events.emit(db, user.id, MODULE_KEY, "icon_light", {"icon_key": "icon_farmer"})
    await events.emit(db, user.id, MODULE_KEY, "ranking", {"metric": "harvest", "score": 1, "period": "total"})
    await log.record(db, user.id, MODULE_KEY, "harvest", f"slot{slot}:{crop.key}")
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"收获{crop.name}×{yield_amount}{var_msg}，经验+{crop.harvest_exp}", back_href="/games/farm/plots", back_text="返回农田")


# ---------------- v0.2.1：土地升级 + 化肥 ----------------
@router.get("/soil")
async def soil_page(request: Request, db: AsyncSession = Depends(get_db)):
    """土地等级系统页"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    plots = (await db.execute(
        select(models.FarmPlot).where(models.FarmPlot.user_id == user.id).order_by(models.FarmPlot.slot)
    )).scalars().all()
    return await render(request, "farm/soil.html", db, user=user, st=st, plots=plots,
                        soil_grades=SOIL_GRADES, variations=VARIATIONS, fertilizers=FERTILIZERS)


@router.post("/soil/upgrade/{slot}")
async def soil_upgrade(slot: int, request: Request, db: AsyncSession = Depends(get_db)):
    """升级土地等级（普通→红→金→黑）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    res = await db.execute(select(models.FarmPlot).where(
        models.FarmPlot.user_id == user.id, models.FarmPlot.slot == slot))
    p = res.scalar_one_or_none()
    if not p:
        return await render(request, "result.html", db, user=user, ok=False, msg="地块不存在", back_href="/games/farm/soil", back_text="返回土地")
    st = await get_state(db, user.id)
    grade = SOIL_GRADES.get(p.soil_type, SOIL_GRADES["普通"])
    nxt = grade["next"]
    if not nxt:
        return await render(request, "result.html", db, user=user, ok=False, msg="已是最高级黑土地", back_href="/games/farm/soil", back_text="返回土地")
    next_grade = SOIL_GRADES[nxt]
    if st.level < next_grade["min_level"]:
        return await render(request, "result.html", db, user=user, ok=False, msg=f"需达到{next_grade['min_level']}级才能升级", back_href="/games/farm/soil", back_text="返回土地")
    # 扣金币（用 harvest_count * level 模拟金币，或检查是否有金币系统）
    # 简化：直接升级，不扣金币（农场模块无独立金币字段）
    p.soil_type = nxt
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "soil_upgrade", f"slot{slot}:{nxt}")
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"地块{slot}升级为{p.soil_type}土地！产量×{next_grade['yield_mul']}", back_href="/games/farm/soil", back_text="返回土地")


@router.post("/fertilize/{slot}")
async def fertilize(slot: int, request: Request, db: AsyncSession = Depends(get_db)):
    """施肥（消耗化肥道具，缩短成熟时间）"""
    import random
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    fert_key = form.get("fert_key", "normal")
    fert = FERTILIZERS.get(fert_key, FERTILIZERS["normal"])
    res = await db.execute(select(models.FarmPlot).where(
        models.FarmPlot.user_id == user.id, models.FarmPlot.slot == slot))
    p = res.scalar_one_or_none()
    if not p or not p.crop_key:
        return await render(request, "result.html", db, user=user, ok=False, msg="没有作物可施肥", back_href="/games/farm/soil", back_text="返回土地")
    # 消耗化肥道具
    ok = await goods.remove_item(db, user.id, fert["item_key"], MODULE_KEY, 1)
    if not ok:
        return await render(request, "result.html", db, user=user, ok=False, msg=f"{fert['name']}不足，去商店购买", back_href="/shop", back_text="去商店")
    # 加速成熟
    p.planted_at = p.planted_at - timedelta(seconds=fert["speedup_sec"])
    # v0.2.1：施肥有概率触发变异（土地等级越高概率越大）
    soil = SOIL_GRADES.get(p.soil_type, SOIL_GRADES["普通"])
    if not p.variation and random.random() < soil["variation_bonus"]:
        p.variation = random.choice(list(VARIATIONS.keys()))
        var = VARIATIONS[p.variation]
        await db.commit()
        await log.record(db, user.id, MODULE_KEY, "fertilize", f"slot{slot}:{fert_key}+变异{p.variation}")
        return await render(request, "result.html", db, user=user, ok=True,
                            msg=f"施肥成功，加速{fert['speedup_sec']}秒！触发了{p.variation}变异（{var['desc']}）", back_href=f"/games/farm/plot/{slot}", back_text="返回地块")
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "fertilize", f"slot{slot}:{fert_key}")
    return await render(request, "result.html", db, user=user, ok=True,
                        msg=f"施肥成功，加速{fert['speedup_sec']}秒", back_href=f"/games/farm/plot/{slot}", back_text="返回地块")


@router.post("/lock/{slot}")
async def toggle_lock(slot: int, request: Request, db: AsyncSession = Depends(get_db)):
    """物品锁：上锁的地块禁止被偷"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    locked = await locks.toggle_item_lock(db, user.id, MODULE_KEY, f"plot_{slot}")
    await log.record(db, user.id, MODULE_KEY, "lock", f"slot{slot}:{locked}")
    return RedirectResponse(f"/games/farm/plot/{slot}", status_code=303)


@router.post("/pest/{slot}")
async def trigger_pest(slot: int, request: Request, db: AsyncSession = Depends(get_db)):
    """（演示用）随机产生虫害"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    res = await db.execute(select(models.FarmPlot).where(
        models.FarmPlot.user_id == user.id, models.FarmPlot.slot == slot))
    p = res.scalar_one_or_none()
    if p and p.crop_key:
        p.pest = True
        await db.commit()
    return RedirectResponse(f"/games/farm/plot/{slot}", status_code=303)


# ---------------- 好友互动：偷菜 ----------------
@router.get("/visit/{uid}")
async def visit_farm(uid: int, request: Request, db: AsyncSession = Depends(get_db)):
    """访问好友农场（受黑名单/隐私约束）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if await fsvc.is_blocked(db, uid, user.id):
        return await render(request, "result.html", db, user=user, ok=False, msg="对方已拉黑你", back_href="/friends", back_text="返回好友")
    host = await db.get(models.User, uid)
    plots = (await db.execute(
        select(models.FarmPlot).where(models.FarmPlot.user_id == uid).order_by(models.FarmPlot.slot)
    )).scalars().all()
    plot_info = []
    for p in plots:
        crop = await db.get(models.Crop, p.crop_key) if p.crop_key else None
        mature = crop_stage(p, crop) == "成熟"
        locked = await locks.is_item_locked(db, uid, MODULE_KEY, f"plot_{p.slot}")
        already = await _already_stolen(db, user.id, p.id)
        plot_info.append({"plot": p, "crop": crop, "mature": mature, "locked": locked, "already": already})
    return await render(request, "farm/visit.html", db, user=user, host=host, plot_info=plot_info)


async def _already_stolen(db: AsyncSession, thief_id: int, plot_id: int) -> bool:
    res = await db.execute(select(models.FarmStealLog).where(
        models.FarmStealLog.thief_id == thief_id, models.FarmStealLog.plot_id == plot_id))
    return res.scalar_one_or_none() is not None


@router.post("/steal/{plot_id}")
async def steal(plot_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """偷菜（受物品锁约束，每人每块地限偷1次）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    p = await db.get(models.FarmPlot, plot_id)
    if not p:
        raise HTTPException(404)
    if p.user_id == user.id:
        return await render(request, "result.html", db, user=user, ok=False, msg="不能偷自己的", back_href="/games/farm", back_text="返回")
    if await fsvc.is_blocked(db, p.user_id, user.id):
        return await render(request, "result.html", db, user=user, ok=False, msg="对方已拉黑你", back_href="/friends", back_text="返回好友")
    if await locks.is_item_locked(db, p.user_id, MODULE_KEY, f"plot_{p.slot}"):
        return await render(request, "result.html", db, user=user, ok=False, msg="🔒 该地块已上锁，无法偷取", back_href=f"/games/farm/visit/{p.user_id}", back_text="返回")
    if await _already_stolen(db, user.id, p.id):
        return await render(request, "result.html", db, user=user, ok=False, msg="已经偷过这块地了", back_href=f"/games/farm/visit/{p.user_id}", back_text="返回")
    crop = await db.get(models.Crop, p.crop_key) if p.crop_key else None
    if not crop or crop_stage(p, crop) != "成熟":
        return await render(request, "result.html", db, user=user, ok=False, msg="还没成熟呢", back_href=f"/games/farm/visit/{p.user_id}", back_text="返回")
    await goods.add_item(db, user.id, crop.harvest_item_key, MODULE_KEY, 1)
    db.add(models.FarmStealLog(plot_id=p.id, thief_id=user.id, item_key=crop.harvest_item_key, amount=1))
    # 互动提醒消息模板
    await events.emit(db, user.id, MODULE_KEY, "interact_notify",
                      {"to_id": p.user_id, "title": "被偷菜", "content": f"{user.nickname} 偷了你的 {crop.name} ×1"})
    await db.commit()
    await log.record(db, user.id, MODULE_KEY, "steal", f"plot{plot_id}:{crop.key}")
    return await render(request, "result.html", db, user=user, ok=True, msg=f"偷到{crop.name}×1，快溜！", back_href=f"/games/farm/visit/{p.user_id}", back_text="继续逛")


@router.get("/rules")
async def rules(request: Request, db: AsyncSession = Depends(get_db)):
    """规则页"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return await render(request, "farm/rules.html", db, user=user)


# ---------- v0.2.6 主线任务链 ----------
@router.get("/mainquests")
async def mainquests_list(request: Request, db: AsyncSession = Depends(get_db)):
    """列表页：8 条主线任务链（新手引导 + 成长里程碑）"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    st = await get_state(db, user.id)
    return await render(request, "farm/mainquests.html", db, user=user, st=st, quests=MAIN_QUESTS)
