from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text, Table, SmallInteger, Numeric, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


friendship = Table(
    'friendships', Base.metadata,
    Column('id', Integer, primary_key=True, index=True, autoincrement=True),
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('friend_user_id', Integer, ForeignKey('users.id')),
    Column('status', SmallInteger, default=1),
    Column('group_name', String(50)),
    Column('remark', String(100)),
    Column('created_at', DateTime, default=datetime.utcnow),
    Column('updated_at', DateTime, default=datetime.utcnow, onupdate=datetime.utcnow),
)


# ==================== 一、账号与用户主数据 ====================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    status = Column(SmallInteger, default=1)
    register_ip = Column(String(50))
    last_login_ip = Column(String(50))
    last_login_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    nickname = Column(String(50))
    avatar = Column(String(255), default="👤")
    gender = Column(SmallInteger, default=0)
    birthday = Column(String(20))
    city_code = Column(String(20))
    city = Column(String(50))
    signature = Column(String(255), default="这家伙很懒，什么都没留下...")
    qq_number = Column(String(20))
    vip_level = Column(Integer, default=0)
    
    level = Column(Integer, default=1)
    exp = Column(Integer, default=0)
    popularity = Column(Integer, default=0)
    charm = Column(Integer, default=0)
    visit_count = Column(Integer, default=0)
    
    theme = Column(String(20), default="default")
    allow_visit = Column(Boolean, default=True)
    allow_message = Column(Boolean, default=True)
    show_online = Column(Boolean, default=True)
    language = Column(String(10), default="zh")
    online = Column(Boolean, default=False)

    family_id = Column(Integer, ForeignKey('families.id'), nullable=True)
    family_role = Column(String(20), default="member")

    wallet = relationship("Wallet", back_populates="user", uselist=False, cascade="all, delete-orphan")
    friends = relationship(
        "User", secondary=friendship,
        primaryjoin=id==friendship.c.user_id,
        secondaryjoin=id==friendship.c.friend_user_id,
        backref="friend_of"
    )
    
    jw_role = relationship("JingwuRole", back_populates="user", uselist=False, cascade="all, delete-orphan")
    farm = relationship("FarmProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    garden = relationship("GardenProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    town = relationship("TownProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    sea = relationship("SeaProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    summon = relationship("SummonProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    
    guestbook = relationship("MessageBoardPost", back_populates="owner", foreign_keys="MessageBoardPost.owner_user_id", cascade="all, delete-orphan")
    visits = relationship("HomepageVisit", back_populates="owner", foreign_keys="HomepageVisit.owner_user_id", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    inventory = relationship("InventoryItem", back_populates="user", cascade="all, delete-orphan")


# ==================== 二、钱包与经济系统 ====================

class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    user = relationship("User", back_populates="wallet")
    
    g_coin = Column(Integer, default=5000)
    gold_coin = Column(Integer, default=0)
    premium_coin = Column(Integer, default=0)
    silver_coin = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WalletLog(Base):
    __tablename__ = "wallet_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    currency_type = Column(String(20), nullable=False)
    change_amount = Column(Integer, default=0)
    before_amount = Column(Integer, default=0)
    after_amount = Column(Integer, default=0)
    source_type = Column(String(30))
    source_id = Column(Integer)
    remark = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)


# ==================== 三、家园主页与互动 ====================

class HomepageVisit(Base):
    __tablename__ = "homepage_visits"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="visits", foreign_keys=[owner_user_id])
    visitor_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    visitor_nickname = Column(String(50))
    source_module = Column(String(30))
    action_type = Column(String(30), default="visit")
    created_at = Column(DateTime, default=datetime.utcnow)


class MessageBoardPost(Base):
    __tablename__ = "message_board_posts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="guestbook", foreign_keys=[owner_user_id])
    author_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    author_nickname = Column(String(50))
    content = Column(Text, nullable=False)
    reply = Column(Text)
    status = Column(SmallInteger, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserActionLog(Base):
    __tablename__ = "user_actions_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action_key = Column(String(50), nullable=False)
    module_key = Column(String(30))
    value = Column(Integer, default=0)
    payload_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


# ==================== 四、好友系统 ====================

class FriendRequest(Base):
    __tablename__ = "friend_requests"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    to_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    from_nickname = Column(String(50))
    message = Column(String(200))
    status = Column(SmallInteger, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserBlacklist(Base):
    __tablename__ = "user_blacklists"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    blocked_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reason = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)


# ==================== 五、家族系统 ====================

class Family(Base):
    __tablename__ = "families"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    owner_user_id = Column(Integer, nullable=False)
    notice = Column(Text)
    description = Column(String(255))
    slogan = Column(String(255))
    level = Column(Integer, default=1)
    exp = Column(Integer, default=0)
    contribution_total = Column(Integer, default=0)
    funds = Column(Integer, default=0)
    member_limit = Column(Integer, default=20)
    status = Column(SmallInteger, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    members = relationship("User", backref="family", foreign_keys="User.family_id")


class FamilyMember(Base):
    __tablename__ = "family_members"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(20), default="member")
    contribution = Column(Integer, default=0)
    today_signin = Column(Boolean, default=False)
    joined_at = Column(DateTime, default=datetime.utcnow)


class FamilySignin(Base):
    __tablename__ = "family_signins"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reward_gcoin = Column(Integer, default=0)
    reward_contribution = Column(Integer, default=0)
    signed_at = Column(DateTime, default=datetime.utcnow)


class FamilyChatMessage(Base):
    __tablename__ = "family_chat_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_nickname = Column(String(50))
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ==================== 六、论坛系统 ====================

class Forum(Base):
    __tablename__ = "forums"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    category = Column(String(30))
    description = Column(String(255))
    icon = Column(String(50), default="📋")
    sort_order = Column(Integer, default=0)
    status = Column(SmallInteger, default=1)
    post_count = Column(Integer, default=0)


class ForumTopic(Base):
    __tablename__ = "forum_topics"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    forum_id = Column(Integer, ForeignKey("forums.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    user_nickname = Column(String(50))
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    view_count = Column(Integer, default=0)
    reply_count = Column(Integer, default=0)
    is_pinned = Column(Boolean, default=False)
    is_locked = Column(Boolean, default=False)
    is_elite = Column(Boolean, default=False)
    status = Column(SmallInteger, default=1)
    last_reply_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class ForumPost(Base):
    __tablename__ = "forum_posts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    topic_id = Column(Integer, ForeignKey("forum_topics.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    user_nickname = Column(String(50))
    content = Column(Text, nullable=False)
    status = Column(SmallInteger, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)


# ==================== 七、背包与商城 ====================

class InventoryTab(Base):
    __tablename__ = "inventory_tabs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    module_key = Column(String(30), default="common")
    capacity = Column(Integer, default=50)
    used_count = Column(Integer, default=0)


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="inventory")
    module_key = Column(String(30), default="common")
    item_type = Column(String(30))
    item_code = Column(String(50), nullable=False)
    item_name = Column(String(100))
    quantity = Column(Integer, default=1)
    locked = Column(Boolean, default=False)
    quality = Column(String(20), default="common")
    icon = Column(String(100))
    description = Column(Text)
    extra_json = Column(Text)
    expire_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class ShopItem(Base):
    __tablename__ = "shop_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    module_key = Column(String(30), default="common")
    item_code = Column(String(50), nullable=False)
    item_name = Column(String(100))
    price_currency = Column(String(20), default="g_coin")
    price_amount = Column(Integer, default=0)
    limit_per_day = Column(Integer, default=0)
    status = Column(SmallInteger, default=1)


# ==================== 八、消息、公告、活动、成就、图标 ====================

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="notifications")
    type = Column(String(30), default="system")
    module_key = Column(String(30))
    title = Column(String(100))
    content = Column(Text)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    scope_type = Column(String(30), default="all")
    scope_key = Column(String(50))
    start_at = Column(DateTime)
    end_at = Column(DateTime)
    status = Column(SmallInteger, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    type = Column(String(30))
    module_key = Column(String(30), default="home")
    start_at = Column(DateTime)
    end_at = Column(DateTime)
    status = Column(SmallInteger, default=1)
    config_json = Column(Text)


class ActivityProgress(Base):
    __tablename__ = "activity_progress"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    activity_id = Column(Integer, ForeignKey("activities.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    progress_value = Column(Integer, default=0)
    progress_json = Column(Text)
    reward_status = Column(SmallInteger, default=0)


class IconDef(Base):
    __tablename__ = "icons"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    icon_key = Column(String(50), unique=True)
    name = Column(String(50), nullable=False)
    icon = Column(String(100))
    source_module = Column(String(30))
    description = Column(String(255))
    unlock_rule_json = Column(Text)
    status = Column(SmallInteger, default=1)


class UserIcon(Base):
    __tablename__ = "user_icons"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    icon_id = Column(Integer, ForeignKey("icons.id"))
    is_lit = Column(Boolean, default=False)
    is_using = Column(Boolean, default=False)
    lit_at = Column(DateTime)


class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    category = Column(String(30))
    name = Column(String(50), nullable=False)
    description = Column(String(255))
    icon = Column(String(50))
    points = Column(Integer, default=10)
    rule_json = Column(Text)
    reward_json = Column(Text)


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    achievement_id = Column(Integer, ForeignKey("achievements.id"))
    progress_value = Column(Integer, default=0)
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime)


# ==================== 九、事件总线与排行 ====================

class PlatformEvent(Base):
    __tablename__ = "platform_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    module_key = Column(String(30))
    event_type = Column(String(50), nullable=False)
    event_payload_json = Column(Text)
    processed_status = Column(SmallInteger, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class RankDefinition(Base):
    __tablename__ = "rank_definitions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    rank_key = Column(String(50), unique=True)
    name = Column(String(50), nullable=False)
    module_key = Column(String(30))
    period_type = Column(String(20), default="total")
    calc_rule_json = Column(Text)


class RankSnapshot(Base):
    __tablename__ = "rank_snapshots"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    rank_key = Column(String(50))
    period_value = Column(String(20))
    user_id = Column(Integer, ForeignKey("users.id"))
    user_nickname = Column(String(50))
    score = Column(Integer, default=0)
    rank_no = Column(Integer)
    extra_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


# ==================== 十、精武堂模块 ====================

class JingwuRole(Base):
    """精武堂角色 - 潜能点/体力/修炼/头衔/货币/法宝武魂宠物关联"""
    __tablename__ = "jingwu_roles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    user = relationship("User", back_populates="jw_role")

    # ---- 基础信息 ----
    name = Column(String(50), nullable=False)
    gender = Column(SmallInteger, default=1)  # 1男 2女
    level = Column(Integer, default=1)
    exp = Column(Integer, default=0)
    title_id = Column(Integer, ForeignKey("jingwu_titles.id"), nullable=True)  # 头衔
    profession = Column(String(20), default="common")
    transferred = Column(Boolean, default=False)
    transfer_path = Column(String(20))
    transfer_name = Column(String(20))

    # ---- 潜能点系统（每级3点，5项加点）----
    # 体质→气血、智力→精气、力量→伤害、耐力→防御、敏捷→速度
    potential = Column(Integer, default=3)       # 可用潜能点（每级+3）
    con_point = Column(Integer, default=0)       # 体质点（影响气血）
    int_point = Column(Integer, default=0)       # 智力点（影响精气/MP）
    str_point = Column(Integer, default=0)       # 力量点（影响伤害）
    end_point = Column(Integer, default=0)       # 耐力点（影响防御）
    agi_point = Column(Integer, default=0)       # 敏捷点（影响速度）
    # 兼容旧字段
    mag_point = Column(Integer, default=0)
    def_point = Column(Integer, default=0)

    # ---- 气血/精气/体力 ----
    hp = Column(Integer, default=100)
    max_hp = Column(Integer, default=100)        # 基础气血 = 等级*20 + 体质*10
    mp = Column(Integer, default=50)
    max_mp = Column(Integer, default=50)         # 基础精气 = 等级*10 + 智力*5
    sp = Column(Integer, default=100)            # 体力（比武耗10，修炼耗20，上限100）
    max_sp = Column(Integer, default=100)        # 体力上限100
    last_sp_recover = Column(DateTime)           # 上次体力恢复时间
    # 兼容旧字段
    stamina = Column(Integer, default=100)
    max_stamina = Column(Integer, default=100)

    # ---- 战斗属性（由属性点+装备+帮派心法等综合计算）----
    damage = Column(Integer, default=10)         # 伤害（力量*2 + 装备）
    defense = Column(Integer, default=5)         # 防御（耐力*2 + 装备）
    speed = Column(Integer, default=10)          # 速度（敏捷*2 + 装备）
    accuracy = Column(Integer, default=100)      # 命中
    dodge = Column(Integer, default=0)           # 闪避%
    crit = Column(Integer, default=5)            # 暴击%
    crit_damage = Column(Integer, default=150)   # 暴击伤害%
    # 兼容旧字段
    base_damage = Column(Integer, default=10)
    base_defense = Column(Integer, default=5)
    base_speed = Column(Integer, default=10)
    base_accuracy = Column(Integer, default=100)
    base_dodge = Column(Integer, default=50)
    base_crit = Column(Integer, default=5)
    base_crit_damage = Column(Integer, default=150)

    # ---- 战斗统计 ----
    combat_power = Column(Integer, default=0)    # 战斗力
    wins_total = Column(Integer, default=0)
    losses_total = Column(Integer, default=0)
    wins_today = Column(Integer, default=0)
    losses_today = Column(Integer, default=0)
    wins_week = Column(Integer, default=0)
    losses_week = Column(Integer, default=0)

    # ---- 修炼状态：0空闲 1修炼中 2气血不顺 3走火入魔 ----
    train_status = Column(SmallInteger, default=0)
    train_type = Column(String(20))              # 普通修炼/修真(80+)/战神宫
    train_start = Column(DateTime)
    train_end = Column(DateTime)
    train_exp_bonus = Column(Float, default=1.0) # 修炼经验倍率
    xiuzhen_unlocked = Column(Boolean, default=False)  # 80级开启修真
    # 兼容旧字段
    is_training = Column(Boolean, default=False)
    training_type = Column(String(20))
    training_start = Column(DateTime)
    training_end = Column(DateTime)

    # ---- 货币系统 ----
    gcoin = Column(Integer, default=1000)        # G币
    yuanbao = Column(Integer, default=0)         # 元宝
    silver = Column(Integer, default=0)          # 银币（兼容）
    bind_yuanbao = Column(Integer, default=0)    # 绑定元宝

    # ---- 北极星/战神宫等扩展 ----
    polaris_level = Column(Integer, default=0)
    polaris_exp = Column(Integer, default=0)
    war_god_floor = Column(Integer, default=0)   # 战神宫层数
    gang_contribution = Column(Integer, default=0)

    # ---- 技能系统 ----
    skill_points = Column(Integer, default=0)     # 技能点（修炼获得，用于学技能）
    skill_pool = Column(JSON, default=list)       # 已装配技能ID列表（技能池，建议9-10个）
    skills_learned = Column(JSON, default=list)   # 已学技能ID列表

    # ---- 装备/法宝/武魂/宠物/帮派关联（use_alter解决循环外键排序问题）----
    talisman_id = Column(Integer, ForeignKey("jingwu_talismans.id", use_alter=True), nullable=True)  # 当前佩戴法宝
    wuhun_id = Column(Integer, ForeignKey("jingwu_wuhun.id", use_alter=True), nullable=True)         # 当前武魂
    active_pet_id = Column(Integer, ForeignKey("jingwu_pets.id", use_alter=True), nullable=True)     # 出战宠物
    gang_id = Column(Integer, ForeignKey("jingwu_gangs.id", use_alter=True), nullable=True)          # 所属帮派

    # ---- 闻香炉 & 异常状态 ----
    xianglu_level = Column(Integer, default=0)           # 闻香炉等级（恢复体力）
    xianglu_last_use = Column(DateTime)                  # 上次使用闻香炉时间
    possess_end_time = Column(DateTime)                  # 走火入魔结束时间

    # ---- 时间戳 ----
    last_battle_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ---- 关系 ----
    title = relationship("JingwuTitle")
    items = relationship("JingwuItem", back_populates="owner", cascade="all, delete-orphan")
    equipments = relationship("JingwuEquipment", back_populates="owner", cascade="all, delete-orphan")
    dungeon = relationship("JingwuDungeon", back_populates="role", uselist=False, cascade="all, delete-orphan")
    pets = relationship("JingwuPet", back_populates="owner", foreign_keys="JingwuPet.owner_id", cascade="all, delete-orphan")
    user_skills = relationship("JingwuUserSkill", back_populates="owner", cascade="all, delete-orphan")
    talismans = relationship("JingwuTalisman", back_populates="owner", foreign_keys="JingwuTalisman.owner_id", cascade="all, delete-orphan")
    talisman = relationship("JingwuTalisman", foreign_keys=[talisman_id])
    wuhun = relationship("JingwuWuhun", foreign_keys=[wuhun_id])
    active_pet = relationship("JingwuPet", foreign_keys=[active_pet_id])
    gang = relationship("JingwuGang", foreign_keys=[gang_id])


class JingwuItem(Base):
    __tablename__ = "jingwu_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("jingwu_roles.id"), nullable=False)
    owner = relationship("JingwuRole", back_populates="items")

    item_type = Column(String(20), nullable=False)
    category = Column(String(20), default="other")
    name = Column(String(100), nullable=False)
    description = Column(Text)
    icon = Column(String(255))
    quantity = Column(Integer, default=1)
    quality = Column(String(20), default="common")
    is_bound = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class JingwuEquipment(Base):
    """精武堂装备实例表 - 5部位/强化/精炼/孔数/宝石镶嵌"""
    __tablename__ = "jingwu_equipments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("jingwu_roles.id"), nullable=False)
    owner = relationship("JingwuRole", back_populates="equipments")

    # ---- 基础信息 ----
    name = Column(String(100), nullable=False)
    # 5部位：1手持(主伤害) 2身穿(主防御) 3头戴(主防御) 4脚穿(主速度) 5佩戴(主气血)
    slot = Column(SmallInteger, nullable=False)    # 1-5
    slot_name = Column(String(20))                 # weapon/armor/helmet/boots/accessory
    level_required = Column(Integer, default=1)
    template_id = Column(Integer, ForeignKey("jingwu_equip_templates.id"), nullable=True)  # 来源模板

    # ---- 强化/精炼 ----
    enhance_lv = Column(Integer, default=0)        # 强化等级 0-50+
    # 精炼品质：0粗糙 1普通 2优良 3优秀 4精良 5精致 6完美 7史诗 8史诗+1 9史诗+2 10史诗+3
    refine_quality = Column(SmallInteger, default=0)
    refine_quality_name = Column(String(20), default="粗糙")
    bind = Column(Boolean, default=True)           # 是否绑定

    # ---- 属性 ----
    main_attr_type = Column(String(20))            # 主属性类型：damage/defense/speed/hp
    main_attr_val = Column(Integer, default=0)     # 主属性值
    # 副属性JSON：{dodge_pct, crit_pct, atk_pct, spd_pct, def_pct, hp_suck_pct, mp_suck_pct}
    sub_attrs = Column(JSON, default=dict)

    # ---- 孔位与宝石镶嵌 ----
    hole_count = Column(SmallInteger, default=0)   # 总孔数(0-5)
    # 孔类型JSON：{holes: [{color:"青"/"橙"/"白", gem_id, gem_name, gem_attr}]}
    gems_embed = Column(JSON, default=list)        # 镶嵌宝石列表

    # ---- 兼容旧字段 ----
    quality = Column(String(20), default="common")
    damage = Column(Integer, default=0)
    defense = Column(Integer, default=0)
    hp = Column(Integer, default=0)
    speed = Column(Integer, default=0)
    accuracy = Column(Integer, default=0)
    dodge = Column(Integer, default=0)
    crit = Column(Integer, default=0)
    crit_damage = Column(Integer, default=0)
    enhance_level = Column(Integer, default=0)
    is_equipped = Column(Boolean, default=False)
    gem_slots = Column(Integer, default=0)
    gems = Column(String(255))

    # ---- 时间戳 ----
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class JingwuEquipTemplate(Base):
    """精武堂装备模板/锻造配方表 - 30/40/50级图谱+材料"""
    __tablename__ = "jingwu_equip_templates"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    # 部位：1手持 2身穿 3头戴 4脚穿 5佩戴
    slot = Column(SmallInteger, nullable=False)
    slot_name = Column(String(20))
    level_required = Column(Integer, nullable=False)   # 30/40/50/60...
    rarity = Column(String(20), default="common")      # 品质：普通/优良/优秀/精良/完美/史诗

    # ---- 基础主属性（打造出的装备主属性参考值）----
    main_attr_type = Column(String(20))                # damage/defense/speed/hp
    main_attr_base = Column(Integer, default=0)        # 基础主属性值

    # ---- 锻造配方 ----
    # 图谱ID/名称
    forge_tupu_id = Column(Integer)
    forge_tupu_name = Column(String(100))
    # 锻造材料JSON：{materials: [{item_id, item_name, count}]}
    forge_materials = Column(JSON, default=list)
    forge_gcoin = Column(Integer, default=0)           # 锻造G币费用

    # ---- 产出副属性池 ----
    sub_attr_pool = Column(JSON, default=list)         # 可能出现的副属性类型列表

    # ---- 模板元数据 ----
    icon = Column(String(255))
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class JingwuDungeon(Base):
    __tablename__ = "jingwu_dungeons"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    role_id = Column(Integer, ForeignKey("jingwu_roles.id"))
    role = relationship("JingwuRole", back_populates="dungeon")
    dungeon_id = Column(Integer, default=1)
    name = Column(String(50), default="三国副本")
    chapter = Column(Integer, default=1)
    stage = Column(Integer, default=1)
    daily_attempts = Column(Integer, default=3)
    max_attempts = Column(Integer, default=3)
    last_reset = Column(DateTime, default=datetime.utcnow)


class BattleLog(Base):
    __tablename__ = "battle_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    attacker_id = Column(Integer)
    defender_id = Column(Integer)
    winner_id = Column(Integer)
    battle_type = Column(String(20), default="pvp")
    rounds = Column(Integer, default=0)
    log = Column(Text)
    reward_silver = Column(Integer, default=0)
    reward_exp = Column(Integer, default=0)
    reward_items = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


# ==================== 十（补）精武堂扩展表：头衔/技能/宠物/法宝/等级经验 ====================

class JingwuTitle(Base):
    """精武堂头衔/称号配置表（少侠100G币~至尊战神200万元宝）"""
    __tablename__ = "jingwu_titles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title_code = Column(String(50), unique=True)
    name = Column(String(50), nullable=False, unique=True)   # 如：无名小卒/少侠/无敌圣者/至尊战神
    level_required = Column(Integer, default=0)              # 佩戴等级要求
    color = Column(String(20), default="#333")               # 称号颜色
    # 获取价格：gcoin_cost 或 yuanbao_cost
    gcoin_cost = Column(Integer, default=0)                  # G币价格
    yuanbao_cost = Column(Integer, default=0)                # 元宝价格
    # 属性加成JSON：{hp_pct, damage_pct, defense_pct, speed_pct, crit_pct...}
    bonus_json = Column(JSON, default=dict)
    req_win = Column(Integer, default=0)                     # 胜利数要求
    description = Column(String(200))
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)


class JingwuSkill(Base):
    """精武堂技能配置表（15个技能：攻击/辅助/特殊）"""
    __tablename__ = "jingwu_skills"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    skill_code = Column(String(50), unique=True)
    name = Column(String(50), nullable=False, unique=True)
    description = Column(Text)
    icon = Column(String(100))

    # 技能类型：attack攻击 / support辅助 / special特殊
    type = Column(String(20), nullable=False, default="attack")
    skill_type = Column(String(20), default="attack")  # 兼容旧字段

    # ---- 攻击类技能参数 ----
    damage_rate = Column(Integer, default=0)        # 伤害倍率%（剑气凌风120/御剑通灵180/人剑合一200/潇湘剑雨360）
    damage_mult = Column(Float, default=1.0)        # 兼容旧字段
    dot_rounds = Column(Integer, default=0)         # 持续伤害回合数（剑影留痕4回合）
    dot_percent = Column(Integer, default=0)        # 每回合持续伤害%（剑影留痕10%气血）

    # ---- 治疗/回复类 ----
    heal_percent = Column(Integer, default=0)       # 即时回复%（妙手回春回50%）
    heal_pct = Column(Float, default=0.0)           # 兼容旧字段
    heal_type = Column(String(20))                  # hp/mp/both
    heal_cond_hp_percent = Column(Integer, default=0)   # 触发条件：气血低于X%（妙手回春<50%）
    heal_cond_mp_percent = Column(Integer, default=0)   # 触发条件：精气低于X%（神清气朗<30%）
    hot_rounds = Column(Integer, default=0)         # 持续回复回合数（五灵归宗4回合）
    hot_percent = Column(Integer, default=0)        # 每回合回复%（五灵归宗10%）

    # ---- 封印/控制类 ----
    seal_rounds = Column(Integer, default=0)        # 封印回合数（天罗地网2/三清缚影3）
    control_turns = Column(Integer, default=0)      # 兼容旧字段

    # ---- 反弹/反制类 ----
    reflect_percent = Column(Integer, default=0)    # 反弹伤害%（回风扫叶50%）
    reflect_rounds = Column(Integer, default=0)     # 反弹持续回合数（4回合）
    counter_pct = Column(Float, default=0.0)        # 兼容旧字段

    # ---- 特殊技能 ----
    absorb_exp_target = Column(String(20))          # 吸星功法：好友
    lifesteal_pct = Column(Float, default=0.0)      # 吸血比例（兼容）
    transfer_dmg_to_hp = Column(Boolean, default=False)  # 斗转星移：伤害转气血
    swap_attrs = Column(Boolean, default=False)     # 移形换影：交换属性
    shield = Column(Boolean, default=False)         # 金钟护体

    # ---- 消耗 ----
    cost_mp = Column(Integer, default=0)            # 精气消耗
    mp_cost = Column(Integer, default=10)           # 兼容旧字段
    cost_sp = Column(Integer, default=0)            # 体力消耗
    cost_gcoin = Column(Integer, default=0)         # G币消耗/学习费用
    cost_yuanbao = Column(Integer, default=0)       # 元宝消耗
    price_gcoin = Column(Integer, default=0)        # 兼容旧字段
    price_sp = Column(Integer, default=0)           # 兼容旧字段

    # ---- 学习条件 ----
    level_required = Column(Integer, default=1)     # 等级要求
    req_level = Column(Integer, default=1)          # 兼容旧字段
    trigger_cond = Column(String(100))              # 触发条件描述
    learn_gcoin = Column(Integer, default=0)
    learn_yuanbao = Column(Integer, default=0)
    is_default = Column(Boolean, default=False)     # 是否默认技能（吸星功法）
    quality = Column(String(20), default="common")  # common/good/excellent/epic/legendary

    # ---- 效果JSON（通用扩展）----
    effect_json = Column(Text)

    # ---- 排序/状态 ----
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class JingwuUserSkill(Base):
    """用户已学技能关联表"""
    __tablename__ = "jingwu_user_skills"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("jingwu_roles.id"), nullable=False)
    skill_id = Column(Integer, ForeignKey("jingwu_skills.id"), nullable=False)
    level = Column(Integer, default=1)
    skill_level = Column(Integer, default=1)        # 技能等级（熟练度）
    proficiency = Column(Integer, default=0)        # 熟练度
    is_equipped = Column(Boolean, default=False)    # 是否装配到技能栏
    equipped_slot = Column(SmallInteger)            # 技能栏位置1-6
    learned_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("JingwuRole", back_populates="user_skills")
    skill = relationship("JingwuSkill")


class JingwuPetTemplate(Base):
    """宠物模板表（4种族基础配置）"""
    __tablename__ = "jingwu_pet_templates"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    pet_code = Column(String(50), unique=True)
    name = Column(String(50), nullable=False)
    # 4种族：1龙(主血) 2虎(主速) 3凤(主精) 4龟(主防)
    race = Column(SmallInteger, nullable=False)
    race_name = Column(String(20))                  # 龙/虎/凤/龟
    talent_name = Column(String(50))                # 龙凝血/虎瞬移/凤噬魔/龟格挡
    talent_desc = Column(Text)
    talent_effect_json = Column(JSON, default=dict)

    icon = Column(String(100), default="🐾")
    quality = Column(String(20), default="common")

    # 1级基础属性
    base_hp = Column(Integer, default=100)
    base_mp = Column(Integer, default=50)
    base_damage = Column(Integer, default=10)
    base_defense = Column(Integer, default=5)
    base_speed = Column(Integer, default=10)

    # 每级成长
    grow_hp = Column(Float, default=10)
    grow_mp = Column(Float, default=5)
    grow_damage = Column(Float, default=2)
    grow_defense = Column(Float, default=1)
    grow_speed = Column(Float, default=1)

    # 附身给人物加成比例%
    possess_bonus_json = Column(JSON, default=dict)
    battle_skill = Column(String(50))               # 出战技能名
    description = Column(Text)
    price_gcoin = Column(Integer, default=0)
    price_yuanbao = Column(Integer, default=0)


class JingwuPet(Base):
    """精武堂宠物表（4种族/5阶段/1-14星/100级）"""
    __tablename__ = "jingwu_pets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("jingwu_roles.id"), nullable=False)

    # ---- 基础信息 ----
    name = Column(String(50), nullable=False)
    nickname = Column(String(50))
    template_id = Column(Integer, ForeignKey("jingwu_pet_templates.id"), nullable=True)
    pet_code = Column(String(50))
    # 4种族：1龙(主血) 2虎(主速) 3凤(主精) 4龟(主防)
    race = Column(SmallInteger, nullable=False)
    race_name = Column(String(20))
    talent_name = Column(String(50))                # 天赋：龙凝血/虎瞬移/凤噬魔/龟格挡

    # ---- 阶段与星级 ----
    # 5阶段：1野兽(1-19) 2灵兽(20-39) 3妖兽(40-59) 4圣兽(60-79) 5神兽(80-100)
    stage = Column(SmallInteger, default=1)
    stage_name = Column(String(20), default="野兽")
    star = Column(SmallInteger, default=1)          # 星级1-14
    max_star = Column(SmallInteger, default=14)

    # ---- 等级经验 ----
    level = Column(Integer, default=1)
    max_level = Column(Integer, default=100)        # 宠物等级上限100
    exp = Column(Integer, default=0)
    exp_required = Column(Integer, default=100)

    # ---- 吞噬系统 ----
    devour_count = Column(Integer, default=0)       # 吞噬次数
    devour_limit = Column(Integer, default=1000)   # 吞噬上限
    quality = Column(String(20), default="common")

    # ---- 状态：0休息 1携带(出战) 2附身(加属性) ----
    status = Column(SmallInteger, default=0)
    is_resting = Column(Boolean, default=True)
    is_battling = Column(Boolean, default=False)    # 出战
    is_possessing = Column(Boolean, default=False)  # 附身（兼容旧字段）

    # ---- 属性 ----
    hp = Column(Integer, default=100)
    max_hp = Column(Integer, default=100)
    mp = Column(Integer, default=50)
    max_mp = Column(Integer, default=50)
    damage = Column(Integer, default=10)
    defense = Column(Integer, default=5)
    speed = Column(Integer, default=10)
    intimacy = Column(Integer, default=0)           # 亲密度
    loyalty = Column(Integer, default=100)          # 忠诚度

    # ---- 技能 ----
    skills_json = Column(JSON, default=list)        # 宠物技能列表

    # ---- 时间戳 ----
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ---- 关系 ----
    owner = relationship("JingwuRole", back_populates="pets", foreign_keys=[owner_id])
    template = relationship("JingwuPetTemplate")


class JingwuTalisman(Base):
    """精武堂法宝表（50级开启，9阶段，熟练度/孔数/属性词条）"""
    __tablename__ = "jingwu_talismans"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("jingwu_roles.id"), nullable=False)

    name = Column(String(100), nullable=False)
    icon = Column(String(100))
    quality = Column(String(20), default="common")

    # ---- 阶段（9阶）：0一元 1二气 2三才 3四相 4五仪 5六甲 6七星 7八卦 8九宫 ----
    stage = Column(SmallInteger, default=0)
    stage_name = Column(String(20), default="一元")
    level = Column(Integer, default=1)              # 兼容旧字段
    level_required = Column(Integer, default=50)    # 50级开启

    # ---- 熟练度 ----
    exp = Column(Integer, default=0)
    proficiency = Column(Integer, default=0)        # 熟练度
    max_proficiency = Column(Integer, default=10000)

    # ---- 孔数与宝石 ----
    hole_count = Column(SmallInteger, default=0)    # 孔数(0-3)
    gems_embed = Column(JSON, default=list)         # 镶嵌宝石

    # ---- 属性词条JSON ----
    # 可出现词条：怒斩/韧性/闪击/精准/必杀/血速/圣盾/技伤/减暴伤
    # 格式：{attrs:[{name:"怒斩", val:5}, {name:"韧性", val:3}]}
    attr_json = Column(JSON, default=dict)
    attrs_count = Column(SmallInteger, default=0)   # 已激活词条数
    max_attrs = Column(SmallInteger, default=5)     # 最大词条数

    # ---- 战斗属性加成（由词条汇总）----
    damage = Column(Integer, default=0)
    defense = Column(Integer, default=0)
    hp = Column(Integer, default=0)
    speed = Column(Integer, default=0)
    crit = Column(Integer, default=0)
    skill_name = Column(String(50))
    skill_desc = Column(Text)

    # ---- 状态 ----
    is_equipped = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("JingwuRole", foreign_keys=[owner_id], back_populates="talismans")


class JingwuLevelExp(Base):
    """精武堂等级经验配置表（1-150级，含修炼4小时经验）"""
    __tablename__ = "jingwu_level_exp"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    level = Column(Integer, unique=True, nullable=False)
    exp_needed = Column(Integer, default=0)         # 升级所需经验
    exp_4h_normal = Column(Integer, default=0)      # 普通修炼4小时经验
    exp_4h_xiuzhen = Column(Integer, default=0)     # 80+修真4小时双倍经验
    title_name = Column(String(50))                 # 对应称号名
    max_sp = Column(Integer, default=100)           # 体力上限
    potential_gain = Column(Integer, default=3)     # 该等级获得潜能点数（每级3）
    # 关键等级数据参考：
    # 1级: exp=240, normal=20, xiuzhen=0
    # 10级: exp=4560, normal=3168
    # 20级: exp=12480, normal=27720
    # 150级: exp=1215840, xiuzhen=1151329608


# ==================== 十一、阳光农场模块 ====================

class FarmProfile(Base):
    __tablename__ = "farm_profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    user = relationship("User", back_populates="farm")

    farm_level = Column(Integer, default=1)
    farm_exp = Column(Integer, default=0)
    farm_gold = Column(Integer, default=1000)
    land_count = Column(Integer, default=6)
    barn_level = Column(Integer, default=1)
    weather_seed = Column(String(20), default="sunny")
    created_at = Column(DateTime, default=datetime.utcnow)

    plots = relationship("FarmPlot", back_populates="farm", cascade="all, delete-orphan")
    animals = relationship("FarmAnimal", back_populates="farm", cascade="all, delete-orphan")
    storage = relationship("FarmStorage", back_populates="farm", cascade="all, delete-orphan")


class FarmPlot(Base):
    __tablename__ = "farm_plots"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    farm_id = Column(Integer, ForeignKey("farm_profiles.id"), nullable=False)
    farm = relationship("FarmProfile", back_populates="plots")
    user_id = Column(Integer, ForeignKey("users.id"))
    plot_no = Column(Integer, nullable=False)
    status = Column(String(20), default="idle")
    crop_code = Column(String(50))
    crop_name = Column(String(50))
    stage = Column(String(20))
    planted_at = Column(DateTime)
    ready_at = Column(DateTime)
    water_count = Column(Integer, default=0)
    fertilizer_count = Column(Integer, default=0)
    insect_state = Column(Boolean, default=False)
    weed_state = Column(Boolean, default=False)


class FarmAnimal(Base):
    __tablename__ = "farm_animals"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    farm_id = Column(Integer, ForeignKey("farm_profiles.id"), nullable=False)
    farm = relationship("FarmProfile", back_populates="animals")
    user_id = Column(Integer, ForeignKey("users.id"))
    animal_code = Column(String(50))
    animal_name = Column(String(50))
    status = Column(String(20), default="baby")
    hunger = Column(Integer, default=100)
    health = Column(Integer, default=100)
    ready_at = Column(DateTime)
    production_ready = Column(Boolean, default=False)
    bought_at = Column(DateTime, default=datetime.utcnow)
    shed_index = Column(Integer)


class FarmStorage(Base):
    __tablename__ = "farm_storage"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    farm_id = Column(Integer, ForeignKey("farm_profiles.id"), nullable=False)
    farm = relationship("FarmProfile", back_populates="storage")
    user_id = Column(Integer, ForeignKey("users.id"))
    item_code = Column(String(50), nullable=False)
    item_name = Column(String(50))
    item_type = Column(String(20), default="crop")
    quantity = Column(Integer, default=0)
    locked = Column(Boolean, default=False)


class FarmFriendAction(Base):
    __tablename__ = "farm_friend_actions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"))
    target_user_id = Column(Integer, ForeignKey("users.id"))
    action_type = Column(String(30), nullable=False)
    target_plot_id = Column(Integer)
    reward_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class FarmVillage(Base):
    __tablename__ = "farm_villages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255))
    level = Column(Integer, default=1)
    exp = Column(Integer, default=0)
    member_count = Column(Integer, default=1)
    member_limit = Column(Integer, default=20)
    funds = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class Crop(Base):
    """作物字典（spec 阳光牧场作物数据表：50作物 × 等级/类型/单价/产量/成熟/再熟/售价）"""
    __tablename__ = "farm_crops"

    key = Column(String(32), primary_key=True)
    name = Column(String(32))
    grow_seconds = Column(Integer, default=60)   # 总成熟时长（秒）
    stages = Column(Integer, default=4)          # 阶段数(种子/发芽/生长/成熟)
    seed_item_key = Column(String(64))
    harvest_item_key = Column(String(64))
    harvest_exp = Column(Integer, default=10)
    price = Column(Integer, default=50)          # 种子价格
    level_req = Column(Integer, default=0)       # 解锁等级
    crop_type = Column(String(16), default="一季")  # 一季/多季
    min_yield = Column(Integer, default=25)      # 最低产量
    regrow_seconds = Column(Integer, default=0)  # 再熟间隔(秒)，0=一季
    sell_price = Column(Integer, default=0)      # 果实售价


class ItemFarm(Base):
    """阳光牧场物品字典（50 种子 + 50 收获物）"""
    __tablename__ = "farm_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key = Column(String(64), unique=True, index=True)
    name = Column(String(32))
    type = Column(String(16))
    module_key = Column(String(32), default="farm")
    sell_price = Column(Integer, default=0)
    description = Column(String(128), default="")


# ==================== 十二、美味小镇模块 ====================

class TownProfile(Base):
    __tablename__ = "town_profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    user = relationship("User", back_populates="town")

    restaurant_level = Column(Integer, default=1)
    restaurant_exp = Column(Integer, default=0)
    restaurant_name = Column(String(50), default="我的餐厅")
    star_level = Column(Integer, default=1)
    street_code = Column(String(30), default="chinese")
    oil_amount = Column(Integer, default=100)
    gold = Column(Integer, default=5000)
    seats = Column(Integer, default=4)
    created_at = Column(DateTime, default=datetime.utcnow)

    tables = relationship("TownTable", back_populates="town", cascade="all, delete-orphan")
    recipes = relationship("TownUserRecipe", back_populates="town", cascade="all, delete-orphan")
    ingredients = relationship("TownIngredient", back_populates="town", cascade="all, delete-orphan")


class TownTable(Base):
    __tablename__ = "town_tables"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    town_id = Column(Integer, ForeignKey("town_profiles.id"), nullable=False)
    town = relationship("TownProfile", back_populates="tables")
    user_id = Column(Integer, ForeignKey("users.id"))
    table_no = Column(Integer, nullable=False)
    status = Column(String(20), default="idle")
    waiter_id = Column(Integer)


class TownRecipe(Base):
    __tablename__ = "town_recipes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    recipe_code = Column(String(50), unique=True)
    name = Column(String(100), nullable=False)
    street_code = Column(String(30))
    level_required = Column(Integer, default=1)
    quality_type = Column(String(20), default="normal")
    ingredient_json = Column(Text)
    oil_cost = Column(Integer, default=1)
    gold_income = Column(Integer, default=10)
    exp_income = Column(Integer, default=5)


class TownUserRecipe(Base):
    __tablename__ = "town_user_recipes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    town_id = Column(Integer, ForeignKey("town_profiles.id"), nullable=False)
    town = relationship("TownProfile", back_populates="recipes")
    user_id = Column(Integer, ForeignKey("users.id"))
    recipe_id = Column(Integer, ForeignKey("town_recipes.id"))
    quality_level = Column(String(20), default="normal")
    learned_at = Column(DateTime, default=datetime.utcnow)


class TownIngredient(Base):
    __tablename__ = "town_ingredients"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    town_id = Column(Integer, ForeignKey("town_profiles.id"), nullable=False)
    town = relationship("TownProfile", back_populates="ingredients")
    user_id = Column(Integer, ForeignKey("users.id"))
    ingredient_code = Column(String(50), nullable=False)
    ingredient_name = Column(String(50))
    quantity = Column(Integer, default=0)
    locked = Column(Boolean, default=False)


class TownFriendAction(Base):
    __tablename__ = "town_friend_actions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"))
    target_user_id = Column(Integer, ForeignKey("users.id"))
    action_type = Column(String(30), nullable=False)
    reward_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class TownWaiter(Base):
    __tablename__ = "town_waiters"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    town_id = Column(Integer, ForeignKey("town_profiles.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    friend_user_id = Column(Integer, ForeignKey("users.id"))
    friend_nickname = Column(String(50))
    status = Column(String(20), default="on")
    bound_table_count = Column(Integer, default=0)
    salary = Column(Integer, default=100)
    hired_at = Column(DateTime, default=datetime.utcnow)


class TownOrder(Base):
    __tablename__ = "town_orders"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    town_id = Column(Integer, ForeignKey("town_profiles.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    table_id = Column(Integer, ForeignKey("town_tables.id"))
    customer_type = Column(String(20), default="normal")
    recipe_id = Column(Integer, ForeignKey("town_recipes.id"))
    recipe_name = Column(String(100))
    status = Column(String(20), default="waiting")
    reward_gold = Column(Integer, default=0)
    reward_exp = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


class ItemTown(Base):
    """美味小镇物品字典（222 食材：217 具名 + 5 万能）"""
    __tablename__ = "town_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key = Column(String(64), unique=True, index=True)
    name = Column(String(32))
    type = Column(String(16))
    module_key = Column(String(32), default="town")
    sell_price = Column(Integer, default=0)
    description = Column(String(128), default="")


# ==================== 十三、魔法花园模块 ====================

class GardenProfile(Base):
    __tablename__ = "garden_profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    user = relationship("User", back_populates="garden")

    garden_level = Column(Integer, default=1)
    garden_exp = Column(Integer, default=0)
    gold = Column(Integer, default=500)
    plot_count = Column(Integer, default=6)
    album_lit_count = Column(Integer, default=0)
    reputation = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    plots = relationship("GardenPlot", back_populates="garden", cascade="all, delete-orphan")
    flowers = relationship("GardenUserFlower", back_populates="garden", cascade="all, delete-orphan")


class GardenPlot(Base):
    __tablename__ = "garden_plots"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    garden_id = Column(Integer, ForeignKey("garden_profiles.id"), nullable=False)
    garden = relationship("GardenProfile", back_populates="plots")
    user_id = Column(Integer, ForeignKey("users.id"))
    plot_no = Column(Integer, nullable=False)
    seed_code = Column(String(50))
    flower_name = Column(String(50))
    stage = Column(String(20))
    color = Column(String(20))
    planted_at = Column(DateTime)
    ready_at = Column(DateTime)
    watered = Column(Boolean, default=False)
    weeded = Column(Boolean, default=False)
    insect_state = Column(Boolean, default=False)


class GardenFlower(Base):
    __tablename__ = "garden_flowers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    flower_code = Column(String(50), unique=True)
    seed_code = Column(String(50))
    name = Column(String(50), nullable=False)
    rarity = Column(String(20), default="common")
    base_colors_json = Column(Text)
    price = Column(Integer, default=10)
    exp_gain = Column(Integer, default=5)
    grow_time = Column(Integer, default=300)
    album_group = Column(String(30))


class GardenUserFlower(Base):
    __tablename__ = "garden_user_flowers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    garden_id = Column(Integer, ForeignKey("garden_profiles.id"), nullable=False)
    garden = relationship("GardenProfile", back_populates="flowers")
    user_id = Column(Integer, ForeignKey("users.id"))
    flower_code = Column(String(50), nullable=False)
    flower_name = Column(String(50))
    color = Column(String(20))
    quantity = Column(Integer, default=0)
    storage_type = Column(String(20), default="flower")


class GardenAlbumEntry(Base):
    __tablename__ = "garden_album_entries"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    flower_code = Column(String(50))
    flower_name = Column(String(50))
    color = Column(String(20))
    category = Column(String(30))
    sort_order = Column(Integer, default=0)


class GardenUserAlbum(Base):
    __tablename__ = "garden_user_album"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    album_entry_id = Column(Integer, ForeignKey("garden_album_entries.id"))
    is_lit = Column(Boolean, default=False)
    lit_at = Column(DateTime)


class GardenFriendAction(Base):
    __tablename__ = "garden_friend_actions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"))
    target_user_id = Column(Integer, ForeignKey("users.id"))
    action_type = Column(String(30), nullable=False)
    flower_code = Column(String(50))
    reward_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class GardenComposeRule(Base):
    __tablename__ = "garden_compose_rules"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    target_seed_code = Column(String(50), nullable=False)
    target_flower_name = Column(String(50))
    cost_json = Column(Text, nullable=False)
    success_rate = Column(Numeric(5, 2), default=1.00)
    gold_cost = Column(Integer, default=0)


# ==================== 魔法花园完整数据（迁移自 3g_games，与上方简化表并存） ====================

class ItemGarden(Base):
    """魔法花园物品字典（520 作物 + 1024 材料）"""
    __tablename__ = "garden_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key = Column(String(64), unique=True, index=True)
    name = Column(String(32))
    type = Column(String(16))
    module_key = Column(String(32), default="garden")
    sell_price = Column(Integer, default=0)
    description = Column(String(128), default="")


class GardenSeed(Base):
    """花种定义（Seed）：播种用的物品定义"""
    __tablename__ = "garden_seeds"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key = Column(String(32), unique=True, index=True)
    name = Column(String(32))
    min_level = Column(Integer, default=1)
    grow_seconds = Column(Integer, default=60)
    stages = Column(Integer, default=4)
    stage_actions = Column(Text, default="")
    yield_min = Column(Integer, default=1)
    yield_max = Column(Integer, default=2)
    possible_blooms = Column(Text, default="")
    rarity = Column(String(16), default="普通")
    item_level = Column(Integer, default=1)
    sellable = Column(Boolean, default=True)
    seed_item_key = Column(String(64))
    obtain_sources = Column(String(128), default="shop")


class GardenBloom(Base):
    """花朵定义（Bloom）：收获得到的实体花朵定义"""
    __tablename__ = "garden_blooms"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key = Column(String(32), unique=True, index=True)
    name = Column(String(32))
    color = Column(String(16), default="白")
    rarity = Column(String(16), default="普通")
    item_level = Column(Integer, default=1)
    sell_price = Column(Integer, default=10)
    album_entry_key = Column(String(32))
    item_key = Column(String(64))
    special_tag = Column(String(32), default="")


class GardenAlbumEntryFull(Base):
    """花谱项（AlbumEntry）：图鉴收集条目，按系列分组（完整数据，与简化 GardenAlbumEntry 并存）"""
    __tablename__ = "garden_album_entries_full"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key = Column(String(32), unique=True, index=True)
    series = Column(String(32), index=True)
    name = Column(String(32))
    description = Column(String(128), default="")
    bloom_key = Column(String(32))


class GardenRecipe(Base):
    """合成配方：花朵/材料 -> 花种"""
    __tablename__ = "garden_recipes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(32))
    result_seed_key = Column(String(32))
    result_qty = Column(Integer, default=1)
    materials = Column(Text)
    success_rate = Column(Integer, default=80)
    fail_credit_threshold = Column(Integer, default=5)
    target_level = Column(Integer, default=1)
    require_lock_check = Column(Boolean, default=False)


class GardenOrderTemplate(Base):
    """订单模板：订单池按等级分层 pool(L)"""
    __tablename__ = "garden_order_templates"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_type = Column(String(16), default="normal", index=True)
    requirements = Column(Text)
    level_min = Column(Integer, default=1, index=True)
    level_max = Column(Integer, default=99)
    weight = Column(Integer, default=100)
    created_at = Column(DateTime, default=datetime.utcnow)


# ==================== 十四、纵横四海模块 ====================

class SeaProfile(Base):
    __tablename__ = "sea_profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    user = relationship("User", back_populates="sea")

    level = Column(Integer, default=1)
    exp = Column(Integer, default=0)
    current_city_code = Column(String(50), default="quanzhou")
    silver_coin = Column(Integer, default=1000)
    power = Column(Integer, default=100)
    max_power = Column(Integer, default=100)
    reputation = Column(Integer, default=0)
    ship_name = Column(String(50), default="我的船")
    ship_level = Column(Integer, default=1)
    ship_hp = Column(Integer, default=100)
    ship_max_hp = Column(Integer, default=100)
    ship_damage = Column(Integer, default=10)
    ship_defense = Column(Integer, default=5)
    ship_capacity = Column(Integer, default=50)
    supplies = Column(Integer, default=100)
    max_supplies = Column(Integer, default=100)
    created_at = Column(DateTime, default=datetime.utcnow)

    tasks = relationship("SeaUserTask", back_populates="sea", cascade="all, delete-orphan")


class SeaCity(Base):
    __tablename__ = "sea_cities"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    city_code = Column(String(50), unique=True)
    name = Column(String(50), nullable=False)
    region = Column(String(30))
    level_range = Column(String(20))
    description = Column(String(255))
    unlock_rule_json = Column(Text)


class SeaUserCity(Base):
    __tablename__ = "sea_user_cities"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    city_id = Column(Integer, ForeignKey("sea_cities.id"))
    unlocked = Column(Boolean, default=False)
    unlocked_at = Column(DateTime)


class SeaRoute(Base):
    __tablename__ = "sea_routes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    from_city_code = Column(String(50))
    to_city_code = Column(String(50))
    danger_level = Column(Integer, default=1)
    travel_time = Column(Integer, default=60)
    event_pool_json = Column(Text)


class SeaTask(Base):
    __tablename__ = "sea_tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    task_type = Column(String(30), default="main")
    title = Column(String(100), nullable=False)
    description = Column(Text)
    city_code = Column(String(50))
    level_required = Column(Integer, default=1)
    objective_json = Column(Text)
    reward_json = Column(Text)


class SeaUserTask(Base):
    __tablename__ = "sea_user_tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    sea_id = Column(Integer, ForeignKey("sea_profiles.id"), nullable=False)
    sea = relationship("SeaProfile", back_populates="tasks")
    user_id = Column(Integer, ForeignKey("users.id"))
    task_id = Column(Integer, ForeignKey("sea_tasks.id"))
    status = Column(String(20), default="available")
    progress_json = Column(Text)
    accepted_at = Column(DateTime)
    completed_at = Column(DateTime)


class SeaEvent(Base):
    __tablename__ = "sea_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    route_id = Column(Integer)
    event_type = Column(String(30))
    result_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class SeaBattle(Base):
    __tablename__ = "sea_battles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    enemy_type = Column(String(30))
    enemy_name = Column(String(50))
    battle_result = Column(String(10))
    reward_json = Column(Text)
    log = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class SeaEquipment(Base):
    __tablename__ = "sea_equipments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    equip_code = Column(String(50), unique=True)
    name = Column(String(100), nullable=False)
    slot_type = Column(String(20))
    rarity = Column(String(20), default="common")
    level_required = Column(Integer, default=1)
    base_attr_json = Column(Text)
    icon = Column(String(100))
    price = Column(Integer, default=0)


class SeaUserEquipment(Base):
    __tablename__ = "sea_user_equipments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    equip_id = Column(Integer, ForeignKey("sea_equipments.id"))
    enhance_level = Column(Integer, default=0)
    gem_json = Column(Text)
    equipped = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ItemSea(Base):
    """纵横四海物品字典（宝石/卡片/消耗品/船只等，可被背包引用）"""
    __tablename__ = "sea_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key = Column(String(64), unique=True, index=True)
    name = Column(String(32))
    type = Column(String(16))
    module_key = Column(String(32), default="sea")
    sell_price = Column(Integer, default=0)
    description = Column(String(128), default="")


class SeaDungeon(Base):
    """副本定义（spec 副本等级要求表）"""
    __tablename__ = "sea_dungeons"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key = Column(String(32), unique=True, index=True)
    name = Column(String(32))
    entry_city = Column(String(32))
    difficulties = Column(Text, default="[]")
    level_reqs = Column(Text, default="[]")
    exps = Column(Text, default="[]")
    drops = Column(Text, default="[]")
    open_days = Column(Text, default="[]")


class SeaEquipSet(Base):
    """装备套装定义（spec 装备套装路线：等级 + 获取方式）"""
    __tablename__ = "sea_equip_sets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key = Column(String(32), unique=True, index=True)
    name = Column(String(32))
    level_req = Column(Integer, default=1)
    source = Column(String(128))
    pieces = Column(Integer, default=4)


class SeaEquipPiece(Base):
    """装备部件件名（spec 全部装备件名清单）

    set_key:   所属套装 key（散件为空）
    slot:      部位 武器/副手/头盔/衣服/腰带/鞋子/配饰
    confirmed: 是否官方文本确认件名（False=按命名规律推测）
    """
    __tablename__ = "sea_equip_pieces"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key = Column(String(32), unique=True, index=True)
    name = Column(String(32))
    set_key = Column(String(32), default="", index=True)
    slot = Column(String(16))
    level_req = Column(Integer, default=1)
    source = Column(String(128), default="")
    confirmed = Column(Boolean, default=False)


class SeaHolyMark(Base):
    """圣痕定义（spec 圣痕种类：10种，白/绿/蓝/紫品质）"""
    __tablename__ = "sea_holy_marks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key = Column(String(32), unique=True, index=True)
    name = Column(String(32))
    quality = Column(String(16))


class SeaShip(Base):
    """船只字典（spec 船只系统：14 艘船）"""
    __tablename__ = "sea_ships"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key = Column(String(32), unique=True, index=True)
    name = Column(String(32))
    buy_city = Column(String(64), default="")
    price = Column(Integer, default=1000)
    currency = Column(String(8), default="铜")
    load = Column(Integer, default=35)
    consume_per_100 = Column(Integer, default=15)


class SeaMainQuest(Base):
    """主线任务链（spec 主线任务系统：12 条链）"""
    __tablename__ = "sea_main_quests"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key = Column(String(32), unique=True, index=True)
    name = Column(String(32))
    rounds = Column(Integer, default=10)
    reward_desc = Column(String(255), default="")
    sort = Column(Integer, default=0)


class SeaCitySpecialty(Base):
    """城市贸易特产（spec 贸易跑商：每城市特产列表）"""
    __tablename__ = "sea_city_specialties"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    city_key = Column(String(32), unique=True, index=True)
    city_name = Column(String(32))
    region = Column(String(16), default="")
    specialties = Column(Text, default="[]")


class SeaPetSkill(Base):
    """宠物技能字典（spec 宠物技能：23 种技能 + T0/T1/T2 分级）"""
    __tablename__ = "sea_pet_skills"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key = Column(String(32), unique=True, index=True)
    name = Column(String(32))
    effect = Column(String(255), default="")
    tier = Column(String(4), default="T2")


# ==================== 十五、家园主页配置 ====================

class UserHomepage(Base):
    __tablename__ = "user_homepages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    skin_id = Column(Integer, default=1)
    background_id = Column(Integer, default=1)
    music_id = Column(Integer)
    layout_json = Column(Text)
    visit_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    guestbook_count = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class HomepageModule(Base):
    __tablename__ = "homepage_modules"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    module_key = Column(String(50), unique=True, nullable=False)
    name = Column(String(50), nullable=False)
    type = Column(String(20), default="display")
    default_enabled = Column(Boolean, default=True)
    config_schema = Column(Text)
    icon = Column(String(50))


class UserHomepageModule(Base):
    __tablename__ = "user_homepage_modules"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    module_key = Column(String(50), nullable=False)
    position = Column(Integer, default=0)
    enabled = Column(Boolean, default=True)
    config_json = Column(Text)


# ==================== 十六、聊天室 ====================

class ChatRoom(Base):
    __tablename__ = "chat_rooms"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    room_type = Column(String(20), default="public")
    room_key = Column(String(50), unique=True)
    name = Column(String(100), nullable=False)
    status = Column(SmallInteger, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    user_nickname = Column(String(50))
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ==================== 十七、同城系统 ====================

class City(Base):
    __tablename__ = "cities"

    code = Column(String(20), primary_key=True)
    name = Column(String(50), nullable=False)
    province = Column(String(50))
    status = Column(SmallInteger, default=1)


class CityFeed(Base):
    __tablename__ = "city_feeds"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    city_code = Column(String(20), ForeignKey("cities.code"))
    user_id = Column(Integer, ForeignKey("users.id"))
    user_nickname = Column(String(50))
    content = Column(Text, nullable=False)
    type = Column(String(20), default="mood")
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


# ==================== 二十一、精武堂补充 - 帮派系统 ====================

class JingwuGang(Base):
    """精武堂帮派表（ID从1000起，名称12字内中文，创建等级40+）"""
    __tablename__ = "jingwu_gangs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)  # 帮派ID从1000起（需在DB设置AUTO_INCREMENT=1000）
    name = Column(String(12), unique=True, nullable=False)  # 名称12字内中文
    leader_id = Column(Integer, ForeignKey("jingwu_roles.id"))
    leader_name = Column(String(50))
    notice = Column(Text)
    announcement = Column(Text)
    description = Column(String(255))

    # ---- 等级/资金/繁荣 ----
    level = Column(SmallInteger, default=1)     # 帮派等级1-5
    max_level = Column(SmallInteger, default=5)
    exp = Column(Integer, default=0)            # 帮派经验/繁荣度
    prosperity = Column(Integer, default=0)     # 繁荣度
    funds = Column(Integer, default=0)          # 帮派资金(G币)

    # ---- 成员 ----
    member_count = Column(Integer, default=1)
    member_limit = Column(Integer, default=30)  # 每级可提升上限
    vice_leader_count = Column(SmallInteger, default=1)  # 副帮主数
    elder_count = Column(SmallInteger, default=2)        # 长老数

    # ---- 入帮条件 ----
    create_level_required = Column(Integer, default=40)  # 创建等级40+
    create_gcoin_cost = Column(Integer, default=50000)   # 创建帮派费用
    join_level_required = Column(Integer, default=20)    # 入帮等级20+
    join_gcoin_fee = Column(Integer, default=500)        # 入帮费500G币
    join_need_approval = Column(Boolean, default=True)   # 入帮需审批

    # ---- 闻香炉 ----
    incense_energy = Column(Integer, default=0) # 闻香炉灵气
    incense_level = Column(SmallInteger, default=0)  # 香炉等级
    incense_max_energy = Column(Integer, default=1000)

    # ---- 香炉修炼/替身术状态 ----
    # 替身术心法：可同时修炼和比武
    xinshen_tishen = Column(Boolean, default=False)    # 替身术心法是否开启
    xinshen_qiangshen_lv = Column(Integer, default=0)  # 强身(气血)等级
    xinshen_ningqi_lv = Column(Integer, default=0)     # 凝气(精气)等级
    xinshen_yijin_lv = Column(Integer, default=0)      # 易筋(伤害)等级
    xinshen_xisui_lv = Column(Integer, default=0)      # 洗髓(防御)等级
    xinshen_qingshen_lv = Column(Integer, default=0)   # 轻身(速度)等级

    # ---- 状态 ----
    status = Column(SmallInteger, default=1)    # 1正常 0解散 2冻结
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ---- 关系 ----
    members = relationship("JingwuGangMember", back_populates="gang", cascade="all, delete-orphan")
    skills = relationship("JingwuGangSkill", back_populates="gang", cascade="all, delete-orphan")
    leader = relationship("JingwuRole", foreign_keys=[leader_id])


class JingwuGangMember(Base):
    """帮派成员表"""
    __tablename__ = "jingwu_gang_members"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    gang_id = Column(Integer, ForeignKey("jingwu_gangs.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    role_id = Column(Integer, ForeignKey("jingwu_roles.id"))
    role_name = Column(String(20), default="member")  # 职位：leader/vice_leader/elder/member
    position = Column(String(20), default="member")   # 兼容旧字段
    nickname = Column(String(50))
    contribution = Column(Integer, default=0)         # 贡献度
    total_contribution = Column(Integer, default=0)   # 历史总贡献
    gcoin_today = Column(Integer, default=0)          # 今日G币贡献
    joined_at = Column(DateTime, default=datetime.utcnow)
    last_contribute_at = Column(DateTime)

    gang = relationship("JingwuGang", back_populates="members")
    role = relationship("JingwuRole", foreign_keys=[role_id])


class JingwuGangSkill(Base):
    """帮派心法表（替身术/强身/凝气/易筋/洗髓/轻身）"""
    __tablename__ = "jingwu_gang_skills"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    gang_id = Column(Integer, ForeignKey("jingwu_gangs.id"))
    skill_name = Column(String(50))
    # 心法类型：tishen替身术/qiangshen强身/ningqi凝气/yijin易筋/xisui洗髓/qingshen轻身
    skill_type = Column(String(20))
    level = Column(Integer, default=1)
    max_level = Column(Integer, default=10)
    # 效果JSON：{hp_bonus, mp_bonus, damage_bonus, defense_bonus, speed_bonus, can_dual_train}
    effect_json = Column(JSON, default=dict)
    # 升级消耗
    upgrade_funds = Column(Integer, default=0)
    upgrade_prosperity = Column(Integer, default=0)

    gang = relationship("JingwuGang", back_populates="skills")


# ==================== 二十二、武魂系统（80级开启） ====================

class JingwuWuhun(Base):
    """精武堂武魂表（80级开启，五系：土80/水90/火100/金110/木120）"""
    __tablename__ = "jingwu_wuhun"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    role_id = Column(Integer, ForeignKey("jingwu_roles.id"), unique=True)

    # ---- 五系：80土/90水/100火/110金/120木 ----
    wuhun_type = Column(String(20), default="earth")  # earth/water/fire/metal/wood
    element_name = Column(String(10), default="土")   # 土/水/火/金/木
    unlock_level = Column(Integer, default=80)        # 80级开启
    level_required = Column(Integer, default=80)      # 对应系开启等级

    # ---- 品质：普通/优秀/精良/完美/传说，每档5星 ----
    quality = Column(String(20), default="common")    # common/good/excellent/perfect/legendary
    quality_star = Column(SmallInteger, default=1)    # 1-5星
    max_quality_star = Column(SmallInteger, default=5)

    # ---- 等级经验 ----
    level = Column(Integer, default=1)
    max_level = Column(Integer, default=10)
    exp = Column(Integer, default=0)

    # ---- 属性类型：single单属性 / double双属性 ----
    attr_type = Column(String(20), default="single")

    # ---- 单属性（8种）：暴击/抗暴击/闪避/防御/伤害/命中/气血/速度 ----
    single_attr_name = Column(String(20))             # crit/crit_resist/dodge/defense/damage/accuracy/hp/speed
    single_attr_val = Column(Integer, default=0)      # 单属性值

    # ---- 双属性（8种组合）----
    # 斩杀(伤害+破防)/狂暴(暴击+暴伤)/坚韧(防御+格挡)/突袭(速度+命中)
    # 猛击(反击+技伤)/圣佑(气血+减暴伤)/轻灵(闪避+抗反击)/沉默(抗暴击+抗技伤)
    double_attr_name = Column(String(20))             # zhan_sha/kuang_bao/jian_ren/tu_xi/meng_ji/sheng_you/qing_ling/chen_mo
    double_attr_val1 = Column(Integer, default=0)
    double_attr_val2 = Column(Integer, default=0)

    # ---- 兼容旧字段 ----
    str_bonus = Column(Integer, default=0)
    con_bonus = Column(Integer, default=0)
    agi_bonus = Column(Integer, default=0)
    def_bonus = Column(Integer, default=0)
    mag_bonus = Column(Integer, default=0)

    # ---- 时间戳 ----
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ---- 关系 ----
    role = relationship("JingwuRole", foreign_keys=[role_id])


class JingwuFabao(Base):
    __tablename__ = "jingwu_fabao"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    role_id = Column(Integer, ForeignKey("jingwu_roles.id"))
    fabao_code = Column(String(50))
    name = Column(String(100))
    quality = Column(String(20), default="common")
    level = Column(Integer, default=1)
    exp = Column(Integer, default=0)
    skill_name = Column(String(50))
    skill_desc = Column(Text)
    is_equipped = Column(Boolean, default=False)
    attr_json = Column(Text)


class JingwuForgeLog(Base):
    __tablename__ = "jingwu_forge_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    role_id = Column(Integer, ForeignKey("jingwu_roles.id"))
    equip_id = Column(Integer)
    equip_name = Column(String(100))
    forge_type = Column(String(20))
    success = Column(Boolean, default=False)
    material_json = Column(Text)
    result_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


# ==================== 二十三、纵横四海扩展系统 ====================

class SeaPet(Base):
    __tablename__ = "sea_pets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    pet_code = Column(String(50), unique=True)
    name = Column(String(100), nullable=False)
    category = Column(String(20), default="normal")
    rarity = Column(String(20), default="common")
    level_required = Column(Integer, default=1)
    base_hp = Column(Integer, default=100)
    base_atk = Column(Integer, default=10)
    base_def = Column(Integer, default=5)
    base_agi = Column(Integer, default=10)
    skill_pool_json = Column(Text)
    icon = Column(String(100))
    description = Column(Text)

    # ---- 3g_games 迁移字段（对齐 seed_sea_large.py）----
    key = Column(String(32), unique=True, index=True)
    quality = Column(String(16), default="白")
    atk = Column(Integer, default=10)
    defense = Column(Integer, default=10)
    agile = Column(Integer, default=10)
    hp = Column(Integer, default=100)
    skill_tag = Column(String(64), default="")
    source = Column(String(64), default="")


class SeaUserPet(Base):
    __tablename__ = "sea_user_pets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    pet_id = Column(Integer, ForeignKey("sea_pets.id"))
    nickname = Column(String(50))
    level = Column(Integer, default=1)
    exp = Column(Integer, default=0)
    hp = Column(Integer, default=100)
    atk = Column(Integer, default=10)
    def_ = Column("def", Integer, default=5)
    agi = Column(Integer, default=10)
    skills_json = Column(Text)
    is_battling = Column(Boolean, default=False)
    intimacy = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class SeaMount(Base):
    __tablename__ = "sea_mounts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    mount_code = Column(String(50), unique=True)
    name = Column(String(100), nullable=False)
    level_required = Column(Integer, default=80)
    rarity = Column(String(20), default="common")
    speed_bonus = Column(Integer, default=0)
    hp_bonus = Column(Integer, default=0)
    atk_bonus = Column(Integer, default=0)
    def_bonus = Column(Integer, default=0)
    icon = Column(String(100))
    description = Column(Text)

    # ---- 3g_games 迁移字段（对齐 seed_sea_large.py，level_req → level_required）----
    key = Column(String(32), unique=True, index=True)
    stat_type = Column(String(16), default="flat")
    stat_value = Column(Integer, default=100)
    category = Column(String(32), default="普通")


class SeaUserMount(Base):
    __tablename__ = "sea_user_mounts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    mount_id = Column(Integer, ForeignKey("sea_mounts.id"))
    level = Column(Integer, default=1)
    is_riding = Column(Boolean, default=False)
    riding_skill_level = Column(Integer, default=1)
    obtained_at = Column(DateTime, default=datetime.utcnow)


class SeaWing(Base):
    __tablename__ = "sea_wings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    wing_code = Column(String(50), unique=True)
    name = Column(String(100), nullable=False)
    level_required = Column(Integer, default=100)
    rarity = Column(String(20), default="common")
    hp_bonus = Column(Integer, default=0)
    atk_bonus = Column(Integer, default=0)
    def_bonus = Column(Integer, default=0)
    vampire_rate = Column(Integer, default=0)
    combo_rate = Column(Integer, default=0)
    iron_wall_rate = Column(Integer, default=0)
    icon = Column(String(100))

    # ---- 3g_games 迁移字段（对齐 seed_sea_large.py，level_req → level_required）----
    key = Column(String(32), unique=True, index=True)
    effects = Column(Text, default="{}")


class SeaUserWing(Base):
    __tablename__ = "sea_user_wings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    wing_id = Column(Integer, ForeignKey("sea_wings.id"))
    level = Column(Integer, default=1)
    is_equipped = Column(Boolean, default=False)
    wing_skill_level = Column(Integer, default=1)
    obtained_at = Column(DateTime, default=datetime.utcnow)


class SeaFollower(Base):
    __tablename__ = "sea_followers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    follower_code = Column(String(50), unique=True)
    name = Column(String(100), nullable=False)
    quality = Column(String(20), default="normal")
    level_required = Column(Integer, default=50)
    base_hp = Column(Integer, default=100)
    base_atk = Column(Integer, default=15)
    base_def = Column(Integer, default=10)
    talent_skill = Column(String(100))
    talent_desc = Column(Text)
    icon = Column(String(100))
    description = Column(Text)

    # ---- 3g_games 迁移字段（对齐 seed_sea_large.py）----
    key = Column(String(32), unique=True, index=True)
    skill_name = Column(String(32))
    skill_desc = Column(String(255))


class SeaUserFollower(Base):
    __tablename__ = "sea_user_followers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    follower_id = Column(Integer, ForeignKey("sea_followers.id"))
    level = Column(Integer, default=1)
    exp = Column(Integer, default=0)
    quality = Column(String(20), default="normal")
    hp = Column(Integer, default=100)
    atk = Column(Integer, default=15)
    def_ = Column("def", Integer, default=10)
    is_battling = Column(Boolean, default=False)
    inherited = Column(Boolean, default=False)
    cultivate_json = Column(Text)
    obtained_at = Column(DateTime, default=datetime.utcnow)


class SeaGem(Base):
    __tablename__ = "sea_gems"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    gem_code = Column(String(50), unique=True)
    name = Column(String(100), nullable=False)
    color = Column(String(20))
    slot_type = Column(String(20))
    rarity = Column(String(20), default="common")
    level = Column(Integer, default=1)
    atk_bonus = Column(Integer, default=0)
    def_bonus = Column(Integer, default=0)
    hp_bonus = Column(Integer, default=0)
    agi_bonus = Column(Integer, default=0)
    icon = Column(String(100))

    # ---- 3g_games 迁移字段（对齐 seed_sea_large.py）----
    key = Column(String(32), unique=True, index=True)
    effect = Column(String(64))
    slots = Column(Text, default="[]")
    tier = Column(Integer, default=1)


class SeaUserGem(Base):
    __tablename__ = "sea_user_gems"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    gem_id = Column(Integer, ForeignKey("sea_gems.id"))
    level = Column(Integer, default=1)
    quantity = Column(Integer, default=1)
    inlaid_equip_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class SeaCard(Base):
    __tablename__ = "sea_cards"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    card_code = Column(String(50), unique=True)
    name = Column(String(100), nullable=False)
    quality = Column(String(20), default="common")
    star_level = Column(Integer, default=1)
    slot_type = Column(String(20))
    monster_source = Column(String(100))
    atk_bonus = Column(Integer, default=0)
    def_bonus = Column(Integer, default=0)
    hp_bonus = Column(Integer, default=0)
    special_effect = Column(Text)
    icon = Column(String(100))

    # ---- 3g_games 迁移字段（对齐 seed_sea_large.py）----
    key = Column(String(32), unique=True, index=True)
    slot = Column(String(32))
    normal_effect = Column(String(64))
    refine_effect = Column(String(64))
    drop_source = Column(String(64), default="")


class SeaUserCard(Base):
    __tablename__ = "sea_user_cards"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    card_id = Column(Integer, ForeignKey("sea_cards.id"))
    enhance_level = Column(Integer, default=0)
    is_equipped = Column(Boolean, default=False)
    equipped_slot = Column(String(20))
    obtained_at = Column(DateTime, default=datetime.utcnow)


class SeaStigmata(Base):
    __tablename__ = "sea_stigmata"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    stigmata_code = Column(String(50), unique=True)
    name = Column(String(100), nullable=False)
    category = Column(String(20))
    quality = Column(String(20), default="common")
    level_required = Column(Integer, default=1)
    base_atk = Column(Integer, default=0)
    base_def = Column(Integer, default=0)
    base_hp = Column(Integer, default=0)
    icon = Column(String(100))
    description = Column(Text)


class SeaUserStigmata(Base):
    __tablename__ = "sea_user_stigmata"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    stigmata_id = Column(Integer, ForeignKey("sea_stigmata.id"))
    level = Column(Integer, default=1)
    exp = Column(Integer, default=0)
    is_equipped = Column(Boolean, default=False)
    equipped_slot = Column(Integer)
    devour_exp = Column(Integer, default=0)
    obtained_at = Column(DateTime, default=datetime.utcnow)


class SeaHideout(Base):
    __tablename__ = "sea_hideouts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    farm_level = Column(Integer, default=1)
    training_room_level = Column(Integer, default=1)
    farm_plots_count = Column(Integer, default=4)
    last_farm_harvest = Column(DateTime)
    last_training_reward = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class SeaHideoutPlot(Base):
    __tablename__ = "sea_hideout_plots"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    hideout_id = Column(Integer, ForeignKey("sea_hideouts.id"))
    plot_no = Column(Integer, nullable=False)
    crop_code = Column(String(50))
    crop_name = Column(String(50))
    planted_at = Column(DateTime)
    ready_at = Column(DateTime)
    status = Column(String(20), default="idle")
    silver_reward = Column(Integer, default=0)


class SeaTrainingRoom(Base):
    __tablename__ = "sea_training_rooms"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    hideout_id = Column(Integer, ForeignKey("sea_hideouts.id"))
    doll_count = Column(Integer, default=1)
    exp_per_hour = Column(Integer, default=100)
    is_training = Column(Boolean, default=False)
    training_start = Column(DateTime)
    accumulated_exp = Column(Integer, default=0)


class SeaGoods(Base):
    __tablename__ = "sea_goods"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    goods_code = Column(String(50), unique=True)
    name = Column(String(100), nullable=False)
    category = Column(String(20))
    buy_price = Column(Integer, default=0)
    sell_price = Column(Integer, default=0)
    level_required = Column(Integer, default=1)
    description = Column(Text)
    icon = Column(String(100))


class SeaUserGoods(Base):
    __tablename__ = "sea_user_goods"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    goods_code = Column(String(50))
    goods_name = Column(String(100))
    quantity = Column(Integer, default=1)
    category = Column(String(20))
    locked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ==================== 二十四、召唤之王模块 ====================

class SummonProfile(Base):
    __tablename__ = "summon_profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    user = relationship("User", back_populates="summon")

    summoner_name = Column(String(50))
    level = Column(Integer, default=1)
    exp = Column(Integer, default=0)
    vitality = Column(Integer, default=100)
    max_vitality = Column(Integer, default=100)
    copper_coin = Column(Integer, default=1000)
    yuanbao = Column(Integer, default=0)
    prestige = Column(Integer, default=0)
    arena_rank = Column(Integer, default=0)
    arena_tier = Column(String(20), default="huang")
    alliance_id = Column(Integer, ForeignKey("summon_alliances.id"))
    master_user_id = Column(Integer)
    apprentice_count = Column(Integer, default=0)
    taoli_value = Column(Integer, default=0)
    catch_ball_normal = Column(Integer, default=20)
    catch_ball_strong = Column(Integer, default=5)
    catch_ball_super = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    beasts = relationship("SummonUserBeast", back_populates="profile", cascade="all, delete-orphan")


class SummonMap(Base):
    __tablename__ = "summon_maps"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    map_code = Column(String(50), unique=True)
    name = Column(String(100), nullable=False)
    level_min = Column(Integer, default=1)
    level_max = Column(Integer, default=100)
    beast_pool_json = Column(Text)
    drop_json = Column(Text)
    description = Column(Text)
    vitality_cost = Column(Integer, default=1)


class SummonBeast(Base):
    __tablename__ = "summon_beasts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    beast_code = Column(String(50), unique=True)
    name = Column(String(100), nullable=False)
    race_type = Column(String(20), default="beast")
    map_level_min = Column(Integer, default=1)
    rarity = Column(String(20), default="common")
    base_hp = Column(Integer, default=100)
    base_patk = Column(Integer, default=15)
    base_matk = Column(Integer, default=10)
    base_pdef = Column(Integer, default=10)
    base_mdef = Column(Integer, default=8)
    base_speed = Column(Integer, default=10)
    growth_min = Column(Integer, default=1)
    growth_max = Column(Integer, default=5)
    skill_pool_json = Column(Text)
    personality_pool_json = Column(Text)
    icon = Column(String(100))
    description = Column(Text)
    catch_rate = Column(Integer, default=50)


class SummonUserBeast(Base):
    __tablename__ = "summon_user_beasts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey("summon_profiles.id"), nullable=False)
    profile = relationship("SummonProfile", back_populates="beasts")
    user_id = Column(Integer, ForeignKey("users.id"))
    beast_id = Column(Integer, ForeignKey("summon_beasts.id"))

    nickname = Column(String(50))
    level = Column(Integer, default=1)
    exp = Column(Integer, default=0)
    growth_star = Column(Integer, default=1)
    personality = Column(String(20), default="brave")
    quality = Column(String(20), default="normal")

    hp = Column(Integer, default=100)
    max_hp = Column(Integer, default=100)
    patk = Column(Integer, default=15)
    matk = Column(Integer, default=10)
    pdef = Column(Integer, default=10)
    mdef = Column(Integer, default=8)
    speed = Column(Integer, default=10)

    status = Column(String(20), default="rest")
    awakened = Column(Boolean, default=False)
    rebirth_count = Column(Integer, default=0)
    obtained_at = Column(DateTime, default=datetime.utcnow)

    skills = relationship("SummonUserBeastSkill", back_populates="beast", cascade="all, delete-orphan")
    bones = relationship("SummonUserBone", back_populates="beast", cascade="all, delete-orphan")
    souls = relationship("SummonUserSoul", back_populates="beast", cascade="all, delete-orphan")
    spirits = relationship("SummonUserSpirit", back_populates="beast", cascade="all, delete-orphan")


class SummonSkill(Base):
    __tablename__ = "summon_skills"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    skill_code = Column(String(50), unique=True)
    name = Column(String(100), nullable=False)
    skill_type = Column(String(20), default="active")
    category = Column(String(20), default="patk")
    damage_formula = Column(String(100))
    base_damage = Column(Integer, default=10)
    trigger_rate = Column(Integer, default=100)
    mp_cost = Column(Integer, default=0)
    cooldown = Column(Integer, default=0)
    description = Column(Text)
    icon = Column(String(100))


class SummonUserBeastSkill(Base):
    __tablename__ = "summon_user_beast_skills"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    beast_id = Column(Integer, ForeignKey("summon_user_beasts.id"), nullable=False)
    beast = relationship("SummonUserBeast", back_populates="skills")
    skill_id = Column(Integer, ForeignKey("summon_skills.id"))
    skill_level = Column(Integer, default=1)
    slot_position = Column(Integer, default=0)
    learned_at = Column(DateTime, default=datetime.utcnow)


class SummonCatchLog(Base):
    __tablename__ = "summon_catch_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    map_id = Column(Integer, ForeignKey("summon_maps.id"))
    beast_id = Column(Integer, ForeignKey("summon_beasts.id"))
    beast_name = Column(String(100))
    ball_type = Column(String(20), default="normal")
    success = Column(Boolean, default=False)
    user_beast_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class SummonBone(Base):
    __tablename__ = "summon_bones"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    bone_code = Column(String(50), unique=True)
    name = Column(String(100), nullable=False)
    slot_type = Column(String(20), nullable=False)
    quality = Column(String(20), default="common")
    level_required = Column(Integer, default=1)
    hp_bonus = Column(Integer, default=0)
    patk_bonus = Column(Integer, default=0)
    matk_bonus = Column(Integer, default=0)
    pdef_bonus = Column(Integer, default=0)
    mdef_bonus = Column(Integer, default=0)
    speed_bonus = Column(Integer, default=0)
    icon = Column(String(100))


class SummonUserBone(Base):
    __tablename__ = "summon_user_bones"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    beast_id = Column(Integer, ForeignKey("summon_user_beasts.id"), nullable=False)
    beast = relationship("SummonUserBeast", back_populates="bones")
    user_id = Column(Integer, ForeignKey("users.id"))
    bone_id = Column(Integer, ForeignKey("summon_bones.id"))
    slot_type = Column(String(20), nullable=False)
    quality = Column(String(20), default="common")
    enhance_level = Column(Integer, default=0)
    advance_level = Column(Integer, default=0)
    hp_bonus = Column(Integer, default=0)
    patk_bonus = Column(Integer, default=0)
    matk_bonus = Column(Integer, default=0)
    pdef_bonus = Column(Integer, default=0)
    mdef_bonus = Column(Integer, default=0)
    speed_bonus = Column(Integer, default=0)
    equipped = Column(Boolean, default=True)


class SummonSoul(Base):
    __tablename__ = "summon_souls"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    soul_code = Column(String(50), unique=True)
    name = Column(String(100), nullable=False)
    quality = Column(String(20), default="waste")
    category = Column(String(20))
    fixed_hp = Column(Integer, default=0)
    fixed_patk = Column(Integer, default=0)
    fixed_matk = Column(Integer, default=0)
    fixed_pdef = Column(Integer, default=0)
    fixed_mdef = Column(Integer, default=0)
    fixed_speed = Column(Integer, default=0)
    percent_hp = Column(Integer, default=0)
    percent_patk = Column(Integer, default=0)
    percent_matk = Column(Integer, default=0)
    percent_pdef = Column(Integer, default=0)
    percent_mdef = Column(Integer, default=0)
    percent_speed = Column(Integer, default=0)
    icon = Column(String(100))


class SummonUserSoul(Base):
    __tablename__ = "summon_user_souls"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    beast_id = Column(Integer, ForeignKey("summon_user_beasts.id"), nullable=False)
    beast = relationship("SummonUserBeast", back_populates="souls")
    user_id = Column(Integer, ForeignKey("users.id"))
    soul_id = Column(Integer, ForeignKey("summon_souls.id"))
    level = Column(Integer, default=1)
    soul_power = Column(Integer, default=0)
    equipped = Column(Boolean, default=False)
    slot_position = Column(Integer, default=0)
    obtained_at = Column(DateTime, default=datetime.utcnow)


class SummonSoulHuntLog(Base):
    __tablename__ = "summon_soul_hunt_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    hunter_level = Column(Integer, default=1)
    cost_copper = Column(Integer, default=0)
    cost_yuanbao = Column(Integer, default=0)
    soul_id = Column(Integer, ForeignKey("summon_souls.id"))
    soul_quality = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)


class SummonSpirit(Base):
    __tablename__ = "summon_spirits"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    spirit_code = Column(String(50), unique=True)
    name = Column(String(100), nullable=False)
    element_type = Column(String(20), nullable=False)
    quality = Column(String(20), default="common")
    attr_pool_json = Column(Text)
    icon = Column(String(100))


class SummonUserSpirit(Base):
    __tablename__ = "summon_user_spirits"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    beast_id = Column(Integer, ForeignKey("summon_user_beasts.id"), nullable=False)
    beast = relationship("SummonUserBeast", back_populates="spirits")
    user_id = Column(Integer, ForeignKey("users.id"))
    spirit_id = Column(Integer, ForeignKey("summon_spirits.id"))
    element_type = Column(String(20), nullable=False)
    quality = Column(String(20), default="common")
    current_attr_json = Column(Text)
    wash_count = Column(Integer, default=0)
    locked = Column(Boolean, default=False)
    equipped = Column(Boolean, default=True)
    obtained_at = Column(DateTime, default=datetime.utcnow)


class SummonArenaMatch(Base):
    __tablename__ = "summon_arena_matches"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    attacker_id = Column(Integer, ForeignKey("users.id"))
    defender_id = Column(Integer, ForeignKey("users.id"))
    attacker_nickname = Column(String(50))
    defender_nickname = Column(String(50))
    tier = Column(String(20), default="huang")
    result = Column(String(10))
    attacker_rank_change = Column(Integer, default=0)
    defender_rank_change = Column(Integer, default=0)
    prestige_change = Column(Integer, default=0)
    battle_log = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class SummonBattlefield(Base):
    __tablename__ = "summon_battlefields"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    battlefield_code = Column(String(50), unique=True)
    name = Column(String(100), nullable=False)
    level_min = Column(Integer, default=1)
    level_max = Column(Integer, default=100)
    open_time_start = Column(String(10), default="06:00")
    open_time_end = Column(String(10), default="24:00")
    camp_a_name = Column(String(50), default="猛虎营")
    camp_b_name = Column(String(50), default="飞鹤寨")
    prestige_reward_win = Column(Integer, default=50)
    prestige_reward_lose = Column(Integer, default=20)
    exp_reward = Column(Integer, default=100)


class SummonBattlefieldRecord(Base):
    __tablename__ = "summon_battlefield_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    battlefield_id = Column(Integer, ForeignKey("summon_battlefields.id"))
    camp = Column(String(10))
    kills = Column(Integer, default=0)
    deaths = Column(Integer, default=0)
    result = Column(String(10))
    prestige_reward = Column(Integer, default=0)
    exp_reward = Column(Integer, default=0)
    copper_reward = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class SummonAlliance(Base):
    __tablename__ = "summon_alliances"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    leader_user_id = Column(Integer)
    leader_nickname = Column(String(50))
    notice = Column(Text)
    description = Column(String(255))
    level = Column(Integer, default=1)
    funds = Column(Integer, default=0)
    contribution_total = Column(Integer, default=0)
    member_count = Column(Integer, default=1)
    member_limit = Column(Integer, default=30)
    skill_level_json = Column(Text)
    storage_capacity = Column(Integer, default=20)
    status = Column(SmallInteger, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)


class SummonAllianceMember(Base):
    __tablename__ = "summon_alliance_members"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    alliance_id = Column(Integer, ForeignKey("summon_alliances.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    user_nickname = Column(String(50))
    role = Column(String(20), default="member")
    contribution = Column(Integer, default=0)
    total_donation = Column(Integer, default=0)
    joined_at = Column(DateTime, default=datetime.utcnow)


class SummonAllianceDonationLog(Base):
    __tablename__ = "summon_alliance_donation_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    alliance_id = Column(Integer, ForeignKey("summon_alliances.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    user_nickname = Column(String(50))
    donation_type = Column(String(20))
    amount = Column(Integer, default=0)
    contribution_reward = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class SummonMasterApprentice(Base):
    __tablename__ = "summon_master_apprentice"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    master_user_id = Column(Integer, ForeignKey("users.id"))
    master_nickname = Column(String(50))
    apprentice_user_id = Column(Integer, ForeignKey("users.id"))
    apprentice_nickname = Column(String(50))
    status = Column(String(20), default="active")
    vitality_today = Column(Boolean, default=False)
    graduated = Column(Boolean, default=False)
    graduated_at = Column(DateTime)
    taoli_reward_taken = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ==================== 二十五、风云三国模块 ====================

class FengyunState(Base):
    """风云三国玩家状态"""
    __tablename__ = "fengyun_state"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    class_key = Column(String(16), default="warrior")  # warrior/assassin/warlock
    faction = Column(String(4), default="shu")  # wei/shu/wu 魏/蜀/吴
    level = Column(Integer, default=1)
    exp = Column(Integer, default=0)
    silver = Column(Integer, default=1000)  # 银两
    honor = Column(Integer, default=0)  # 荣誉值
    hp = Column(Integer, default=200)
    mp = Column(Integer, default=100)
    atk = Column(Integer, default=20)
    defense = Column(Integer, default=10)
    dodge = Column(Integer, default=5)
    crit = Column(Integer, default=5)
    current_city = Column(String(32), default="chengdu")
    training_end_at = Column(DateTime, nullable=True)  # 演武结束时间


class FengyunSkill(Base):
    """技能字典（spec 技能系统：3 职业 × 4 类型）"""
    __tablename__ = "fengyun_skills"

    key = Column(String(32), primary_key=True)
    name = Column(String(32))
    class_key = Column(String(16))  # warrior/assassin/warlock
    skill_type = Column(String(16))  # active/passive/auxiliary/status
    unlock_level = Column(Integer, default=1)
    cost_silver = Column(Integer, default=0)
    cost_exp = Column(Integer, default=0)
    effect = Column(String(255), default="")


class FengyunUserSkill(Base):
    """玩家已学技能"""
    __tablename__ = "fengyun_user_skills"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    skill_key = Column(String(32))
    level = Column(Integer, default=1)
    __table_args__ = (UniqueConstraint("user_id", "skill_key", name="uq_fy_user_skill"),)


class FengyunEquip(Base):
    """装备字典（spec 装备系统：5 品质 × 7 部位）"""
    __tablename__ = "fengyun_equips"

    key = Column(String(32), primary_key=True)
    name = Column(String(32))
    quality = Column(String(16))  # 普通/精良/卓越/史诗/神器
    slot = Column(String(16))  # 头/手/衣/腿/鞋/裤子/饰品
    class_req = Column(String(16), default="")  # 限定职业，空=通用
    level_req = Column(Integer, default=1)
    atk_bonus = Column(Integer, default=0)
    def_bonus = Column(Integer, default=0)
    hp_bonus = Column(Integer, default=0)
    price = Column(Integer, default=100)


class FengyunUserEquip(Base):
    """玩家装备实例"""
    __tablename__ = "fengyun_user_equips"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    equip_key = Column(String(32))
    slot = Column(String(16))
    equipped = Column(Boolean, default=False)


class FengyunDungeon(Base):
    """副本定义（spec 副本系统：按阵营和等级划分）"""
    __tablename__ = "fengyun_dungeons"

    key = Column(String(32), primary_key=True)
    name = Column(String(32))
    faction = Column(String(16))  # wei/shu/wu/all
    level_min = Column(Integer, default=16)
    level_max = Column(Integer, default=25)
    city = Column(String(32))  # 入口城市
    npc = Column(String(32))  # 任务 NPC
    reward_exp = Column(Integer, default=0)
    reward_silver = Column(Integer, default=0)


class FengyunLegion(Base):
    """军团（spec 军团系统：5 级，最大 100 人）"""
    __tablename__ = "fengyun_legions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(32), unique=True)
    leader_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    level = Column(Integer, default=1)  # 1-5 级
    contribution = Column(Integer, default=0)  # 军团贡献值
    notice = Column(String(255), default="广纳天下英豪")
    created_at = Column(DateTime, default=datetime.utcnow)


class FengyunLegionMember(Base):
    """军团成员"""
    __tablename__ = "fengyun_legion_members"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    legion_id = Column(Integer, ForeignKey("fengyun_legions.id", ondelete="CASCADE"), index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    contribution = Column(Integer, default=0)
    joined_at = Column(DateTime, default=datetime.utcnow)


class FengyunTitle(Base):
    """称号字典（spec 称号系统：前缀+后缀组合）"""
    __tablename__ = "fengyun_titles"

    key = Column(String(32), primary_key=True)
    name = Column(String(32))
    title_type = Column(String(16))  # prefix 前缀 / suffix 后缀 / pair 配对
    grade = Column(Integer, default=1)  # 称号品级
    hp_bonus = Column(Integer, default=0)
    atk_bonus = Column(Integer, default=0)
    def_bonus = Column(Integer, default=0)


class FengyunAchievement(Base):
    """成就字典（spec 成就系统：3 难度 × 12 类型）"""
    __tablename__ = "fengyun_achievements"

    key = Column(String(32), primary_key=True)
    name = Column(String(32))
    difficulty = Column(String(8))  # 简单/中等/困难
    category = Column(String(16))  # 成长/任务/杀怪/PK/山庄/社交/副将/道具/装备
    desc = Column(String(128), default="")
    hp_bonus = Column(Integer, default=0)
    mp_bonus = Column(Integer, default=0)
    atk_bonus = Column(Integer, default=0)
    def_bonus = Column(Integer, default=0)
    dodge_bonus = Column(Integer, default=0)
    crit_bonus = Column(Integer, default=0)


class FengyunCity(Base):
    """城市字典（spec 游戏地图：魏蜀吴三区域城市）"""
    __tablename__ = "fengyun_cities"

    key = Column(String(32), primary_key=True)
    name = Column(String(32))
    faction = Column(String(16))  # wei/shu/wu/neutral
    intro = Column(String(128), default="")


class ItemFengyun(Base):
    """风云三国物品字典（189 件：装备/系列/名器/BOSS凭证/虎符/消耗品）"""
    __tablename__ = "fengyun_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key = Column(String(64), unique=True, index=True)
    name = Column(String(32))
    type = Column(String(16))
    module_key = Column(String(32), default="fengyun")
    sell_price = Column(Integer, default=0)
    description = Column(String(128), default="")


# ==================== 幻想西游（v0.2.3 新增模块）====================
class XyouState(Base):
    """幻想西游玩家状态（spec：五门派/转职/200级/气血法力）"""
    __tablename__ = "xyou_state"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    sect_key = Column(String(16), default="")  # jiangjun/fangcun/longgong/yuegong/putuo 空=未转职
    level = Column(Integer, default=1)
    exp = Column(Integer, default=0)
    silver = Column(Integer, default=1000)  # 银两
    gold_bean = Column(Integer, default=0)  # 金豆（充值货币）
    hp = Column(Integer, default=150)
    mp = Column(Integer, default=80)
    atk = Column(Integer, default=15)
    defense = Column(Integer, default=10)
    speed = Column(Integer, default=8)
    lingli = Column(Integer, default=10)  # 灵力
    shengwang = Column(Integer, default=0)  # 声望
    current_scene = Column(String(32), default="xinshoucun")  # 当前场景
    cultivate_end_at = Column(DateTime, nullable=True)  # 修炼结束时间
    daily_counters = Column(Text, default="{}")  # JSON: 日常计数
    auto_settings = Column(Text, default="{}")  # v0.2.3 JSON: 自动战斗/挂机设置


class XyouSkill(Base):
    """技能字典（spec：五门派技能系统）"""
    __tablename__ = "xyou_skills"

    key = Column(String(32), primary_key=True)
    name = Column(String(32))
    sect_key = Column(String(16))  # jiangjun/fangcun/longgong/yuegong/putuo
    skill_type = Column(String(16))  # active/passive/auxiliary/seal
    unlock_level = Column(Integer, default=1)
    cost_silver = Column(Integer, default=0)
    cost_mp = Column(Integer, default=0)  # 法力消耗
    effect = Column(String(255), default="")


class XyouUserSkill(Base):
    """玩家已学技能"""
    __tablename__ = "xyou_user_skills"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    skill_key = Column(String(32))
    level = Column(Integer, default=1)  # 技能熟练度等级
    __table_args__ = (UniqueConstraint("user_id", "skill_key", name="uq_xyou_user_skill"),)


class XyouEquip(Base):
    """装备字典（spec：武器/头盔/盔甲/靴子/戒指/手镯）"""
    __tablename__ = "xyou_equips"

    key = Column(String(32), primary_key=True)
    name = Column(String(32))
    quality = Column(String(16))  # 白/蓝/紫/金/神/圣
    slot = Column(String(16))  # 武器/头盔/盔甲/靴子/戒指/手镯
    sect_req = Column(String(16), default="")  # 限定门派，空=通用
    level_req = Column(Integer, default=1)
    atk_bonus = Column(Integer, default=0)
    def_bonus = Column(Integer, default=0)
    hp_bonus = Column(Integer, default=0)
    mp_bonus = Column(Integer, default=0)
    price = Column(Integer, default=100)


class XyouUserEquip(Base):
    """玩家装备实例"""
    __tablename__ = "xyou_user_equips"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    equip_key = Column(String(32))
    slot = Column(String(16))
    worn = Column(Boolean, default=False)


class XyouDungeon(Base):
    """副本字典（spec：15-90级+ 副本，含普通/困难双难度）"""
    __tablename__ = "xyou_dungeons"

    key = Column(String(32), primary_key=True)
    name = Column(String(32))
    level_min = Column(Integer, default=1)
    level_max = Column(Integer, default=200)
    scene = Column(String(32))  # 入口场景
    difficulty = Column(String(16), default="普通")  # 普通/困难
    reward_exp = Column(Integer, default=0)
    reward_silver = Column(Integer, default=0)
    drop_quality = Column(String(16), default="白")


class XyouPet(Base):
    """宠物字典（spec：捕捉/8只/出战/经验20%）"""
    __tablename__ = "xyou_pets"

    key = Column(String(32), primary_key=True)
    name = Column(String(32))
    level_req = Column(Integer, default=1)  # 携带等级
    base_hp = Column(Integer, default=100)
    base_atk = Column(Integer, default=10)
    base_def = Column(Integer, default=5)
    skill = Column(String(64), default="")  # 天赋技能
    capture_rate = Column(Float, default=0.3)  # 捕捉概率


class XyouUserPet(Base):
    """玩家宠物实例"""
    __tablename__ = "xyou_user_pets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    pet_key = Column(String(32))
    nickname = Column(String(32), default="")
    level = Column(Integer, default=1)
    exp = Column(Integer, default=0)
    loyalty = Column(Integer, default=80)  # 忠诚度
    in_battle = Column(Boolean, default=False)  # 是否出战


class XyouScene(Base):
    """场景字典（spec：世界地图区域）"""
    __tablename__ = "xyou_scenes"

    key = Column(String(32), primary_key=True)
    name = Column(String(32))
    region = Column(String(16))  # 新手/长安/宝象/乌鸡/傲来/天宫/地府/蓬莱/灵山
    level_min = Column(Integer, default=1)
    intro = Column(String(128), default="")
    exits = Column(Text, default="[]")  # JSON: 出口场景key列表


class XyouMaterial(Base):
    """高级升级材料字典（v0.2.3 全网检索补全）"""
    __tablename__ = "xyou_materials"

    key = Column(String(48), primary_key=True)
    name = Column(String(32))
    purpose = Column(String(128), default="")  # 用途
    source = Column(String(128), default="")  # 获取方式


class XyouCoord(Base):
    """长安城/区域坐标字典（v0.2.3 spec 参数补全）"""
    __tablename__ = "xyou_coords"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    scene_key = Column(String(32), default="changan")  # 所属场景
    place = Column(String(32))  # 地点名
    coord = Column(String(64), default="")  # 坐标/位置
    npc_or_func = Column(String(128), default="")  # NPC/功能


class ItemXyou(Base):
    """幻想西游物品字典（装备/药品/材料等，module_key=xyou）"""
    __tablename__ = "xyou_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key = Column(String(64), unique=True, index=True)
    name = Column(String(32))
    type = Column(String(16))
    module_key = Column(String(32), default="xyou")
    sell_price = Column(Integer, default=0)
    description = Column(String(128), default="")