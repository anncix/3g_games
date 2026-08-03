"""聊天室 + 私聊"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..database import get_db
from ..deps import get_current_user
from ..platform import locks, friends as fsvc, log
from .views import render

router = APIRouter(prefix="/chat")


@router.get("")
async def chat_rooms(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    rooms = (await db.execute(select(models.ChatRoom))).scalars().all()
    return await render(request, "chat/rooms.html", db, user=user, rooms=rooms)


@router.get("/room/{room_id}")
async def chat_room(room_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    room = await db.get(models.ChatRoom, room_id)
    res = await db.execute(select(models.ChatRoomMessage, models.User).join(
        models.User, models.ChatRoomMessage.user_id == models.User.id
    ).where(models.ChatRoomMessage.room_id == room_id).order_by(models.ChatRoomMessage.created_at.desc()).limit(50))
    msgs = list(reversed(res.all()))
    return await render(request, "chat/room.html", db, user=user, room=room, msgs=msgs)


@router.post("/room/{room_id}")
async def post_room_msg(room_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    content = form.get("content", "").strip()
    if content:
        db.add(models.ChatRoomMessage(room_id=room_id, user_id=user.id, content=content[:500]))
        await db.commit()
    return RedirectResponse(f"/chat/room/{room_id}", status_code=303)


@router.get("/private/{uid}")
async def private_chat(uid: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    other = await db.get(models.User, uid)
    if not other:
        return RedirectResponse("/friends", status_code=303)
    if not await locks.can_chat(db, user.id, uid):
        return await render(request, "result.html", db, user=user, ok=False, msg="对方已关闭私聊或拉黑你", back_href="/friends", back_text="返回好友")
    res = await db.execute(select(models.ChatMessage).where(
        ((models.ChatMessage.from_id == user.id) & (models.ChatMessage.to_id == uid)) |
        ((models.ChatMessage.from_id == uid) & (models.ChatMessage.to_id == user.id))
    ).order_by(models.ChatMessage.created_at).limit(100))
    msgs = res.scalars().all()
    return await render(request, "chat/private.html", db, user=user, other=other, msgs=msgs)


@router.post("/private/{uid}")
async def send_private(uid: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if not await locks.can_chat(db, user.id, uid):
        return await render(request, "result.html", db, user=user, ok=False, msg="对方已关闭私聊", back_href="/friends", back_text="返回好友")
    form = await request.form()
    content = form.get("content", "").strip()
    if content:
        db.add(models.ChatMessage(from_id=user.id, to_id=uid, content=content[:500]))
        await db.commit()
    return RedirectResponse(f"/chat/private/{uid}", status_code=303)
