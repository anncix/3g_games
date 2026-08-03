"""数据库引擎与会话"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from . import config


class Base(DeclarativeBase):
    pass


engine = create_async_engine(config.DB_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with SessionLocal() as db:
        yield db


async def init_db():
    import os
    os.makedirs(config.DB_PATH.parent, exist_ok=True)
    from . import models  # noqa: F401  ensure models imported
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
