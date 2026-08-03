# QQ家园 — 怀旧平台化复刻

> 版本：**v0.1.3** （2026-08-03 魔法花园对齐新版总纲：订单交易系统/品质5档/统一加成/价值体系）
>
> 基于 **FastAPI + SQLite + Jinja2(简版 WAP 风)** 实现的怀旧 QQ 家园平台复刻。
> 严格遵循《怀旧QQ家园平台设计规范》：平台统一、模块自治、旧逻辑优先、一页只做一件事。

包含：**前台 WAP 页面** + **后台管理系统** + **JSON API 规范** + **六个游戏模块**。

---

## 更新日志

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
