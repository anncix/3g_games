"""家族系统"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from ..platform import icons, events, log
from .views import render

router = APIRouter(prefix="/family", tags=["家族"])


@router.get("")
async def family_home(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    fm = (await db.execute(select(models.FamilyMember).where(models.FamilyMember.user_id == user.id))).scalar_one_or_none()
    family = None
    members = []
    if fm:
        family = await db.get(models.Family, fm.family_id)
        res = await db.execute(select(models.FamilyMember, models.User).join(
            models.User, models.FamilyMember.user_id == models.User.id
        ).where(models.FamilyMember.family_id == fm.family_id))
        members = res.all()
    # 家族列表（用于加入）
    families = []
    if not family:
        res = await db.execute(select(models.Family).limit(20))
        families = res.scalars().all()
    return await render(request, "family.html", db, user=user, family=family, members=members, fm=fm, families=families)


@router.post("/create")
async def create_family(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    name = form.get("name", "").strip()
    desc = form.get("description", "").strip()
    if not name:
        return await render(request, "result.html", db, user=user, ok=False, msg="家族名不能空", back_href="/family", back_text="返回")
    fm = (await db.execute(select(models.FamilyMember).where(models.FamilyMember.user_id == user.id))).scalar_one_or_none()
    if fm:
        return await render(request, "result.html", db, user=user, ok=False, msg="你已加入家族", back_href="/family", back_text="返回")
    fam = models.Family(name=name, leader_id=user.id, description=desc)
    db.add(fam)
    await db.commit()
    await db.refresh(fam)
    db.add(models.FamilyMember(family_id=fam.id, user_id=user.id, role="leader"))
    await db.commit()
    # 加入家族点亮图标
    await events.emit(db, user.id, "platform", "icon_light", {"icon_key": "icon_family"})
    await log.record(db, user.id, "platform", "create_family", name)
    return await render(request, "result.html", db, user=user, ok=True, msg=f"创建家族 {name} 成功", back_href="/family", back_text="返回家族")


@router.post("/join/{family_id}")
async def join_family(family_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    fm = (await db.execute(select(models.FamilyMember).where(models.FamilyMember.user_id == user.id))).scalar_one_or_none()
    if fm:
        return await render(request, "result.html", db, user=user, ok=False, msg="已加入家族", back_href="/family", back_text="返回")
    db.add(models.FamilyMember(family_id=family_id, user_id=user.id, role="member"))
    await db.commit()
    await events.emit(db, user.id, "platform", "icon_light", {"icon_key": "icon_family"})
    await log.record(db, user.id, "platform", "join_family", str(family_id))
    return RedirectResponse("/family", status_code=303)


@router.post("/leave")
async def leave_family(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    fm = (await db.execute(select(models.FamilyMember).where(models.FamilyMember.user_id == user.id))).scalar_one_or_none()
    if not fm:
        return RedirectResponse("/family", status_code=303)
    await db.delete(fm)
    await db.commit()
    return RedirectResponse("/family", status_code=303)
