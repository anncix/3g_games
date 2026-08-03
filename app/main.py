"""QQ家园平台 FastAPI 入口"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from . import config
from .database import init_db
from .routers import (
    auth, profile, lobby, friends, family, forum, chat, city, message,
    activity, ranking, icons, settings as settings_router, support,
    inventory, shop, farm, town, garden, sea, summon, martial, fengyun, xyou, admin, api, story,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化数据库 + 种子数据
    await init_db()
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


@app.get("/health", tags=["健康检查"])
async def health():
    return {"status": "ok", "app": "qq_home", "version": config.VERSION}
