"""全部数据模型：平台公共系统 + 四个游戏模块

设计原则对应规范：
- 平台统一：好友/加锁/货品/图标/消息/排行 均为平台公共表，模块只上报事件
- 模块自治：每个模块拥有自己的玩法表，但背包走平台 inventory（带 module_key 分页）
- 操作留痕：OperationLog 记录关键动作，便于客服申诉
"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    String, Integer, Boolean, Text, DateTime, ForeignKey, Float, UniqueConstraint, Index, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now():
    return datetime.utcnow()


# ============================================================
# 平台核心：用户 / 会话
# ============================================================
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    nickname: Mapped[str] = mapped_column(String(32), default="")
    avatar: Mapped[str] = mapped_column(String(255), default="")  # 头像 URL 或文字代号
    signature: Mapped[str] = mapped_column(String(128), default="")  # 签名
    gender: Mapped[int] = mapped_column(Integer, default=0)  # 0未知 1男 2女
    city: Mapped[str] = mapped_column(String(32), default="")  # 同城用
    coins: Mapped[int] = mapped_column(Integer, default=1000)  # 平台公共货币
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    last_login: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Session(Base):
    __tablename__ = "sessions"
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# ============================================================
# 平台公共：好友 / 黑名单 / 来访 / 留言 / 私聊
# ============================================================
class Friend(Base):
    __tablename__ = "friends"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    friend_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    group_name: Mapped[str] = mapped_column(String(16), default="我的好友")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    __table_args__ = (UniqueConstraint("user_id", "friend_id", name="uq_friend_pair"),)


class Blacklist(Base):
    __tablename__ = "blacklist"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    blocked_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    __table_args__ = (UniqueConstraint("user_id", "blocked_id", name="uq_block_pair"),)


class Visit(Base):
    """来访记录"""
    __tablename__ = "visits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    host_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    visitor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    visited_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Guestbook(Base):
    """留言板"""
    __tablename__ = "guestbook"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    host_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ChatMessage(Base):
    """私聊消息"""
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    to_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(String(500))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ChatRoom(Base):
    __tablename__ = "chat_rooms"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    topic: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ChatRoomMessage(Base):
    __tablename__ = "chat_room_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("chat_rooms.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# ============================================================
# 平台公共：加锁（隐私锁 / 物品锁）
# ============================================================
class PrivacyLock(Base):
    """隐私锁：影响访问和交流"""
    __tablename__ = "privacy_locks"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    # 访问可见范围: 0=所有人 1=仅好友 2=无人
    allow_visit: Mapped[int] = mapped_column(Integer, default=0)
    allow_guestbook: Mapped[int] = mapped_column(Integer, default=0)
    allow_chat: Mapped[int] = mapped_column(Integer, default=0)
    show_in_city: Mapped[bool] = mapped_column(Boolean, default=True)


class ItemLock(Base):
    """物品锁：影响资源安全（禁止翻/偷/消耗/出售）"""
    __tablename__ = "item_locks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    module_key: Mapped[str] = mapped_column(String(32), index=True)
    item_ref: Mapped[str] = mapped_column(String(64))  # 物品 key 或资源槽位标识
    locked: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    __table_args__ = (UniqueConstraint("user_id", "module_key", "item_ref", name="uq_item_lock"),)


# ============================================================
# 平台公共：货品（物品字典 / 背包 / 商店）
# ============================================================
class Item(Base):
    """物品字典：所有物品必须先登记在此"""
    __tablename__ = "items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(32))
    type: Mapped[str] = mapped_column(String(16))  # crop/ingredient/flower/material/equip/prop/decor
    module_key: Mapped[str] = mapped_column(String(32), default="platform")  # 归属模块或 platform
    stackable: Mapped[bool] = mapped_column(Boolean, default=True)
    bindable: Mapped[bool] = mapped_column(Boolean, default=False)  # 绑定规则
    expires: Mapped[int] = mapped_column(Integer, default=0)  # 过期秒数 0=永不过期
    sell_price: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(String(128), default="")


class Inventory(Base):
    """背包：平台统一入口，按 module_key 分页"""
    __tablename__ = "inventory"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    module_key: Mapped[str] = mapped_column(String(32), index=True)  # farm/town/garden/sea/platform
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)  # 物品锁状态冗余
    acquired_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint("user_id", "item_id", "module_key", name="uq_inv_slot"),)


class ShopItem(Base):
    """商店上架：只能引用物品字典里的物品"""
    __tablename__ = "shop_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    price: Mapped[int] = mapped_column(Integer)  # 平台金币
    currency: Mapped[str] = mapped_column(String(16), default="金币")
    stock: Mapped[int] = mapped_column(Integer, default=-1)  # -1 无限
    category: Mapped[str] = mapped_column(String(16), default="prop")  # prop/decor/accel
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


# ============================================================
# 平台公共：图标 / 成就 / 模块注册
# ============================================================
class Module(Base):
    """模块注册表"""
    __tablename__ = "modules"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    intro: Mapped[str] = mapped_column(String(128), default="")
    entry: Mapped[str] = mapped_column(String(64))  # 路由路径
    sort: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Icon(Base):
    """图标定义：身份展示，点亮即展示"""
    __tablename__ = "icons"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(String(128), default="")
    source: Mapped[str] = mapped_column(String(16), default="platform")  # platform / module_key
    trigger: Mapped[str] = mapped_column(String(128), default="")  # 触发条件描述


class UserIcon(Base):
    """用户图标点亮状态。模块只能上报事件，由平台统一判定点亮。"""
    __tablename__ = "user_icons"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    icon_id: Mapped[int] = mapped_column(ForeignKey("icons.id"))
    lit: Mapped[bool] = mapped_column(Boolean, default=False)
    lit_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint("user_id", "icon_id", name="uq_user_icon"),)


class Achievement(Base):
    """成就：记录/目标，可有进度与奖励"""
    __tablename__ = "achievements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(String(128), default="")
    target: Mapped[int] = mapped_column(Integer, default=1)
    reward_coins: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(16), default="platform")


class UserAchievement(Base):
    __tablename__ = "user_achievements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    achievement_id: Mapped[int] = mapped_column(ForeignKey("achievements.id"))
    progress: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    reward_claimed: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("user_id", "achievement_id", name="uq_user_achv"),)


# ============================================================
# 平台公共：消息中心 / 活动 / 排行 / 操作日志
# ============================================================
class Message(Base):
    """消息中心。模块只能通过事件上报，不可直接写（用 platform.events.emit）"""
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(16), default="system")  # system/interact/progress/reward
    title: Mapped[str] = mapped_column(String(64), default="")
    content: Mapped[str] = mapped_column(String(255), default="")
    module_key: Mapped[str] = mapped_column(String(32), default="")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Activity(Base):
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(String(255), default="")
    type: Mapped[str] = mapped_column(String(16), default="event")  # event/signin/ranking
    start_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    end_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class ActivityProgress(Base):
    __tablename__ = "activity_progress"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    claimed: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("activity_id", "user_id", name="uq_actv_user"),)


class RankingEntry(Base):
    """排行分数。模块上报分数，平台统一展示。"""
    __tablename__ = "ranking_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_key: Mapped[str] = mapped_column(String(32), index=True)
    metric: Mapped[str] = mapped_column(String(32))  # 指标名 e.g. level/harvest/flower_lit
    period: Mapped[str] = mapped_column(String(8), default="total")  # day/week/month/total
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    score: Mapped[float] = mapped_column(Float, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    __table_args__ = (
        UniqueConstraint("module_key", "metric", "period", "user_id", name="uq_rank"),
        Index("ix_rank_score", "module_key", "metric", "period", "score"),
    )


class OperationLog(Base):
    """操作留痕：可追溯（客服/申诉）"""
    __tablename__ = "operation_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    module_key: Mapped[str] = mapped_column(String(32), default="platform")
    action: Mapped[str] = mapped_column(String(32))
    detail: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Settings(Base):
    """用户设置"""
    __tablename__ = "settings"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    notify_message: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_activity: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_interact: Mapped[bool] = mapped_column(Boolean, default=True)


class SupportTicket(Base):
    """客服工单"""
    __tablename__ = "support_tickets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(16))  # account/currency/item/social/module
    title: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(16), default="open")  # open/replied/closed
    reply: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# ============================================================
# 平台公共：家族 / 论坛
# ============================================================
class Family(Base):
    __tablename__ = "families"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True)
    leader_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    description: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class FamilyMember(Base):
    __tablename__ = "family_members"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16), default="member")  # leader/elder/member
    contributed: Mapped[int] = mapped_column(Integer, default=0)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    __table_args__ = (UniqueConstraint("family_id", "user_id", name="uq_family_member"),)


class ForumBoard(Base):
    __tablename__ = "forum_boards"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(String(128), default="")
    sort: Mapped[int] = mapped_column(Integer, default=0)


class ForumThread(Base):
    __tablename__ = "forum_threads"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("forum_boards.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(String(2000))
    views: Mapped[int] = mapped_column(Integer, default=0)
    replies: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ForumPost(Base):
    __tablename__ = "forum_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("forum_threads.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# ============================================================
# 模块1：阳光农场 Farm
# 老味道点：成长计时 / 护理(浇水除虫施肥) / 偷菜互助 / 回访节奏
# ============================================================
class Crop(Base):
    """作物字典"""
    __tablename__ = "farm_crops"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    grow_seconds: Mapped[int] = mapped_column(Integer, default=60)  # 总成熟时长
    stages: Mapped[int] = mapped_column(Integer, default=4)  # 阶段数(种子/发芽/生长/成熟)
    seed_item_key: Mapped[str] = mapped_column(String(64))
    harvest_item_key: Mapped[str] = mapped_column(String(64))
    harvest_exp: Mapped[int] = mapped_column(Integer, default=10)
    price: Mapped[int] = mapped_column(Integer, default=50)  # 种子价格


class FarmPlot(Base):
    """农田槽位"""
    __tablename__ = "farm_plots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    slot: Mapped[int] = mapped_column(Integer)  # 0..N
    crop_key: Mapped[str] = mapped_column(String(32), default="")  # 空则未种植
    planted_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    watered: Mapped[bool] = mapped_column(Boolean, default=False)
    pest: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否有虫害
    __table_args__ = (UniqueConstraint("user_id", "slot", name="uq_farm_slot"),)


class FarmState(Base):
    """农场玩家状态"""
    __tablename__ = "farm_state"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    level: Mapped[int] = mapped_column(Integer, default=1)
    exp: Mapped[int] = mapped_column(Integer, default=0)
    plot_count: Mapped[int] = mapped_column(Integer, default=6)  # 可用地块数
    harvest_count: Mapped[int] = mapped_column(Integer, default=0)  # 累计收获次数（图标触发用）


class FarmStealLog(Base):
    """偷菜记录（用于互助/反作弊/留痕）"""
    __tablename__ = "farm_steal_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plot_id: Mapped[int] = mapped_column(ForeignKey("farm_plots.id", ondelete="CASCADE"))
    thief_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    item_key: Mapped[str] = mapped_column(String(64))
    amount: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# ============================================================
# 模块2：美味小镇 Town（v0.0.4 怀旧版完整设计规范）
# 双主轴：餐厅星级(规模) + 菜谱等级(内容)
# 老味道点：翻橱柜/添油/合菜/雇服务员/挑剔客人/蟑螂
# ============================================================
class TownRecipe(Base):
    """菜谱字典（6 级菜 × 3 品质：普通/极品/金牌）

    recipe_level: 1-6（菜谱级别，对应解锁等级 Lv1/10/20/35/50/65）
    base_price: 基础售价（品质系数单独乘算：普通1.0/极品1.25/金牌1.55）
    base_exp: 顾客消费基础经验（品质不提升经验，保留旧逻辑）
    base_oil: 单次开灶耗油
    cook_seconds: 制作时间
    """
    __tablename__ = "town_recipes"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    recipe_level: Mapped[int] = mapped_column(Integer, default=1)  # 1-6 级菜
    ingredients: Mapped[str] = mapped_column(Text)  # JSON: {item_key: qty}
    cook_seconds: Mapped[int] = mapped_column(Integer, default=30)
    output_item_key: Mapped[str] = mapped_column(String(64))
    base_price: Mapped[int] = mapped_column(Integer, default=18)  # 基础售价
    base_exp: Mapped[int] = mapped_column(Integer, default=2)  # 顾客消费基础经验
    base_oil: Mapped[int] = mapped_column(Integer, default=8)  # 开灶耗油
    unlock_level: Mapped[int] = mapped_column(Integer, default=1)  # 解锁等级
    # 旧字段兼容（保留以便平滑迁移）
    price: Mapped[int] = mapped_column(Integer, default=20)
    unlock_stars: Mapped[int] = mapped_column(Integer, default=0)


class TownRecipeProgress(Base):
    """玩家菜谱进度（熟练度 + 品质 + 上架）

    proficiency: 熟练度（做一次+1）
    quality: 普通/极品/金牌
    on_shelf: 是否上架营业（0/1）
    """
    __tablename__ = "town_recipe_progress"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    recipe_key: Mapped[str] = mapped_column(ForeignKey("town_recipes.key", ondelete="CASCADE"))
    learned: Mapped[bool] = mapped_column(Boolean, default=False)
    proficiency: Mapped[int] = mapped_column(Integer, default=0)
    quality: Mapped[str] = mapped_column(String(8), default="普通")  # 普通/极品/金牌
    on_shelf: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("user_id", "recipe_key", name="uq_town_recipe_progress"),)


class TownState(Base):
    """餐厅状态（v0.0.4 完整字段）

    stars: 0-5 星（0星=Lv1起步，5星=Lv70满阶）
    oil / oil_cap: 当前油量 / 油壶容量（初始 3000，可扩到 8000）
    coins: 模块金币（独立于平台 user.coins，开局 10000）
    total_revenue: 累计营收（升星条件）
    total_service: 累计营业次数（升星条件）
    fame: 人气（被翻+1，雇佣等）
    last_service_at: 上次营业结算时间（顾客周期 180 秒）
    last_oil_drain: 上次油量自然消耗时间
    """
    __tablename__ = "town_state"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    level: Mapped[int] = mapped_column(Integer, default=1)
    exp: Mapped[int] = mapped_column(Integer, default=0)
    stars: Mapped[int] = mapped_column(Integer, default=0)  # 0-5 星
    oil: Mapped[int] = mapped_column(Integer, default=3000)  # 当前油量
    oil_cap: Mapped[int] = mapped_column(Integer, default=3000)  # 油壶容量
    coins: Mapped[int] = mapped_column(Integer, default=10000)  # 模块金币（开局 10000）
    dishes_served: Mapped[int] = mapped_column(Integer, default=0)  # 兼容旧字段
    total_revenue: Mapped[int] = mapped_column(Integer, default=0)
    total_service: Mapped[int] = mapped_column(Integer, default=0)
    fame: Mapped[int] = mapped_column(Integer, default=0)
    table_count: Mapped[int] = mapped_column(Integer, default=3)  # 已摆桌位数
    cooking_recipe: Mapped[str] = mapped_column(String(32), default="")
    cooking_started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    last_service_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    last_oil_drain: Mapped[datetime] = mapped_column(DateTime, default=_now)


class TownDailyLog(Base):
    """小镇日限计数（翻柜/丢蟑螂/被翻补偿）

    按 (user_id, date) 唯一
    flip_total: 今日翻柜总次数（上限 15）
    roach_throw: 今日丢蟑螂次数（上限 2）
    """
    __tablename__ = "town_daily_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    date: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD
    flip_total: Mapped[int] = mapped_column(Integer, default=0)
    roach_throw: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_town_daily"),)


class TownFlipLog(Base):
    """翻柜互动记录（同好友每日上限 3 + 10 分钟冷却 + 衰减）

    thief_id: 翻取者
    host_id: 被翻者
    times_today: 对该好友今日第几次（1/2/3，第4次起收益0）
    """
    __tablename__ = "town_flip_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thief_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    host_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    item_key: Mapped[str] = mapped_column(String(64))
    times_today: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class TownWaiter(Base):
    """服务员（雇好友，12 小时）

    bonus_type: coins/satisfaction/speed（金币+3%/满意度+2%/速度-5%制作时间）
    """
    __tablename__ = "town_waiters"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)  # 雇主
    friend_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))  # 服务员
    bonus_type: Mapped[str] = mapped_column(String(16), default="coins")
    hired_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    expire_at: Mapped[datetime] = mapped_column(DateTime)


class TownCockroach(Base):
    """蟑螂（封 1 桌，15 分钟自动消失，单餐厅上限 3 只）"""
    __tablename__ = "town_cockroaches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)  # 被丢者
    thrower_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))  # 丢蟑螂者
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    expire_at: Mapped[datetime] = mapped_column(DateTime)


class TownFacility(Base):
    """设施（24 小时生效）：奖杯/海报/保鲜柜/省油灶/卫生香氛"""
    __tablename__ = "town_facilities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    facility_key: Mapped[str] = mapped_column(String(32))  # trophy/poster/fresh_cabinet/oil_stove/sanitizer
    expire_at: Mapped[datetime] = mapped_column(DateTime)


# ---------- v0.1.1：赛厨 / 厨艺大赛 ----------
class TownChefTool(Base):
    """玩家厨具（5 类：铲/刀/锅/味/意）

    level: 厨具等级（强化等级，影响厨力）
    equipped: 是否装备（每类只能装备 1 件）
    """
    __tablename__ = "town_chef_tools"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    tool_key: Mapped[str] = mapped_column(String(16))  # spade/knife/pot/flavor/mind
    level: Mapped[int] = mapped_column(Integer, default=1)
    equipped: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    __table_args__ = (UniqueConstraint("user_id", "tool_key", name="uq_town_chef_tool"),)


class TownChefSkill(Base):
    """玩家技能点分配（火候/刀功/厨艺/调味，共 40 点）

    spec 示例：15 火候 / 9 刀功 / 8 厨艺 / 8 调味
    allocated: 已分配点数（剩余 = 40 - allocated）
    """
    __tablename__ = "town_chef_skills"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    huohou: Mapped[int] = mapped_column(Integer, default=0)    # 火候
    daogong: Mapped[int] = mapped_column(Integer, default=0)  # 刀功
    chuyi: Mapped[int] = mapped_column(Integer, default=0)    # 厨艺
    tiaowei: Mapped[int] = mapped_column(Integer, default=0)  # 调味


class TownMatchLog(Base):
    """赛厨对战记录（spec：3 评委打分，总分高者胜，平局被挑战方胜）

    attacker_id: 主动挑战者
    defender_id: 被挑战者
    attacker_score / defender_score: 三评委总分
    winner_id: 胜者 user_id
    """
    __tablename__ = "town_match_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attacker_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    defender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    attacker_score: Mapped[int] = mapped_column(Integer, default=0)
    defender_score: Mapped[int] = mapped_column(Integer, default=0)
    winner_id: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str] = mapped_column(Text, default="")  # JSON：评委打分明细
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class TownContestEntry(Base):
    """厨艺大赛报名记录（spec：4 赛区，每日 8-23 时报名，23 时匹配，次日 8 时公布）

    zone: junior/middle/senior/super
    signup_date: 报名日期 YYYY-MM-DD
    matched: 是否已匹配
    result: win/lose/pending
    """
    __tablename__ = "town_contest_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    zone: Mapped[str] = mapped_column(String(16))
    signup_date: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD
    matched: Mapped[bool] = mapped_column(Boolean, default=False)
    opponent_id: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[str] = mapped_column(String(16), default="pending")  # pending/win/lose
    reward_coin: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    __table_args__ = (UniqueConstraint("user_id", "signup_date", name="uq_town_contest_daily"),)


# ============================================================
# 模块3：魔法花园 Garden
# 老味道点：成长阶段操作(发芽/花苗/花蕾) / 合成花种 / 花谱点亮核心目标 / 偷花送花展示
# 设计规范：花种(Seed)/花朵(Bloom)/花谱项(AlbumEntry) 三概念分离
# ============================================================
class GardenSeed(Base):
    """花种定义（Seed）：播种用的物品定义

    possible_blooms: JSON {bloom_key: weight} 同一种花种可能产出多种颜色花朵
    stage_actions: JSON {"1":"water","2":"weed","3":"debug"} 各阶段需要的操作
    item_level: 物品等级 1-8（强度轴），受玩家等级段上限约束
    rarity: 普通/稀有/史诗/传说（获取难度轴）
    """
    __tablename__ = "garden_seeds"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    min_level: Mapped[int] = mapped_column(Integer, default=1)
    grow_seconds: Mapped[int] = mapped_column(Integer, default=60)  # 总成长时间
    stages: Mapped[int] = mapped_column(Integer, default=4)  # 阶段数：发芽/花苗/花蕾/成熟
    stage_actions: Mapped[str] = mapped_column(Text, default="")  # JSON 各阶段需要操作
    yield_min: Mapped[int] = mapped_column(Integer, default=1)
    yield_max: Mapped[int] = mapped_column(Integer, default=2)
    possible_blooms: Mapped[str] = mapped_column(Text, default="")  # JSON {bloom_key: weight}
    rarity: Mapped[str] = mapped_column(String(16), default="普通")  # 普通/稀有/史诗/传说
    item_level: Mapped[int] = mapped_column(Integer, default=1)  # 物品等级 1-8
    sellable: Mapped[bool] = mapped_column(Boolean, default=True)
    seed_item_key: Mapped[str] = mapped_column(String(64))  # 关联平台物品字典（种子）
    obtain_sources: Mapped[str] = mapped_column(String(128), default="shop")  # shop/craft/exchange/drop


class GardenBloom(Base):
    """花朵定义（Bloom）：收获得到的实体花朵定义

    一个花种可产出多种花朵（颜色/稀有度不同）
    item_level: 物品等级（与产出花种一致或略低）
    """
    __tablename__ = "garden_blooms"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    color: Mapped[str] = mapped_column(String(16), default="白")  # 白/红/黄/紫...
    rarity: Mapped[str] = mapped_column(String(16), default="普通")  # 普通/稀有/史诗/传说
    item_level: Mapped[int] = mapped_column(Integer, default=1)  # 物品等级 1-8
    sell_price: Mapped[int] = mapped_column(Integer, default=10)
    album_entry_key: Mapped[str] = mapped_column(String(32))  # 对应花谱项
    item_key: Mapped[str] = mapped_column(String(64))  # 关联平台物品字典（花朵）
    special_tag: Mapped[str] = mapped_column(String(32), default="")  # 活动限定/合成材料...


class GardenAlbumEntry(Base):
    """花谱项（AlbumEntry）：图鉴收集条目，按系列分组"""
    __tablename__ = "garden_album_entries"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    series: Mapped[str] = mapped_column(String(32), index=True)  # 野花系列/玫瑰系列/传说系列/节日限定
    name: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(String(128), default="")
    bloom_key: Mapped[str] = mapped_column(String(32))  # 对应花朵


class GardenPot(Base):
    """花盆槽位（状态机）

    状态机: 空(seed_key='') -> 已播种 -> 发芽期 -> 花苗期 -> 花蕾期 -> 成熟 -> 收获后空
    watered/weeded/debugged: 当前生长周期内三件套操作是否完成
    """
    __tablename__ = "garden_pots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    slot: Mapped[int] = mapped_column(Integer)
    seed_key: Mapped[str] = mapped_column(String(32), default="")  # 关联 GardenSeed
    planted_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    watered: Mapped[bool] = mapped_column(Boolean, default=False)  # 浇水
    weeded: Mapped[bool] = mapped_column(Boolean, default=False)   # 除草
    debugged: Mapped[bool] = mapped_column(Boolean, default=False) # 除虫
    __table_args__ = (UniqueConstraint("user_id", "slot", name="uq_garden_slot"),)


class GardenState(Base):
    """花园等级与经验：经验来自劳动行为（播种/操作/收获/点亮/帮忙）"""
    __tablename__ = "garden_state"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    level: Mapped[int] = mapped_column(Integer, default=1)
    exp: Mapped[int] = mapped_column(Integer, default=0)
    pot_count: Mapped[int] = mapped_column(Integer, default=4)
    coins: Mapped[int] = mapped_column(Integer, default=200)  # 模块金币（买基础花种/道具）


class GardenCollection(Base):
    """花谱点亮记录（对应 AlbumEntry）"""
    __tablename__ = "garden_collection"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    entry_key: Mapped[str] = mapped_column(String(32))  # 关联 GardenAlbumEntry
    lit: Mapped[bool] = mapped_column(Boolean, default=True)
    lit_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    __table_args__ = (UniqueConstraint("user_id", "entry_key", name="uq_garden_col"),)


class GardenRecipe(Base):
    """合成配方：花朵/材料 -> 花种

    怀旧但可控的合成：
    - success_rate: 基础成功率(0-100)，随目标物品等级上升而下降
    - fail_credit_threshold: 失败累计阈值，满值必成（防挫败保底）
    - target_level: 目标花种物品等级（用于经验奖励与操作锁判定）
    - require_lock_check: 高阶合成是否强制操作锁校验
    """
    __tablename__ = "garden_recipes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    result_seed_key: Mapped[str] = mapped_column(String(32))  # 合成产出花种
    result_qty: Mapped[int] = mapped_column(Integer, default=1)
    materials: Mapped[str] = mapped_column(Text)  # JSON {item_key: qty}
    success_rate: Mapped[int] = mapped_column(Integer, default=80)  # 基础成功率%
    fail_credit_threshold: Mapped[int] = mapped_column(Integer, default=5)  # 保底阈值
    target_level: Mapped[int] = mapped_column(Integer, default=1)  # 目标物品等级
    require_lock_check: Mapped[bool] = mapped_column(Boolean, default=False)  # 高阶强制操作锁


class GardenExchange(Base):
    """兑换：活动材料 -> 花种（稳定路径，非纯概率）"""
    __tablename__ = "garden_exchanges"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    result_seed_key: Mapped[str] = mapped_column(String(32))
    result_qty: Mapped[int] = mapped_column(Integer, default=1)
    materials: Mapped[str] = mapped_column(Text)  # JSON {item_key: qty}
    activity_key: Mapped[str] = mapped_column(String(32), default="")  # 关联活动（可空）


class GardenCraftCredit(Base):
    """合成保底值记录：失败累计，满值必成（防挫败）"""
    __tablename__ = "garden_craft_credits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("garden_recipes.id", ondelete="CASCADE"))
    credits: Mapped[int] = mapped_column(Integer, default=0)  # 已累计失败值
    __table_args__ = (UniqueConstraint("user_id", "recipe_id", name="uq_craft_credit"),)


class GardenDailyLog(Base):
    """每日社交互动计数（防刷限速：偷花/帮忙日限 + 衰减）"""
    __tablename__ = "garden_daily_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    date: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD
    steal_count: Mapped[int] = mapped_column(Integer, default=0)
    help_count: Mapped[int] = mapped_column(Integer, default=0)
    order_reroll_paid: Mapped[int] = mapped_column(Integer, default=0)  # v0.1.3：当日付费刷新订单次数
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_garden_daily"),)


# v0.1.3：订单交易系统（spec 经济主引擎 / 主要回收池）
class GardenOrder(Base):
    """订单实例：玩家产出 → 订单交付 → 金币/经验回收

    spec 公式：
    - V_req = Σ(qty_i * value_coin(item_i) * Q_value_mul(Q_req_i))
    - R_coin = floor(V_req * margin(type) * urgency_mul * difficulty_mul)
    - R_exp  = floor(R_coin^p * exp_scale(L))
    """
    __tablename__ = "garden_orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    order_type: Mapped[str] = mapped_column(String(16), default="normal")  # normal/premium/limited
    requirements: Mapped[str] = mapped_column(Text)  # JSON [{item_key, qty, quality}]
    reward_coin: Mapped[int] = mapped_column(Integer, default=0)
    reward_exp: Mapped[int] = mapped_column(Integer, default=0)
    reward_token: Mapped[int] = mapped_column(Integer, default=0)  # 活动代币(活动单)
    expire_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)  # 限时单截止
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False)


class GardenOrderLog(Base):
    """订单交付历史（统计 + 任务追踪）"""
    __tablename__ = "garden_order_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    order_type: Mapped[str] = mapped_column(String(16))
    coin_gain: Mapped[int] = mapped_column(Integer, default=0)
    exp_gain: Mapped[int] = mapped_column(Integer, default=0)
    token_gain: Mapped[int] = mapped_column(Integer, default=0)
    delivered_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# v0.1.4：订单模板表（spec 大全级资料库 / 订单池按等级分层 pool(L)）
class GardenOrderTemplate(Base):
    """订单模板：spec 订单系统分册 order_templates

    requirements: JSON [{item_key, name, qty, quality, value_coin, item_level, rarity}]
    奖励不在模板存死，由 _calc_order_reward 按 spec 公式即时计算（单一真值源）。
    level_min/level_max: 玩家等级分层过滤（spec：pool(L)）。
    weight: 抽取权重（限时单可低权）。
    """
    __tablename__ = "garden_order_templates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_type: Mapped[str] = mapped_column(String(16), default="normal", index=True)  # normal/premium/limited
    requirements: Mapped[str] = mapped_column(Text)  # JSON
    level_min: Mapped[int] = mapped_column(Integer, default=1, index=True)
    level_max: Mapped[int] = mapped_column(Integer, default=99)
    weight: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)



# ============================================================
# 模块4：纵横四海 Sea
# 老味道点：城市节点+航线推进 / 任务驱动 / 遭遇结算 / 装备长期成长
# ============================================================
class SeaCity(Base):
    """城市节点字典"""
    __tablename__ = "sea_cities"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    parent_city: Mapped[str] = mapped_column(String(32), default="")  # 前置城市
    unlock_level: Mapped[int] = mapped_column(Integer, default=1)
    intro: Mapped[str] = mapped_column(String(128), default="")


class SeaRoute(Base):
    """航线：from -> to"""
    __tablename__ = "sea_routes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_city: Mapped[str] = mapped_column(String(32), index=True)
    to_city: Mapped[str] = mapped_column(String(32))
    required_level: Mapped[int] = mapped_column(Integer, default=1)
    travel_seconds: Mapped[int] = mapped_column(Integer, default=30)


class SeaEquipment(Base):
    """装备字典"""
    __tablename__ = "sea_equipment"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    slot: Mapped[str] = mapped_column(String(16))  # ship/sail/cannon/figure
    stat: Mapped[int] = mapped_column(Integer, default=1)  # 战力/速度加成
    price: Mapped[int] = mapped_column(Integer, default=100)


class SeaState(Base):
    """航海玩家状态"""
    __tablename__ = "sea_state"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    level: Mapped[int] = mapped_column(Integer, default=1)
    exp: Mapped[int] = mapped_column(Integer, default=0)
    current_city: Mapped[str] = mapped_column(String(32), default="port_a")
    ship_name: Mapped[str] = mapped_column(String(32), default="小木船")
    power: Mapped[int] = mapped_column(Integer, default=10)  # 总战力
    traveling_to: Mapped[str] = mapped_column(String(32), default="")
    travel_arrive_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class SeaQuest(Base):
    """任务实例"""
    __tablename__ = "sea_quests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    city_key: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(16), default="encounter")  # encounter/battle/trade
    reward_exp: Mapped[int] = mapped_column(Integer, default=20)
    reward_coins: Mapped[int] = mapped_column(Integer, default=50)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/done/failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class SeaUserEquip(Base):
    """玩家装备（长期成长线）"""
    __tablename__ = "sea_user_equips"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    equip_key: Mapped[str] = mapped_column(String(32))
    slot: Mapped[str] = mapped_column(String(16))
    equipped: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("user_id", "equip_key", name="uq_sea_equip"),)


# v0.1.5：纵横四海大全级资料库（spec 物品/副本/宠物/坐骑/羽翼/随从/宝石/卡片/圣痕）
class SeaDungeon(Base):
    """副本定义（spec 副本等级要求表）

    difficulties: JSON ["普通","精英","困难","噩梦","炼狱"]
    level_reqs:   JSON [5,15,25,35,45] 对应各难度等级要求
    exps:         JSON 各难度经验
    drops:        JSON 掉落物 key 列表
    open_days:    JSON 开放星期 [1,6,0]=周一/六/日
    """
    __tablename__ = "sea_dungeons"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    entry_city: Mapped[str] = mapped_column(String(32))  # 入口城市
    difficulties: Mapped[str] = mapped_column(Text, default="[]")
    level_reqs: Mapped[str] = mapped_column(Text, default="[]")
    exps: Mapped[str] = mapped_column(Text, default="[]")
    drops: Mapped[str] = mapped_column(Text, default="[]")
    open_days: Mapped[str] = mapped_column(Text, default="[]")


class SeaPet(Base):
    """宠物定义（spec 宠物列表：白/紫/橙品质，等级上限40）"""
    __tablename__ = "sea_pets"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    quality: Mapped[str] = mapped_column(String(16))  # 白/紫/橙
    atk: Mapped[int] = mapped_column(Integer, default=10)
    defense: Mapped[int] = mapped_column(Integer, default=10)
    agile: Mapped[int] = mapped_column(Integer, default=10)
    hp: Mapped[int] = mapped_column(Integer, default=100)
    skill_tag: Mapped[str] = mapped_column(String(64), default="")  # 推荐技能标签
    source: Mapped[str] = mapped_column(String(64), default="")  # 获取来源


class SeaMount(Base):
    """坐骑定义（spec 坐骑列表：等级要求 + 属性加成）"""
    __tablename__ = "sea_mounts"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    level_req: Mapped[int] = mapped_column(Integer, default=80)
    stat_type: Mapped[str] = mapped_column(String(16))  # flat 固定值 / pct 百分比
    stat_value: Mapped[int] = mapped_column(Integer, default=100)  # 攻防敏体各加成
    category: Mapped[str] = mapped_column(String(32), default="普通")  # 普通/稀有/黑暗军团/神圣军团


class SeaWing(Base):
    """羽翼定义（spec 羽翼列表：体魄/吸血/连击/铁壁）"""
    __tablename__ = "sea_wings"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    level_req: Mapped[int] = mapped_column(Integer, default=80)
    effects: Mapped[str] = mapped_column(Text)  # JSON {"体魄":3,"吸血":3}


class SeaFollower(Base):
    """随从定义（spec 随从列表：海贼王角色 + 传说技能）"""
    __tablename__ = "sea_followers"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    skill_name: Mapped[str] = mapped_column(String(32))
    skill_desc: Mapped[str] = mapped_column(String(255))
    quality: Mapped[str] = mapped_column(String(16), default="普通")  # 普通/优秀/精锐/完美/传说


class SeaGem(Base):
    """宝石定义（spec 宝石列表：效果 + 可镶嵌部位）"""
    __tablename__ = "sea_gems"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    effect: Mapped[str] = mapped_column(String(64))  # 毒攻/麻痹/致命/体力上限...
    slots: Mapped[str] = mapped_column(Text)  # JSON 可镶嵌部位列表
    tier: Mapped[int] = mapped_column(Integer, default=1)  # 碎片1/小2/中3/大4/完美5


class SeaCard(Base):
    """卡片定义（spec 卡片列表：附魔装备，普通/精致效果）"""
    __tablename__ = "sea_cards"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    slot: Mapped[str] = mapped_column(String(32))  # 附魔部位（手持/腰/头/躯体/脚/配饰/全部位）
    normal_effect: Mapped[str] = mapped_column(String(64))
    refine_effect: Mapped[str] = mapped_column(String(64))
    drop_source: Mapped[str] = mapped_column(String(64), default="")


class SeaHolyMark(Base):
    """圣痕定义（spec 圣痕种类：10种，白/绿/蓝/紫品质）"""
    __tablename__ = "sea_holy_marks"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    quality: Mapped[str] = mapped_column(String(16))  # 白/绿/蓝/紫


class SeaEquipSet(Base):
    """装备套装定义（spec 装备套装路线：等级 + 获取方式）"""
    __tablename__ = "sea_equip_sets"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    level_req: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[str] = mapped_column(String(128))  # 获取方式
    pieces: Mapped[int] = mapped_column(Integer, default=4)  # 套装件数


# ============================================================
# 召唤之王（v0.0.6）：召唤师 + 幻兽 + 战斗 + 日常任务
# 静态配置（经验表/120图鉴/60技能/属性公式/捕捉公式/掉落表/日常任务）见 routers/summon_data.py
# ============================================================
class SummonState(Base):
    """召唤师状态：等级 / 经验 / 活力 / 多货币 / 地图进度 / 日常计数"""
    __tablename__ = "summon_state"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    level: Mapped[int] = mapped_column(Integer, default=1)
    exp: Mapped[int] = mapped_column(Integer, default=0)
    energy: Mapped[int] = mapped_column(Integer, default=120)           # 活力
    energy_updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    coins: Mapped[int] = mapped_column(Integer, default=5000)           # 铜钱
    gems: Mapped[int] = mapped_column(Integer, default=100)             # 元宝
    prestige: Mapped[int] = mapped_column(Integer, default=0)           # 声望
    arena_coin: Mapped[int] = mapped_column(Integer, default=0)         # 擂台币
    bf_coin: Mapped[int] = mapped_column(Integer, default=0)            # 战场币
    guild_coin: Mapped[int] = mapped_column(Integer, default=0)         # 贡献
    mentor_coin: Mapped[int] = mapped_column(Integer, default=0)        # 桃李值
    current_map: Mapped[str] = mapped_column(String(16), default="T1")  # 当前所在段位地图
    stage_cleared: Mapped[int] = mapped_column(Integer, default=0)      # 当前地图已通关数
    captures_today: Mapped[int] = mapped_column(Integer, default=0)     # 今日抓捕次数
    daily_log_date: Mapped[str] = mapped_column(String(10), default="") # 日限重置日期 YYYY-MM-DD
    capture_pity: Mapped[str] = mapped_column(Text, default="{}")       # JSON: {rarity: 连续失败次数}
    daily_counters: Mapped[str] = mapped_column(Text, default="{}")     # JSON: {metric: 今日次数}
    daily_tasks: Mapped[str] = mapped_column(Text, default="{}")        # JSON: {task_id: 已领奖}
    last_battle_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class SummonPet(Base):
    """玩家拥有的幻兽（每只独立个体）"""
    __tablename__ = "summon_pets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    species_id: Mapped[str] = mapped_column(String(16), index=True)     # SZW_0001 等
    nickname: Mapped[str] = mapped_column(String(32), default="")
    level: Mapped[int] = mapped_column(Integer, default=1)
    exp: Mapped[int] = mapped_column(Integer, default=0)
    # 个体属性（捕获/升级时按段位范围+定位系数+资质+成长星计算）
    hp: Mapped[int] = mapped_column(Integer, default=100)
    atk_phy: Mapped[int] = mapped_column(Integer, default=20)
    atk_mag: Mapped[int] = mapped_column(Integer, default=20)
    def_phy: Mapped[int] = mapped_column(Integer, default=10)
    def_mag: Mapped[int] = mapped_column(Integer, default=10)
    spd: Mapped[int] = mapped_column(Integer, default=10)
    crit: Mapped[float] = mapped_column(Float, default=0.05)
    growth_stars: Mapped[int] = mapped_column(Integer, default=3)        # 成长星 1-5
    aptitudes: Mapped[str] = mapped_column(Text, default="{}")          # JSON: 6维资质 0.85-1.15
    skills: Mapped[str] = mapped_column(Text, default="[]")             # JSON: [skill_id,...]
    team_slot: Mapped[int] = mapped_column(Integer, default=-1)         # -1=未上阵, 0-3=出战位
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# ============================================================
# 模块6：精武堂 Martial（v0.1.0）
# 老味道点：人物养成 / 修炼挂机 / 加点流派 / 装备强化 / 比武对抗 / 帮派社交
# 静态配置（公式/技能/装备/日常任务/活跃奖励）见 routers/martial_data.py
# ============================================================
class MartialState(Base):
    """精武堂玩家状态：等级/经验/银两/荣誉/四维属性/修炼/比武/日常"""
    __tablename__ = "martial_state"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    level: Mapped[int] = mapped_column(Integer, default=1)
    exp: Mapped[int] = mapped_column(Integer, default=0)
    silver: Mapped[int] = mapped_column(Integer, default=2000)        # 银两（模块货币）
    honor: Mapped[int] = mapped_column(Integer, default=0)            # 荣誉（PVP 货币）
    attr_points: Mapped[int] = mapped_column(Integer, default=0)      # 可分配属性点
    strength: Mapped[int] = mapped_column(Integer, default=5)
    agility: Mapped[int] = mapped_column(Integer, default=5)
    physique: Mapped[int] = mapped_column(Integer, default=5)
    inner_power: Mapped[int] = mapped_column(Integer, default=5)
    # 修炼
    cultivate_started_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    cultivate_biguan: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否闭关中
    # 比武
    arena_score: Mapped[int] = mapped_column(Integer, default=1000)
    arena_wins: Mapped[int] = mapped_column(Integer, default=0)
    # 帮派
    guild_id: Mapped[int] = mapped_column(Integer, default=0)
    contribution: Mapped[int] = mapped_column(Integer, default=0)     # 帮派贡献
    # 日常
    daily_log_date: Mapped[str] = mapped_column(String(10), default="")
    daily_counters: Mapped[str] = mapped_column(Text, default="{}")   # JSON: {metric: 今日次数}
    daily_tasks: Mapped[str] = mapped_column(Text, default="{}")      # JSON: {task_id: 已领奖}
    daily_activity: Mapped[str] = mapped_column(Text, default="{}")   # JSON: {point: 已领奖}
    daily_activity_point: Mapped[int] = mapped_column(Integer, default=0)
    last_battle_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class MartialEquip(Base):
    """玩家装备实例"""
    __tablename__ = "martial_equips"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    slot: Mapped[str] = mapped_column(String(16))                     # 部位
    quality: Mapped[str] = mapped_column(String(16), default="white") # white/green/blue/purple/orange
    strengthen: Mapped[int] = mapped_column(Integer, default=0)       # 强化等级 0-10
    stats: Mapped[str] = mapped_column(Text, default="{}")            # JSON: 基础属性
    equipped: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class MartialSkill(Base):
    """玩家已学技能"""
    __tablename__ = "martial_skills"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    skill_id: Mapped[str] = mapped_column(String(16), index=True)
    level: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (UniqueConstraint("user_id", "skill_id", name="uq_martial_skill"),)


class MartialStageLog(Base):
    """PVE 关卡通关记录"""
    __tablename__ = "martial_stage_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    stage_id: Mapped[str] = mapped_column(String(16))
    cleared: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class MartialArenaLog(Base):
    """比武战报"""
    __tablename__ = "martial_arena_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attacker_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    defender_id: Mapped[int] = mapped_column(Integer, index=True)
    win: Mapped[bool] = mapped_column(Boolean, default=False)
    score_delta: Mapped[int] = mapped_column(Integer, default=0)
    battle_log: Mapped[str] = mapped_column(Text, default="[]")       # JSON 战报
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class MartialGuild(Base):
    """帮派（门派）"""
    __tablename__ = "martial_guilds"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True)
    leader_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    notice: Mapped[str] = mapped_column(String(255), default="振兴武林，广纳英豪")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class MartialGuildMember(Base):
    """帮派成员"""
    __tablename__ = "martial_guild_members"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("martial_guilds.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    contribution: Mapped[int] = mapped_column(Integer, default=0)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
