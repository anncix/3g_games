"""QQ家园平台 FastAPI 入口"""
import os
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from sqlalchemy import delete

from . import config
from .database import init_db
from .routers import (
    auth, profile, lobby, friends, family, forum, chat, city, message,
    activity, ranking, icons, settings as settings_router, support,
    inventory, shop, farm, town, garden, sea, summon, martial, fengyun, xyou, admin, api, story,
)


async def _cleanup_expired_sessions(db) -> int:
    """v0.3.1 启动时清理过期会话（sessions 表只增不删问题）。返回清理条数。"""
    from . import models
    result = await db.execute(
        delete(models.Session).where(models.Session.expires_at < datetime.utcnow())
    )
    await db.commit()
    return result.rowcount


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化数据库
    await init_db()
    from .database import SessionLocal
    # v0.3.1 启动清理过期会话
    async with SessionLocal() as db:
        await _cleanup_expired_sessions(db)
    # 种子数据（受 SEED_ON_START 开关控制，生产建议关）
    if config.SEED_ON_START:
        from . import seed
        await seed.seed()
    yield


app = FastAPI(title="QQ家园 - 怀旧平台复刻", version=config.VERSION, lifespan=lifespan)

# 静态资源
app.mount("/static", StaticFiles(directory=str(config.BASE_DIR / "app" / "static")), name="static")

# 注册路由
routers = [
    auth.router, profile.router, lobby.router, friends.router, family.router,
    forum.router, chat.router, city.router, message.router, activity.router,
    ranking.router, icons.router, settings_router.router, support.router,
    inventory.router, shop.router,
    farm.router, town.router, garden.router, sea.router, summon.router,
    martial.router,
    fengyun.router,
    xyou.router,
    admin.router, api.router,
    story.router,
]
for r in routers:
    app.include_router(r)


@app.exception_handler(404)
async def not_found(request: Request, exc):
    from .deps import get_current_user
    from .database import SessionLocal
    async with SessionLocal() as db:
        user = await get_current_user(request, db)
    from .routers.views import render
    return await render(request, "result.html", db=None, user=user, ok=False, msg="页面不存在 (404)", back_href="/", back_text="回首页")


@app.exception_handler(500)
async def server_error(request: Request, exc):
    """v0.3.1 500 错误页：返回 WAP 风格错误页而非 Starlette 默认 JSON。"""
    from .deps import get_current_user
    from .database import SessionLocal
    try:
        async with SessionLocal() as db:
            user = await get_current_user(request, db)
    except Exception:
        user = None
    from .routers.views import render
    return await render(request, "result.html", db=None, user=user, ok=False,
                        msg="服务器开小差了 (500)，请稍后重试", back_href="/", back_text="回首页")


@app.get("/health", tags=["健康检查"])
async def health():
    return {"status": "ok", "app": "qq_home", "version": config.VERSION}
