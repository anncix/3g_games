# QQ家园 — 怀旧平台化复刻

> 版本：**v0.2.7** （2026-08-04 召唤之王原版规格图鉴：spec 权威对齐 45 组常量参考层 + /guide 路由 + 模板，与现行 120 宠/60 技能/战斗/装备系统并存）
>
> 基于 **FastAPI + SQLite + Jinja2(简版 WAP 风)** 实现的怀旧 QQ 家园平台复刻。
> 严格遵循《怀旧QQ家园平台设计规范》：平台统一、模块自治、旧逻辑优先、一页只做一件事。

包含：**前台 WAP 页面** + **后台管理系统** + **JSON API 规范** + **八个游戏模块**。

---

## 更新日志

### v0.2.7 （2026-08-04）— 召唤之王原版规格图鉴（spec 权威对齐 45 组常量参考层 + /guide 路由 + 模板）

以用户提供的《召唤之王完整游戏资料》（原版玩法/数值/系统全解）为权威依据，重新设计召唤之王模块：在**不破坏现行可玩系统**（120 宠/60 技能/战斗/装备/主线任务）的前提下，新增一层"原版规格参考层"，把原版菜单结构、等级解锁、种族阶位、战骨/魔魂/战灵三大装备系统、地图、副本、经验/活力、社交、货币体系、新手路线全量沉淀为静态常量，并通过原版图鉴页集中展示原版风貌。策略与 v0.2.5 精武堂 WAP 原版资料补全一致（保守增量，参考层并存）。

**一、原版规格参考层（summon_data.py +45 组常量，纯静态不入库）**

按资料十三章结构对齐，覆盖原版全部系统：

| 章 | 常量组 | 内容 |
|----|--------|------|
| 二、菜单界面 | `MENU_INFO_BAR`（6 项）+ `MENU_STRUCTURE`（16 项菜单，含功能/开放条件） | 主界面信息栏 + 16 项核心功能菜单 |
| 三、角色系统 | `LEVEL_UNLOCKS_SPEC`（8 段等级表）+ `TALENT_SCHOOLS`（3 流派） | 1~110 级可带幻兽数/魔魂槽位/解锁内容 + 兽王/幻法/暗牧三大天赋 |
| 四、宠物系统 | `PET_RACES_SPEC`（4 种族）+ `PET_QUALITY_TIERS`（4 阶位）+ `PET_EVAL_DIMENSIONS`（4 维鉴定）+ `PET_PERSONALITIES`（6 性格）+ `SKILLS_SPEC`（8 技能）+ `MAP_PET_RECOMMEND`（5 等级段推荐）+ `PET_CHANGE_STRATEGY` + `CAPTURE_BALLS_SPEC`（3 球）+ `PET_GROWTH_ITEMS`（3 道具） | 兽/虫/羽/水四族 + 黄玄地天四阶 + 成长率/资质/技能/性格四维 + 原版技能表 + 各等级地图推荐 + 换宠策略 + 捕捉/养成道具 |
| 五、物品与装备 | `BONE_PARTS_SPEC`（7 部位）+ `BONE_GRADES_SPEC`（8 品级）+ `BONE_STRENGTHEN_TIERS`（6 强化阶）+ `BONE_STRENGTHEN_RULES` + `SOUL_GRADES_SPEC`（6 品级）+ `SOUL_AFFIXES_FIXED`/`SOUL_AFFIXES_PERCENT`（天魂极品属性）+ `SOUL_HUNTERS_SPEC`（7 档猎魂师）+ `SOUL_HUNTER_ITEM_PRICES` + `SOUL_XP_SPEC`（升级经验公式表）+ `SPIRIT_SLOTS_SPEC`（6 槽）+ `SPIRIT_QUALITY_TIERS`（4 品质）+ `SPIRIT_RULES` + `OTHER_ITEMS_SPEC` | 战骨 7 部位/8 品级/6 强化阶 + 魔魂 6 品级/天魂极品属性/猎魂师价目表/升级经验表 + 战灵 6 槽/4 品质/洗炼规则 + 其他道具 |
| 六、地图系统 | `MAPS_SPEC`（7 大地图）+ `MAP_MECHANICS`（天气/昼夜/扫图/修行） | 新手村→清溪→石工矿场/湖里→树藤沼泽→落日荒漠→雪山，含天气昼夜机制 |
| 七、副本与挑战 | `DUNGEONS_SPEC`（6 玩法）+ `ARENA_TIERS_SPEC`（4 阶擂台）+ `ARENA_TIPS` + `BATTLEFIELD_ZONES`（2 战场分区） | 通天塔/战灵塔/擂台/战场/联盟战/修行 + 黄玄地天四阶 + 猛虎/飞鹤战场 |
| 八、任务系统 | `NEWBIE_TASKS_SPEC` + `MAIN_TASKS_SPEC` + `DAILY_ACTIVITIES`（6 活动） | 新手任务/主线任务/日常活动表 |
| 九、经验体系 | `EXP_SOURCES_SPEC`（6 途径）+ `VITALITY_SPEC`（活力值系统） | 六大经验途径 + 活力自动回复/互灌/师徒 4 倍/日常奖励 |
| 十、战斗规则 | `BATTLE_RULES_SPEC` | 自动文字战报/技能概率/六大属性/速度定序/可重试 |
| 十一、社交系统 | `ALLIANCE_SPEC` + `MASTER_APPRENTICE_SPEC` + `FRIEND_SPEC` | 联盟捐献/寄存/技能/火能 + 师徒(40 收/30 拜/35 出师/4 倍活力) + 好友互灌/雇佣 |
| 十二、货币体系 | `CURRENCY_TABLE_SPEC`（8 种货币） | 铜钱/元宝/活力/焚火晶/灵石/声望/桃李值/贡献 |
| 十三、新手路线 | `NEWBIE_GUIDE`（5 阶段）+ `NEWBIE_PRINCIPLES`（4 原则） | 1-20→20 转折→30 攒资源→40 成型→50+ 终极 + 成长≥3星/技能重质/速度为王/换宠节奏稳 |

> 另含 `SPEC_SECTIONS` 索引常量（13 章分节目录），供图鉴页分节展示。

**二、路由 + 模板（+1 路由 +1 模板 +1 导航）**

| 项 | 路径 | 说明 |
|----|------|------|
| 路由 | `GET /games/summon/guide` | 原版规格图鉴页，渲染 guide.html，传入 `D=summon_data` |
| 模板 | `app/templates/summon/guide.html` | 13 章卡片式展示原版规格，沿用 WAP 层级页风格（tag/card/li/section-title） |
| 导航 | `summon/home.html` 快捷入口 | 在"图鉴"后新增"原版图鉴"链接 → `/games/summon/guide` |

**三、设计原则：参考层并存，不破坏现行系统**

- 现行可玩系统（120 宠图鉴/60 基础技能×3 阶=180 技能/回合战斗/战骨魔魂战灵装备/8 章主线任务/通天塔/擂台/战场）**完全保留**，未做任何数值改动
- 新增的 `*_SPEC` 常量为**纯参考层**，仅供 guide 页展示原版风貌，不参与现行战斗/捕捉/装备判定
- 与现行系统形成对照：如原版 8 技能表（`SKILLS_SPEC`）vs 现行 60 技能库（`SKILLS`）；原版 4 种族（`PET_RACES_SPEC`）vs 现行 6 种族（`RACE_LIST`，含龙/亡灵）。两套并存，玩家可在图鉴页看到原版风貌，在游戏内体验复刻版

**四、闭环验证**
- ✅ IMPORT OK：`VERSION = 0.2.7`；45 组 spec 常量全部可访问（无 MISSING）
- ✅ 数据计数校验：MENU 16 / LEVEL 8 / TALENT 3 / RACES 4 / TIERS 4 / SKILLS 8 / MAP_RECOMMEND 5 / BONE_PARTS 7 / BONE_GRADES 8 / BONE_TIERS 6 / SOUL_GRADES 6 / SOUL_HUNTERS 7 / SPIRIT_SLOTS 6 / SPIRIT_QUALITY 4 / MAPS 7 / DUNGEONS 6 / ARENA 4 / BF_ZONES 2 / DAILY 6 / EXP 6 / CURRENCY 8 / NEWBIE_GUIDE 5 / PRINCIPLES 4 —— 全部与原版资料一致
- ✅ 元组 arity 校验：所有模板解包用的常量字段数与 guide.html 的 `{% for ... in ... %}` 解包完全匹配
- ✅ 字典校验：`BONE_STRENGTHEN_RULES`/`SPIRIT_RULES`/`MAP_MECHANICS`/`VITALITY_SPEC`/`BATTLE_RULES_SPEC` 为 dict（模板 `.items()` 可用）；`SOUL_XP_SPEC` 含 formula/max_level/table/cumulative_to_max 四键；`ALLIANCE_SPEC`/`MASTER_APPRENTICE_SPEC` 嵌套键齐全
- ✅ 路由注册：`/games/summon/guide` 已加入 `summon.router`

**文件变更**
- `app/routers/summon_data.py`：+v0.2.7 原版规格参考层（45 组常量 + SPEC_SECTIONS 索引）
- `app/routers/summon.py`：+1 路由 `/guide`（`summon_guide` 渲染 guide.html）
- `app/templates/summon/guide.html`：+1 原版规格图鉴模板（13 章展示）
- `app/templates/summon/home.html`：快捷入口 +原版图鉴链接
- `app/config.py`：版本号 0.2.6 → 0.2.7

---

### v0.2.6 （2026-08-04）— 全游戏主线任务补全 + 导航栏目完善（6 模块 +6 路由 +6 模板）

修复致命问题：八个游戏模块中六个（阳光农场/美味小镇/召唤之王/风云三国/精武堂/幻想西游）**完全没有主线任务**，且首页导航栏目缺失主线入口。本次全网检索原版玩法资料，为六模块补全结构化主线任务链，新增主线任务页面，并在各游戏首页快捷入口首位补全"主线任务"导航链接。

**一、主线任务链补全（6 模块 +MAIN_QUESTS 常量，统一 5 元组结构）**

统一结构：`(sort 序号, 名称, 解锁等级, 目标/剧情描述, 奖励)`，按等级顺序解锁，纯静态常量不入库。

- **阳光农场** `farm.py` MAIN_QUESTS（8 步·新手引导+成长里程碑，来源：阳光农场原版玩法 + baike.com 红土地词条）
  播种希望(1) → 辛勤浇灌(3) → 丰收时刻(5) → 偷菜有道(8) → 作物进阶(12) → 红土开荒(28) → 社交达人(35) → 农场大亨(50)
- **美味小镇** `town.py` MAIN_QUESTS（8 步·经营成长线，来源：美味小镇原版玩法 + youxiabc.com 攻略）
  开业大吉(1) → 食材采购(5) → 菜谱升级(10) → 油壶扩容(15) → 蟑螂来袭(20) → 雇佣帮手(25) → 厨艺大赛(40) → 金牌餐厅(60)
- **召唤之王** `summon_data.py` MAIN_QUESTS（8 步·收集+推进，来源：召唤之王原版玩法 + zol.com 攻略）
  初次捕捉(1) → 图鉴开启(5) → 战骨强化(10) → 通天塔(15) → 擂台首胜(20) → 魂之猎手(30) → 联盟加入(40) → 幻兽大师(60)
- **风云三国** `fengyun_data.py` MAIN_QUESTS（8 章·三国剧情主线，来源：三国演义 + 三国风云官方事件大全）
  黄巾之乱(1) → 董卓之乱(10) → 群雄逐鹿(20) → 官渡之战(35) → 赤壁之战(50) → 三国鼎立(65) → 北伐中原(80) → 天下一统(100)
- **精武堂** `martial_data.py` MAIN_QUESTS（8 步·武学成长线，来源：精武堂WAP原版玩法 + 用户资料）
  初入江湖(1) → 修炼有成(10) → 技能初成(15) → 比武切磋(20) → 战神宫(25) → 加入帮派(30) → 装备锻造(40) → 武林大会(50)
- **幻想西游** `xyou_data.py` MAIN_QUESTS（8 章·西行取经剧情主线，来源：西游记 + zol.com.cn 幻想西游攻略）
  新手起步(1) → 拜师入门(9) → 长安历练(15) → 中级转职(59) → 西行启程(70) → 大闹天宫(80) → 地府探险(90) → 灵山取经(180)

> 已有主线模块（无需补全）：纵横四海 `sea_data.py` MAIN_QUESTS（12 条链/4000+环，DB 入库）、魔法花园 `garden_data.py` QUEST_CHAIN（7 步交互式任务链）。

**二、路由 + 模板（+6 路由 +6 模板）**

| 模块 | 路由 | 模板 | 说明 |
|------|------|------|------|
| 阳光农场 | `GET /games/farm/mainquests` | `farm/mainquests.html` | 8 章主线展示 |
| 美味小镇 | `GET /games/town/mainquests` | `town/mainquests.html` | 8 章主线展示 |
| 召唤之王 | `GET /games/summon/mainquests` | `summon/mainquests.html` | 8 章主线展示 |
| 风云三国 | `GET /games/fengyun/mainquests` | `fengyun/mainquests.html` | 8 章三国剧情展示 |
| 精武堂 | `GET /games/martial/mainquests` | `martial/mainquests.html` | 8 章武学成长展示 |
| 幻想西游 | `GET /games/xyou/mainquests` | `xyou/mainquests.html` | 8 章西行取经展示 |

模板沿用 WAP 层级页设计，卡片式展示每章（序号·名称·解锁等级·剧情/目标·奖励），与既有 `sea/mainquests.html` 风格一致。

**三、导航栏目完善（6 模块首页快捷入口首位 +主线任务）**

各游戏首页 `home.html` 的"快捷入口"网格首位新增"主线任务"链接，确保玩家进入游戏即可看到主线入口：
- `farm/home.html` / `town/home.html` / `summon/home.html` / `fengyun/home.html` / `martial/home.html` / `xyou/home.html`
- 同时清理 fengyun/martial/xyou 首页误放在快捷入口里的"返回大厅"重复链接（底部已有返回按钮）

> 已有主线入口模块（无需补全）：纵横四海 `sea/home.html`（第39行）、魔法花园 `garden/home.html`（魔法任务）。

**四、闭环验证**
- ✅ IMPORT OK：`VERSION = 0.2.6`；8 模块主线任务常量全部可访问（farm/town/summon/fengyun/martial/xyou 各 8 条 + sea 12 条 + garden 7 步）
- ✅ 路由注册：7 个 `/games/*/mainquests` 路由全部注册（6 新增 + sea 既有）
- ✅ HTTP 冒烟（demo 登录）：6 个新 mainquests 页面均 200，含"主线任务"文案（farm 2807 / town 2816 / summon 2788 / fengyun 3267 / martial 2817 / xyou 3484 字节）
- ✅ 导航校验：6 个游戏首页均含 `/mainquests` 链接

**文件变更**
- `app/routers/xyou_data.py`：+MAIN_QUESTS（8 章西行取经主线）
- `app/routers/farm.py` / `town.py` / `summon.py` / `fengyun.py` / `martial.py` / `xyou.py`：各 +1 路由 `/mainquests`
- `app/templates/{farm,town,summon,fengyun,martial,xyou}/mainquests.html`：+6 主线任务模板
- `app/templates/{farm,town,summon,fengyun,martial,xyou}/home.html`：快捷入口 +主线任务链接
- `app/config.py`：版本号 0.2.5 → 0.2.6

> 注：farm/town/summon/fengyun/martial 的 MAIN_QUESTS 常量已在 v0.2.6 开发周期内先行写入对应 data 文件，本次完成 xyou 补全 + 路由/模板/导航闭环。

---

### v0.2.5 （2026-08-03）— 精武堂 WAP 原版资料补全（22 组常量 + 资料图鉴路由）

对精武堂模块做"验证 + 全网检索补全丢失数据 + 整理使程序合理"。当前模块采用 PC 版四维属性(strength/agility/physique/inner_power)+8 部位+5 品质设定（v0.1.0 定版，34 路由 + 13 模板，核心玩法完整），与用户提供的《QQ家园精武堂完整游戏系统资料》（WAP 原版 2009.10-2015.06）存在版本差异。采用**保守增量**策略：不破坏现有战斗/属性/装备系统，在 `martial_data.py` 追加 22 组 WAP 原版资料常量（纯参考层），新增 1 个资料图鉴路由 + 模板展示原版风貌。

**一、WAP 原版资料补全（martial_data.py +22 组常量）**
- `LEVEL_TITLES`（10 档等级称号）：2-9 无名小卒 → 10-19 武林新丁 → ... → 90+ 无敌圣者
- `ADD_POINT_SCHOOLS`（4 种加点流派）：猛攻型/高防型/迅猛型/平衡型（5 属性·每级 3 点·80 级以上 5 点）
- `EXP_TABLE_WAP`（1-87 级精确经验表）：1级=20 → 30级=112,840 → 60级=1,659,625 → 87级=13,517,103
- `WARSHRINE_7FLOORS`（战神宫 7 层完整数据）：山下修身馆/战神山前平台/.../战神旋梯（含矿产+酒窖）
- `PETS_FOUR_BEASTS`（四圣兽宠物）：东方神龙(气血)/玄冥神虎(速度)/不死凤凰(精气)/神龟玄武(防御)，含 5 阶进化链+技能+评价+魂砂
- `PET_LEVEL_STAGES`（5 档等级阶段）：野兽(1-19)→灵兽(20-39)→妖兽(40-59)→圣兽(60-79)→神兽(80-100)
- `PET_ATTACH_MULT`（附身加成倍数）：气血×2.0 / 伤害×0.5 / 速度×0.1 / 防御×1.3
- `PET_SOUL_SAND_MAX_STAR`/`PET_STAR_HP_BONUS`/`PET_SOUL_GUARD_TOTAL_HP`（吞砂顿悟）：14星上限 / 9-13星加血表 / 魂之守护共加血6580
- `BLESSING_LIFE_POWER`（命力祈福 5 档）：念福佑(500)→烧福香(700)→写福愿(1000)→挂福袋(1200)→拜福神(1500)
- `WUHUN_RANK_SYSTEM`（武魂段位）：武林大会获武魂 → 累计段位 → 精武宝库买图谱前置
- `GUILD_XINFA`/`GUILD_XINFA_MAX_LEVEL`/`GUILD_XINFA_LEVEL_COST`（帮派心法 5 种 1-10 级）：强身(力)/凝气(血)/易筋(防)/洗髓(精)/轻身(速)
- `FORGE_RECIPES_WAP`（15 条锻造配方）：5 部位×3 等级（松纹剑/锋灵剑/流光剑 + 耀瞳华服/幽冥冷衫/沧月薄衣 + ...）
- `STAMINA_SYSTEM`（体力系统）：基础100 + 魔钻+20% + 消耗表(比武10/练功房20/战神宫15/武林大会20) + 恢复(每天回满/大力丸4次/闻香炉3次)
- `WULIN_DA_HUI`（武林大会规则）：10级开启 / 20体力 / 3分区(初级1-29/中级30-49/高级50+) / 精武王等称号
- `CURRENCIES_WAP`（四货币体系）：G币(免费)/元宝(充值1元≈100)/银票(交易)/帮贡(帮派)
- `SKILL_RECOMMENDATIONS`/`SKILL_CORE_PICKS`（15 技能推荐组合 + 核心技能标注）：潇湘剑雨(大招)/妙手回春(回血)/三清缚影(封印)/天罗地网(控制)/移形换影(越级)
- `EXP_SOURCES_WAP`（5 种经验获取途径）：练功房/战神宫/比武PK/帮派古树/加成卡
- `EQUIP_STRENGTHEN_WAP`（装备强化要点）：上限50级 / 耐久500次 / 失败清零 / 满属性参考 / 技巧
- `GUILD_BUILDINGS`（6 个帮派建筑）：闻香炉/温泉古树/矿洞/书院/工坊/聚义厅
- `GUILD_JOIN_CREATE`（帮派加入/创建条件）：加入20级+500G币 / 创建40级+会旗 / 帮战周一报名周三签到

**二、路由 + 模板（+1 路由 +1 模板）**
- `GET /games/martial/archive`：WAP 原版资料图鉴页（14 节内容：版本说明/等级称号/加点流派/87级经验表/四圣兽宠物/战神宫7层/命力祈福/武魂段位/武林大会/帮派心法/锻造配方/装备强化/技能功法/体力系统/四货币）
- `templates/martial/archive.html`：沿用 WAP 层级页设计，表格+卡片展示全部 22 组常量
- `home.html` 快捷入口新增"原版资料"链接

**三、设计决策（保守增量，零行为变更）**
- 当前模块用 PC 版四维属性设定（v0.1.0 定版可运行），**不替换** `exp_needed()` 公式 / 战斗 / 装备 / 技能逻辑
- WAP 原版资料作为**纯参考层常量**，供资料图鉴页展示原版风貌
- 零 URL 变更（仅新增 `/archive`）、零数据表变更、零行为变更

**四、闭环验证**
- ✅ IMPORT OK：`VERSION = 0.2.5`；22 组新常量全部可访问（87 级经验表 len=87 / 7 层战神宫 / 4 圣兽 / 15 锻造配方 / 5 命力祈福 / 5 帮派心法）
- ✅ 种子闭环：全量 seed 正常通过（含 martial 模块）
- ✅ HTTP 冒烟（demo 登录）：`/games/martial/archive` 200，len=17280
- ✅ 内容校验：含等级称号(武林新丁) / 87级经验(13517103) / 战神宫7层(战神旋梯) / 四圣兽(东方神龙+不死凤凰) / 命力祈福(念福佑+拜福神) / 帮派心法(强身+洗髓) / 锻造配方(松纹剑+流光剑) / 四货币(G币+银票) / 武林大会(精武王) —— 10 项全 True

**文件变更**
- `app/routers/martial_data.py`：+22 组 WAP 原版资料常量（参考层）
- `app/routers/martial.py`：+1 路由 `/archive`
- `app/templates/martial/archive.html`：新增资料图鉴模板（14 节）
- `app/templates/martial/home.html`：快捷入口 +1（原版资料）
- `app/config.py`：版本号 0.2.4 → 0.2.5

---

### v0.2.4 （2026-08-03）— 路由结构整理（26 个 router 加 tags 分组 / Swagger 文档可读性）

对全平台路由结构做"验证 + 分析 + 整理使程序合理"。结合全网检索的原版玩法与 FastAPI 路由规范（`https://fastapi.tiangolo.com/tutorial/bigger-applications/`）逐一核对后，确认 8 个游戏模块 + 18 个平台模块共 **322 个路由结构清晰**（`/games/*` 游戏命名空间 + 平台裸路径 + `/api/*` JSON 接口），此前分析中"四海仅 8 路由 / 召唤 8 大系统 0 路由"的判断系基于过时数据——实际 sea 已 21 路由（ships/dungeons/trade/pets/gems/cards/holymarks/equipsets/mainquests 全覆盖）、summon 已 37 路由（bone/soul/spirit/arena/battlefield/alliance/mentor/tower 全覆盖）、garden 已 35 路由（含 quest 任务链）。

唯一确凿且全平台一致的结构性缺口是：**26 个路由文件全部未设 `tags`，导致 Swagger 文档 322 个接口堆在 default 分组下不可读**。本次按 FastAPI 大型项目规范为全部 router 补 tags 分组，零行为变更、零 URL 变更。

**一、tags 分组方案（27 分组）**

| 分组 | 路由数 | 涉及文件 |
|---|---|---|
| 美味小镇 | 37 | town.py |
| 召唤之王 | 37 | summon.py |
| 魔法花园 | 35 | garden.py |
| 精武堂 | 34 | martial.py |
| 幻想西游 | 31 | xyou.py |
| 纵横四海 | 21 | sea.py |
| 风云三国 | 21 | fengyun.py |
| API | 17 | api.py |
| 阳光农场 | 15 | farm.py |
| 管理 | 12 | admin.py |
| 好友 | 8 | friends.py |
| 账号 | 6 | auth.py |
| 个人主页 | 6 | profile.py |
| 论坛 | 6 | forum.py |
| 设置 | 6 | settings.py |
| 聊天 | 5 | chat.py |
| 家族 | 4 | family.py |
| 活动 | 4 | activity.py |
| 客服 | 4 | support.py |
| 消息 | 3 | message.py |
| 背包 | 3 | inventory.py |
| 商店 | 2 | shop.py |
| 大厅 | 1 | lobby.py |
| 同城 | 1 | city.py |
| 排行 | 1 | ranking.py |
| 图标 | 1 | icons.py |
| 健康检查 | 1 | main.py（`/health`） |

**二、整理要点**
- 8 游戏模块 tags：阳光农场 / 美味小镇 / 魔法花园 / 纵横四海 / 召唤之王 / 精武堂 / 风云三国 / 幻想西游
- 18 平台模块 tags：账号 / 大厅 / 个人主页 / 好友 / 家族 / 论坛 / 聊天 / 同城 / 消息 / 活动 / 排行 / 图标 / 设置 / 客服 / 背包 / 商店 / 管理 / API
- `/health` 健康检查端点补 `tags=["健康检查"]`
- **零 URL 变更、零行为变更**：仅给 `APIRouter(...)` / `@app.get(...)` 增加 `tags=` 参数，不改动 prefix、不改路由路径、不改业务逻辑
- 平台裸路径（`/my`、`/lobby`、`/friends` 等）保持不变，避免破坏前端链接与已发布 URL

**三、闭环验证**
- ✅ IMPORT OK：`VERSION = 0.2.4`；app 正常初始化
- ✅ OpenAPI schema：322 路由全部带 tags，27 个分组（26 模块 + 健康检查），无 tag 路由 = 0
- ✅ HTTP 冒烟（demo 登录）：31 路由全 200——8 游戏首页 + summon 8 子系统（bone/arena/tower/soul/spirit/alliance/mentor/battlefield）+ sea 9 子系统（ships/trade/dungeons/pets/gems/cards/holymarks/equipsets/mainquests）+ xyou 5 新页（materials/coords/autobattle/roadmap/dungeon_bosses）+ `/docs` Swagger 页
- ✅ Swagger 文档 `/docs` 200，27 分组按字母与规模有序排列，可读性显著提升

**四、路由结构现状结论（验证后）**
- 平台模块（无 `/games` 前缀）：auth/lobby/profile/friends/family/forum/chat/city/messages/activity/ranking/icons/settings/support/inventory/shop/admin — 共 60 路由
- 游戏模块（`/games/*`）：farm/town/garden/sea/summon/martial/fengyun/xyou — 共 231 路由，8 模块均完整覆盖原版核心玩法
- JSON API（`/api/*`）：认证 + 各模块状态快照 — 17 路由
- 全平台 322 路由，结构清晰，无孤儿数据表、无重复路由、无缺失入口

**文件变更**
- 26 个路由文件：`APIRouter(prefix=..., tags=[...])` 各加 tags 参数
- `app/main.py`：`/health` 端点加 `tags=["健康检查"]`
- `app/config.py`：版本号 0.2.3 → 0.2.4

---

### v0.2.3 （2026-08-03）— 幻想西游全网检索补全（参数补全 + 自动战斗挂机 + 5 新路由）

对 v0.2.2 上线的幻想西游模块做"验证 + 全网检索补全丢失数据 + 整理使程序合理"。按用户提供的《QQ家园〈幻想西游〉完整详细资料（参数补全版）》及 zol.com.cn 玩家攻略（副本指南/升级篇）、baike.com 词条、docin.com 新手指南交叉补全 v0.2.2 中"资料不详 / 参数缺失"的部分：药品完整参数表、高级升级材料、长安城坐标、副本 BOSS 详细掉落、自动战斗挂机系统、升级路线图等。所有新数据落独立静态配置 `xyou_data.py`，经 `seed_xyou.py` 幂等入库，并新增 5 个路由 + 5 个模板对外展示。

**一、全网检索补全静态配置（routers/xyou_data.py 扩展 ~22 组常量）**
- `MEDICINES_EXPANDED`（14 种药品完整参数）：止血草/金疮药/金创药/小还丹/大还丹/九转回魂丹/仙灵丹 + 鼠儿果/龙涎草/凝神露/天仙玉露/瑶池玉液 + 还魂符/高级还魂符
  - 含等级要求 / HP·MP 恢复值 / 售价 / 获取方式（长安药店·怪掉落·副本·炼丹·BOSS）
- `GEM_TIERS`（5 阶宝石/水晶等级与使用区间）：一阶(1-30级)→二阶(30-50)→三阶(50-70,含水晶)→四阶(70-90,含玄武石)→五阶(90+,含佛印石)
- `ADVANCED_MATERIALS`（19 种高级升级材料）：轩辕石/蓬莱仙石/玄阴寒玉/补天陨铁/英雄牌/圣装精华/金刚石/金精/金犀角/烈焰火羽/冰凌石/雷晶/冰晶/逆鳞/黑曜石/引魄/食尸鬼之皮/剥皮鬼之皮/炼尸宝石
  - 含用途 + 获取方式（蓬莱仙岛BOSS/极寒之地副本/高级BOSS掉落/阵营战奖励等）
- `REGION_MATERIALS`（按 6 大场景区域分组的普通材料掉落分布）：长安区域/城南荒野/紫竹林区域/宝象国区域/师门区域/高级区域
  - 含每种材料的掉落怪物与具体位置（如黑狗血→背阴巷黑狗 / 铁砂→大雁塔扫帚怪 / 紫竹根→紫竹林副本紫竹战士）
- `CHANGAN_COORDS`（12 条长安城核心坐标）：十字街头/青龙街/白虎街/朱雀街/玄武街/大雁塔/背阴巷/碑林/慈恩寺(123,202)/冰风谷(8,5)/水晶宫(2535,940)/皇陵
  - 含坐标位置 + NPC/功能（门派接引使/房玄龄/药店/铁匠铺/拍卖行/仓库/帮派管理员/皇宫入口等）
- `REGION_ENTRIES`（13 个其他重要区域进入方式 + 推荐等级）：城南荒野/紫竹林/五大门派/宝象国/黑松林/双茶陵/乌鸡国/乌林子/傲来国花果山/天宫兜率宫/斩妖台/地府望乡台/蓬莱仙岛
- `TASK_TYPES`（8 种任务类型与标识）：主线(金色!)/支线(银色!)/门派(蓝色!)/日常(绿色!)/副本(紫色!)/活动(红色!)/转职(特殊)/天宫剧情(特殊任务链)
- `PROMOTION_QUESTS_DETAIL`（9/59 级转职任务完整流程）：9级找门派接引使→选门派→掌门试炼；59级回师门→房玄龄→兵马前阵(7,2)→抄碑文→杀怪
- `DUNGEON_BOSSES`（8 个副本 BOSS 详细掉落）：冰晶塔/白骨陵墓/波月洞/老君炉/水帘洞/斩妖台/枉死城/降妖除魔
  - 含 BOSS 列表 + 掉落物 + 入口位置（如白骨陵墓 6 BOSS 掉食尸鬼之皮/剥皮鬼之皮/炼尸宝石/白骨靴/祭祀之帽等 8 件）
- 扩展 `DUNGEONS`：新增 3 副本（大雁塔25级 / 盘丝洞240级 / 降妖除魔周末活动），副本总数 19 → 22
- `BATTLE_HOTKEYS_DEFAULT`（战斗界面 9 个快捷键默认配置）：1小红药/2小蓝药/3普攻/4门派基础/5门派单攻/6门派群攻/7大红药/8大蓝药/9回城符
- `SYSTEM_SETTINGS`（4 项系统设置参数）：快捷技能/聊天频道开关/图片显示/自动战斗
- `BASE_ATTRS`（六大基础属性）：体质/力量/智力/敏捷/耐力/精神 + 影响战斗属性 + 侧重职业
- `POTENTIAL_RULES`（潜力点规则）：1-10级自动分配 / 11级起每级 5 点自由分配
- `EXP_SOURCES`（11 种经验获取渠道）：打怪/主线/支线/师门/副本/六千年蟠桃3000万/九千年蟠桃1亿/经验粽子100万/师徒1000万/双倍/挂机
- `LEVEL_GATES`（6 个升级阶段卡点）：9级转职/59级转职/109级转职/135级师门套装/139级师徒出师/200级满级
- `LEVELING_ROADMAP`（7 段新手快速升级路线）：1-10级30分钟/10-40级拜师直跳/40-59级1-2天/60级领蟠桃1分钟/60-80级3-5天/80-99级1-2周/100级+长期
- `PET_BATTLE_RULES`（10 项宠物系统参数）：捕捉术10级学/血量<30%可捕/携带8只/出战1只/获人物20%经验/不超人物等级/忠诚0-100等
- `PET_GROWTH_EXAMPLE`（水兽成长属性示例）：1级初始值 + 每级增长（体质25+3/智慧25+3/精神40+5等）
- `PET_SKILL_CATEGORIES`（4 类宠物技能）：攻击/护主/辅助/生活
- `AUTO_BATTLE_SETTINGS`（8 项自动战斗/挂机参数）：自动遇敌/自动攻击/自动补血阈值/自动补蓝阈值/技能顺序/自动拾取/宠物自动出战/离线挂机
- `TENGYUN_LEVEL_REQ`（腾云驾雾解锁等级 = 30 级）
- `BAG_CATEGORIES`（5 类背包分类）：药品/装备/材料/任务/其他

**二、数据模型层（models.py 新增 2 表 + 1 字段）**
- `XyouMaterial`（高级升级材料字典）：key / name / purpose（用途） / source（获取方式）
- `XyouCoord`（区域坐标字典）：id / scene_key（所属场景，默认 changan） / place（地点名） / coord（坐标/位置） / npc_or_func（NPC/功能）
- `XyouState` 新增 `auto_settings` 字段（Text，JSON 存储自动战斗/挂机设置，默认 `{}`）

**三、生成器 seed_xyou.py 扩展（幂等 / 可断点续跑）**
- 新增 stats 计数：`medicines`（扩展药品）/ `materials`（高级材料）/ `coords`（坐标）
- 第 8 步：14 种扩展药品落 Item 字典（key=xyou_med_*，含等级/恢复值/售价/来源描述）
- 第 9 步：19 种高级升级材料双写（Item 字典 + XyouMaterial 表，key=xyou_mat_*）
- 第 10 步：12 条长安城坐标落 XyouCoord 表（scene_key=changan，按 place 去重）
- 日志输出扩展：`[xyou-v023] 场景+10 技能+45 装备+108 龙宫叉+8 副本+22 宠物+13 物品字典+116 药品+14 扩展药品+14 高级材料+19 坐标+12`
- 幂等校验：以 key 存在性判断，重跑 stats 全 0（含新增 3 类计数）

**四、路由层 routers/xyou.py 扩展（+5 路由）**
- `GET /games/xyou/materials`：高级材料图鉴页（按 key 排序展示 19 种材料 + 6 区域材料分布 + 5 阶宝石表）
- `GET /games/xyou/coords`：长安城坐标页（12 条核心坐标 + 13 区域进入方式）
- `GET /games/xyou/autobattle`：自动战斗/挂机设置页（4 项系统设置 + 8 项自动参数 + 9 快捷键默认配置 + 当前设置表单）
- `POST /games/xyou/autobattle/save`：保存自动战斗设置（auto_encounter/auto_attack/hp_threshold/mp_threshold/auto_pickup/pet_auto_summon 落 XyouState.auto_settings JSON）
- `GET /games/xyou/roadmap`：升级路线图页（6 个卡点 + 7 段升级路线 + 11 种经验渠道）
- `GET /games/xyou/dungeon_bosses`：副本 BOSS 掉落页（8 个副本 BOSS 列表 + 掉落物 + 入口位置）
- home.html 快捷入口新增 5 个链接（材料图鉴/长安坐标/自动战斗/升级路线/副本BOSS）

**五、模板层 app/templates/xyou/（新增 5 模板）**
- `materials.html`：高级材料图鉴（19 种材料卡 + 6 区域分布表 + 5 阶宝石表）
- `coords.html`：长安城坐标（12 条坐标表 + 13 区域进入方式表）
- `autobattle.html`：自动战斗设置（系统设置项 + 9 快捷键默认 + 我的设置表单）
- `roadmap.html`：升级路线图（6 卡点表 + 7 段路线表 + 11 经验渠道表）
- `dungeon_bosses.html`：副本 BOSS 掉落（8 副本 BOSS 卡 + 掉落物列表 + 入口位置）
- 全部沿用 WAP 层级页设计（topbar + crumb + card 列表 + footer），与其他模板视觉一致

**闭环验证**
- ✅ IMPORT OK：`VERSION = 0.2.3`；22 组新常量全部可访问；`XyouMaterial`/`XyouCoord` 模型存在；`XyouState.auto_settings` 字段存在
- ✅ 种子闭环：RUN1 全部插入（场景10/技能45/装备108/龙宫叉8/副本22/宠物13/物品116/药品14/**扩展药品14/高级材料19/坐标12**）
- ✅ 幂等性：RUN2 全 0（含新增 medicines/materials/coords 三类计数）
- ✅ HTTP 冒烟（demo 登录）：5 新路由 GET 全 200（materials 6727B / coords 4470B / autobattle 4245B / roadmap 4873B / dungeon_bosses 4204B）
- ✅ POST 保存：`/autobattle/save` 200，返回"自动战斗设置已保存"
- ✅ 内容校验：materials 页含"轩辕石/蓬莱仙石"；coords 页含"十字街头/青龙街"；dungeon_bosses 页含"冰晶/黑曜石"；roadmap 页含"蟠桃/200级"
- ✅ 完整种子：`[xyou-v023]` 日志输出与其他模块并列，平台全量 seed 通过

**文件变更**
- `app/routers/xyou_data.py`：+22 组常量（MEDICINES_EXPANDED/GEM_TIERS/ADVANCED_MATERIALS/REGION_MATERIALS/CHANGAN_COORDS/REGION_ENTRIES/TASK_TYPES/PROMOTION_QUESTS_DETAIL/DUNGEON_BOSSES/BATTLE_HOTKEYS_DEFAULT/SYSTEM_SETTINGS/BASE_ATTRS/POTENTIAL_RULES/EXP_SOURCES/LEVEL_GATES/LEVELING_ROADMAP/PET_BATTLE_RULES/PET_GROWTH_EXAMPLE/PET_SKILL_CATEGORIES/AUTO_BATTLE_SETTINGS/TENGYUN_LEVEL_REQ/BAG_CATEGORIES）+ DUNGEONS +3 副本
- `app/routers/xyou.py`：+5 路由（materials/coords/autobattle/autobattle_save/roadmap/dungeon_bosses）+ home.html 入口
- `app/seed_xyou.py`：扩展 3 步（扩展药品/高级材料/坐标）+ stats 计数
- `app/models.py`：新增 `XyouMaterial` / `XyouCoord`（2 表）+ `XyouState.auto_settings`（1 字段）
- `app/templates/xyou/`：新增 5 模板（materials/coords/autobattle/roadmap/dungeon_bosses）+ home.html 入口扩展
- `app/seed.py`：xyou 模块描述更新为 v0.2.3
- `app/config.py`：版本号 0.2.2 → 0.2.3

---

### v0.2.2 （2026-08-03）— 新增幻想西游模块（spec 五门派西行 MMORPG 全系统）

按用户提供的《QQ家园〈幻想西游〉完整详细资料》（2006 年上线，2013-11-27 停服，运营近 8 年）落地第八个游戏模块「幻想西游」。题材为穿越大唐盛世西行取经，玩家拜入五大门派修行，沿西行之路降妖除魔。新增独立静态配置文件 `xyou_data.py`（与 `fengyun_data.py` / `martial_data.py` / `sea_data.py` / `summon_data.py` 对齐架构），完整复刻 WAP 文字网游玩法结构与产品节奏。

**一、核心系统设计（spec 落地）**
- 五大门派体系：将军府(物理近战) / 方寸山(法术封印) / 龙宫(法术群攻) / 月宫(仙法半辅) / 普陀山(治疗辅助)
  - 每门派独立基础属性 + 每级成长（将军府气血最高/方寸山封印王者/龙宫群攻最快/月宫均衡/普陀组队抢手）
  - 门派专属武器：将军府枪戟刀 / 方寸山剑拂尘 / 龙宫叉 / 月宫环杖 / 普陀山杖莲台
- 200 级封顶 + 多段转职：9 级入门派 / 59 / 109 / 139 / 169 / 189 级转职
  - 转职节点锁经验，需完成转职任务才能继续升级（spec：9 级不入门派经验锁死）
  - 转职任务对齐 spec：59 级找房玄龄→兵马前阵抄碑文→杀怪；109/139/169/189 回师门挑战
- 经验公式分阶段缓增（对齐 spec 千万级经验道具量级）：新手 100-800 → 初级 1k-50k → 中级 50k-500k → 中高 500k-2M → 高级 2M-10M → 顶级 10M-50M → 终极 50M+

**二、数据模型层（models.py 新增 9 表）**
- `XyouState`（玩家状态：门派/等级/经验/银两/金豆/气血法力攻防速灵力/声望/当前场景/修炼结束时间/日常计数）
- `XyouSkill`（技能字典：key/名称/门派/类型/解锁等级/银两消耗/法力消耗/效果）
- `XyouUserSkill`（玩家已学技能：user_id + skill_key 唯一）
- `XyouEquip`（装备字典：品质/部位/门派限定/等级需求/攻防HPMP加成/价格）
- `XyouUserEquip`（玩家装备实例：equip_key/部位/是否穿戴）
- `XyouDungeon`（副本定义：等级区间/入口场景/难度/经验银两奖励/掉落品质）
- `XyouPet`（宠物字典：携带等级/基础属性/天赋技能/捕捉概率）
- `XyouUserPet`（玩家宠物实例：昵称/等级/经验/忠诚度/是否出战）
- `XyouScene`（场景字典：区域/最低等级/简介/出口场景 JSON 列表）

**三、静态配置文件 routers/xyou_data.py（新增，~430 行）**
- `SECTS`：5 门派（key/名称/定位/核心属性/描述）+ `SECT_BASE_ATTRS`（1 级裸装）+ `SECT_PER_LEVEL`（每级增量）
- `SECT_WEAPON`：门派专属武器类型映射
- `SKILLS`：45 技能（5 门派 × 9，4 类型 active/passive/auxiliary/seal）
  - 将军府：横扫千军/不动如山/破甲击/虎贲之力/霸王冲锋/战神降临/龙吟斩/天罡战气/定鼎天下
  - 方寸山：失心符/定身符/五雷咒/催眠符/符咒精通/驱邪符/天雷咒/心若止水/乾坤符
  - 龙宫：九龙诀(基础心法)/呼风唤雨(龙卷雨击群攻)/龙腾/逆鳞/破浪诀/游龙术(含水遁)/沧海横流/龙啸九天/龙王降临
  - 月宫：月华斩/冰魄咒/寒月诀/霜华护体/广寒月华/嫦娥奔月/广寒冰封/月神之怒/广寒仙境
  - 普陀山：普度众生/金刚不坏/杨柳甘露(复活)/佛光普照/灵动九天/大悲咒(群疗)/舍生取义/九转还魂/佛法无边
- `EQUIP_QUALITIES` / `EQUIP_SLOTS`：6 品质(白蓝紫金神圣) × 6 部位(武器头盔盔甲靴子戒指手镯)
  - `QUALITY_MULT`：白 1.0x → 蓝 1.4x → 紫 2.0x → 金 3.0x → 神 4.5x → 圣 6.5x
- `gen_equip_stats()` / `gen_equip_price()`：按 spec 价值体系生成装备属性与售价
- `LONGGONG_WEAPON_CHAIN`：龙宫叉完整升级路线 8 件套（黄袍武器→龙鳞叉→龙鳞破天叉→青龙叉→青龙在天叉→天龙叉→龙王叉→诛仙叉）
  - 升级消耗对齐 spec：500 万银两+宝石 / 三国声望 / 金豆 80→200 / 银两 7 亿→20 亿
- `DUNGEONS`：19 副本（15-90+ 级，含普通/困难双难度）
  - 15 级水晶宫 / 58 级冰晶塔 / 73 级变异竹林 / 70 级白骨陵墓(普通/困难) / 80 级波月洞·莲花洞·压龙洞·水帘洞(普通/困难)·老君炉(普通/困难) / 85 级斩妖台(普通/困难) / 90 级枉死城(普通/困难) / 70 级妖皇殿 / 限时极夜冰原
- `PETS`：13 宠物（1-150 级携带等级，捕捉概率 0.02-0.60）
- `SCENES`：10 场景（9 大区域：新手村/长安/开封/宝象/乌鸡/傲来/天宫/地府/蓬莱/灵山）
  - 出口引用场景 key 闭环（长安↔所有区域；新手村→长安；西天灵山为终点）
- `POTIONS_AND_PROPS`：14 药品与经验道具（HP/MP/复活/经验/Buff）
  - 经验道具对齐 spec：粽子 100 万 / 六千年蟠桃 3000 万 / 九千年蟠桃 1 亿 / 人参果 500 万
- `MONSTERS`：13 怪物（覆盖九大区域场景，2-180 级）
- `MENTOR_*`：师徒系统（55 级开启 / 拜 139 级以上玩家 / 拜师奖励 1000 万经验）
- `WEDDING_TIERS`：三档婚礼（简朴/热闹/豪华，激活 1/2/3 条房屋属性）
- `CHILD_BIRTH`：子女生育（千年人参 30% / 万年人参 100% / 连续 7 个千年必成）
- `PROMOTION_QUESTS`：6 段转职任务节点详情
- `calc_damage()` / `calc_pet_exp()`：战斗伤害公式 + 宠物经验（人物 20%）

**四、生成器 seed_xyou.py（幂等 / 可断点续跑）**
- **10 场景**（spec 九大区域世界地图）：新手村→长安城→开封府 / 宝象国 / 乌鸡国 / 傲来国 / 天宫 / 地府 / 蓬莱仙岛→西天灵山
- **45 技能**（5 门派 × 9，4 类型 active/passive/auxiliary/seal 全覆盖）
- **108 通用装备**（6 品质 × 6 部位 × 3 等级档 10/40/80 = 108 件）
  - key 规范：`xyou_eq_{quality_pinyin}_{slot_pinyin}_{lvl}`
  - 同步落 Item 字典（116 条），可被背包/商店引用
- **8 件龙宫叉系列**（sect_req=longgong 限定）：黄袍武器→诛仙叉完整升级链
- **19 副本**（含 6 个普通/困难双难度版本）：场景入口引用场景 key 闭环
- **13 宠物**（1-150 级携带等级）：小游鱼/野兔/狼王/火苗/石狮子/海龟/蝴蝶精/白骨精/火焰鸟/雪狼/龙子/玄武/烛龙
- **14 药品与经验道具**：4 档 HP 药 + 3 档 MP 药 + 复活药 + 4 经验道具 + 2 Buff 药
- 全部物品同步落 Item 字典（module_key=xyou）

**五、路由层 routers/xyou.py（新增，~800 行 / 16 路由）**
- 角色创建（5 门派选择）+ 主页（状态栏/导航/场景/转职待办/修炼待领）
- 技能学习（按门派筛选 / 解锁等级校验 / 银两消耗）
- 装备穿戴/卸下（6 部位，门派限定校验）
- 装备商店购买（按门派筛选可购买装备）
- 副本挑战（按等级段进入校验，简易战斗胜率，掉落随机装备）
- 修炼挂机（4 小时封顶，每小时 500 经验 / 200 银两）
- 转职系统（6 段转职节点，完成转职任务解锁经验上限）
- 宠物系统（设置出战 / 休息，出战宠物自动获 20% 经验）
- 世界地图（10 场景移动，相邻场景校验，等级门槛）
- 战斗系统（场景内遇怪，日限 50 场，宠物经验加成）
- 规则页（13 章节：核心定位/门派/等级转职/技能/装备/副本/宠物/世界地图/货币/修炼/师徒/婚姻子女/战斗公式）

**六、模板层 app/templates/xyou/（新增 12 模板）**
- home / create / skills / equip / shop / dungeons / cultivate / promote / pet / scenes / battle / rules
- 全部沿用 WAP 层级页设计（topbar + crumb + card 列表 + footer），与其他模块视觉一致

**闭环验证**
- ✅ 路由闭环：`python -c "from app.main import app"` IMPORT OK；26 个 _IncludedRouter（含 xyou）
- ✅ 种子闭环：`[xyou-v022] 场景+10 技能+45 装备+108 龙宫叉+8 副本+19 宠物+13 物品字典+116 药品+14`
- ✅ 幂等性：重跑全 0（场景+0/技能+0/装备+0/龙宫叉+0/副本+0/宠物+0/物品字典+0/药品+0）
- ✅ HTTP 冒烟测试（demo 登录）：home/rules/dungeons/scenes/skills/battle/create 全 200
- ✅ 完整玩法流程：选门派→学技能→进副本(等级拦截)→战斗(获经验+宠物经验)→修炼(4h领取) 全流程通过
- ✅ 数据完整性：场景 exits 引用闭环 / 副本 scene 引用场景 key / 装备 sect_req 限定门派 / 龙宫叉升级路线 8 件套
- ✅ 架构对齐：xyou_data.py 与 fengyun_data.py / martial_data.py / sea_data.py / summon_data.py 同级

**文件变更**
- 新增 `app/routers/xyou_data.py`（静态配置，~430 行）
- 新增 `app/routers/xyou.py`（路由层，~800 行 / 16 路由）
- 新增 `app/seed_xyou.py`（生成器，~163 行）
- 新增 12 个 `app/templates/xyou/*.html` 模板
- `app/models.py`：新增 9 表（XyouState/Skill/UserSkill/Equip/UserEquip/Dungeon/Pet/UserPet/Scene）
- `app/seed.py`：注册 xyou 模块 + 接入 `seed_xyou(db)` + 新增 `icon_xyou` 图标
- `app/main.py`：注册 xyou 路由（import + routers 列表）
- `app/config.py`：版本号 0.2.1 → 0.2.2

---

### v0.2.1 （2026-08-03）— 全网检索补全六模块核心玩法 + 平台活动/排行增强

基于全网检索到的经典 QQ 家园原版玩法资料（zol.com 玩家攻略 / doc88.com 道具编码表 / baike.com 红土地百科 / youxiabc.com 作物排行 / QQ经典农场频道攻略），补全 v0.2.0 后仍缺失的六模块核心玩法与平台级系统。

**一、精武堂 · 战神宫（spec 核心修炼场所，来源 zol.com 玩家攻略）**
- 新增 `martial_data.py` `WARSHRINE` 配置：20级进入 / 前3层 / 15体力2小时 / 经验倍率1.5x→3x→4.5x / 4小时排位混战
- 新增 4 路由（[martial.py](file:///workspace/app/routers/martial.py)）：战神宫主页 / 开始修炼 / 领取经验 / 挑战上层
- 修炼状态存 `daily_counters` JSON（warshrine_floor + warshrine_started_at），不改 models
- 新增 [warshrine.html](file:///workspace/app/templates/martial/warshrine.html) 模板：3层排位卡 + 各层在线玩家榜 + 规则说明
- 规则对齐原版：必须停止练功房修炼才能进战神宫 / 排位失败掉1层 / 1层免排位

**二、魔法花园 · 7步魔法任务链（spec 灵魂玩法，来源 doc88.com + jinchutou.com 攻略）**
- 新增 `garden_data.py` `QUEST_CHAIN` 配置：7步暗香魔杖/五彩之翼任务，精确材料/概率/魅力/经验/周期
  - 第1步 神秘的魔杖（好友花园探索，+60魅力）→ 第2步 绿野精灵（1断枝+99水仙+99牡丹，70%，+1000魅力）
  - 第3步 海洋之心（5断枝+188美人蕉+188荷花，65%，+1200魅力）→ 第4步 宝石玫瑰（50%，+1500魅力）
  - 第5步 黄金玫瑰（45%，+1580魅力）→ 第6步 钻石玫瑰（30%，+1680魅力）→ 第7步 五彩之翼（5花各99朵，100%，+1888魅力+暗香使者称号）
- 新增 3 路由（[garden.py](file:///workspace/app/routers/garden.py)）：任务链主页 / 探索好友花园 / 合成种植
- 魅力值 + 任务进度存 `craft_queue` JSON（迁移为dict结构，兼容旧工坊队列），不改 models
- 新增 [quest.html](file:///workspace/app/templates/garden/quest.html) 模板：7步进度条 + 当前步材料/概率/奖励 + 探索/合成按钮

**三、阳光农场 · 土地等级 + 化肥 + 变异（来源 baike.com 红土地百科 + youxiabc.com + QQ经典农场频道）**
- 新增 `SOIL_GRADES` 配置：普通→红(28级,+10%)→金(60级,+50%)→黑(+100%)土地，含变异概率加成
- 新增 `FERTILIZERS` 配置：普通化肥(加速60s)/有机化肥(加速30s×5次)/高级化肥(加速120s×3次)
- 新增 `VARIATIONS` 配置：爱心(产量×3)/湿润(产量×2)/暗化(售价×2)/冰冻(售价×3)，可叠加
- 新增 3 路由（[farm.py](file:///workspace/app/routers/farm.py)）：土地等级页 / 升级土地 / 施肥
- 修改收获路由：土地等级产量加成 + 变异效果应用 + 收获后变异清空
- `models.py` FarmPlot 新增 `soil_type` + `variation` 字段
- `seed.py` 新增 3 化肥道具（farm_fert_normal/organic/premium）
- 新增 [soil.html](file:///workspace/app/templates/farm/soil.html) 模板：土地等级一览 + 地块升级 + 化肥系统 + 变异效果

**四、美味小镇 · 外卖订单系统（spec 后期升级途径）**
- 新增 2 路由（[town.py](file:///workspace/app/routers/town.py)）：外卖订单页 / 完成订单
- 每日生成3单（随机已学菜品×1-3量，24h时限），完成奖励大额经验+金币，日限10单
- 订单状态存 `daily_counters` JSON（运行时 ALTER TABLE 幂等添加列，不改 models）
- 新增 [delivery.html](file:///workspace/app/templates/town/delivery.html) 模板：3订单卡 + 库存检查 + 完成按钮

**五、平台级 · 限时活动 + 多指标排行（来源原版活动/排行系统）**
- [activity.py](file:///workspace/app/routers/activity.py) 新增 2 路由：限时活动列表 / 领取礼包
  - 4 限时活动：双倍经验周 / 农场收获赛 / 节日登录礼 / 帮派争霸赛
  - 登录礼每日限领1次（OperationLog 去重），奖励88金币+节日礼包
- [ranking.py](file:///workspace/app/routers/ranking.py) 增强为多指标排行：等级榜/农场收获榜/花园等级榜/精武堂战力榜/纵横四海榜
  - 支持 `?metric=farm|garden|martial|sea|level` 选择，Top10 展示
- 新增 [events.html](file:///workspace/app/templates/activity/events.html) + [ranking/index.html](file:///workspace/app/templates/ranking/index.html) 模板

**闭环验证**
- ✅ IMPORT OK（全模块路由注册无冲突）
- ✅ 种子闭环：`[fengyun-v020] 城市+13 技能+30 装备+105 官方系列+48 名器+11 BOSS+14 副本+13 称号+15 成就+21 物品字典+189` + 3 化肥道具
- ✅ 幂等性：重跑全 0
- ✅ 风云三国冒烟测试：ALL SMOKE TESTS PASSED
- ✅ 战神宫：20级门槛 / 3层经验倍率 / 排位挑战逻辑闭环
- ✅ 7步任务链：探索→合成→概率→魅力奖励→暗香使者称号 全流程通过
- ✅ 农场：土地升级→产量加成 / 施肥→加速+变异触发→收获变异效果 全流程通过
- ✅ 外卖订单：生成→库存检查→完成→奖励→日限 全流程通过
- ✅ 活动/排行：4活动展示+领取去重 / 5指标排行切换 全流程通过

**文件变更**
- `app/routers/martial_data.py`：新增 WARSHRINE 配置
- `app/routers/martial.py`：+4 战神宫路由 / `app/templates/martial/warshrine.html`（新）
- `app/routers/garden_data.py`（新）：QUEST_CHAIN 7步配置
- `app/routers/garden.py`：+3 任务链路由 / `app/templates/garden/quest.html`（新）
- `app/routers/farm.py`：SOIL_GRADES/FERTILIZERS/VARIATIONS 配置 + 3 路由 + 收获改造 / `app/templates/farm/soil.html`（新）
- `app/routers/town.py`：+2 外卖订单路由 / `app/templates/town/delivery.html`（新）
- `app/routers/activity.py`：+2 活动路由 / `app/templates/activity/events.html`（新）
- `app/routers/ranking.py`：多指标排行增强 / `app/templates/ranking/index.html`（新）
- `app/models.py`：FarmPlot +soil_type +variation 字段
- `app/seed.py`：+3 化肥道具
- `app/config.py`：版本号 0.2.0 → 0.2.1

---

### v0.2.0 （2026-08-03）— 风云三国路由层上线 + 全网检索补全装备/名器/BOSS 数据

本次将之前未带版本号的 PR 提交（路由层 + 模板层）合并定版为 v0.2.0，并通过全网检索补全 spec 中标注"资料不详"的装备系列/顶级名器/世界 BOSS 数据。风云三国模块从 v0.1.9 的"纯数据层"升级为"可玩路由层"，同时纵横四海/召唤之王/魔法花园三个模块的路由与模板同步扩展。

**一、风云三国路由层（合并未带版本号 PR，fengyun.py 659 行 + 11 模板）**
- 新增 `app/routers/fengyun.py`：风云三国完整路由层（659 行）
  - 角色创建（3 职业 / 3 阵营选择）+ 主页（状态栏/导航/场景）
  - 技能学习/升级（消耗银两+经验，按解锁等级校验）
  - 装备穿戴/卸下（7 部位，职业限定校验，自动重算属性）
  - 商店购买（铁匠铺/药店/杂货店，按城市 NPC 划分）
  - 副本挑战（按阵营×等级段，进入校验，奖励经验+银两+装备掉落）
  - 军团创建/加入/贡献（15 级解锁，虎符道具消耗）
  - 称号切换（前缀+后缀组合，配对激发隐藏属性）
  - 成就查看（3 难度 × 9 类型，六维属性加成）
  - 演武挂机（2-6 小时，周一 10 倍经验，偷师日限）
  - 规则页（职业/阵营/装备/副本/军团/演武/荣誉/称号/成就全系统说明）
- 新增 11 个 fengyun 模板：home/create/skills/equip/shop/dungeons/legion/titles/achievements/training/rules
- 新增 `_smoke_fengyun.py` 冒烟测试（12 GET 路由 + 6 POST 流程全通过）
- `app/main.py`：注册 fengyun 路由（import + routers 列表）
- `app/seed.py`：新增 `icon_fengyun` 图标成就（三国名将·风云三国达到10级）

**二、全网检索补全装备数据（v0.2.0 核心，来源 doc88.com 道具编码表）**
spec 标注"由于游戏停运超10年，70级以上装备/饰品/套装效果资料不详"，本次全网检索补全：

- **官方 7 大装备系列**（`EQUIP_SERIES`，48 件，每系列 7 件套 = 4 职业武器 + 衣 + 盾 + 靴）
  - 百战系列（白·1级，普通）：百战长枪/短刀/羽扇/木弓/布衫/盾/靴
  - 烈风系列（蓝·1级，卓越低档）：烈风戟/剑/扇/长弓/披衣/盾/靴
  - 凰霞系列（绿·16级，精良）：凰霞长戟/刀/折扇/弓/护甲/盾/靴
  - 龙翔系列（蓝·30级，卓越）：龙翔枪/刀/羽扇/金弓/披风/盾/靴
  - 霆震系列（紫·50级，史诗）：霆震枪/剑/骨扇/弓/披风/金盾/靴
  - 霆震·精系列（紫+·60级，史诗强化版，属性 +45%）：霆震枪·精/剑·精/骨扇·精/弓·精/披风·精/金盾·精/靴·精
  - 幻灵系列（橙·70级，神器）：幻灵枪/刀/羽扇/弓/披风/盾
  - 属性数值全部对齐 doc88.com 道具编码表精确数值（如霆震枪 atk=690，幻灵枪 atk=1340）

- **顶级名器 11 件**（`NAMED_WEAPONS`，spec 明示十大名剑 + 三国名器）
  - 十大名剑：鱼肠剑（刺客神器·50级）/七星龙渊剑（术士史诗·60级）/巨阙剑/承影剑/七圣刀（顶级·60级·价值约500元）
  - 三国名器：倚天剑（太和山）/丈八蛇矛（桃园）/方天画戟（下邳）/青龙偃月刀（泰山）/龙胆枪（80级·张让掉落）/华蜓（100级·周瑜掉落）

- **顶级 BOSS/神兽 14 只**（`WORLD_BOSSES`，spec 明示龙之九子+烛龙+四大神兽）
  - 龙之九子：赑屃/鸱吻/蒲牢/狴犴/饕餮/蚣蝮/睚眦/狻猊/椒图（70-78级，掉落神器）
  - 烛龙（90级，钟山之神，神兽级 BOSS）
  - 四大神兽：青龙/白虎/朱雀/玄武（85级，掉落神器）

**三、纵横四海路由扩展（合并未带版本号 PR）**
- `app/routers/sea.py` 扩展（+358 行）：新增 9 个子页面路由
- 新增 9 个 sea 模板：cards/dungeons/equipsets/gems/holymarks/mainquests/pets/ships/trade
- 覆盖 spec 纵横四海全系统：卡片/副本/装备套装/宝石/圣痕/主线任务/宠物/船只/贸易

**四、召唤之王路由扩展（合并未带版本号 PR）**
- `app/routers/summon.py` 扩展（+726 行）：新增 8 个子页面路由
- 新增 8 个 summon 模板：alliance/arena/battlefield/bone/mentor/soul/spirit/tower
- `app/routers/summon_data.py`：IMPLEMENTED_METRICS 新增 8 个日常指标
- `app/models.py` SummonState 新增 6 字段：bone_levels/souls/spirits/alliance_skills/tower_floors/mentor_count
- 覆盖 spec 召唤之王全系统：联盟/竞技场/战场/炼骨/师徒/战灵/灵体/通天塔

**五、魔法花园路由扩展（合并未带版本号 PR）**
- `app/routers/garden.py` 扩展（+406 行）：新增装饰系统/合成工坊队列
- 新增 `app/templates/garden/deco.html`：装饰放置页（环境值/套装系统）
- `app/models.py` GardenState 新增 4 字段：decorations/env_score/craft_queue/craft_slots
- `app/seed.py`：新增 10 个花园装饰物品（喷泉/池塘/路灯/花拱门/长椅/雕塑/栅栏/景观树/鸟笼/风车）
- 3 套装效果：水景套装(喷泉+池塘,+10) / 灯饰套装(路灯+花拱门,+15) / 雕塑套装(雕塑+花拱门+长椅,+20)

**闭环验证**
- ✅ 路由闭环：`python -c "from app.main import app"` IMPORT OK；fengyun 路由已注册
- ✅ 种子闭环：`[fengyun-v020] 城市+13 技能+30 装备+105 官方系列+48 名器+11 BOSS+14 副本+13 称号+15 成就+21 物品字典+189`
- ✅ 幂等性：重跑全 0（城市+0/技能+0/装备+0/官方系列+0/名器+0/BOSS+0/副本+0/称号+0/成就+0/物品字典+0）
- ✅ 冒烟测试：`_smoke_fengyun.py` ALL SMOKE TESTS PASSED（12 GET + 6 POST 全通过）
- ✅ 装备数值闭环：官方系列属性对齐 doc88.com 道具编码表（如霆震枪 atk=690 / 幻灵枪 atk=1340 / 龙翔披风 def=660）
- ✅ BOSS 闭环：14 只世界 BOSS 全部落 Item 字典（fy_boss_token_*），可被战斗系统引用
- ✅ 架构闭环：fengyun 路由层与数据层分离（fengyun.py 路由 / fengyun_data.py 静态配置 / seed_fengyun.py 生成器）

**文件变更**
- 新增 `app/routers/fengyun.py`（路由层，659 行）
- 新增 11 个 `app/templates/fengyun/*.html` 模板
- 新增 `_smoke_fengyun.py`（冒烟测试）
- 新增 9 个 `app/templates/sea/*.html` + 8 个 `app/templates/summon/*.html` + `app/templates/garden/deco.html`
- `app/routers/fengyun_data.py`：新增 EQUIP_SERIES(48件) / NAMED_WEAPONS(11件) / WORLD_BOSSES(14只)
- `app/routers/{garden,sea,summon,summon_data}.py`：路由扩展（合并未带版本号 PR）
- `app/models.py`：GardenState +4字段 / SummonState +6字段
- `app/seed_fengyun.py`：新增官方系列/名器/BOSS 种子逻辑（v0.2.0 全网检索补全）
- `app/seed.py`：新增 10 花园装饰物品 + icon_fengyun 图标
- `app/main.py`：注册 fengyun 路由
- `app/config.py`：版本号 0.1.9 → 0.2.0

---

### v0.1.9 （2026-08-03）— 风云三国模块上线（spec 三国 MMORPG 全系统资料库）

按用户提供的《QQ风云三国全系统资料》（约 2010 年上线，2015-06-20 随 QQ家园关停）落地第七个游戏模块「风云三国」。题材为古典小说《三国演义》，玩家扮演现代人穿越到三国时期。本次按 spec 落地三职业/三阵营/副本/军团/演武/荣誉/称号/成就/魔钻全系统资料库，新增独立静态配置文件 `fengyun_data.py`（与 martial_data.py / sea_data.py 对齐架构）。

**数据模型层（models.py 新增 8 表）**
- `FengyunState`（玩家状态：职业/阵营/等级/银两/荣誉/六维属性/当前城市/演武结束时间）
- `FengyunSkill`（技能字典：key/名称/职业/类型/解锁等级/银两消耗/经验消耗/效果）
- `FengyunUserSkill`（玩家已学技能：user_id + skill_key 唯一）
- `FengyunEquip`（装备字典：品质/部位/职业限定/等级需求/攻防HP加成/价格）
- `FengyunUserEquip`（玩家装备实例：equip_key/部位/是否穿戴）
- `FengyunDungeon`（副本定义：阵营/等级区间/入口城市/NPC/经验银两奖励）
- `FengyunLegion` + `FengyunLegionMember`（军团：5 级，最大 100 人，贡献值升级）
- `FengyunTitle`（称号字典：前缀/后缀/配对，品级 + HP/ATK/DEF 加成）
- `FengyunAchievement`（成就字典：3 难度 × 9 类型，六维属性加成）
- `FengyunCity`（城市字典：阵营归属/简介）

**静态配置文件 routers/fengyun_data.py（新增，与其他模块对齐）**
- `CLASSES`：3 职业（战士高防 / 刺客高外功 / 术士高内功），含基础属性 + 每级成长
- `FACTIONS`：3 阵营（魏/蜀/吴，跨阵营 PK 获荣誉）
- `SKILLS`：30 技能（3 职业 × 10，4 类型 active/passive/auxiliary/status）
- `EQUIP_QUALITIES` / `EQUIP_SLOTS`：5 品质 × 7 部位，含品质系数 + 部位主属性
- `gen_equip_stats()` / `gen_equip_price()`：按 spec 价值体系（神器 = 2×史诗 = 4×卓越）生成装备属性与交易参考价
- `DUNGEONS`：13 副本（蜀4 + 魏4 + 吴3 + 终极2，覆盖 16-60 级，含 spec 明示威震逍遥津 28000 经验/1300 银两）
- `LEGION_LEVELS`：5 级军团（0→100000 贡献，20→100 人，虎符升级道具）
- `honor_for_kill()`：荣誉计算（高 15 / 低 10 级内 10 / 低 10-20 级 5 / 低 20+ 级 0）
- `TITLES` + `TITLE_PAIR_RULES`：15 称号（6 前缀 + 6 后缀 + 3 配对激发隐藏属性）
- `ACHIEVEMENTS`：21 成就（3 难度 × 9 类型：成长/任务/杀怪/PK/山庄/社交/副将/道具/装备）
- `CITIES`：13 城市（蜀4/魏4/吴3/中立2，含副本入口 NPC 对齐）
- `MOZHUAN_PRIVILEGES`：魔钻 6 大特权（每日礼包/经验祝福/商城八折/免费传送/专属称号/身份展示）
- `TRAINING_*` / `STEAL_*`：演武封顶 6 小时 + 周一 10 倍经验 + 偷师日限规则
- `PK_MODES` / `QUEST_TYPES`：3 种 PK 模式 + 4 大任务类型
- `exp_needed()` 等级经验公式（60 级上限）

**生成器 seed_fengyun.py（幂等 / 可断点续跑）**
- **13 城市**（spec 三区域 + 中立洛阳）：建宁/永安/成都/江陵 + 北平中区/晋阳西区/许昌中区/下邳北区 + 吴郡/柴桑/建业 + 洛阳/洛阳南区
- **30 技能**（3 职业 × 10，4 类型）：战士(盾墙/破甲斩/怒吼…定鼎天下) / 刺客(影遁/背刺/毒刃…九幽灭魂) / 术士(内功心法/火球术…九天玄雷)
- **105 装备**（5 品质 × 7 部位 × 3 等级档 = 105 件）：普通→精良→卓越→史诗→神器 × 头/手/衣/腿/鞋/裤子/饰品 × 10/30/50 级档
  - 同步落 Item 字典 `fy_eq_*`（105 条，可被背包/商店引用）
  - 交易参考价对齐 spec：神器价 = 2×史诗价 = 4×卓越价（同等级）
- **13 副本**（按阵营 × 等级段）：
  - 蜀：火烧博望(16-25) / 千里单骑(26-35) / 桃园结义(36-45) / 大战长坂(46-55)
  - 魏：计定辽东(16-25) / 威震逍遥津(26-35, 28000 经验/1300 银两) / 曹丕选妃(36-45) / 火烧乌巢(46-55)
  - 吴：白衣渡江(16-25) / 火烧连营(26-35) / 江东霸王(36-45)
  - 终极：七擒孟获(56-60) / 智斗马超(56-60)，三阵营通用
- **5 级军团虎符道具**（一级~五级军团虎符，军团创建/升级消耗）
- **15 称号**（6 前缀 + 6 后缀 + 3 配对隐藏）：霸/神/龙/武/天/皇 + 王/尊/帝/神/侯/仙 + 霸王/神仙/天子配对激发隐藏属性
- **21 成就**（3 难度 × 9 类型）：成长/任务/杀怪/PK/山庄/社交/副将/道具/装备，完成提升六维属性
- **6 消耗品**：双倍经验卡/回血丹/回蓝丹/缘分值包/银两包/魔钻月卡
- 全部物品同步落 Item 字典（module_key=fengyun，共 116 条），可被背包/商店引用

**闭环验证**
- ✅ 城市闭环：fengyun_cities 13 条；副本 city 字段全部命中城市 key（建宁/永安/成都/江陵/北平中区/晋阳西区/许昌中区/下邳北区/吴郡/柴桑/建业/洛阳/洛阳南区）
- ✅ 技能闭环：fengyun_skills 30 条（战士10/刺客10/术士10）；4 类型 active/passive/auxiliary/status 全覆盖
- ✅ 装备闭环：fengyun_equips 105 条（5 品质 × 7 部位 × 3 档）；价格对齐 spec（神器 = 2×史诗 = 4×卓越）；同步落 Item 字典 105 条
- ✅ 副本闭环：fengyun_dungeons 13 条；威震逍遥津奖励 = 28000 经验 + 1300 银两（spec 明示）
- ✅ 称号闭环：fengyun_titles 15 条（6 前缀 + 6 后缀 + 3 配对）；配对规则 3 条（霸+王→霸王 / 神+仙→神仙 / 天+帝→天子）
- ✅ 成就闭环：fengyun_achievements 21 条（3 难度 × 9 类型）；六维属性加成（HP/MP/ATK/DEF/闪避/暴击）
- ✅ 物品字典闭环：fengyun 模块 Item 116 条（105 装备 + 5 虎符 + 6 消耗品）
- ✅ 幂等性：重跑 stats 全 0（fengyun-v019 城市+0/技能+0/装备+0/副本+0/称号+0/成就+0/物品字典+0）
- ✅ 架构对齐：fengyun_data.py 与 martial_data.py / sea_data.py / summon_data.py 同级，风云三国模块静态配置独立

**文件变更**
- 新增 `app/routers/fengyun_data.py`（静态配置，~390 行）
- 新增 `app/seed_fengyun.py`（生成器，~157 行）
- `app/models.py`：新增 8 表（FengyunState/Skill/UserSkill/Equip/UserEquip/Dungeon/Legion/LegionMember/Title/Achievement/City）
- `app/seed.py`：注册 fengyun 模块 + 接入 `seed_fengyun(db)`
- `app/config.py`：版本号 0.1.8 → 0.1.9

---

### v0.1.8 （2026-08-03）— 纵横四海补全（spec 船只/主线任务/城市特产/宠物技能/补全城市/sea_data.py静态配置）

按 spec《纵横四海全系统完整目录 + 世界地图与城市》补齐 v0.1.7 前完全缺失的 4 类系统数据，并新增 Sea 模块独立静态配置文件 `sea_data.py`（与 martial_data.py / summon_data.py 对齐架构）。v0.1.7 前 Sea 模块有 0 艘船、0 条主线任务链、0 个宠物技能、0 个城市特产；本次按 spec 落地全量数据。

**数据模型层（models.py 新增 4 表）**
- `SeaShip`（船只字典：key/名称/购买地点/价格/货币/载重/消耗每百海里）
- `SeaMainQuest`（主线任务链：key/名称/环数/主要奖励/顺序）
- `SeaCitySpecialty`（城市贸易特产：city_key/城市名/区域/特产JSON列表）
- `SeaPetSkill`（宠物技能字典：key/名称/效果/T0-T1-T2 分级）

**静态配置文件 routers/sea_data.py（新增，与其他模块对齐）**
- `SHIPS`：14 艘船（轻木帆船 1000 铜 → 明永乐大帆船 2 金贝）
- `MAIN_QUESTS`：12 条主线任务链（美味任务 10 环 → 封印迷阵 450 环，共 4000+ 环）
- `PET_SKILLS`：23 种宠物技能（T0:9 / T1:3 / T2:11）
- `CITY_SPECIALTIES`：34 城市特产（5 区域：地中海9/北海6/非洲7/印度洋4/东亚8）
- `REGIONS` / `CURRENCIES` / `BATTLE_MELEE_ROUND` / `TRADE_ROUTE_RECOMMEND` 等常量
- `exp_needed()` 等级经验公式（199 级上限）

**补全生成器 seed_sea_v018.py（幂等）**
- **14 艘船**（spec 船只系统，v0.1.7 前 0 艘）：
  - 轻木帆船(威尼斯/1000铜/载35) → 明永乐大帆船(商城/2金贝/载150)
  - 同步落 Item 字典 `sea_ship_*`（14 条，可被背包/商店引用）
- **12 条主线任务链**（spec 主线任务系统，v0.1.7 前 0 条）：
  - 美味任务(10环) → 寻裔之路(30) → 聚宝盆(100) → 妖气长安(350) → 地魔宝藏(550) → 蒂拉之剑(361) → 天魔传奇(319) → 玉历宝钞(370) → 釜底抽薪(370) → 天魔归来(458) → 天工神剪(251) → 封印迷阵(450)
  - 奖励含地魔/天魔套装、龙珠、设计图等
- **23 种宠物技能**（spec 宠物技能，v0.1.7 前 0 种）：
  - T0(9): 威压/怒吼/迷惑/剥夺/无敌/卸刃/卸甲/卸配/免卸
  - T1(3): 封血/嗜血/净化
  - T2(11): 封毒/封麻/封虚/圣光/振幅/清风/御身/利刃/谩骂/身虚/金钟
- **34 城市贸易特产**（spec 贸易跑商，v0.1.7 前 0 个）：
  - 5 区域 34 城市：地中海(威尼斯葡萄酒/雅典绘画…)、北海(伦敦毛织品/哥本哈根玻璃…)、非洲(圣乔治象牙/卢旺达琥珀…)、印度洋(亚丁咖啡/锡兰可可…)、东亚(长安小麦/泉州陶瓷器…)
- **16 个补全城市**（spec 世界地图，v0.1.7 前缺失）：
  - 地中海补 6：马赛/伊斯坦堡/突尼斯/亚历山大/阿尔及尔/拉古扎
  - 北海补 3：南特/汉堡/奥斯陆
  - 非洲补 2：卢旺达/马达加斯加
  - 印度洋补 1：孟买
  - 东亚补 4：大阪/杭州/广州/马六甲
  - 城市总数 23 → 39（含 5 个平台 demo 城市）

**闭环验证**
- ✅ 船只闭环：sea_ships 14 条 + sea 模块 ship 类型 Item 14 条；轻木帆船→明永乐大帆船全覆盖
- ✅ 任务闭环：sea_main_quests 12 条；环数合计 3659 环（spec 称 4000+ 环，差异来自部分任务环数估算）
- ✅ 技能闭环：sea_pet_skills 23 条（T0:9/T1:3/T2:11）；威压→金钟全覆盖
- ✅ 特产闭环：sea_city_specialties 34 条（地中海9/北海6/非洲7/印度洋4/东亚8）；里斯本正确归入地中海
- ✅ 城市闭环：sea_cities 39 条（34 spec + 5 平台 demo）；里斯本区域已修正
- ✅ 幂等性：重跑 stats 全 0（sea-v018 船只+0/主线任务+0/宠物技能+0/城市特产+0/补全城市+0）
- ✅ 架构对齐：sea_data.py 与 martial_data.py / summon_data.py 同级，Sea 模块不再缺静态配置

**文件变更**
- 新增 `app/routers/sea_data.py`（静态配置，~177 行）
- 新增 `app/seed_sea_v018.py`（补全生成器，~118 行）
- `app/models.py`：新增 4 表（SeaShip/SeaMainQuest/SeaCitySpecialty/SeaPetSkill）
- `app/seed.py`：接入 `seed_sea_v018(db)`
- `app/config.py`：版本号 0.1.7 → 0.1.8

---

### v0.1.7 （2026-08-03）— 四模块数据补全（阳光牧场50作物/美味小镇233食材/精武堂15手机版技能）

按 spec《阳光牧场作物数据表》《美味小镇物品资料总览》《精武堂手机版技能》补齐三模块丢失数据。v0.1.6 前农场仅 2 作物、小镇仅 14 食材、精武堂仅 10 技能；本次按 spec 落地全量数据并扩展 `Crop` 模型字段以承接 spec 多维信息。

**数据模型层（models.py 扩展 1 表）**
- `Crop`（作物字典）扩展 5 个字段（向后兼容，旧作物默认值即可）：
  - `level_req` 解锁等级 / `crop_type` 一季·多季·鲜花 / `min_yield` 最低产量 / `regrow_seconds` 再熟间隔(秒，0=一季) / `sell_price` 果实售价
  - 旧 2 作物（萝卜/番茄）保留，仅补全新字段；spec 西红柿自动合并到已有 tomato 记录

**阳光牧场作物生成器 seed_farm_large.py（幂等）**
- 按 spec《阳光牧场作物数据表》落地 **50 种作物**（v0.1.6 前仅 2 种）：
  - 等级 0~54 全覆盖（竹子/胡萝卜→黑加仑/菠萝蜜/薄荷）
  - `grow_seconds` = 成熟小时 × 3600；`regrow_seconds` = 再熟小时 × 3600（0=一季）
  - `crop_type`：有再熟小时→"多季"，否则→"一季"（一季 10 / 多季 41）
  - 同步落 Item 字典：种子 `farm_seed_*` + 收获物 `farm_*`（共 100 条，可被背包/商店引用）

**美味小镇食材生成器 seed_town_large.py（幂等）**
- 按 spec《美味小镇物品资料总览》落地 **233 食材体系**（v0.1.6 前仅 14 种）：
  - 一级 22 / 二级 65 / 三级 50 / 四级 30 / 五级 30 / 六级神秘 10 / 六级其他(西式) 10 / 万能 6 = 223
  - 售价随级别递增（1级5/2级10/3级20/4级40/5级80/6级150）
  - 六级神秘食材：神秘九天翅/神秘九孔鲍/神秘黄金肚/神秘高山虫/神秘金丝盏/神秘龙涎香/神秘金蟾菇/神秘雪川雏/神秘金钱鳘/神秘宝田犊
  - 六级西式食材：橄榄油/三文鱼/黑胡椒/迷迭香/意大利面/罗勒/百里香/牛至/月桂叶/藏红花丝
  - 万能食材 1~6 级（v0.1.1 已有 6 级，本次补 1-5 级，已存在则跳过）
  - 全部食材落 Item 字典 `town_ing_lv{level}_{idx}`，可被菜谱 ingredients JSON 引用

**精武堂手机版 15 技能（routers/martial_data.py）**
- 按 spec《精武堂手机版 15 技能》补齐 SKM_11~SKM_25（v0.1.6 前 SKM_01~SKM_10）：
  - 攻击类 5：剑影留痕/御剑通灵/剑气凌风/人剑合一/潇湘剑雨
  - 辅助类 5（被动增益）：妙手回春(气血+30/级)/神清气朗(内息+20/级)/金钟护体(外防+8/级)/武神附体(外攻+10/级)/五灵归宗(全属性+5/级)
  - 特殊类 5：吸星功法/三清缚影/斗转星移/回风扫叶/天罗地网
  - `skill_passive_bonus()` 扩展支持 SKM_16~SKM_20 被动加成计算

**闭环验证**
- ✅ 作物闭环：farm_crops 共 51 条（50 spec + 萝卜），一季 10 / 多季 41；seed_item_key/harvest_item_key 均落 Item 字典（farm 模块 102 条物品）
- ✅ 食材闭环：town_ing_lv* 共 217 条 + town_wild_ing* 6 条；全部可被菜谱 ingredients JSON 引用
- ✅ 技能闭环：SKILLS 共 25 条；skill_passive_bonus 支持 SKM_05~SKM_20 全部被动；五灵归宗 lv5 = 全属性+25
- ✅ 幂等性：以 key 存在性判断，重跑 stats 全 0（farm-large +0 / town-large +0）
- ✅ 向后兼容：Crop 新字段均有 default，旧代码不报错；旧萝卜/番茄记录自动补全新字段

**文件变更**
- 新增 `app/seed_farm_large.py`（50 作物生成器，~115 行）
- 新增 `app/seed_town_large.py`（233 食材生成器，~107 行）
- `app/models.py`：`Crop` 表扩展 5 字段（level_req/crop_type/min_yield/regrow_seconds/sell_price）
- `app/routers/martial_data.py`：SKILLS 字典 +15 条（SKM_11~SKM_25），skill_passive_bonus +5 分支
- `app/seed.py`：接入 `seed_farm_large(db)` + `seed_town_large(db)`
- `app/config.py`：版本号 0.1.6 → 0.1.7

---

### v0.1.6 （2026-08-03）— 纵横四海装备件名补全（spec 全部装备件名清单）

按《纵横四海全部装备件名》补齐装备部件级件名。v0.1.5 的 `SeaEquipSet` 仅存套装级信息（套装名/等级/获取方式/件数），无具体部件名；本次新增 `SeaEquipPiece` 表，落地 spec 整理的 19 个官方确认件名 + 按命名规律推测的 ~55 个件名，使装备体系从"套装名"细化到"部件件名"。

**数据模型层（models.py 新增 1 表）**
- `SeaEquipPiece`（装备部件件名：件名 / 所属套装 key / 部位 / 等级要求 / 获取方式 / confirmed 确认度）
  - `set_key` 引用 `SeaEquipSet.key`（散件如魑魅魍魉/冷石弯刀/流失岁月 set_key 为空）
  - `slot` 部位：武器/副手/头盔/衣服/腰带/鞋子/配饰
  - `confirmed`：True=官方文本确认件名，False=按命名规律推测

**装备件名生成器 seed_sea_equips.py（幂等）**
- **官方确认件名 19 个**（confirmed=True，来自主线文本/百科）：
  - 天魔防具四件：天魔荆棘皇冠(头)/天魔玄夜战铠(衣)/天魔碧玉束腰(腰)/天魔风沙之靴(脚)
  - 天魔武器：天魔轮回权杖(140级)
  - 地魔双环：地魔指环(左)/地魔指环(右)（80级副手）
  - 地魔配饰/武器：地魔回魂之恋(配饰)/地魔飓风斩(武器)/地魔恋战(110级)
  - 蒂拉之剑(武器)/海誓戒(135级配饰)
  - 强力散件：往事如风(100级配饰)/生命的意义(128级武器)/复仇(159级武器)
  - 主线/牛头山散件：魑魅魍魉(戒指)/冷石弯刀(武器)/流失岁月(配饰)
  - 奔月武器：月剑(30级)
- **命名规律推测件名 ~55 个**（confirmed=False，按 spec 归纳的命名后缀生成）：
  - 命名规律：武器→之剑 / 头盔→战盔 / 衣服→战甲 / 腰带→束腰 / 鞋子→战靴 / 配饰→戒
  - 覆盖套装：武士/哥伦布/霸者/奔月(防具)/麦哲伦/七海/海盗王/蒂拉(防具)/地魔(防具)/虚无/烈焰/四象/玉兔
  - 纯防具套装（虚无/烈焰/四象）仅生成 4 防具件；标准套装生成武器+4防具；玉兔加配饰

**闭环验证**
- ✅ 套装关联：confirmed 与 guessed 件名的 `set_key` 全部命中 `SeaEquipSet.key`（散件 set_key 为空）
- ✅ 部位覆盖：7 部位（武器/副手/头盔/衣服/腰带/鞋子/配饰）均有件名落地
- ✅ 确认度区分：19 件 confirmed=True / ~55 件 confirmed=False，可按确认度筛选
- ✅ 幂等性：以 key 存在性判断，重跑 stats 全 0

**文件变更**
- 新增 `app/seed_sea_equips.py`（件名生成器，~140 行）
- `app/models.py`：新增 `SeaEquipPiece` 表
- `app/seed.py`：接入 `seed_sea_equips(db)`
- `app/config.py`：版本号 0.1.5 → 0.1.6

---

### v0.1.5 （2026-08-03）— 纵横四海大全级资料库（spec 32系统/20城市/24套装/60宝石/21卡片/40圣痕/60宠物/12坐骑/8羽翼/9随从/10副本）

按《QQ家园《纵横四海》游戏资料大全》补齐 32 个系统的大全级资料库，使模块从"简版航线 demo"升级为完整 RPG 体验。核心新增：

**数据模型层（models.py 新增 9 表）**
- `SeaDungeon`（副本定义：难度/等级要求/经验/掉落/开放日，JSON 字段存储五档难度对应数据）
- `SeaPet`（宠物：白/紫/橙品质，攻/防/敏/体四维 + 技能标签 + 获取来源）
- `SeaMount`（坐骑：等级要求 + 属性加成，flat 固定值 / pct 百分比两种类型 + 阵营分类）
- `SeaWing`（羽翼：体魄/吸血/连击/铁壁效果，JSON effects）
- `SeaFollower`（随从：海贼王角色 + 传说技能名 + 技能描述 + 品质）
- `SeaGem`（宝石：5 档 tier + 效果 + 可镶嵌部位 JSON）
- `SeaCard`（卡片：附魔部位 + 普通/精致双效果 + 掉落来源）
- `SeaHolyMark`（圣痕：10 种 × 4 品质 白/绿/蓝/紫）
- `SeaEquipSet`（装备套装：等级要求 + 获取方式 + 件数）

**超大数据生成器 seed_sea_large.py（幂等 / 可断点续跑）**
- **城市 20**：spec 主要城市表全覆盖（地中海/北海/非洲/亚洲/其他海域），含威尼斯/伦敦/开普敦/泉州等关键城市，并补齐 19 条相邻双向航线
- **装备套装 24**：spec 装备套装路线表全系列（武士/哥伦布/奔月/霸者/地魔/天魔/玉兔等）
- **宝石 60**：12 种 × 5 档（碎片/小/中/大/完美），覆盖绿宝石/蛇牙/鲸须/龙珠/猫眼石/玄铁石/琥珀石/龙泉宝石等，全部同步落 Item 字典
- **卡片 21**：spec 卡片列表全量（莱温特/莫迪奥拉/狼人/飞翼兽/贪婪哥布林等）
- **圣痕 40**：10 种 × 4 品质（白/绿/蓝/紫）
- **宠物 60**：spec 基础宠物 + 精英档 + 12 变种，覆盖白/紫/橙品质
- **坐骑 12**：暴风狮鹫/炽焰战蝎/暗月战狼/魔法飞毯/机甲蝰蛇等
- **羽翼 8**：自由之翼/魔龙之翼/死亡之翼/公海之翼等
- **随从 9**：路飞/索隆/香吉士/布鲁克/福兰奇/罗宾/娜美/乔巴/乌索普全角色 + 传说技能
- **副本 10**：威尼斯探险/温莎庄园/贝河/五行阵/巨鲸/诸葛/基德的宝藏/天魔之乱/情侣/圣乔治
- **消耗品 40+**：药品/经验道具/宠物道具/装备材料/活动道具，全部落 Item 字典可被背包引用

**闭环验证**
- ✅ 城市 → 副本：`entry_city` 引用城市 key，开放日符合 spec（周一/六/日等）
- ✅ 副本 drops：统一引用装备套装定义 key（`set_*` meta 引用）或 Item 字典 key（`sea_*`），全部可解析
- ✅ 宝石/卡片：均同步落 Item 字典（宝石 60 / 卡片 21），可被背包引用
- ✅ 宠物/坐骑/羽翼/随从：品质/属性/技能符合 spec 描述
- ✅ 幂等性：以 key 存在性判断，重跑 stats 全 0

**文件变更**
- 新增 `app/seed_sea_large.py`（生成器，~410 行）
- `app/models.py`：新增 9 张 Sea 表
- `app/seed.py`：接入 `seed_sea_large(db)`
- `app/config.py`：版本号 0.1.4 → 0.1.5

**待办（下一版本）**
- 材料掉落表（副本 drops 当前仅存 key，未挂掉落概率/数量）
- 副本实战入口（当前仅字典存在，未接入 sea 路由的副本挑战流程）

---

### v0.1.4 （2026-08-03）— 魔法花园大全级资料库（spec 物品体系/订单系统分册落地）

按《QQ家园·魔法花园 新版总纲 + 四大分册》补齐"大全级"资料库样例规模，使体系可无限扩展并闭环跑通。

**超大数据生成器 `app/seed_garden_large.py`（幂等 / 可断点续跑）**
- 复现：v0.1.3 仅落了公式与少量手写内容（8 花种 / 5 配方），spec 要求"可无限扩展的资料库结构 + 样例规模清单确保闭环跑通"
- 新增 `GardenOrderTemplate` 表（spec `order_templates` / 订单池按等级分层 `pool(L)`）
- 按统一价值体系（`value_coin = max(sell,1)*4`，对齐 `item_value_coin` 的 `grow_seconds=0` 分支）批量生成：
  - **作物 520**（8 tier × 65：`GardenBloom`+`GardenSeed`+`GardenAlbumEntry`+`Item` 各 520 同步）
    - tier→稀有度：T1-2 普通 / T3-4 稀有 / T5-6 史诗 / T7-8 传说
    - tier→解锁等级：1/6/11/16/21/31/46/66（对齐段位起始等级）
    - tier→成长时长：60/90/150/240/360/540/780/1080 秒
  - **材料 1024**（8 tier × 128，`Item` 字典 `type=material`）
  - **配方 1536**（`GardenRecipe`，target tier 2-8 循环填满；成功率 `92-(tier-1)*8`；高阶 tier≥6 强制操作锁）
    - 输入：2-3 个同阶/低阶材料 + 50% 概率 1 个低阶花朵；产出：对应 tier 花种
  - **订单模板 3072**（`GardenOrderTemplate`，按 tier 权重 20/18/16/14/12/10/6/4 分配；type 比例 normal60%/premium28%/limited12%）
    - 闭环：需求 item 70% 取花朵（收获产出）/ 30% 取材料（工坊产出），保证 plant→harvest→deliver 主路径
    - `level_min` = tier 解锁等级，`level_max` = 99（spec `pool(L)` 分层）
- 幂等：`need = TARGET - current` 填至目标；已达标则 0 新增（重跑验证通过）

**订单实例化改造 `app/routers/garden.py::_ensure_orders`**
- 优先从模板池实例化（按 `level_min <= 玩家等级 <= level_max` 过滤 + weight 加权抽取）
- 奖励仍走 `_calc_order_reward` 单一真值源（spec 公式即时计算，模板不存死奖励）
- 无模板时回退原动态生成（玩家已点亮花谱花朵池，新手 Lv1 野花保底）

**文件变更**
- 新增 `app/seed_garden_large.py`（生成器，~280 行）
- `app/models.py`：新增 `GardenOrderTemplate` 表
- `app/seed.py`：接入 `seed_garden_large(db)`
- `app/routers/garden.py`：`_ensure_orders` 模板池实例化
- `app/config.py`：版本号 0.1.3 → 0.1.4

**端到端验证**
- ✅ 数据量：bloom 531 / seed 528 / album 531 / material 2158 / recipe 1536 / order_template 3072
- ✅ 闭环：订单模板需求 item 缺失=0；配方材料 item 缺失=0；配方产出 seed 缺失=0
- ✅ 幂等：重跑 stats 全 0
- ✅ 订单实例化：`_ensure_orders` 从模板生成 4-6 单，需求 item 全部存在于字典
- ✅ 交付闭环：给 demo T1 花朵+材料 → 找到可交付订单 → 扣材料发奖励 → `GardenOrderLog` 记录 → API `active_orders`/`total_order_coin` 更新
- ✅ 页面：`/games/garden/orders` 渲染订单卡（200）；`/api/garden/state` 返回 active_orders=6

**待办（下一版本）**
- 材料掉落表 `drops`（当前 1024 材料仅字典存在，无 drop 来源；spec `drops` 表族）
- 工坊制作队列（slot 工作台并行，替代当前即时合成）
- 环境值 / 装扮系统（env_score + deco + set_bonus + 边际递减 buff）

---

### v0.1.3 （2026-08-03）— 魔法花园对齐新版总纲（订单/品质/价值/加成）

按用户提供的《QQ家园·魔法花园 新版总纲 + 四大分册》（系统总纲 / 页面结构 / 公式规则 / 物品体系），对照现有 garden 模块做验证与补齐。核心差距：原模块只有"种→收→合成→点亮"单线，缺少 spec 强调的**订单交易（经济主引擎）**、**品质系统（核心长期追求）**、**统一加成公式（必须写死）**、**物品价值体系（定价底座）**。本次补齐这 4 项，闭合"产出 → 订单消费 → 金币/经验回收"主循环；环境值/装扮与工坊制作队列记入待办（下一版本）。

**订单交易系统（spec：经济主引擎 / 主要回收池）**
- 复现：原模块收获后只有"卖/合成/点亮花谱"三条出路，spec 要求"产出必须有去处"，订单是主要回收池与金币经验主来源
- 新增 `GardenOrder`（订单实例）+ `GardenOrderLog`（交付历史）2 张表
- 订单类型：普通单(margin 1.15) / 加价单(1.45) / 限时单(1.75，8 小时截止)
- 需求生成：从玩家已点亮花谱的花朵池抽取 1-3 种，每种 1-3 个，附带品质要求（新手用 Lv1 野花保底）
- 奖励公式（spec 原文落地）：
  - `V_req = Σ(qty_i × value_coin(item_i) × Q_value_mul(Q_req_i))`
  - `R_coin = floor(V_req × margin(type) × urgency_mul × difficulty_mul)`
  - `R_exp = floor(R_coin^0.6 × exp_scale(L))`（p<1 避免金币单一驱动升级）
- 刷新：每日 2 次免费，之后 `cost = 50 × 1.5^n`（防刷递增）；同时进行上限 6 单
- 路由：`/orders`（订单板）/ `/orders/deliver/{id}`（交付）/ `/orders/reroll`（刷新）/ `/orders/history`（历史）

**统一加成公式（spec：必须写死）**
- 复现：原模块各处加成自写一套口径，spec 强制 `final = base × (1 + Σadd) × Π(1 + mul_i)` + cap 上限 + 边际递减
- 新增 `apply_buff(base, add_terms, mul_terms, cap)` 工具函数，统一所有加成叠加口径
- 关键项必须有 cap（例：成长减免最多 80%）；长期加成边际递减

**品质系统（spec：核心长期追求）**
- 复现：原模块只有稀有度（普通/稀有/史诗/传说）单轴，spec 要求品质（N/G/R/E/L）作为独立轴 + 权重抽取
- 新增 `QUALITY_TIERS`（5 档）+ `QUALITY_WEIGHT_BASE`（基础权重 70/20/7/2.5/0.5）
- `roll_quality(quality_buff, env_score)` 权重抽取：`W_q = W_base × (1 + buff) × env_quality_mul`
- `env_quality_mul` 边际递减：`1 + 0.3×(1 - exp(-env_score/50))`（spec 原文）
- `Q_VALUE_MUL`：品质对订单价值倍率 N1.0 / G1.1 / R1.25 / E1.45 / L1.7（订单需求按品质加价）

**物品价值体系（spec：四段式 item_value 定价底座）**
- 复现：原模块无统一内部价值，spec 要求所有物品进同一价值坐标系，否则订单/配方会失控
- 新增 `v_time_unit(L) = 8 + 0.5×L`（时间价值）
- `crop_base_value(grow_seconds, level)`：`V_crop_base = T_grow_hours × V_time_unit(L) / plot_efficiency`
- `item_value_coin(item_level, rarity, grow_seconds, base_sell)`：时间价值 + 稀有溢价（`RARITY_MUL` 普通1.0/稀有1.8/史诗2.6/传说4.0）
- `value_coin` 用于订单/配方定价，不等于玩家可见卖价（spec：卖价 = value × sell_ratio，作回收口非赚钱手段）

**API 与入口更新**
- `GET /api/garden/state` 新增字段：`active_orders`（活跃订单数）/ `total_order_coin`（累计交付金币）
- `garden/home.html` 快捷入口新增：订单板
- `garden/rules.html` 新增 4 章节：订单交易系统 / 统一加成公式 / 品质系统 / 物品价值体系

**数据模型变更（2 张新表 + 1 字段）**
- `GardenOrder`：订单实例（order_type / requirements JSON / reward_coin / reward_exp / reward_token / expire_at）
- `GardenOrderLog`：交付历史（coin_gain / exp_gain / token_gain / delivered_at）
- `GardenDailyLog` 新增 `order_reroll_paid`（当日付费刷新次数）

**文件变更**
- `app/routers/garden.py`：新增订单路由 4 条 + 工具函数 4 个 + spec 公式配置 8 组（apply_buff/QUALITY_*/roll_quality/v_time_unit/crop_base_value/item_value_coin/ORDER_*/order_exp_scale）
- `app/routers/api.py`：`/garden/state` 新增 active_orders / total_order_coin
- `app/models.py`：新增 `GardenOrder` / `GardenOrderLog`（2 表）+ `GardenDailyLog.order_reroll_paid`
- `app/templates/garden/`：新增 `orders.html` / `order_history.html`（2 模板）
- `app/templates/garden/home.html`：快捷入口新增订单板
- `app/templates/garden/rules.html`：新增 4 章节
- `app/config.py`：版本号 0.1.2 → 0.1.3

**待办（下一版本）**
- 环境值 / 装扮系统（env_score + deco + set_bonus + 边际递减 buff）
- 工坊制作队列（slot 工作台并行 + queue_item 时间戳完成，替代当前即时合成）

**端到端验证**
- ✅ 导入校验：apply_buff / roll_quality / item_value_coin / ORDER_MARGIN 可访问；GardenOrder/GardenOrderLog 模型存在
- ✅ 公式校验：apply_buff(100, [0.1, 0.2], [0.05], cap=150) = 138；roll_quality 返回 N/G/R/E/L 之一
- ✅ 订单闭环：进入订单板自动生成订单 → 交付扣材料发奖励 → 历史记录
- ✅ 刷新防刷：免费 2 次后 cost=50×1.5^n 递增
- ✅ API：`/api/garden/state` 返回 active_orders / total_order_coin

---

### v0.1.2 （2026-08-03）— 全仓库模拟运行修复（5 项）

对仓库做整体模拟运行与逐模块走查，复现并修复 4 个逻辑错误与 1 个功能缺口。修复原则：回归每条成就/图标定义，使触发点与定义语义一致；写操作留痕变量需在作用域内定义。

**[高] 农场收获 NameError 500**
- 复现：登录 demo → 购种子 → 种植 → 等成熟 → POST `/games/farm/harvest/{slot}` → 500
- 根因：`harvest` 末尾日志记录 `await log.record(..., f"slot{slot}:{crop_key}")` 引用了未定义变量 `crop_key`（作用域内只有 `p.crop_key` 与 `crop`，无 `crop_key`）
- 修复：改为 `crop.key`（与上方 `crop.name`/`crop.harvest_exp` 同源）
- 影响：农场核心闭环在收获阶段中断，修复后收获闭环恢复

**[高] 二星餐厅成就错位**
- 复现：首次完成一道菜即可能点亮"二星餐厅"成就
- 根因：成就定义 `achv_chef_star2` = "餐厅升至2星"（`seed.py`），正确触发点应在 `apply_star` 升星成功后；但 `finish_cook` 每次完成烹饪都上报 `achv_chef_star2 delta=1`，导致做菜即可推进
- 修复：移除 `finish_cook` 中错误的 `achv_chef_star2` 上报；保留 `apply_star` 中 `if st.stars >= 2: 上报 achv_chef_star2`（已存在，正确）
- 影响：成就触发点与定义一致，仅在升至 2 星时点亮

**[中] 勤劳农夫图标触发条件错误**
- 复现：图标定义 `icon_farmer` = "收获10次作物"（`seed.py`），但 `harvest` 用 `if st.exp + (st.level-1)*100 >= 100` 经验近似判断，因不同作物 `harvest_exp` 不同（如番茄=20），实际可能 5 次收获就点亮
- 根因：缺少真实收获计数器
- 修复：
  - `FarmState` 模型新增 `harvest_count` 字段（累计收获次数）
  - `harvest` 中 `st.harvest_count += 1`，触发条件改为 `if st.harvest_count >= 10`
- 影响：图标触发严格对齐"收获10次"定义

**[中] 花谱大师成就被无关动作推进**
- 复现：成就定义 `achv_flower_master` = "点亮全部花谱"（`seed.py`），但 `stage_action`（浇水/除草/除虫）、`harvest`（收花）、`craft`（合成种子）三处都上报 `achv_flower_master delta=1`
- 根因：浇水/收花/合成都能涨这个成就，语义跑偏
- 修复：移除 `stage_action` / `harvest` / `craft` 三处错误上报；保留 `album_light`（点亮花谱）中的上报（已存在，正确）
- 影响：成就只在真正点亮花谱条目时推进，与定义一致

**[功能缺口] JSON API 缺召唤之王状态接口**
- 复现：`api.py` 仅有 `/farm/state` `/town/state` `/garden/state` `/sea/state` 四个状态接口，缺 `/summon/state`；README API 列表也仅列四个
- 修复：新增 `GET /api/summon/state`，返回召唤师核心状态：等级/经验/活力/铜钱/元宝/声望/擂台币/当前地图/通关数/幻兽总数/上阵数/最高幻兽等级
- 影响：前端或外部调用方可统一拉取五个模块状态，API 能力完整

**文件变更**
- `app/routers/farm.py`：`harvest` 修复 `crop_key`→`crop.key`；图标触发改为 `harvest_count >= 10`
- `app/routers/town.py`：`finish_cook` 移除错误的 `achv_chef_star2` 上报
- `app/routers/garden.py`：`stage_action` / `harvest` / `craft` 移除错误的 `achv_flower_master` 上报
- `app/routers/api.py`：新增 `GET /api/summon/state` 接口
- `app/models.py`：`FarmState` 新增 `harvest_count` 字段
- `app/config.py`：版本号 0.1.1 → 0.1.2

**端到端验证**
- ✅ 导入校验：`SummonState`/`SummonPet` 可访问；`FarmState.harvest_count` 字段存在
- ✅ 农场收获冒烟：种番茄→催熟→收获返回 200（不再 500），`harvest_count` 递增
- ✅ 勤劳农夫图标：收获 10 次后触发（不再受 `harvest_exp` 差异影响）
- ✅ 二星餐厅成就：做菜不再推进；仅 `apply_star` 升至 2 星时推进
- ✅ 花谱大师成就：浇水/收花/合成不再推进；仅 `album_light` 点亮花谱时推进
- ✅ 召唤 API：`GET /api/summon/state` 返回 12 个字段，含幻兽统计

---

### v0.1.1 （2026-08-03）— 美味小镇对齐《页面结构与数值资料汇总》

按用户提供的《QQ家园〈美味小镇〉页面结构与数值资料汇总》整理稿，对照现有美味小镇实现做验证与补齐：页面信息架构、子系统边界、关键规则与可验证公式逐条对齐；无法从公开资料交叉验证的部分（如上座率经验表）明确标记 `[unverified]`。保留老味道（翻橱柜/添油/合菜/雇好友/升星挑剔客），新增赛厨对抗与厨艺大赛两条 PVP 玩法线。

**油壶容量扩档（6 档 → 8 档）**
- 对齐 spec 原档 8 档：`3000默认 → 4000初级金币 → 5000中级积分 → 5500高级(上) → 6000高级(下) → 7000黄金(上) → 8000黄金(下) → 9000白金(上)`
- spec 原档 5500/6000/7000/8000 走元宝、9000 走活动；本平台只有金币单一货币，统一按兑换价值折算为金币成本（40000/80000/120000/180000/280000）
- `OIL_POT_TABLE` 由 6 行扩展为 8 行，补齐 5500 与 9000 两档缺口

**赛厨系统（v0.1.1 新增 PVP 线）**
- **厨具 5 类**：`[铲]/[刀]/[锅]/[味]/[意]`，每类只能装配对应厨具（`CHEF_TOOLS` 配置，base_power 10，售价 2000 金币）
- **厨具强化**：+1~+10 级，消耗 `1000×当前等级` 金币，影响厨力
- **技能点 40 点**：火候/刀功/厨艺/调味（spec 示例分配 15/9/8/8）；可重置（消耗 2000 金币）
- **3 评委打分**：系统随机挑 3 名 NPC（从 4 项技能中抽 3 项作为各评委关注点）；基础分 = 厨力/10 + 随机扰动，关注点技能 ×3 加成
- **胜负判定**：三评委总分高者胜；总分相同则**被挑战方胜**（spec 原口径）
- **厨力公式**：`等级×10 + 星级×200 + 已学菜×5 + 金牌菜×20 + 装备厨具等级和×15 + 技能点总数×8`
- **奖励**：胜 +200 金币/+30 经验；负 +50 安慰金币；每日 10 次上限
- 路由：`/chef`（赛厨中心）/ `/match`（选对手）/ `/match/challenge/{uid}`（挑战结算）

**厨艺大赛（v0.1.1 新增赛事线）**
- **4 赛区**：初级区 40-49 / 中级区 50-59 / 高级区 60-69 / 超级区 70+（`CONTEST_ZONES`）
- **报名**：消耗 20 体力（本平台 10 金币/体力折算 = 200 金币）· 每日 8-23 时 · 每日 1 次
- **匹配**：spec 为 23 时后系统随机匹配；本平台简化为玩家点"立即结算"匹配同赛区 NPC/玩家，单场决胜负
- **公布**：次日 8 时前公布（本平台即时结算）
- **奖励**：胜 +500 金币；负 +100 安慰金币
- 路由：`/contest`（大赛页）/ `/contest/signup`（报名）/ `/contest/settle`（结算）

**菜谱与菜式（spec 三维度对齐）**
- **菜系 8 大 + 综合街映射**（展示用）：湘→湖南街 / 粤→广东街 / 川→四川街 / 闽→福建街 / 徽→安徽街 / 鲁→山东街 / 浙→浙江街 / 苏→江苏街 / 综合→综合一街/二街
- **菜式级别**：1-6 级（佛跳墙比葱拌豆腐高级）—— 已由 v0.0.4 `RECIPE_LEVEL_TABLE` 落地
- **菜等**：同菜升级（普通→极品→金牌）—— 已由 v0.0.4 `RECIPE_UPGRADE_TABLE` 落地
- **金牌食材替换映射**（`GOLD_INGREDIENT_REPLACE`，展示用）：猪肉→山黑猪肉 / 鸡蛋→草鸡蛋 / 鸡肉→三黄鸡肉 / 牛肉→雪花牛肉 / 蘑菇·香菇→神秘金蟾菇 / 鱼翅→神秘九天翅 / 鲍鱼→神秘九孔鲍 等 26 条

**万能食材（v0.1.1 新增替代位机制）**
- spec：合成时只差 1 个食材，可用对应级别万能食材补齐
- 注册 6 级万能食材物品字典：`town_wild_ing_1` ~ `town_wild_ing_6`（售价 30/50/80/120/180/260 金币）
- 食材级别映射（`ING_LEVEL_BY_PREFIX`）：按 item_key 前缀映射到 1-6 级
- 做菜时校验：缺 1 个且只差 1 个 → 自动消耗对应级别万能食材×1 补齐；否则提示食材不足
- 万能食材作为"替代位"机制，不替代普通食材

**上座率经验表（spec 标记 [unverified]，展示用）**
- `SEAT_COVER_TABLE`：按餐厅等级段给出菜品覆盖建议（11-15级→5普通菜 … 91+→210极品+165金牌）
- spec 明确标注为玩家总结性质，作为菜品覆盖建议与系统检查项，不作为硬性规则

**规则页与入口更新**
- `town/rules.html` 新增 6 个章节：菜谱与菜式三维度 / 菜系街道映射 / 食材体系(233种+金牌替换) / 上座率经验表[unverified] / 赛厨系统 / 厨艺大赛
- `town/home.html` 快捷入口新增：赛厨中心 / 厨艺大赛

**数据模型变更（4 张新表）**
- `TownChefTool`：玩家厨具（5 类，UniqueConstraint(user_id, tool_key)）
- `TownChefSkill`：玩家技能点分配（user_id 主键，4 维属性）
- `TownMatchLog`：赛厨对战记录（3 评委打分明细 JSON）
- `TownContestEntry`：厨艺大赛报名记录（UniqueConstraint(user_id, signup_date)）

**种子数据补齐**
- 物品字典：6 级万能食材注册到平台物品字典
- demo 用户初始：万能食材×2/×1 + 菜谱碎片×5 + 特殊调料×1 + 初始厨具(铲)1件便于上手赛厨

**文件变更**
- `app/routers/town.py`：新增赛厨/厨艺大赛路由 12 条 + 工具函数 7 个 + 静态配置 8 组（CUISINE_STREETS/CHEF_TOOLS/SKILL_*/CONTEST_*/MATCH_*/SEAT_COVER_TABLE/GOLD_INGREDIENT_REPLACE/WILD_INGREDIENTS/ING_LEVEL_BY_PREFIX）+ 油壶表扩档 6→8 + 万能食材替代逻辑嵌入做菜流程
- `app/models.py`：新增 `TownChefTool` / `TownChefSkill` / `TownMatchLog` / `TownContestEntry`（4 表）
- `app/templates/town/`：新增 `chef.html` / `match.html` / `match_result.html` / `contest.html`（4 模板）
- `app/templates/town/home.html`：快捷入口新增赛厨中心/厨艺大赛
- `app/templates/town/rules.html`：新增 6 章节（菜式三维度/菜系街道/食材体系/上座率表/赛厨/大赛）
- `app/seed.py`：6 级万能食材物品字典 + demo 初始万能食材/碎片/调料/厨具
- `app/config.py`：版本号 0.1.0 → 0.1.1

**端到端验证**
- ✅ 导入校验：CHEF_TOOLS 5 / SKILL_TOTAL_POINTS 40 / CONTEST_ZONES 4 / WILD_INGREDIENTS 6 / OIL_POT_TABLE 8 档
- ✅ 万能食材替代：缺 1 个 → 自动消耗对应级别万能食材；缺 >1 个 → 拒绝
- ✅ 厨力计算：等级×10 + 星级×200 + 已学菜×5 + 金牌菜×20 + 厨具等级和×15 + 技能点×8
- ✅ 赛厨流程：选好友对手 → 3 评委打分 → 总分高者胜（平局被挑战方胜）→ 奖惩 + 记录
- ✅ 厨艺大赛：报名（时段+赛区+体力折算）→ 结算（匹配 NPC/玩家）→ 奖励

---

### v0.1.0 （2026-08-03）— 精武堂模块上线

新增第六个游戏模块「精武堂」：人物养成 / 修炼挂机 / 加点流派 / 装备强化打造 / 比武对抗 / PVE 挑战 / 日常任务活跃奖励 / 帮派社交。按用户提供的《精武堂完整玩法解析 + 结构与系统解析 + 页面树全量拆解》落地，口径：怀旧 / 旧逻辑 / WAP 层级页 / 可复刻落地。

**核心定位与主循环**
- 本质是"以人物养成、修炼推进、比武对抗、装备成长、帮派社交"为核心的文字页战斗模块
- 主循环：`修炼/任务 → 获得经验资源 → 升级加点 → 换装强化 → 比武/挑战 → 继续养成`
- 日常短循环：看状态 → 领修炼收益 → 加点/换装 → 打比武或挑战 → 帮派/排行 → 继续挂机

**四线并行成长体系**
- **等级线**（1-80）：经验公式 `need(L)=120+80×L`（方案A，平台统一），决定属性成长/装备门槛/玩法解锁
- **属性点线**：每级 +3 点，自由分配四维（力量/敏捷/体魄/内息），形成暴力外功/高敏闪避/血防坦克/内功爆发/均衡五流派
- **装备线**：8 部位（武器/衣服/护腕/腰带/鞋子/项链/戒指/秘籍）× 5 品质（白绿蓝紫橙），强化 +0~+10
- **技能线**：10 门武学（4 主动 + 6 被动），最高 5 级，主动系数影响伤害，被动加属性

**修炼系统（挂机/回访引擎）**
- 普通修炼：每小时 200 经验 / 120 银两
- 闭关修炼：经验×2.0 / 银两×1.5，消耗 20 荣誉，每日 2 次
- 离线收益上限 12 小时，形成"上线收一次"的固定心智
- 首页一键领取修炼收益

**战斗结算（半自动回合制，文字战报式）**
- 出手顺序：速度高者先手
- 命中率 = clamp(hit / (hit + dodge), 0.25, 0.95)
- 暴击率 = clamp(crit, 0.05, 0.60) · 暴击 ×1.5
- 外功/内功伤害 = atk×技能系数 × (1 - def/(def+200+lv×20)) × 暴击 × 随机（取较高者结算）
- 最多 12 回合，超时比剩余血量
- 战力 = hp×0.20 + 外攻×1.8 + 内攻×1.8 + 外防×1.3 + 内防×1.3 + 命中×0.8 + 闪避×0.8 + 速度×1.2 + 技能分 + 装备分

**比武场（PVP）**
- 每日免费 10 次，额外次数 5 荣誉/次
- 胜利 +12 比武分 +5 荣誉 · 失败 -4 比武分（不低于0）+1 荣誉
- 取其他玩家作对手，无对手时生成 NPC
- 完整战报（回合/技能/伤害/暴击/未命中/剩余血量）

**挑战关卡（PVE）**
- 每日 10 次，9 个阶梯关卡（木人桩→武林盟主）
- 奖励银两/经验/材料（强化石/玄铁精华/精炼石/骨粉/洗点丹）
- 通关记录持久化

**装备系统**
- 强化 +1~+10：成功率 100%→30%，消耗银两+强化石，前期高成功率
- 打造：12级开启，消耗 3 玄铁精华 + 500 银两，随机品质（偏向低品质）
- 8 穿戴槽位 + 背包装备，一键穿戴/卸下

**日常任务 + 活跃奖励**
- 12 项日常任务（修炼/挑战/强化/打造/比武/帮派等），每项给活跃点
- 活跃度档位：20/40/60/80/100，对应递增奖励
- 每日 0 点重置进度与领奖状态

**帮派（门派）系统**
- 创建消耗 10000 银两 · 加入/退出/帮主退出解散
- 捐献：银两/荣誉 → 贡献（日限 3 次）
- 帮派商店：贡献兑换强化石/玄铁精华/精炼石/洗点碎片/小还丹
- 帮派成员列表 + 公告

**加点洗点**
- 顶部显示可分配点数，每属性 +1 操作
- 洗点消耗 5000 银两，归还全部已分配点数

**平台集成**
- 排行/背包/消息走平台公共系统（events.emit 上报 + 链接跳转）
- 12 个精武堂道具注册到平台物品字典（强化石/玄铁精华/精炼石/骨粉/洗点碎片/洗点丹/小还丹/比武券/比武勋章/悬赏令/帮派贡献箱/帮派令）
- 图标"武林高手"（精武堂10级）+ 成就"比武新秀"（胜3场）/"一代宗师"（30级）
- 关键操作全部 log.record 留痕（修炼/加点/强化/打造/比武/PVE/帮派）

**页面树（WAP 层级页）**
- 精武堂首页（状态汇总 + 修炼收益 + 待办 + 快捷入口）
- 修炼（普通/闭关 + 一键领取）
- 加点（四维分配 + 派生属性 + 洗点）
- 技能（武学谱 + 学习/升级）
- 装备（8 槽位 + 背包 + 强化 + 打造）
- 比武场（对手列表 + 挑战 + 战报结果页）
- 挑战（9 关卡 + 战报结果页）
- 日常任务（12 任务 + 活跃奖励 5 档）
- 帮派（创建/加入/成员/捐献/商店）
- 规则

**文件变更**
- `app/routers/martial_data.py`（新增）：全量静态配置（属性公式/装备/技能/修炼/PVP/PVE/日常任务/活跃/帮派/战斗结算）
- `app/routers/martial.py`（新增）：模块路由（30 条：首页/修炼/加点/技能/装备/比武/PVE/任务/活跃/帮派/规则）
- `app/models.py`：新增 `MartialState` / `MartialEquip` / `MartialSkill` / `MartialStageLog` / `MartialArenaLog` / `MartialGuild` / `MartialGuildMember`（7 表）
- `app/templates/martial/`（新增 12 模板）：home/cultivate/attrs/skills/equip/arena/arena_result/challenge/challenge_result/tasks/guild/rules
- `app/deps.py`：新增通用 `from_json` Jinja2 过滤器（解析 JSON 字符串为 dict/list）
- `app/seed.py`：注册 martial 模块 + 12 个道具字典 + demo 初始强化石/玄铁精华/小还丹/白品质武器 + 图标/成就
- `app/main.py`：注册 martial 路由
- `app/config.py`：版本号 0.0.9 → 0.1.0

**端到端验证**
- ✅ 导入校验：SKILLS 10 / DAILY_TASKS 12 / PVE_STAGES 9 / GUILD_SHOP 5
- ✅ HTTP 冒烟（demo 登录）：首页/修炼/加点/技能/装备/比武/挑战/任务/帮派/规则 全 200
- ✅ 写操作冒烟：修炼领取 / 加点 / 学技能 / PVE 挑战 S01 / PVP 挑战 NPC 全通过
- ✅ 修复 NPC MartialState 默认属性为 None 的 bug（显式传四维属性）

---

### v0.0.9 （2026-08-03）— 魔法花园/美味小镇整理去重 + 服务员解雇

按用户提供的《魔法花园 / 美味小镇（方案C）玩法全细节 + 结构与系统解析 + 页面树全量拆解》设计规范，对照现有实现做整理去重与修补。两模块均已高度成熟（花园22路由/小镇24路由），本次聚焦"分析并整理去重复，让整个程序合理"，不重复造平台已有的功能（排行/商城/消息/仓库统一走平台）。

**魔法花园 — 整理去重**
- 删除孤儿模板 `garden/collection.html`：依赖未传入的 `flowers`/`lit_keys` 变量，无任何路由引用，功能已被 `album.html` 完整覆盖
- 移除未使用导入 `icons`（全文 0 引用，冗余 import）

**美味小镇 — 整理去重 + 补缺**
- 移除未使用导入 `icons`（全文 0 引用，冗余 import）
- 新增服务员解雇路由 `POST /games/town/waiter/fire/{waiter_id}`：对齐设计规范页面树"解雇/替换（确认→结果）"，此前仅靠 12 小时自动过期，现可主动解雇释放服务员位
- `waiter.html` 每位已雇佣好友增加"解雇"按钮

**设计规范对齐分析（不造重复轮子）**
- 排行榜/商城/消息中心/仓库：设计规范明确标注"可走平台"，模块内仅 `events.emit` 上报，不在模块内重复实现
- 花园"套系奖励"/"好友留言"/小镇"街坊"/"厨柜页"：属新功能扩展，本次不纳入（避免过度工程），留待后续按需迭代
- 两模块 `rules.html` 经核对均已准确反映实现，无笔误需修正

**文件变更**
- `app/routers/garden.py`：移除未用 `icons` 导入
- `app/routers/town.py`：移除未用 `icons` 导入 + 新增 `fire_waiter` 路由
- `app/templates/garden/collection.html`：删除（孤儿模板）
- `app/templates/town/waiter.html`：已雇佣服务员增加解雇按钮
- `app/config.py`：版本号 0.0.8 → 0.0.9

**端到端验证**
- ✅ 导入校验：garden.py / town.py 均无 `icons` 残留引用
- ✅ 路由校验：town 新增 `/waiter/fire/{waiter_id}` 路由注册成功
- ✅ HTTP 冒烟：`/health` 返回 `version: 0.0.9`

---

### v0.0.8 （2026-08-03）— 召唤之王战灵洗炼/联盟技能逐级消耗配表补齐

补齐两张用户提供的"不缺参数"配表：战灵洗炼费用（含锁词条）+ 联盟技能逐级消耗（1→10级），并新增查询函数供后续玩法路由调用。整理去重，修正 rules.html 战骨公式笔误。

**新增配表（2 张全量）**
- `cfg_spirit_reroll_cost`（30 行）：当日第 1-30 次洗炼费用
  - 前 3 次免费（`is_free=1`）
  - 第 4 次起消耗铜钱+灵力，线性递增（500+20 → 7000+280）
  - 第 30 次封顶（`SPIRIT_REROLL_DAILY_CAP=30`）
- `cfg_spirit_reroll_lock_cost`（4 行）：锁词条额外费用（叠加到洗炼费用）
  - 不锁 0/0 · 锁1条 800铜钱+30灵力 · 锁2条 1600+60 · 锁3条 2600+100
  - 锁词条则不再享受免费次数
- `cfg_alliance_skill_level_cost`（10 行）：联盟技能逐级消耗
  - 1级 20贡献 → 10级 110贡献，每级+10
  - 满级累计 650贡献，每级+1%加成（满级+10%）
  - 4 条技能（GSK_HP/ATK/DEF/SPD）消耗一致

**新增辅助函数（3 个）**
- `spirit_reroll_cost(roll_no, lock_count=0)` → `(coin, dust, is_free)`：洗炼费用查询，含锁词条叠加与封顶处理
- `alliance_skill_cost(skill_id, from_level)` → `(this_cost, cumulative, bonus_total)`：单次升级消耗
- `alliance_skill_cumulative_cost(skill_id, to_level)` → `int`：升到指定等级的累计贡献

**修正与整理**
- `rules.html` 战骨公式笔误 `floor((lv-1)/5)` → `floor(lv/5)`（与 v0.0.7 实际公式一致）
- `rules.html` 战灵区补充洗炼/锁词条费用说明
- `rules.html` 联盟区补充技能逐级消耗说明（1级20→10级110，满级650）
- `summon_data.py` 文件头版本 0.0.7 → 0.0.8

**文件变更**
- `app/routers/summon_data.py`：新增 2 张配表 + 3 个辅助函数 + 文件头版本
- `app/templates/summon/rules.html`：修正战骨公式笔误 + 补充战灵洗炼/联盟技能说明
- `app/config.py`：版本号 0.0.7 → 0.0.8

**端到端验证**
- ✅ 导入校验：SPIRIT_REROLL_COST 30 / SPIRIT_REROLL_LOCK_COST 4 / ALLIANCE_SKILL_LEVEL_COST 10
- ✅ 洗炼费用：roll1=(0,0,True) / roll4=(500,20,False) / roll30=(7000,280,False)
- ✅ 锁词条：roll1+lock1=(800,30,False)（锁则不再免费）/ roll4+lock2=(2100,80,False)
- ✅ 联盟技能：GSK_HP 0→1=(20,20,0.01) / 9→10=(110,650,0.10) / 10→11=(0,650,0.10)（满级）
- ✅ 累计：GSK_HP 到10级 = 650贡献
- ✅ HTTP 冒烟：首页/规则页 200

---

### v0.0.7 （2026-08-03）— 召唤之王全量配表定版

按用户提供的完整 CSV 配表包，补齐 v0.0.6 中缺失的高级系统参数表，修正规则页错误，去除 v1.0 冗余标记，整理去重使整个程序合理。

**补齐的配表（21 张全量）**
- `cfg_skill_base`（60 条）：对齐 notes 字段（降DEF_PHY / DEF_MAG%提升 / 对应天魂模板 等）
- `cfg_pet_species`（120 只）+ `cfg_pet_skill_pool`（120 映射）：已与 v0.0.6 一致，校验通过
- `cfg_bone_parts`（7 部位）：扩展为 `BONE_PARTS` 字典含 stats 字段（头骨→HP|DEF_MAG 等）
- `cfg_bone_upgrade`（100 级）：公式化去重 → `bone_upgrade_cost(level)` 函数，coin=200+60×lv / stone=1+floor((lv-1)/5)
- `cfg_soul_rarity`（6 阶）：补齐 `GOD` 神魂阶（v0.0.6 仅 5 阶缺失神魂）
- `cfg_soul_hunt`（7 档猎魂师）：新增 `SOUL_HUNT` 表（艾米→凯文高级，铜钱/追魂法宝双货币）
- `cfg_soul_xp`（9 级）：新增 `SOUL_XP` 表（2000→512000 递增）
- `cfg_soul_feed`（5 阶）：新增 `SOUL_FEED` 表（黄50/玄100/地200/天400/神1000）
- `cfg_spirit_slots`（6 槽）：扩展为 `SPIRIT_SLOTS` 字典含 slot→element
- `cfg_spirit_quality_weights`（4 品质）：新增 `SPIRIT_QUALITY_WEIGHTS`（普通/精良/优秀/传奇）
- `cfg_spirit_affixes`（16 词条）：新增 `SPIRIT_AFFIXES`（flat/pct/special 三系）
- `cfg_arena`（10 参数）：新增 `ARENA` 字典（日10免费/胜12声望+18擂台币/赛季7天/Top100奖）
- `cfg_battlefield`（10 参数）：新增 `BATTLEFIELD` 字典（06:00-24:00/40分线/日5场/胜30声望+35战场币）
- `cfg_kill_box_drops`（6 项）：新增 `KILL_BOX_DROPS` 掉落池
- `cfg_alliance_donation`（3 项）：新增 `ALLIANCE_DONATION`（焚火晶1/金袋10/内丹10）
- `cfg_alliance_skills`（4 技能）：新增 `ALLIANCE_SKILLS`（HP/ATK/DEF/SPD 各10级）
- `cfg_alliance_storage`（2 参数）：新增 `ALLIANCE_STORAGE`（日1免费/额外15贡献）
- `cfg_master_apprentice`（7 参数）：新增 `MASTER_APPRENTICE` 字典（40收徒/徒≤30/35出师/4倍互灌/出师奖）
- `cfg_shop`（26 条）：扩展为 8 字段格式（shop/slot/item_id/price_currency/price_amount/limit_daily/limit_weekly/notes）

**修正的错误**
- `rules.html` 抓捕日限 30→60（实际 `DAILY_LIMITS["capture"]=60`）
- `rules.html` 抓捕公式 旧"0.6×球倍率-稀有度难度"→ 正确"基础率×球倍率+级差+保底"
- `rules.html` 魔魂 5阶→6阶（补齐神魂）
- `rules.html` 高级系统区补充：战骨强化公式/猎魂师7档/吞噬收益/擂台赛季/战场分线时间/杀戮礼包/联盟4技能/师徒出师奖

**去除冗余与整理**
- 清理所有 "v1.0" 标记（文件头/属性生成注释/捕捉系统注释/docstring）
- `summon.py` 文件头 "v1.0 新增" 行移除
- 战骨强化 100 行重复表 → 公式函数 `bone_upgrade_cost()` 去重
- `SHOP` 5 字段 → 8 字段，同步更新 `summon.py` 3 处迭代解包
- 保留 `BONE_PART_NAMES`/`SOUL_RARITY_NAMES`/`SPIRIT_ELEMENTS`/`ARENA_DAILY_FREE` 等向后兼容别名

**文件变更**
- `app/routers/summon_data.py`：SKILLS notes 对齐 + SHOP 8字段 + 新增 21 张配表 + 清理 v1.0
- `app/routers/summon.py`：适配 SHOP 8字段迭代（shop_view / shop_buy）+ 文件头清理
- `app/templates/summon/rules.html`：修正抓捕日限/公式/魔魂阶数 + 补齐高级系统详情
- `app/config.py`：版本号 0.0.6 → 0.0.7

**端到端验证**
- ✅ 导入校验：SKILLS 60 / PETS 120 / PET_SKILL_POOL 120 / SKILL_POOLS 18 / SHOP 26 全量
- ✅ 新增表校验：BONE_PARTS 7 / SOUL_RARITY 6(含GOD) / SOUL_HUNT 7 / SOUL_XP 9 / SOUL_FEED 5 / SPIRIT_AFFIXES 16 / KILL_BOX_DROPS 6 / ALLIANCE_SKILLS 4
- ✅ SHOP 8字段迭代：shop_view / shop_buy 路由正常
- ✅ 战骨公式：bone_upgrade_cost(1)=(260,1) / bone_upgrade_cost(50)=(3200,11) / bone_upgrade_cost(100)=(6200,21)
- ✅ HTTP 冒烟：首页/商店/规则页全 200

---

### v0.0.6 （2026-08-03）— 召唤之王复刻定版 v1.0 可跑服参数落地

按《召唤之王复刻定版 v1.0（可跑服、参数不缺）》重构召唤之王模块：把所有玩法改为"可配表参数"，去重并整理，确保整条核心循环（生成/捕捉/掉落/日常）全部可跑、参数齐全无省略号。

**属性生成公式化（不再手写每只宠数值）**
- 段位基础范围 `TIER_BASE_RANGES`：T1–T8 各给 hp/atk/def/spd 的 min–max
- 定位系数 `ROLE_COEF`：TANK/PHY/MAG/CTRL/CURSE 五职业 6 维系数
- 每级成长步长 `STEP_BASE`：HP=6 / ATK=0.9 / DEF=0.7 / SPD=0.06
- 公式：`BaseStat = Uniform(min..max) × aptitude × role_coef`，`Stat(L) = floor(Base + (L-1) × Step)`，`Step = StepBase × rarity_mul × growth_star_mul`
- 6 维资质 0.85–1.15，成长星 1–5（倍率 1.0–1.25），稀有度 N1.0/R1.08/E1.16/L1.25

**捕捉系统（成功率+球倍率+级差+保底，全参数）**
- 同级基础率：N0.35 / R0.22 / E0.12 / L0.06
- 球倍率：普通×1.0 / 强力×1.5 / 超级×2.2
- 级差加成：玩家高于宠物 +0.01~+0.10，低于 -0.02~-0.20
- 连续失败保底：N8/R10/E12/L15 次触发 +0.08~0.10，上限 +0.16~0.20
- 最终公式：`p = clamp(base × ball_mul + level_diff + pity, 0.01, 0.95)`

**技能池系统（120 只图鉴全量映射）**
- 12 主池 `PM_*`（按种族×职业）+ 6 稀有池 `PR_*`（OFFENSE/CONTROL/SURVIVE/CURSE/DRAGON/SOUL）
- `PET_SKILL_POOL` 120 行全量映射：每只宠 → (签名技能, 主池, 稀有池)
- 抽取规则：槽1签名(Lv1) / 槽2主池(Lv1) / 槽3主池(Lv10) / 槽4稀有池(Lv30)
- 技能槽解锁：slot1=1 / slot2=1 / slot3=10 / slot4=30

**4 套掉落表（普通/精英/副本/BOSS，完全可跑）**
- `DROP_NORMAL`：铜钱60-120 / 普通球 / 灵石 / 黄魂粉
- `DROP_ELITE`：铜钱120-220 / 强力球 / 灵石 / 黄玄魂粉
- `DROP_DUNGEON`：铜钱220-380 / 超级球 / 灵石 / 玄地魂粉 / 灵力
- `DROP_BOSS`：铜钱380-650 / 地天魂粉 / 战灵钥匙 / 追魂法宝 / 擂台战场宝箱
- 段位加成 `tier_mul`：影响铜钱数量，不影响掉落概率

**每日副本路由（新）**
- `/games/summon/dungeon`：每日 5 次上限，耗活力 6，使用 `DROP_DUNGEON`
- 新增 `summon/dungeon.html` 模板

**日常任务系统（12 项，全参数奖励）**
- D001–D012：普通关/精英关/副本/擂台/战骨/通天塔/猎魂/战灵塔/战场/联盟捐献/师徒/捕捉
- 每日 0 点重置进度与领奖状态，未实现功能显示"即将开放"
- 当前已实现指标：`stage_normal_win` / `stage_elite_win` / `dungeon_win` / `capture_success`
- 新增 `summon/tasks.html` 模板 + 首页"可领"徽标

**幻兽培养完善**
- 资质 6 维显示（pet_detail.html）：HP/物攻/魔攻/物防/魔防/速度 各 0.85–1.15
- 技能槽位显示：`skills|length / skill_slots`
- 技能池映射展示：签名池 + 稀有池
- 重生入口：消耗重生丹重洗成长星/资质/技能（保留等级），持有数实时显示

**修复与整理**
- 修复 `battle.html` 引用未传入的 `coin_reward` 字段，改用 `drop_text` + `leveled` 标记
- `seed.py` 补齐 11 个缺失 v1.0 道具：重生丹碎片/追魂法宝/地天魂宝箱/灵力/焚火晶/金袋/内丹/杀戮礼包/擂台宝箱/战场宝箱
- `SummonState` 新增字段：`capture_pity` / `daily_counters` / `daily_tasks`（JSON 存储保底与日限）
- `SummonPet` 新增字段：`aptitudes`（6 维资质 JSON）
- 升级时按公式重算属性（保留资质），重生时重洗资质+成长星+技能

**文件变更**
- `app/routers/summon_data.py`：补齐 `SKILL_POOLS`(18池) / `PET_SKILL_POOL`(120映射) / `TIER_BASE_RANGES` / `ROLE_COEF` / `STEP_BASE` / 捕捉公式 / 4 套掉落表 / `DAILY_TASKS` / `IMPLEMENTED_METRICS`
- `app/routers/summon.py`：新增 `/dungeon` `/dungeon/battle` `/tasks` `/tasks/claim/{id}` `/pet/{id}/rebirth` 路由
- `app/templates/summon/`：新增 `tasks.html` `dungeon.html`，更新 `home/battle/pet_detail.html`
- `app/models.py`：`SummonState` / `SummonPet` 扩展新字段
- `app/seed.py`：召唤之王道具字典补齐至 21 项
- `app/config.py`：版本号 0.0.5 → 0.0.6

**端到端验证**
- ✅ 属性生成：段位范围 × 资质 × 定位系数 × 成长步长（含升级重算）
- ✅ 捕捉公式：基础率 × 球倍率 + 级差 + 保底，失败累计保底，成功重置
- ✅ 技能池抽取：按图鉴池映射 + 宠物等级解锁槽位
- ✅ 4 套掉落：普通/精英/副本/BOSS 按权重抽取
- ✅ 日常任务：进度计数 + 领奖 + 首页徽标
- ✅ 副本路由：日限 5 次 + 耗活力 6 + 副本掉落表

---

### v0.0.5 （2026-08-03）— 召唤之王图鉴抓捕回合战斗模块上线

新增第五个游戏模块「召唤之王」：120 只幻兽图鉴 + 60 基础技能(×3阶=180) + 回合制战斗 + 种族克制 + 段位推进 + 抓捕系统。按《召唤之王复刻版可跑服全量配置包》落地，公开规则对齐 + 复刻定版数值。

**双轴成长体系**
- 召唤师等级（1-80）：经验公式 `need(L)=120+80×L`（方案A），决定段位解锁/出战位/魔魂槽
- 幻兽图鉴（120只）：6族(水/兽/虫/羽/龙/亡灵) × 8段位(T1-T8) × 4稀有度(N/R/E/L)

**核心循环**
`进地图 → 刷关卡(遭遇战) → 抓捕幻兽 → 组队 → 升级 → 解锁高段位 → 收集图鉴`

**120 幻兽图鉴**
- T1-T8 每段 15 只，按种族/职业/产出池分布
- 4 稀有度成长系数：N1.0 / R1.08 / E1.16 / L1.25
- 成长星 1-5（倍率 1.0-1.25），影响个体属性
- 种族基础属性 + 职业加成 + 稀有度 + 成长星 + 等级 共同决定个体属性

**60 基础技能 × 3 阶 = 180 技能**
- 5 系：PHY物攻 / TANK坦克 / MAG法攻 / CTRL控制 / CURSE诅咒
- 阶倍率：1阶1.0 / 2阶1.35 / 3阶1.75
- 主动/被动双类型，按职业池分配技能

**回合制战斗系统**
- 按速度降序行动（SPD_DESC）
- 物伤=(物攻×技能系数-物防)×种族系数 / 法伤=(魔攻×技能系数-魔防)×种族系数
- 暴击率5% × 1.5倍 / 基础命中95% / 基础闪避5%
- 种族克制环形：水>龙>羽>虫>兽>亡灵>水（克制+12%/被克-10%）
- 自动结算，最多12回合，超时比剩余血量

**抓捕系统**
- 3 种球：普通×1.0 / 强力×1.5 / 超级×2.2
- 成功率 = 0.6×球倍率 - 稀有度难度（N0/R0.1/E0.25/L0.45）
- 每日抓捕上限 30 次，自动消耗最优球

**段位地图（T1-T8）**
- 每 10 级解锁一段，每段 15 关，每 5 关精英关
- 普通关耗活力2 / 精英关耗活力4，活力上限120（每5分钟+1）
- 通关一段自动进入下一段位

**等级解锁节点**
- Lv1：地图/抓捕 · Lv10：擂台/战骨 · Lv20：T2
- Lv30：魔魂(3槽起每10级+1) · Lv35：战灵/战灵塔
- Lv40：战场/师徒/T4 · Lv60：第4出战位

**高级系统（规则就绪，核心循环先行）**
- 战骨：7部位强化（头/胸/臂/腿/手/尾/元魂）
- 魔魂：5阶(废/黄/玄/地/天)，天魂为基准 1.0，黄/玄/地 = 12.5%/25%/50%
- 战灵：6元素槽(水/土/火/木/金/神)，35级开启，4品质词条池
- 通天塔50层(产焚火晶) / 战灵塔30层
- 战场：40级分线(猛虎≤39/飞鹤≥40)，杀戮礼包掉落
- 联盟：捐献换贡献（焚火晶1:1/金袋1:10/内丹1:10），4线10级技能
- 师徒：40+收徒，徒≤30，35出师，互灌4倍活力

**数据模型**
- `SummonState`：召唤师状态（等级/经验/活力/多货币/地图进度/日限）
- `SummonPet`：玩家幻兽个体（species_id/等级/属性/技能/成长星/出战槽）
- 静态配置（120图鉴/60技能/地图/商店/战斗公式）置于 `summon_data.py` 常量

**文件结构**
- `app/routers/summon_data.py`（新增）：全量静态配置包
- `app/routers/summon.py`（新增）：模块路由（首页/地图/关卡/战斗/抓捕/幻兽/图鉴/商店/规则）
- `app/models.py`：新增 `SummonState` + `SummonPet`
- `app/templates/summon/`（新增）：home/map/stage/battle/pets/pet_detail/album/shop/rules
- `app/seed.py`：注册 summon 模块 + 召唤道具字典 + demo 初始球与初始幻兽
- `app/main.py`：注册 summon 路由

**端到端验证**
- ✅ 进入地图 → 选择段位 → 挑战关卡（耗活力）
- ✅ 回合战斗结算（种族克制/暴击/技能/速度序）
- ✅ 抓捕幻兽（球消耗/成功率/图鉴点亮）
- ✅ 幻兽上阵/下阵/放生/属性查看
- ✅ 召唤师+幻兽升级（经验公式/属性重算）
- ✅ 通关段位自动进下一段
- ✅ 图鉴收集进度（120只按段位分组）
- ✅ 商店购买捕捉球（铜钱/元宝双货币）

---

### v0.0.4 （2026-08-03）— 美味小镇怀旧版完整定版数值落地

按《美味小镇方案C 完整定版数值》重构美味小镇模块：餐厅星级(0-5星)×菜谱等级(1-6级)双主轴、6级食材×3品质菜谱、顾客满意度系统、油壶6档扩容、翻柜日限+衰减+冷却、蟑螂轻恶作剧、好友服务员雇佣、设施24小时增益。保留老味道（翻橱柜/添油/合菜/雇好友/升星挑剔客），做轻保护防崩盘。

**双主轴成长体系**
- 餐厅星级（规模轴）：0星→5星，决定桌位上限/服务员位/厨柜容量/设施位/挑剔客占比/收益系数
- 菜谱等级（内容轴）：1-6级菜 × 3品质（普通/极品/金牌），决定售价/经验/油耗/解锁等级
- 星级申请条件：等级 + 菜谱数量 + 累计营业 + 累计收入（对齐旧攻略 11-80 学菜门槛）

**基础定版数值（保留老味道）**
- 开局金币 10000 · 顾客周期 180秒 · 1名服务员服务3桌
- 油壶初始 3000（3000→4000 是怀旧关键点）· 可扩至 8000
- 1星起 10% 挑剔客，每升1星 +10%（5星上限 40%）
- 经验公式：`need(L→L+1)=120+80×L`（与平台方案A统一）

**菜谱系统（6级×3品质）**
- `TownRecipe` 扩展：`recipe_level`/`base_price`/`base_exp`/`base_oil`/`unlock_level`
- 品质系数：普通1.0 / 极品1.25 / 金牌1.55（**品质只升售价，不升经验**，保留旧逻辑）
- 升级需求表：普通→极品（熟练度+金币+菜谱碎片）/ 极品→金牌（+特殊调料）
- 新增 `TownRecipeProgress` 表：熟练度/品质/上架状态

**顾客系统（营业压力来源）**
- 顾客类型：普通客(1.0x) / 挑剔客(1.25x金币,指定菜) / 稀有客(1.60x金币,高阶菜)
- 满意度：当周期上菜=100%，延迟衰减，缺油-20
- 结算公式：`单次收益 = 售价×品质系数×顾客系数×星级系数`

**油量系统（怀旧标志资源）**
- 6档油壶：3000→4000→5000→6000→7000→8000（纯金币成长，不走付费门槛）
- 补油包：小(300/60金) / 中(1000/180金) / 大(3000/480金)
- 待机耗油：每有效桌每周期2油（保守，避免离线崩盘）
- 做菜耗油：1级菜8油 → 6级菜50油

**翻橱柜系统（怀旧核心互动 + 轻保护）**
- 日限 15次 · 同好友日限 3次 · 冷却 10分钟
- 收益衰减：第1次100% → 第2次70% → 第3次40% → 第4次0%
- 大堆叠额外掉落（20%概率+1，10%概率再+1）
- 食材可上锁防翻 · 被翻者得补偿（1金+1人气）
- 新增 `TownDailyLog`/`TownFlipLog` 表：日限计数 + 翻柜记录

**蟑螂恶作剧（轻惩罚，非高压）**
- 日限 2次 · 对同一目标冷却 30分钟 · 单餐厅上限 3只
- 单只效果：封1桌 15分钟自动消失
- 卫生香氛设施：50%概率抵抗

**服务员系统（好友雇佣）**
- 雇好友 12小时/500金 · 加成：金币+3%/满意度+2%/速度-5%制作时间
- 含系统默认1名，星级决定总服务员位（0星1人 → 5星6人）
- 新增 `TownWaiter` 表

**设施系统（24小时增益）**
- 奖杯(经验+1) / 海报(金币+1) / 保鲜柜(防翻-50%) / 省油灶(耗油-10%) / 卫生香氛(蟑螂-50%)
- 设施位由星级决定（0星2位 → 5星7位）
- 新增 `TownFacility` 表

**页面与模板更新**
- `town/home.html`：完整餐厅概况（星级/油量/桌位/服务员/待办/营业入口）
- `town/recipes.html`：6级菜谱列表（学菜/烹饪/上架/升级预览）
- `town/recipe_detail.html`（新增）：菜谱详情（食材/学菜/烹饪/上架/品质升级）
- `town/oil.html`（新增）：油量管理（补油包/油壶扩容）
- `town/star.html`（新增）：升星页（当前星级/申请条件/星级效果）
- `town/waiter.html`（新增）：服务员管理（已雇佣/可雇佣好友）
- `town/facility.html`（新增）：设施管理（5类设施购买/生效状态）
- `town/serve_result.html`（新增）：营业结算（顾客流水明细）
- `town/visit.html`：翻橱柜（日限/冷却/保鲜柜/丢蟑螂/帮清理）
- `town/rules.html`：完整更新规则页（双主轴/6级菜/顾客/油量/翻柜/蟑螂/服务员/设施）

**API 扩展**
- `/api/town/state` 新增字段：`oil_cap`/`coins`/`total_service`/`total_revenue`/`fame`/`table_count`/`table_cap`/`waiter_total`/`cabinet_cap`/`facility_slots`/`picky_pct`/`rare_pct`/`revenue_coef`/`serving_tables`/`active_waiters`/`active_roaches`/`oil_pct`/`exp_needed`

**数据模型变更**
- `TownRecipe` 新增 `recipe_level`/`base_price`/`base_exp`/`base_oil`/`unlock_level`
- `TownState` 新增 `stars`/`oil_cap`/`coins`/`total_revenue`/`total_service`/`fame`/`table_count`/`last_oil_drain`
- 新增表：`TownRecipeProgress`(菜谱进度) / `TownDailyLog`(日限计数) / `TownFlipLog`(翻柜记录) / `TownWaiter`(服务员) / `TownCockroach`(蟑螂) / `TownFacility`(设施)

**端到端验证**
- ✅ 学菜 → 烹饪 → 出锅（消耗食材+油，得成品+熟练度+经验）
- ✅ 上架菜谱 → 营业结算（顾客消费，金币+经验，挑剔/稀有客）
- ✅ 菜谱升级品质（普通→极品→金牌，熟练度+金币+材料）
- ✅ 翻橱柜日限+冷却+收益衰减（第1-3次衰减100/70/40%）
- ✅ 油壶扩容（3000→4000）+ 补油包购买
- ✅ 缺油停业（油量0无法营业）
- ✅ 雇佣好友服务员（12小时，金币+3%加成）

---

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

**五个游戏模块（保留老味道点）**
- 阳光农场：成长计时 / 浇水除虫施肥 / 偷菜互助 / 成熟可收
- 美味小镇：食材短缺驱动互动 / 翻橱柜 / 添油营业 / 升星与挑剔客人
- 魔法花园：发芽-花苗-花蕾阶段操作 / 合成花种 / 花谱点亮 / 偷花送花
- 纵横四海：城市节点+航线推进 / 任务驱动 / 遭遇战斗结算 / 装备成长线
- 召唤之王：120图鉴抓捕 / 回合战斗 / 种族克制 / 段位推进 / 组队成长

**后台管理**
- 用户管理、模块上下架、商店商品管理、工单处理、操作日志查询
- 概览看板：用户数 / 待处理工单 / 消息量 / 模块状态

**JSON API 规范（16 端点）**
- 鉴权：`/api/login` `/api/register` `/api/me`
- 社交：`/api/friends` `/api/friends/add` `/api/friends/remove`
- 资源：`/api/inventory` `/api/shop/buy` `/api/messages`
- 平台能力：`/api/ranking` `/api/icons` `/api/events/emit`
- 模块状态：`/api/farm/state` `/api/town/state` `/api/garden/state` `/api/sea/state` `/api/summon/state`
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
│   │   ├── summon.py        #   ★ 召唤之王
│   │   ├── summon_data.py   #   召唤之王静态配置（120图鉴/60技能/地图/商店）
│   │   ├── admin.py         #   ★ 后台管理
│   │   ├── api.py           #   ★ JSON API 规范 (/api/*)
│   │   └── views.py         #   渲染助手（统一上下文）
│   ├── templates/           # Jinja2 WAP 模板（单列、列表为主、怀旧风）
│   │   ├── base.html / macros.html
│   │   ├── home.html / login.html / my_home.html ...
│   │   ├── farm/ town/ garden/ sea/ summon/ admin/ chat/ forum/ support/
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
| **美味小镇** | 食材短缺 / 翻橱柜 / 添油 / 升星挑剔客人 | 买食材→学菜烹饪→上架营业→油量管理→翻好友橱柜→升星解锁菜谱/桌位/服务员 |
| **魔法花园** | 阶段操作 / 合成花种 / 花谱点亮 / 偷花送花 | 买/合成花种→种入花盆(发芽/花苗/花蕾/盛开)→收获点亮花谱→偷花/送花 |
| **纵横四海** | 城市节点 / 航线推进 / 任务遭遇 / 装备成长 | 启航港出发→沿航线推进→港口自动生成任务→遭遇结算(战力影响)→买装备提升战力 |
| **召唤之王** | 120图鉴 / 回合战斗 / 种族克制 / 段位抓捕 | 进地图→刷关卡遭遇战→抓捕幻兽→组队→升级解锁段位→收集图鉴 |

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
| GET | `/api/summon/state` | 召唤之王状态（v0.1.2 新增） |

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
- 小镇：`town_recipes / town_recipe_progress / town_state / town_daily_logs / town_flip_logs / town_waiters / town_cockroaches / town_facilities`
- 花园：`garden_seeds / garden_blooms / garden_album_entries / garden_pots / garden_state / garden_collection / garden_recipes / garden_exchanges / garden_craft_credits / garden_daily_logs`
- 航海：`sea_cities / sea_routes / sea_equipment / sea_state / sea_quests / sea_user_equips`
- 召唤：`summon_state / summon_pets`（静态配置 120图鉴/60技能/地图/商店 见 `summon_data.py`）

---

## 七、玩法演示流程

### 阳光农场
1. `demo` 登录 → 游戏大厅 → 阳光农场
2. 快捷入口 → 种子商店 → 买萝卜种子
3. 农场背包确认有种子 → 我的农田 → 第1块地 → 种植
4. 浇水加速 → 等待成熟 → 收获(得萝卜×2 + 经验)
5. 给地块上锁 → 去 `lily` 的农场偷菜（被锁则偷不到）

### 美味小镇（v0.0.4 怀旧版）
1. 买食材 → 菜谱 → 学菜 → 烹饪（消耗食材+油，30-180秒）→ 出锅收菜（熟练度+1，经验+2）
2. 菜谱上架 → 营业接待（180秒周期，顾客消费，挑剔客/稀有客加成）
3. 菜谱升级：普通→极品→金牌（熟练度+金币+菜谱碎片+特殊调料，品质只升售价不升经验）
4. 油量管理：做菜+待机耗油 → 油量0停业 → 补油包/油壶扩容（3000→4000→…→8000）
5. 餐厅升星：0星→5星（等级+菜谱数+累计营业+累计收入，解锁桌位/服务员位/设施位）
6. 翻橱柜：日限15次/同好友3次/冷却10分钟，收益衰减100→70→40→0%
7. 雇好友服务员（12小时，金币+3%/满意度+2%）+ 设施增益（奖杯/海报/保鲜柜/省油灶/卫生香氛）

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

### 召唤之王（v0.0.5）
1. 初始幻兽（岩牙狼）自动上阵 → 世界地图选段位 → 挑战关卡（耗活力2/4）
2. 回合战斗：按速度序行动，技能+种族克制+暴击自动结算，胜利得金币+经验
3. 抓捕幻兽：消耗捕捉球（普通×1.0/强力×1.5/超级×2.2），成功率随稀有度下降
4. 幻兽仓库：上阵/下阵/放生（返还铜钱），查看属性与技能
5. 通关一段15关 → 自动进入下一段位（T1→T2…→T8）
6. 图鉴：120只按段位分组，未收集显示"？？？"
7. 等级解锁：Lv10擂台/Lv30魔魂/Lv35战灵/Lv40战场师徒/Lv60第4出战位

---

## 八、技术要点

- **平台与模块解耦**：模块绝不直接写平台表，全部通过 `platform/events.emit()` 上报，由平台统一判定点亮图标/推进成就/记排行/发消息。
- **物品字典统一**：`items` 表是唯一物品来源，商店只引用字典物品，禁止“匿名物品”。
- **背包分页**：`inventory.module_key` 实现 farm/town/garden/sea/summon 分页，统一入口。
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
