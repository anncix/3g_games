"""依赖注入：当前用户 / 数据库会话 / 模板"""
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, Request, HTTPException, status
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import config
from .database import get_db, SessionLocal
from . import models

templates = Jinja2Templates(directory=str(config.BASE_DIR / "app" / "templates"))


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """从 cookie token 解析当前用户；未登录返回 None（页面自行决定跳转）"""
    token = request.cookies.get(config.SESSION_COOKIE)
    if not token:
        return None
    sess = await db.get(models.Session, token)
    if not sess or sess.expires_at < datetime.utcnow():
        return None
    user = await db.get(models.User, sess.user_id)
    return user


async def require_user(user=Depends(get_current_user)):
    """强制要求登录"""
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    return user


async def require_admin(user=Depends(require_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


# ---------------- 会话管理 ----------------
async def create_session(db: AsyncSession, user_id: int) -> str:
    token = secrets.token_hex(16)
    sess = models.Session(
        token=token,
        user_id=user_id,
        expires_at=datetime.utcnow() + timedelta(seconds=config.SESSION_TTL_SECONDS),
    )
    db.add(sess)
    await db.commit()
    return token


async def destroy_session(db: AsyncSession, token: str):
    sess = await db.get(models.Session, token)
    if sess:
        await db.delete(sess)
        await db.commit()


# ---------------- 密码哈希（直接使用 bcrypt，兼容 4.x；不可用时降级 sha256） ----------------
import hashlib

try:
    import bcrypt as _bcrypt

    def hash_password(p: str) -> str:
        # bcrypt 限制 72 字节，截断处理
        return _bcrypt.hashpw(p.encode("utf-8")[:72], _bcrypt.gensalt()).decode("utf-8")

    def verify_password(p: str, h: str) -> bool:
        try:
            if h.startswith("sha256$"):
                return h == "sha256$" + hashlib.sha256(p.encode()).hexdigest()
            return _bcrypt.checkpw(p.encode("utf-8")[:72], h.encode("utf-8"))
        except Exception:
            return False
except Exception:  # pragma: no cover

    def hash_password(p: str) -> str:
        return "sha256$" + hashlib.sha256(p.encode()).hexdigest()

    def verify_password(p: str, h: str) -> bool:
        if h.startswith("sha256$"):
            return h == "sha256$" + hashlib.sha256(p.encode()).hexdigest()
        return False
