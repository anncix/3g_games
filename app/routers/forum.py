"""论坛系统"""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from ..platform import events, log
from .views import render

router = APIRouter(prefix="/forum", tags=["论坛"])


@router.get("")
async def forum_home(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    boards = (await db.execute(select(models.ForumBoard).order_by(models.ForumBoard.sort))).scalars().all()
    return await render(request, "forum/home.html", db, user=user, boards=boards)


@router.get("/board/{board_id}")
async def board(board_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    board = await db.get(models.ForumBoard, board_id)
    res = await db.execute(select(models.ForumThread, models.User).join(
        models.User, models.ForumThread.author_id == models.User.id
    ).where(models.ForumThread.board_id == board_id).order_by(models.ForumThread.created_at.desc()))
    threads = res.all()
    return await render(request, "forum/board.html", db, user=user, board=board, threads=threads)


@router.get("/new/{board_id}")
async def new_thread_page(board_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    board = await db.get(models.ForumBoard, board_id)
    return await render(request, "forum/new.html", db, user=user, board=board)


@router.post("/new/{board_id}")
async def new_thread(board_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    title = form.get("title", "").strip()
    content = form.get("content", "").strip()
    if not title:
        return await render(request, "result.html", db, user=user, ok=False, msg="标题不能空", back_href=f"/forum/new/{board_id}", back_text="返回")
    t = models.ForumThread(board_id=board_id, author_id=user.id, title=title, content=content)
    db.add(t)
    await db.commit()
    # 论坛发帖成就
    await events.emit(db, user.id, "platform", "achievement", {"key": "achv_social", "delta": 0})
    await log.record(db, user.id, "platform", "forum_post", title[:20])
    # 累计发帖5次点亮图标
    count = (await db.execute(select(func.count(models.ForumThread.id)).where(models.ForumThread.author_id == user.id))).scalar() or 0
    if count >= 5:
        await events.emit(db, user.id, "platform", "icon_light", {"icon_key": "icon_forum"})
    return RedirectResponse(f"/forum/thread/{t.id}", status_code=303)


@router.get("/thread/{thread_id}")
async def thread(thread_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    t = await db.get(models.ForumThread, thread_id)
    if not t:
        raise HTTPException(404)
    t.views += 1
    await db.commit()
    author = await db.get(models.User, t.author_id)
    res = await db.execute(select(models.ForumPost, models.User).join(
        models.User, models.ForumPost.author_id == models.User.id
    ).where(models.ForumPost.thread_id == thread_id).order_by(models.ForumPost.created_at))
    posts = res.all()
    return await render(request, "forum/thread.html", db, user=user, t=t, author=author, posts=posts)


@router.post("/reply/{thread_id}")
async def reply(thread_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    t = await db.get(models.ForumThread, thread_id)
    if not t:
        raise HTTPException(404)
    form = await request.form()
    content = form.get("content", "").strip()
    if content:
        db.add(models.ForumPost(thread_id=thread_id, author_id=user.id, content=content[:500]))
        t.replies += 1
        await db.commit()
    return RedirectResponse(f"/forum/thread/{thread_id}", status_code=303)
