from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from datetime import datetime, date
import json

from models.database import get_db
from models.models import (
    User, MessageBoardPost, HomepageVisit, Family, FamilyMember, FamilySignin,
    FamilyChatMessage, Forum, ForumTopic, ForumPost,
    Notification, Wallet, FriendRequest, UserBlacklist,
    InventoryItem, ShopItem, UserIcon, IconDef, Achievement, UserAchievement,
    HomepageModule, UserHomepageModule, Announcement, ChatRoom, ChatMessage,
    City, CityFeed
)
from utils.auth import get_current_user
from utils.i18n import t
from utils.common import change_currency, add_item, add_notification, fire_event

router = APIRouter(prefix="/home", tags=["home"])
templates = Jinja2Templates(directory="templates")


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
    return {
        "request": request,
        "user": user,
        "lang": lang,
        "theme": theme,
        "_": lambda key: t(key, lang),
        "unread_count": unread_count,
        "now": datetime.utcnow(),
    }


def add_home_exp(user: User, exp: int, db: Session):
    user.exp += exp
    exp_needed = user.level * 100
    while user.exp >= exp_needed:
        user.exp -= exp_needed
        user.level += 1
        change_currency(
            user.id, "g_coin", user.level * 100,
            "level_up", remark=f"升级到Lv.{user.level}奖励", db=db
        )
        add_notification(
            user.id, "system", "升级啦！",
            f"恭喜你升级到家园Lv.{user.level}，获得{user.level * 100}G币奖励！",
            db=db
        )
        fire_event(user.id, "home", "home_level_up", {"level": user.level}, db=db)
        exp_needed = user.level * 100


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    
    if not user.wallet:
        wallet = Wallet(user_id=user.id)
        db.add(wallet)
        db.commit()
        db.refresh(wallet)
    
    guestbook_entries = db.query(MessageBoardPost).filter(
        MessageBoardPost.owner_user_id == user.id
    ).order_by(desc(MessageBoardPost.created_at)).limit(10).all()
    
    visitors = db.query(HomepageVisit).filter(
        HomepageVisit.owner_user_id == user.id
    ).order_by(desc(HomepageVisit.created_at)).limit(8).all()
    
    sections = db.query(Forum).order_by(Forum.sort_order).all()
    
    topics = db.query(ForumTopic).order_by(
        desc(ForumTopic.is_pinned),
        desc(ForumTopic.last_reply_at)
    ).limit(10).all()
    
    announcements = db.query(Announcement).filter(
        Announcement.status == 1
    ).order_by(desc(Announcement.created_at)).limit(3).all()
    
    friend_requests = db.query(FriendRequest).filter(
        FriendRequest.to_user_id == user.id,
        FriendRequest.status == 0
    ).count()
    
    ctx.update({
        "guestbook": guestbook_entries,
        "visitors": visitors,
        "sections": sections,
        "topics": topics,
        "announcements": announcements,
        "friend_request_count": friend_requests,
    })
    return templates.TemplateResponse("home/index.html", ctx)


@router.get("/my", response_class=HTMLResponse)
async def my_home(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    
    guestbook_entries = db.query(MessageBoardPost).filter(
        MessageBoardPost.owner_user_id == user.id
    ).order_by(desc(MessageBoardPost.created_at)).all()
    
    visitors = db.query(HomepageVisit).filter(
        HomepageVisit.owner_user_id == user.id
    ).order_by(desc(HomepageVisit.created_at)).limit(20).all()
    
    ctx.update({
        "guestbook": guestbook_entries,
        "visitors": visitors,
    })
    return templates.TemplateResponse("home/my.html", ctx)


@router.get("/profile/{user_id}", response_class=HTMLResponse)
async def view_profile(request: Request, user_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        return RedirectResponse(url="/home/", status_code=302)
    
    viewer = ctx["user"]
    existing_visitor = db.query(HomepageVisit).filter(
        HomepageVisit.owner_user_id == target.id,
        HomepageVisit.visitor_user_id == viewer.id
    ).first()
    
    if not existing_visitor and viewer.id != target.id:
        visitor = HomepageVisit(
            owner_user_id=target.id,
            visitor_user_id=viewer.id,
            visitor_nickname=viewer.nickname or viewer.username
        )
        db.add(visitor)
        target.visit_count += 1
        target.popularity += 1
        db.commit()
    
    is_friend = False
    for f in viewer.friends:
        if f.id == target.id:
            is_friend = True
            break
    
    has_requested = db.query(FriendRequest).filter(
        FriendRequest.from_user_id == viewer.id,
        FriendRequest.to_user_id == target.id,
        FriendRequest.status == 0
    ).first() is not None
    
    guestbook_entries = db.query(MessageBoardPost).filter(
        MessageBoardPost.owner_user_id == target.id
    ).order_by(desc(MessageBoardPost.created_at)).limit(20).all()
    
    ctx.update({
        "target": target,
        "is_friend": is_friend,
        "has_requested": has_requested,
        "guestbook": guestbook_entries,
    })
    return templates.TemplateResponse("home/profile.html", ctx)


@router.post("/guestbook/add")
async def add_guestbook(
    request: Request,
    owner_id: int = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db)
):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    owner = db.query(User).filter(User.id == owner_id).first()
    if not owner:
        return RedirectResponse(url="/home/", status_code=302)
    
    entry = MessageBoardPost(
        owner_user_id=owner_id,
        author_user_id=user.id,
        author_nickname=user.nickname or user.username,
        content=content
    )
    db.add(entry)
    
    add_home_exp(user, 2, db)
    owner.popularity += 1
    
    if user.id != owner.id:
        add_notification(
            owner.id, "guestbook", "有人给你留言了",
            f"{user.nickname or user.username}在你的留言板留言了", db=db
        )
    
    db.commit()
    return RedirectResponse(url=f"/home/profile/{owner_id}", status_code=302)


# ==================== 好友系统 ====================

@router.get("/friends", response_class=HTMLResponse)
async def friends_list(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    friends = user.friends
    
    requests_received = db.query(FriendRequest).filter(
        FriendRequest.to_user_id == user.id,
        FriendRequest.status == 0
    ).all()
    
    requests_sent = db.query(FriendRequest).filter(
        FriendRequest.from_user_id == user.id,
        FriendRequest.status == 0
    ).all()
    
    visitors = db.query(HomepageVisit).filter(
        HomepageVisit.owner_user_id == user.id
    ).order_by(desc(HomepageVisit.created_at)).limit(20).all()
    
    ctx.update({
        "friends": friends,
        "requests_received": requests_received,
        "requests_sent": requests_sent,
        "visitors": visitors,
    })
    return templates.TemplateResponse("home/friends.html", ctx)


@router.post("/friends/request/{user_id}")
async def send_friend_request(request: Request, user_id: int, message: str = Form(""), db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    target = db.query(User).filter(User.id == user_id).first()
    
    is_friend = any(f.id == user_id for f in user.friends)
    
    existing = db.query(FriendRequest).filter(
        FriendRequest.from_user_id == user.id,
        FriendRequest.to_user_id == user_id,
        FriendRequest.status == 0
    ).first()
    
    if target and not is_friend and user.id != user_id and not existing:
        req = FriendRequest(
            from_user_id=user.id,
            to_user_id=user_id,
            from_nickname=user.nickname or user.username,
            message=message
        )
        db.add(req)
        add_notification(
            user_id, "friend", "新的好友申请",
            f"{user.nickname or user.username}请求添加你为好友", db=db
        )
        db.commit()
    
    return RedirectResponse(url=f"/home/profile/{user_id}", status_code=302)


@router.get("/friends/accept/{request_id}")
async def accept_friend_request(request: Request, request_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    req = db.query(FriendRequest).filter(
        FriendRequest.id == request_id,
        FriendRequest.to_user_id == user.id
    ).first()
    
    if req and req.status == 0:
        req.status = 1
        from_user = db.query(User).filter(User.id == req.from_user_id).first()
        if from_user:
            user.friends.append(from_user)
            from_user.friends.append(user)
            add_home_exp(user, 10, db)
            add_notification(
                req.from_user_id, "friend", "好友申请已通过",
                f"{user.nickname or user.username}通过了你的好友申请", db=db
            )
        db.commit()
    
    return RedirectResponse(url="/home/friends", status_code=302)


@router.get("/friends/reject/{request_id}")
async def reject_friend_request(request: Request, request_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    req = db.query(FriendRequest).filter(
        FriendRequest.id == request_id,
        FriendRequest.to_user_id == user.id
    ).first()
    
    if req and req.status == 0:
        req.status = 2
        db.commit()
    
    return RedirectResponse(url="/home/friends", status_code=302)


# ==================== 家族系统 ====================

@router.get("/gang", response_class=HTMLResponse)
async def gang_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    my_gang = user.family
    all_gangs = db.query(Family).filter(Family.status == 1).all()
    
    messages = []
    can_signin = False
    if my_gang:
        messages = db.query(FamilyChatMessage).filter(
            FamilyChatMessage.family_id == my_gang.id
        ).order_by(desc(FamilyChatMessage.created_at)).limit(50).all()
        
        today_signed = db.query(FamilySignin).filter(
            FamilySignin.family_id == my_gang.id,
            FamilySignin.user_id == user.id,
            FamilySignin.signed_at >= datetime.combine(date.today(), datetime.min.time())
        ).first()
        can_signin = today_signed is None
    
    ctx.update({
        "my_gang": my_gang,
        "all_gangs": all_gangs,
        "messages": messages,
        "can_signin": can_signin,
    })
    return templates.TemplateResponse("home/gang.html", ctx)


@router.post("/gang/create")
async def create_gang(
    request: Request,
    name: str = Form(...),
    slogan: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db)
):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    if user.family_id:
        return RedirectResponse(url="/home/gang", status_code=302)
    
    wallet = user.wallet
    if not wallet or wallet.g_coin < 10000:
        return RedirectResponse(url="/home/gang?error=1", status_code=302)
    
    existing = db.query(Family).filter(Family.name == name).first()
    if existing:
        return RedirectResponse(url="/home/gang?error=2", status_code=302)
    
    gang = Family(
        name=name,
        slogan=slogan,
        description=description,
        owner_user_id=user.id
    )
    db.add(gang)
    db.flush()
    
    change_currency(user.id, "g_coin", -10000, "family_create", remark=f"创建家族[{name}]", db=db)
    user.family_id = gang.id
    user.family_role = "leader"
    
    member = FamilyMember(
        family_id=gang.id,
        user_id=user.id,
        role="leader",
        contribution=100
    )
    db.add(member)
    
    add_home_exp(user, 50, db)
    fire_event(user.id, "family", "family_created", {"family_id": gang.id, "name": name}, db=db)
    db.commit()
    
    return RedirectResponse(url="/home/gang", status_code=302)


@router.get("/gang/signin")
async def gang_signin(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    if not user.family_id:
        return RedirectResponse(url="/home/gang", status_code=302)
    
    today_signed = db.query(FamilySignin).filter(
        FamilySignin.family_id == user.family_id,
        FamilySignin.user_id == user.id,
        FamilySignin.signed_at >= datetime.combine(date.today(), datetime.min.time())
    ).first()
    
    if not today_signed:
        reward_gcoin = 50 + user.level * 5
        reward_contribution = 10
        
        signin = FamilySignin(
            family_id=user.family_id,
            user_id=user.id,
            reward_gcoin=reward_gcoin,
            reward_contribution=reward_contribution
        )
        db.add(signin)
        
        change_currency(user.id, "g_coin", reward_gcoin, "family_signin", remark="家族签到奖励", db=db)
        
        member = db.query(FamilyMember).filter(
            FamilyMember.family_id == user.family_id,
            FamilyMember.user_id == user.id
        ).first()
        if member:
            member.contribution += reward_contribution
            member.today_signin = True
        
        family = user.family
        family.contribution_total += reward_contribution
        family.exp += reward_contribution
        if family.exp >= family.level * 1000:
            family.exp -= family.level * 1000
            family.level += 1
            family.member_limit += 5
        
        add_home_exp(user, 5, db)
        db.commit()
    
    return RedirectResponse(url="/home/gang", status_code=302)


@router.post("/gang/chat")
async def gang_chat(request: Request, content: str = Form(...), db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    if user.family_id and content.strip():
        msg = FamilyChatMessage(
            family_id=user.family_id,
            user_id=user.id,
            user_nickname=user.nickname or user.username,
            content=content.strip()
        )
        db.add(msg)
        db.commit()
    
    return RedirectResponse(url="/home/gang", status_code=302)


@router.get("/gang/join/{gang_id}")
async def join_gang(request: Request, gang_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    if user.family_id:
        return RedirectResponse(url="/home/gang", status_code=302)
    
    gang = db.query(Family).filter(Family.id == gang_id, Family.status == 1).first()
    if not gang:
        return RedirectResponse(url="/home/gang", status_code=302)
    
    member_count = db.query(FamilyMember).filter(FamilyMember.family_id == gang_id).count()
    if member_count >= gang.member_limit:
        return RedirectResponse(url="/home/gang?error=3", status_code=302)
    
    user.family_id = gang.id
    user.family_role = "member"
    
    member = FamilyMember(
        family_id=gang.id,
        user_id=user.id,
        role="member"
    )
    db.add(member)
    gang.member_count = member_count + 1
    
    add_home_exp(user, 20, db)
    add_notification(
        gang.owner_user_id, "family", "新成员加入",
        f"{user.nickname or user.username}加入了你的家族", db=db
    )
    db.commit()
    
    return RedirectResponse(url="/home/gang", status_code=302)


# ==================== 论坛系统 ====================

@router.get("/forum", response_class=HTMLResponse)
async def forum_home(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    sections = db.query(Forum).order_by(Forum.sort_order).all()
    topics = db.query(ForumTopic).order_by(
        desc(ForumTopic.is_pinned),
        desc(ForumTopic.last_reply_at)
    ).limit(30).all()
    
    ctx.update({
        "sections": sections,
        "topics": topics,
    })
    return templates.TemplateResponse("home/forum.html", ctx)


@router.get("/forum/section/{section_id}", response_class=HTMLResponse)
async def forum_section(request: Request, section_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    section = db.query(Forum).filter(Forum.id == section_id).first()
    if not section:
        return RedirectResponse(url="/home/forum", status_code=302)
    
    topics = db.query(ForumTopic).filter(
        ForumTopic.forum_id == section_id
    ).order_by(
        desc(ForumTopic.is_pinned),
        desc(ForumTopic.last_reply_at)
    ).all()
    
    ctx.update({
        "section": section,
        "topics": topics,
    })
    return templates.TemplateResponse("home/forum_section.html", ctx)


@router.get("/forum/post/{topic_id}", response_class=HTMLResponse)
async def forum_topic(request: Request, topic_id: int, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    topic = db.query(ForumTopic).filter(ForumTopic.id == topic_id).first()
    if not topic:
        return RedirectResponse(url="/home/forum", status_code=302)
    
    topic.view_count += 1
    
    replies = db.query(ForumPost).filter(
        ForumPost.topic_id == topic_id
    ).order_by(ForumPost.created_at).all()
    
    author = db.query(User).filter(User.id == topic.user_id).first()
    
    db.commit()
    
    ctx.update({
        "topic": topic,
        "replies": replies,
        "author": author,
    })
    return templates.TemplateResponse("home/forum_post.html", ctx)


@router.get("/forum/topic/create")
async def create_topic_page(request: Request, section_id: int = 0, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    sections = db.query(Forum).order_by(Forum.sort_order).all()
    ctx.update({
        "sections": sections,
        "current_section": section_id,
    })
    return templates.TemplateResponse("home/forum_create.html", ctx)


@router.post("/forum/topic/create")
async def create_topic(
    request: Request,
    section_id: int = Form(...),
    title: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db)
):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    
    topic = ForumTopic(
        forum_id=section_id,
        user_id=user.id,
        user_nickname=user.nickname or user.username,
        title=title,
        content=content,
        last_reply_at=datetime.utcnow()
    )
    db.add(topic)
    
    section = db.query(Forum).filter(Forum.id == section_id).first()
    if section:
        section.post_count += 1
    
    add_home_exp(user, 15, db)
    fire_event(user.id, "forum", "forum_topic_created", {"topic_id": topic.id}, db=db)
    db.commit()
    
    return RedirectResponse(url=f"/home/forum/post/{topic.id}", status_code=302)


@router.post("/forum/reply/{topic_id}")
async def reply_topic(
    request: Request,
    topic_id: int,
    content: str = Form(...),
    db: Session = Depends(get_db)
):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    topic = db.query(ForumTopic).filter(ForumTopic.id == topic_id).first()
    if not topic:
        return RedirectResponse(url="/home/forum", status_code=302)
    
    reply = ForumPost(
        topic_id=topic_id,
        user_id=user.id,
        user_nickname=user.nickname or user.username,
        content=content
    )
    db.add(reply)
    
    topic.reply_count += 1
    topic.last_reply_at = datetime.utcnow()
    
    add_home_exp(user, 3, db)
    db.commit()
    
    return RedirectResponse(url=f"/home/forum/post/{topic_id}", status_code=302)


# ==================== 消息中心 ====================

@router.get("/messages", response_class=HTMLResponse)
async def messages_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    messages = db.query(Notification).filter(
        Notification.user_id == user.id
    ).order_by(desc(Notification.created_at)).all()
    
    for msg in messages:
        msg.is_read = True
    db.commit()
    
    ctx.update({
        "messages": messages,
    })
    return templates.TemplateResponse("home/messages.html", ctx)


# ==================== 游戏大厅 ====================

@router.get("/gamelobby", response_class=HTMLResponse)
async def game_lobby(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    
    # 整理游戏状态数据
    zongheng_status = None
    if user.sea:
        from models.models import SeaCity
        current_city = db.query(SeaCity).filter(SeaCity.city_code == user.sea.current_city_code).first()
        zongheng_status = {
            "ship_name": user.sea.ship_name,
            "current_port": current_city.name if current_city else "未知",
            "silver": user.sea.silver_coin,
        }
    
    summon_status = None
    if user.summon:
        beast_count = len(user.summon.beasts) if user.summon.beasts else 0
        summon_status = {
            "summoner_name": user.summon.summoner_name or user.nickname or user.username,
            "level": user.summon.level,
            "beast_count": beast_count,
        }
    
    game_status = {
        "jingwutang": user.jw_role,
        "magic_garden": user.garden,
        "sunny_farm": user.farm,
        "delicious_town": user.town,
        "zongheng_sihai": zongheng_status,
        "summon_king": summon_status,
    }
    
    ctx.update({
        "game_status": game_status,
    })
    return templates.TemplateResponse("home/gamelobby.html", ctx)


# ==================== 背包系统 ====================

@router.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request, module_key: str = "common", db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    items = db.query(InventoryItem).filter(
        InventoryItem.user_id == user.id,
        InventoryItem.module_key == module_key
    ).all()
    
    modules = [
        {"key": "common", "name": "常用", "icon": "📦"},
        {"key": "jingwutang", "name": "精武堂", "icon": "⚔️"},
        {"key": "garden", "name": "花园", "icon": "🌸"},
        {"key": "farm", "name": "牧场", "icon": "🌾"},
        {"key": "town", "name": "小镇", "icon": "🍳"},
        {"key": "sea", "name": "航海", "icon": "⛵"},
    ]
    
    ctx.update({
        "items": items,
        "modules": modules,
        "current_module": module_key,
    })
    return templates.TemplateResponse("home/inventory.html", ctx)


# ==================== 商城 ====================

@router.get("/shop", response_class=HTMLResponse)
async def shop_page(request: Request, module_key: str = "common", db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    items = db.query(ShopItem).filter(
        ShopItem.status == 1,
        ShopItem.module_key == module_key
    ).all()
    
    modules = [
        {"key": "common", "name": "常用道具", "icon": "📦"},
        {"key": "jingwutang", "name": "精武堂", "icon": "⚔️"},
        {"key": "garden", "name": "魔法花园", "icon": "🌸"},
        {"key": "farm", "name": "阳光牧场", "icon": "🌾"},
        {"key": "sea", "name": "纵横四海", "icon": "⛵"},
    ]
    
    ctx.update({
        "shop_items": items,
        "modules": modules,
        "current_module": module_key,
    })
    return templates.TemplateResponse("home/shop.html", ctx)


@router.post("/shop/buy/{item_id}")
async def buy_item(request: Request, item_id: int, quantity: int = Form(1), db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    item = db.query(ShopItem).filter(ShopItem.id == item_id, ShopItem.status == 1).first()
    
    if not item:
        return RedirectResponse(url="/home/shop", status_code=302)
    
    total_cost = item.price_amount * quantity
    wallet = user.wallet
    
    currency_map = {
        "g_coin": wallet.g_coin if wallet else 0,
        "premium_coin": wallet.premium_coin if wallet else 0,
        "silver_coin": user.sea.silver_coin if user.sea else 0,
    }
    
    current = currency_map.get(item.price_currency, 0)
    if current < total_cost:
        return RedirectResponse(url="/home/shop?error=1", status_code=302)
    
    if item.price_currency == "g_coin":
        change_currency(user.id, "g_coin", -total_cost, "shop_buy", source_id=item_id, remark=f"购买{item.item_name}", db=db)
    elif item.price_currency == "premium_coin":
        change_currency(user.id, "premium_coin", -total_cost, "shop_buy", source_id=item_id, remark=f"购买{item.item_name}", db=db)
    
    add_item(
        user.id, item.module_key, item.item_code, item.item_name,
        quantity, db=db
    )
    
    add_notification(
        user.id, "system", "购买成功",
        f"成功购买 {item.item_name} x{quantity}", db=db
    )
    db.commit()
    
    return RedirectResponse(url="/home/shop", status_code=302)


# ==================== 图标与成就 ====================

@router.get("/icons", response_class=HTMLResponse)
async def icons_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    all_icons = db.query(IconDef).filter(IconDef.status == 1).all()
    user_icons = db.query(UserIcon).filter(UserIcon.user_id == user.id).all()
    lit_icon_ids = {ui.icon_id for ui in user_icons if ui.is_lit}
    
    ctx.update({
        "all_icons": all_icons,
        "lit_icon_ids": lit_icon_ids,
    })
    return templates.TemplateResponse("home/icons.html", ctx)


@router.get("/achievements", response_class=HTMLResponse)
async def achievements_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    all_achievements = db.query(Achievement).all()
    user_achievements = db.query(UserAchievement).filter(UserAchievement.user_id == user.id).all()
    completed_ids = {ua.achievement_id for ua in user_achievements if ua.completed}
    
    ctx.update({
        "all_achievements": all_achievements,
        "completed_ids": completed_ids,
    })
    return templates.TemplateResponse("home/achievements.html", ctx)


# ==================== 排行榜 ====================

@router.get("/ranking", response_class=HTMLResponse)
async def ranking_page(request: Request, rank_key: str = "home_level", db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    from models.models import RankDefinition, RankSnapshot
    ranks = db.query(RankDefinition).all()
    
    if rank_key == "home_level":
        users = db.query(User).order_by(desc(User.level), desc(User.exp)).limit(50).all()
        rank_list = []
        for i, u in enumerate(users):
            rank_list.append({
                "rank": i + 1,
                "nickname": u.nickname or u.username,
                "score": f"Lv.{u.level}",
                "user_id": u.id,
            })
        title = "家园等级榜"
    elif rank_key == "home_popularity":
        users = db.query(User).order_by(desc(User.popularity)).limit(50).all()
        rank_list = []
        for i, u in enumerate(users):
            rank_list.append({
                "rank": i + 1,
                "nickname": u.nickname or u.username,
                "score": f"{u.popularity}人气",
                "user_id": u.id,
            })
        title = "家园人气榜"
    elif rank_key == "home_wealth":
        users = db.query(User).join(Wallet).order_by(desc(Wallet.g_coin)).limit(50).all()
        rank_list = []
        for i, u in enumerate(users):
            rank_list.append({
                "rank": i + 1,
                "nickname": u.nickname or u.username,
                "score": f"{u.wallet.g_coin if u.wallet else 0}G币",
                "user_id": u.id,
            })
        title = "家园财富榜"
    else:
        rank_list = []
        title = "排行榜"
    
    my_rank = None
    for i, item in enumerate(rank_list):
        if item["user_id"] == ctx["user"].id:
            my_rank = i + 1
            break
    
    ctx.update({
        "ranks": ranks,
        "rank_list": rank_list,
        "title": title,
        "current_rank": rank_key,
        "my_rank": my_rank,
    })
    return templates.TemplateResponse("home/ranking.html", ctx)


# ==================== 设置 ====================

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    return templates.TemplateResponse("home/settings.html", ctx)


@router.post("/settings/save")
async def save_settings(
    request: Request,
    nickname: str = Form(None),
    signature: str = Form(None),
    language: str = Form(None),
    theme: str = Form(None),
    db: Session = Depends(get_db)
):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    if nickname:
        user.nickname = nickname
    if signature:
        user.signature = signature
    if language:
        user.language = language
    if theme:
        user.theme = theme
    
    db.commit()
    return RedirectResponse(url="/home/settings", status_code=302)


# ==================== 聊天室 ====================

@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request, room_key: str = "public_main", db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    rooms = db.query(ChatRoom).filter(ChatRoom.status == 1).all()
    room = db.query(ChatRoom).filter(ChatRoom.room_key == room_key).first()
    
    messages = []
    if room:
        messages = db.query(ChatMessage).filter(
            ChatMessage.room_id == room.id
        ).order_by(desc(ChatMessage.created_at)).limit(50).all()
        messages = list(reversed(messages))
    
    ctx.update({
        "rooms": rooms,
        "current_room": room,
        "messages": messages,
    })
    return templates.TemplateResponse("home/chat.html", ctx)


@router.post("/chat/send")
async def chat_send(request: Request, room_key: str = Form(...), content: str = Form(...), db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    room = db.query(ChatRoom).filter(ChatRoom.room_key == room_key).first()
    
    if room and content.strip():
        msg = ChatMessage(
            room_id=room.id,
            user_id=user.id,
            user_nickname=user.nickname or user.username,
            content=content.strip()
        )
        db.add(msg)
        db.commit()
    
    return RedirectResponse(url=f"/home/chat?room_key={room_key}", status_code=302)


# ==================== 同城 ====================

@router.get("/city", response_class=HTMLResponse)
async def city_page(request: Request, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    cities = db.query(City).filter(City.status == 1).all()
    city_code = ctx["user"].city_code
    
    feeds = []
    if city_code:
        feeds = db.query(CityFeed).filter(
            CityFeed.city_code == city_code
        ).order_by(desc(CityFeed.created_at)).limit(30).all()
    
    ctx.update({
        "cities": cities,
        "current_city": city_code,
        "feeds": feeds,
    })
    return templates.TemplateResponse("home/city.html", ctx)


@router.post("/city/feed")
async def city_feed(request: Request, content: str = Form(...), db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    user = ctx["user"]
    if user.city_code and content.strip():
        feed = CityFeed(
            city_code=user.city_code,
            user_id=user.id,
            user_nickname=user.nickname or user.username,
            content=content.strip()
        )
        db.add(feed)
        add_home_exp(user, 2, db)
        db.commit()
    
    return RedirectResponse(url="/home/city", status_code=302)


@router.get("/city/set/{city_code}")
async def set_city(request: Request, city_code: str, db: Session = Depends(get_db)):
    ctx = get_common_context(request, db)
    if not ctx:
        return RedirectResponse(url="/auth/login", status_code=302)
    
    city = db.query(City).filter(City.code == city_code).first()
    if city:
        ctx["user"].city_code = city_code
        ctx["user"].city = city.name
        db.commit()
    
    return RedirectResponse(url="/home/city", status_code=302)
