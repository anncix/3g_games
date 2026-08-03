# QQ家园 — 怀旧平台化复刻

> 版本：**v0.0.3** （2026-08-03 魔法花园怀旧版完整设计规范落地）
>
> 基于 **FastAPI + SQLite + Jinja2(简版 WAP 风)** 实现的怀旧 QQ 家园平台复刻。
> 严格遵循《怀旧QQ家园平台设计规范》：平台统一、模块自治、旧逻辑优先、一页只做一件事。

包含：**前台 WAP 页面** + **后台管理系统** + **JSON API 规范** + **四个游戏模块**。

---

## 更新日志

### v0.0.3 （2026-08-03）— 魔法花园怀旧版完整设计规范落地

按《怀旧版（旧逻辑）完整设计规范》合并稿重构魔法花园：物品等级×稀有度双轴、魔法师 16 段位称号体系、方案A 经验曲线、合成成功率+保底+操作锁、社交日限+衰减、物品等级上限防越级、风控留痕。

**物品等级 × 稀有度 双轴体系**
- 物品等级 Lv1–Lv8（强度/效率轴）：影响成长时间、产量、售价、合成目标
- 稀有度 4 档（普通/稀有/史诗/传说，获取难度轴）
- 玩家等级段 → 物品等级上限映射（防越级使用）：
  - Lv1–10 → ≤Lv2 / Lv11–20 → ≤Lv3 / Lv21–30 → ≤Lv4 / Lv31–40 → ≤Lv5
  - Lv41–50 → ≤Lv6 / Lv51–65 → ≤Lv7 / Lv66–80 → ≤Lv8
- `GardenSeed.item_level` / `GardenBloom.item_level` 字段；播种/购买/合成均校验上限

**魔法师称号体系（16 段位，每 5 级一段）**
- 1–5 见习 / 6–10 学徒 / 11–15 初阶 / 16–20 中阶 / 21–25 高阶 / 26–30 精英
- 31–35 大魔法师 / 36–40 魔导师 / 41–45 大魔导师 / 46–50 贤者 / 51–55 奥术贤者
- 56–60 秘法宗师 / 61–65 元素宗师 / 66–70 大元素使 / 71–75 星辉大法师 / 76–80 传奇魔法王座
- 段位起始等级（1/6/11/16/21/31/46/66）为强解锁点：新花盆/新花种/新合成栏位
- 显示方式：`称号 + Lv`，段位内可用 I–V 细分
- 花盆数随段位解锁：基础 4 + 段位索引，上限 12

**等级经验（方案A）**
- 升级公式：`need(L→L+1) = 120 + 80×L`（1 级需 200，80 级需 6520，满级累计 268800）
- 动作经验（怀旧简单）：播种+2 / 浇水除草除虫+3 / 收获(3+物品等级×2) / 点亮花谱(15+物品等级×5) / 帮忙+2 / 合成(5+目标等级×3)

**合成工坊（怀旧但可控）**
- `GardenRecipe` 新增字段：`success_rate`(基础成功率%) / `fail_credit_threshold`(保底阈值) / `target_level`(目标物品等级) / `require_lock_check`(高阶操作锁)
- 新增 `GardenCraftCredit` 表：按 (user_id, recipe_id) 累计失败值
- 成功率随目标等级上升而下降（百合 90% → 牡丹 50%）
- 保底机制：失败累计"合成值"，满值必成（防挫败）；成功重置保底
- 高阶合成（≥Lv6）强制 `require_lock_check=True`，记录 `craft_lock_check` 风控日志
- 物品等级上限校验：防越级合成（Lv1 玩家不能合成 Lv3 百合）

**社交互动（日限 + 衰减 + 防刷）**
- 新增 `GardenDailyLog` 表：按 (user_id, date) 记录偷花/帮忙次数
- 偷花：每日 10 次上限；收益衰减（前 3 次满额 exp+2/coin+5，4–6 次半额 exp+1/coin+2，7–10 次仅花无奖励）
- 帮忙：每日 10 次上限；双方奖励（exp+2/coin+5）
- 保底：被偷花盆清空但只损失 1 朵，主人不血亏
- 花盆可上锁防偷（物品锁域）

**风控与客服（怀旧但必须有）**
- 高价值操作强制校验：高阶合成（≥Lv6）触发 `craft_lock_check` 风控日志
- 行为限速：偷花/帮忙/合成尝试均有日限
- 操作留痕：`OperationLog` 记录全部关键动作（plant/stage_action/harvest/steal_flower/help_friend/craft_success/craft_fail/exchange/shop_buy/album_lit 等）
- 客服追溯：可按 `用户 + 时间` 拉出操作流水（含资源变化与拦截原因）

**页面与模板更新**
- `garden/home.html`：显示称号 + 段位范围 + 物品等级上限
- `garden/craft.html`：显示成功率、保底进度条、目标物品等级、高阶锁标识
- `garden/shop.html`：显示物品等级、稀有度，动态定价（普通 Lv×20，稀有翻倍）
- `garden/rules.html`：完整更新规则页（方案A 经验 / 16 段位称号 / 双轴体系 / 合成规则 / 社交日限）

**API 扩展**
- `/api/garden/state` 新增字段：`title`(称号) / `tier_range`(段位范围) / `item_level_cap`(物品等级上限) / `exp_needed`(下级所需经验)

**数据模型变更**
- `GardenSeed` 新增 `item_level`、`rarity`、`obtain_sources`
- `GardenBloom` 新增 `item_level`、`rarity`、`color`、`special_tag`
- `GardenRecipe` 新增 `success_rate`、`fail_credit_threshold`、`target_level`、`require_lock_check`
- 新增表：`GardenCraftCredit`(合成保底累计) / `GardenDailyLog`(社交日限计数)

**端到端验证**
- ✅ 物品等级上限拦截（Lv1 防合成 Lv3 百合）
- ✅ 合成工坊页面渲染（成功率 + 保底进度条）
- ✅ 等级提升后解锁合成（Lv11 可合成百合）
- ✅ 保底机制（失败累计 + 成功重置）
- ✅ 高阶合成操作锁校验留痕（craft_lock_check 日志记录）

---

### v0.0.2 （2026-08-03）— 魔法花园完整重新设计

按《魔法花园完整设计》规范重新实现花园模块，覆盖等级/花种花朵花谱三概念分离/阶段状态机/三件套操作/合成兑换/偷花帮忙送花/事件上报/展示页。

**数据模型重构（三概念分离）**
- `GardenSeed`（花种）：min_level / grow_seconds / stage_actions / yield_rule / possible_blooms / rarity / obtain_sources
- `GardenBloom`（花朵）：color / rarity / sell_price / album_entry_key / item_key / special_tag
- `GardenAlbumEntry`（花谱项）：series（野花/玫瑰/传说系列）/ bloom_key
- `GardenPot`（花盆状态机）：seed_key / planted_at / watered / weeded / debugged
- `GardenState`：level / exp / pot_count / coins（模块金币）
- `GardenCollection`（点亮记录）/ `GardenRecipe`（合成配方）/ `GardenExchange`（兑换）

**等级系统**
- 经验来自劳动：播种+2 / 浇水除草除虫+3 / 收获+5 / 点亮花谱+15 / 帮好友+2
- 升级曲线：每级所需经验 = 等级 × 80
- 等级影响：可种花种列表 / 商店可购买项

**种植阶段状态机**
- 空地 → 已播种 → 发芽期 → 花苗期 → 花蕾期 → 成熟 → 收获 → 空地
- 发芽/花苗/花蕾期各需一次操作（浇水/除草/除虫）
- 三件套完成度影响产量：完成2+操作 → 产量+1
- 不操作不毁花，仅影响收益（减少惩罚）

**收获结算（清晰展示）**
- 展示获得花朵（名称/颜色/数量/稀有度）
- 展示金币/经验获得
- 首次获得花朵自动点亮花谱
- 结果页推荐下一步：卖出/入库/合成

**花谱系统（图鉴内核）**
- 按系列分组：野花系列 / 玫瑰系列 / 传说系列
- 点亮规则：持有该花朵可点亮（收获自动点亮 + 手动点亮双路径）
- 点亮奖励：花园经验+15 / 花园金币+20 / 平台图标+成就+排行
- 展示页：花谱点亮总数 / 最近点亮 / 稀有花收藏

**合成与兑换**
- 合成工坊：固定配方（花朵/材料 → 花种），稳定产出
- 兑换中心：活动材料 → 稀有花种，非纯概率
- 稀有花获取三路并存：随机掉落 / 合成路线 / 活动兑换

**好友互动**
- 偷花：从成熟花圃偷1朵，每盆限偷1次，被偷有消息提醒
- 帮忙：帮好友浇水/除草/除虫，+2经验+5金币
- 送花：送好友花朵
- 花盆可上锁防偷（物品锁）

**事件上报（garden_* 系列）**
- 花谱点亮 → icon_light / ranking / achievement
- 被偷/被帮忙 → interact_notify（消息提醒）
- 收获/操作 → achievement（成就进度）

**完整页面树**
- 魔法花园首页 / 花圃列表 / 花盆详情 / 播种 / 阶段操作 / 收获结果
- 花谱（分组/详情/点亮）/ 展示页
- 合成工坊 / 兑换中心 / 花种商店 / 规则
- 好友花园（偷花/帮忙/送花）

**验收标准达成**
- 花圃状态机完整可跑通（播种→阶段→收获）✓
- 三种阶段操作存在并影响收益 ✓
- 花种与花朵分离 ✓
- 花谱可点亮且能展示进度 ✓
- 合成+兑换两条路径得稀有花种 ✓
- 偷花+帮忙均有消息提醒 ✓
- 关键物品可上锁 ✓
- 模块事件能上报平台 ✓

---

### v0.0.1 （2026-08-03）— 首版合并发布

首个带版本号的合并版本，平台核心 + 四模块玩法闭环全部就绪。

**平台基座**
- FastAPI 异步入口 + SQLite(aiosqlite) 持久化，启动自动建库写种子
- 会话 Cookie 鉴权，bcrypt 密码哈希（兼容 4.x，不可用时降级 sha256）
- 统一 WAP 风模板（单列布局 / 列表为主 / 短标签短状态）+ 公共结果页
- 顶层固定入口：家园首页 / 我的家园 / 好友 / 家族 / 论坛 / 聊天室 / 同城 / 游戏大厅 / 消息 / 活动 / 排行图标

**公共系统（平台统一，模块只调用不重写）**
- 好友系统：加/删好友、黑名单、来访记录、留言板、私聊
- 加锁双制：隐私锁（访问/留言/私聊/同城）+ 物品锁（防翻/偷/消耗/出售）
- 货品字典：统一物品注册（名称/类型/堆叠/绑定/过期），商店只卖字典内物品
- 图标与成就分离：图标=身份展示，成就=记录目标；模块只触发条件，平台统一判定点亮
- 事件总线：模块通过 `/api/events/emit` 上报，不可直接改平台数据
- 操作留痕：全站行为日志，支撑客服申诉

**四个游戏模块（保留老味道点）**
- 阳光农场：成长计时 / 浇水除虫施肥 / 偷菜互助 / 成熟可收
- 美味小镇：食材短缺驱动互动 / 翻橱柜 / 添油营业 / 升星与挑剔客人
- 魔法花园：发芽-花苗-花蕾阶段操作 / 合成花种 / 花谱点亮 / 偷花送花
- 纵横四海：城市节点+航线推进 / 任务驱动 / 遭遇战斗结算 / 装备成长线

**后台管理**
- 用户管理、模块上下架、商店商品管理、工单处理、操作日志查询
- 概览看板：用户数 / 待处理工单 / 消息量 / 模块状态

**JSON API 规范（16 端点）**
- 鉴权：`/api/login` `/api/register` `/api/me`
- 社交：`/api/friends` `/api/friends/add` `/api/friends/remove`
- 资源：`/api/inventory` `/api/shop/buy` `/api/messages`
- 平台能力：`/api/ranking` `/api/icons` `/api/events/emit`
- 模块状态：`/api/farm/state` `/api/town/state` `/api/garden/state` `/api/sea/state`
- 统一返回 `{code, msg, data}`，`code=0` 成功

**内置数据**
- 3 个测试账号（admin / demo / lily）
- 4 个模块注册、物品字典、作物/菜谱/花种/城市节点、图标成就、论坛板块、聊天室、活动

---

## 一、快速开始

### 1. 环境要求
- Python 3.10+（已在 3.14 验证）
- 无需额外数据库，SQLite 自动创建于 `data/qq_home.db`

### 2. 安装与启动

```bash
cd qq_home
pip install -r requirements.txt

# 一键启动（自动建库 + 写入种子数据 + 开启热重载）
bash run.sh

# 或手动启动
python3 -c "import asyncio; from app import seed; asyncio.run(seed.seed())"  # 初始化数据
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

打开浏览器访问：<http://localhost:8000>

### 3. 内置账号

| 账号 | 密码 | 角色 | 说明 |
|------|------|------|------|
| `admin` | `admin123` | 站长 | 可进后台管理 |
| `demo` | `demo123` | 普通用户 | 上海，阿强 |
| `lily` | `lily123` | 普通用户 | 广州，小莉 |

> 首次启动会自动建表并写入：模块注册、物品字典、作物/菜谱/花种/城市、图标、成就、论坛板块、聊天室、活动、3 个账号。

---

## 二、项目结构

```
qq_home/
├── app/
│   ├── main.py              # FastAPI 入口（挂载全部路由 + 静态资源 + 启动初始化）
│   ├── config.py            # 配置（DB 路径、会话、密钥）
│   ├── database.py          # 引擎、会话工厂、init_db
│   ├── models.py            # 全部 SQLAlchemy 模型（平台 + 4 模块）
│   ├── deps.py              # 认证依赖、会话管理、密码哈希(bcrypt)
│   ├── seed.py              # 种子数据
│   ├── platform/            # ★ 平台公共服务（模块与平台交互的唯一通道）
│   │   ├── friends.py       #   好友系统（全站共用，模块不得自建）
│   │   ├── locks.py         #   加锁：隐私锁 + 物品锁
│   │   ├── goods.py         #   货品：物品字典 + 背包 + 出售
│   │   ├── icons.py         #   图标(身份展示) + 成就(记录/目标)
│   │   ├── events.py        #   ★ 事件总线（模块只能上报事件，5.5）
│   │   ├── ranking.py       #   排行（模块上报分数，平台展示）
│   │   └── log.py           #   操作留痕（客服/申诉追溯）
│   ├── routers/             # 路由层
│   │   ├── auth.py          #   注册/登录/登出
│   │   ├── profile.py       #   我的家园/他人主页/来访/留言/动态
│   │   ├── lobby.py         #   游戏大厅（模块统一入口）
│   │   ├── friends.py       #   好友/黑名单/搜索
│   │   ├── family.py        #   家族
│   │   ├── forum.py         #   论坛
│   │   ├── chat.py          #   聊天室 + 私聊
│   │   ├── city.py          #   同城
│   │   ├── message.py       #   消息中心
│   │   ├── activity.py      #   活动 + 每日签到
│   │   ├── ranking.py       #   排行榜
│   │   ├── icons.py         #   图标墙
│   │   ├── inventory.py     #   背包（按 module_key 分页）
│   │   ├── shop.py          #   商店（只引用物品字典）
│   │   ├── settings.py      #   设置（隐私锁/物品锁/提醒/资料）
│   │   ├── support.py       #   客服（FAQ/提单/申诉/日志查询）
│   │   ├── farm.py          #   ★ 阳光农场
│   │   ├── town.py          #   ★ 美味小镇
│   │   ├── garden.py        #   ★ 魔法花园
│   │   ├── sea.py           #   ★ 纵横四海
│   │   ├── admin.py         #   ★ 后台管理
│   │   ├── api.py           #   ★ JSON API 规范 (/api/*)
│   │   └── views.py         #   渲染助手（统一上下文）
│   ├── templates/           # Jinja2 WAP 模板（单列、列表为主、怀旧风）
│   │   ├── base.html / macros.html
│   │   ├── home.html / login.html / my_home.html ...
│   │   ├── farm/ town/ garden/ sea/ admin/ chat/ forum/ support/
│   └── static/
│       └── style.css        # 怀旧 WAP 样式
├── data/                    # SQLite 数据库（自动生成）
├── requirements.txt
├── run.sh
└── README.md
```

---

## 三、设计规范落地说明

### 总体原则
- **旧逻辑优先**：所有模块遵循 `列表页 → 详情页 → 操作页 → 结果页 → 返回上级`，每个写操作都返回结果页（`result.html`）。
- **一页只做一件事**：每个页面最多 1 个主操作。
- **短操作、多回访**：农场成熟、小镇添油、花园盛开都形成“上线看一眼”的节奏。
- **强关系链**：好友/家族/论坛/聊天室驱动偷菜/翻柜/偷花/送花等互动。
- **平台统一，模块自治**：公共系统统一入口，模块只负责玩法闭环。

### 1) 信息架构
顶层固定入口（底部 footer 一致）：`家园 / 我的 / 好友 / 大厅 / 消息`。
所有游戏模块从 `游戏大厅 (/lobby)` 进入，模块内提供“返回大厅”与“返回家园”，深层页面 2 次内可回首页。

### 2) 核心页面
- **家园首页 `/`**：公告栏 + 好友动态摘要 + 家族摘要 + 游戏大厅入口 + 消息提醒（无大图 banner/瀑布流）。
- **我的家园 `/my`**：主页展示(头像/昵称/签名) + 图标展示位 + 背包/来访/留言/动态入口。

### 3) 视觉与交互
单列布局、列表为主、表格为辅；标签 2-6 字、状态 2-4 字；出售/分解/放弃等危险操作有确认页（`confirm.html`）；操作均给结果页。

### 4) 公共系统
| 系统 | 实现 | 对应文件 |
|------|------|----------|
| 好友 | 加/删/黑名单/来访/留言/私聊，全站共用 | `platform/friends.py` |
| 隐私锁 | 主页/留言/私聊/同城 可见范围(所有人/仅好友/无人) | `platform/locks.py` |
| 物品锁 | 上锁后禁止翻/偷/消耗/出售，带锁图标提示 | `platform/locks.py` |
| 货品 | 统一物品字典(名称/类型/堆叠/绑定/过期) + 背包分页 | `platform/goods.py` |
| 商店 | 只上架字典物品，平台金币结算 | `routers/shop.py` |
| 图标 | 身份展示，平台统一判定点亮，模块只能触发条件 | `platform/icons.py` |
| 成就 | 记录/目标，可有进度与奖励 | `platform/icons.py` |

### 5) 模块接入规范（8 条合规）
1. **模块注册**：`Module` 表（key/名称/简介/入口/排序/上下架），后台可管理。
2. **模块首页**：每个模块 `/games/{key}` 输出 我的进度 + 今日待办 + 快捷入口。
3. **页面树约束**：归类为 列表/详情/操作/结果/规则 五类页面。
4. **背包分页**：统一用 `/inventory?m={key}`，模块提供 farm/town/garden/sea 分页。
5. **事件上报**：模块只能 `events.emit()` 上报，不可直接改 消息/活动/图标/成就/排行。
6. **消息模板**：收获/互动(被偷/被翻)/进度(升星)/奖励 提醒均已实现。
7. **排行输出**：声明指标(harvest/dishes/flower_lit/level)、周期、展示字段。
8. **安全风控**：遵守黑名单/隐私锁/物品锁/操作留痕。

### 6) 设置与客服
- **设置 `/settings`**：隐私锁 + 消息提醒开关 + 物品锁管理 + 黑名单 + 账号资料。
- **客服 `/support`**：FAQ + 分类提单(账号/货币/物品/社交/模块) + 申诉 + 操作日志查询。

### 7) 四个模块的老味道点

| 模块 | 老味道点 | 玩法 |
|------|----------|------|
| **阳光农场** | 成长计时 / 护理 / 偷菜互助 / 回访节奏 | 买种→种植→浇水加速/除虫→成熟收获→去好友家偷菜(可上锁防偷) |
| **美味小镇** | 食材短缺 / 翻橱柜 / 添油 / 升星挑剔客人 | 买食材→烹饪→出锅卖钱→油量下降需添油→翻好友橱柜→出餐升星解锁菜谱 |
| **魔法花园** | 阶段操作 / 合成花种 / 花谱点亮 / 偷花送花 | 买/合成花种→种入花盆(发芽/花苗/花蕾/盛开)→收获点亮花谱→偷花/送花 |
| **纵横四海** | 城市节点 / 航线推进 / 任务遭遇 / 装备成长 | 启航港出发→沿航线推进→港口自动生成任务→遭遇结算(战力影响)→买装备提升战力 |

---

## 四、JSON API 规范

所有 API 位于 `/api/*`，统一响应格式：

```json
{ "code": 0, "msg": "ok", "data": {...} }
```
`code != 0` 表示错误。

### 认证
- 登录返回 `token`，后续请求放在 `Authorization: Bearer <token>` 头（也兼容 cookie）。
- 模块事件上报需带 `X-Module-Key` 头。

### 主要接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/login` | 登录，返回 token + user |
| POST | `/api/register` | 注册 |
| GET | `/api/me` | 当前用户信息 |
| GET | `/api/friends` | 好友列表 |
| POST | `/api/friends/add` | 加好友 |
| GET | `/api/inventory?m=farm` | 背包(按模块分页) |
| POST | `/api/shop/buy` | 购买物品(按 key) |
| GET | `/api/messages` | 消息列表 |
| GET | `/api/ranking?m=farm&metric=harvest` | 排行榜 |
| GET | `/api/icons` | 图标墙 |
| POST | `/api/events/emit` | ★ 模块事件上报(5.5 核心) |
| GET | `/api/farm/state` | 农场状态 |
| GET | `/api/town/state` | 小镇状态 |
| GET | `/api/garden/state` | 花园状态 |
| GET | `/api/sea/state` | 航海状态 |

### 模块事件上报示例

```bash
# 模块只能通过此接口上报事件，平台统一处理
curl -X POST http://localhost:8000/api/events/emit \
  -H "Authorization: Bearer <token>" \
  -H "X-Module-Key: farm" \
  -H "Content-Type: application/json" \
  -d '{"event":"ranking","payload":{"metric":"harvest","score":1,"period":"total"}}'
```

`event` 取值：`message` / `icon_light` / `achievement` / `ranking` / `activity_progress` / `interact_notify`。

---

## 五、后台管理系统

入口 `/admin`（需站长权限）。功能：

| 页面 | 路径 | 能力 |
|------|------|------|
| 概览 | `/admin` | 用户数/工单数/消息数/模块状态 |
| 用户管理 | `/admin/users` | 调整金币、设置/取消站长 |
| 模块管理 | `/admin/modules` | 上下架开关、调整大厅排序 |
| 商店管理 | `/admin/shop` | 商品上下架 |
| 客服工单 | `/admin/tickets` | 查看工单、回复处理 |
| 操作日志 | `/admin/logs` | 全站操作留痕(最近200条，申诉追溯) |

> 所有管理操作均记录到 `OperationLog`，可追溯。

---

## 六、数据模型概览

**平台公共表**：`users / sessions / friends / blacklist / visits / guestbook / chat_messages / chat_rooms / chat_room_messages / privacy_locks / item_locks / items / inventory / shop_items / modules / icons / user_icons / achievements / user_achievements / messages / activities / activity_progress / ranking_entries / operation_logs / settings / support_tickets / families / family_members / forum_boards / forum_threads / forum_posts`

**模块表**：
- 农场：`farm_crops / farm_plots / farm_state / farm_steal_logs`
- 小镇：`town_recipes / town_state`
- 花园：`garden_seeds / garden_blooms / garden_album_entries / garden_pots / garden_state / garden_collection / garden_recipes / garden_exchanges / garden_craft_credits / garden_daily_logs`
- 航海：`sea_cities / sea_routes / sea_equipment / sea_state / sea_quests / sea_user_equips`

---

## 七、玩法演示流程

### 阳光农场
1. `demo` 登录 → 游戏大厅 → 阳光农场
2. 快捷入口 → 种子商店 → 买萝卜种子
3. 农场背包确认有种子 → 我的农田 → 第1块地 → 种植
4. 浇水加速 → 等待成熟 → 收获(得萝卜×2 + 经验)
5. 给地块上锁 → 去 `lily` 的农场偷菜（被锁则偷不到）

### 美味小镇
1. 买大米×2 → 菜谱 → 烹饪蛋炒饭
2. 等待出锅 → 收菜(得金币+经验，累计出餐升星)
3. 油量低于30 → 添油(消耗食用油)
4. 食材不足 → 去 `lily` 的橱柜翻食材

### 魔法花园（v0.0.3 怀旧版）
1. 买野花种子（Lv1）→ 种植 → 经历发芽/花苗/花蕾/盛开（三件套操作提升产量）
2. 收获 → 点亮花谱（核心目标，奖励经验+金币）
3. 升级解锁：Lv6 玫瑰 / Lv11 百合 / Lv16 郁金香 / Lv21 兰花 / Lv31 莲花 / Lv46 牡丹 / Lv66 传说花
4. 合成工坊：成功率+保底（百合 90% → 牡丹 50%；失败累计合成值满必成）
5. 高阶合成（≥Lv6 莲花/牡丹）触发操作锁校验，记录风控日志
6. 去 `lily` 花园偷花（日限 10 次，收益衰减）或 送花给她
7. 段位称号：见习→学徒→初阶→…→传奇魔法王座（每 5 级一段，段位起始解锁新花盆）

### 纵横四海
1. 启航港 → 航线图 → 启航前往珊瑚礁岛(需2级)
2. 港口自动生成任务 → 执行遭遇结算(战力影响成功率)
3. 升级解锁新航线 → 装备商店买船帆/火炮提升战力
4. 到达商旅之城触发成就

---

## 八、技术要点

- **平台与模块解耦**：模块绝不直接写平台表，全部通过 `platform/events.emit()` 上报，由平台统一判定点亮图标/推进成就/记排行/发消息。
- **物品字典统一**：`items` 表是唯一物品来源，商店只引用字典物品，禁止“匿名物品”。
- **背包分页**：`inventory.module_key` 实现 farm/town/garden/sea 分页，统一入口。
- **加锁双轨**：隐私锁(访问/交流) + 物品锁(资源安全)，互动前均校验。
- **操作留痕**：`OperationLog` 记录全部关键动作，客服申诉可查。
- **怀旧 WAP 风**：单列、列表为主、蓝链接、小字号、朴素表格，无现代 KPI 大卡/瀑布流。

---

## 九、开发与扩展

### 新增一个游戏模块（满足 8 条接入规范）

1. 在 `models.py` 增加模块玩法表。
2. 在 `seed.py` 注册模块到 `Module` 表 + 物品字典 `items`。
3. 在 `routers/` 新建 `mymodule.py`，实现首页/列表/详情/操作/结果/规则页面。
4. 玩法内只调 `platform` 服务：用 `goods` 管物品、`events.emit` 上报、`locks` 校验锁、`friends` 校验黑名单。
5. 在 `main.py` 的 `routers` 列表注册路由。
6. 声明排行指标与消息模板。

### 重置数据
```bash
rm -f data/qq_home.db
python3 -c "import asyncio; from app import seed; asyncio.run(seed.seed())"
```

---

## 十、API 速查（curl 示例）

```bash
# 登录拿 token
TOKEN=$(curl -s -X POST http://localhost:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"demo123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['token'])")

# 查我的信息
curl -s http://localhost:8000/api/me -H "Authorization: Bearer $TOKEN"

# 查农场背包
curl -s "http://localhost:8000/api/inventory?m=farm" -H "Authorization: Bearer $TOKEN"

# 上报排行分数（模块事件）
curl -s -X POST http://localhost:8000/api/events/emit \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Module-Key: farm" \
  -H "Content-Type: application/json" \
  -d '{"event":"ranking","payload":{"metric":"harvest","score":1}}'

# 查排行
curl -s "http://localhost:8000/api/ranking?m=farm&metric=harvest" -H "Authorization: Bearer $TOKEN"
```

---

## 十一、默认配置

| 项 | 默认值 | 位置 |
|----|--------|------|
| 数据库 | `data/qq_home.db` (SQLite) | `config.py` |
| 端口 | 8000 | `run.sh` |
| 会话有效期 | 7 天 | `config.py` |
| 平台货币 | 金币 | `config.py` |
| 物品堆叠上限 | 999 | `config.py` |

> 生产部署请修改 `SECRET_KEY`、启用 HTTPS、更换持久化数据库。

---

## 十二、测试账号速查

| 场景 | 账号 | 操作 |
|------|------|------|
| 体验全部前台 | `demo` / `demo123` | 玩4个模块、加好友、发帖、聊天 |
| 后台管理 | `admin` / `admin123` | 用户/模块/工单/日志管理 |
| 互访互动 | `lily` / `lily123` | 被 demo 偷菜/翻柜/偷花/私聊 |

---

**怀旧 QQ 家园，平台化复刻完成。** 所有规范条目均有对应实现，前台/后台/API 三位一体。
