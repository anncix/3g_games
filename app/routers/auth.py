"""认证：注册 / 登录 / 登出（含 JSON API）"""
from fastapi import APIRouter, Request, Depends, Response, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models, config
from ..database import get_db
from ..deps import get_current_user, create_session, destroy_session, hash_password, verify_password, templates
from .views import render

router = APIRouter(tags=["账号"])


@router.get("/")
async def index(request: Request, db: AsyncSession = Depends(get_db)):
    """家园首页（中心枢纽）— 未登录跳登录"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    # 公告栏
    notice = "欢迎回到QQ家园！今天也要记得浇水收菜、给餐厅添油哦～"
    # 好友动态摘要（来访/留言摘要）
    from sqlalchemy import func
    visit_count = (await db.execute(
        select(func.count(models.Visit.id)).where(models.Visit.host_id == user.id)
    )).scalar() or 0
    gb_count = (await db.execute(
        select(func.count(models.Guestbook.id)).where(models.Guestbook.host_id == user.id)
    )).scalar() or 0
    # 家族摘要
    fm = (await db.execute(
        select(models.FamilyMember).where(models.FamilyMember.user_id == user.id)
    )).scalar_one_or_none()
    family = None
    if fm:
        family = await db.get(models.Family, fm.family_id)
    # 消息/活动提醒
    msg_unread = (await db.execute(
        select(func.count(models.Message.id)).where(
            models.Message.user_id == user.id, models.Message.is_read.is_(False)
        )
    )).scalar() or 0
    # 模块列表
    mods = (await db.execute(
        select(models.Module).where(models.Module.enabled.is_(True)).order_by(models.Module.sort)
    )).scalars().all()
    return await render(request, "home.html", db, user=user, notice=notice,
                        visit_count=visit_count, gb_count=gb_count, family=family, msg_unread=msg_unread, mods=mods)


@router.get("/login")
async def login_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if user:
        return RedirectResponse("/", status_code=303)
    return await render(request, "login.html", db, user=None)


@router.post("/login")
async def login(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    form = await request.form()
    username = form.get("username", "").strip()
    password = form.get("password", "")
    # 支持 JSON
    if not username:
        try:
            data = await request.json()
            username = data.get("username", "")
            password = data.get("password", "")
        except Exception:
            pass
    res = await db.execute(select(models.User).where(models.User.username == username))
    user = res.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        if request.headers.get("accept", "").startswith("application/json"):
            raise HTTPException(401, "用户名或密码错误")
        return await render(request, "result.html", db, user=None, ok=False, msg="用户名或密码错误", back_href="/login", back_text="返回登录")
    user.last_login = __import__("datetime").datetime.utcnow()
    token = await create_session(db, user.id)
    if request.headers.get("accept", "").startswith("application/json"):
        return {"token": token, "user_id": user.id, "nickname": user.nickname}
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(config.SESSION_COOKIE, token, httponly=True, max_age=config.SESSION_TTL_SECONDS)
    return resp


@router.get("/register")
async def register_page(request: Request, db: AsyncSession = Depends(get_db)):
    return await render(request, "register.html", db, user=None)


@router.post("/register")
async def register(request: Request, db: AsyncSession = Depends(get_db)):
    form = await request.form()
    username = form.get("username", "").strip()
    password = form.get("password", "")
    nickname = form.get("nickname", "").strip() or username
    city = form.get("city", "").strip()
    if len(username) < 3 or len(password) < 4:
        return await render(request, "result.html", db, user=None, ok=False, msg="用户名≥3位，密码≥4位", back_href="/register", back_text="返回注册")
    res = await db.execute(select(models.User).where(models.User.username == username))
    if res.scalar_one_or_none():
        return await render(request, "result.html", db, user=None, ok=False, msg="用户名已存在", back_href="/register", back_text="返回注册")
    user = models.User(username=username, password_hash=hash_password(password), nickname=nickname, city=city)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = await create_session(db, user.id)
    from fastapi.responses import Response
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(config.SESSION_COOKIE, token, httponly=True, max_age=config.SESSION_TTL_SECONDS)
    return resp


@router.post("/logout")
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get(config.SESSION_COOKIE)
    if token:
        await destroy_session(db, token)
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(config.SESSION_COOKIE)
    return resp
