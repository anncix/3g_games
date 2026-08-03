"""平台公共服务：模块只能通过这些服务与平台交互

对应规范 4.x / 5.5：
- 模块不得自建好友体系，只能通过 friends 服务
- 模块只能上报事件（emit_event），不可直接修改 消息/活动/图标/成就/排行
- 物品必须经物品字典 + inventory，禁止匿名物品
"""
from . import friends, locks, goods, icons, events, ranking, log

__all__ = ["friends", "locks", "goods", "icons", "events", "ranking", "log"]
