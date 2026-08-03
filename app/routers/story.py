"""v0.2.9 平台层剧情总览：聚合 8 个游戏模块的主线任务链

spec：平台化复刻（方案B）—— 游戏是平台里的内容层，剧情总览把各模块主线
串成统一的家园进度看板，落实"先到家园，再去游戏"的旧逻辑。
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user
from .views import render
from . import wap_layout as W
from . import platform_spec as P

router = APIRouter(tags=["剧情总览"])


def _normalize_quests(quests, module_key: str):
    """归一化各模块 MAIN_QUESTS 为统一 (sort, name, unlock_level, desc, reward) 五元组。

    兼容两种结构：
      - 标准（farm/town/summon/martial/fengyun/xyou/garden 无）: (sort, name, lv, desc, reward)
      - sea: (key, name, level, reward, sort)
    """
    out = []
    for q in quests:
        if len(q) == 5:
            a, b, c, d, e = q
            # sea 结构: (key, name, level, reward, sort)
            if isinstance(a, str) and isinstance(c, int) and isinstance(e, int):
                out.append((e, b, c, "", d))  # (sort, name, lv, desc, reward)
            else:
                # 标准: (sort, name, lv, desc, reward)
                out.append((a, b, c, d, e))
        elif len(q) == 4:
            # 兜底：某些模块可能是 4 元组
            a, b, c, d = q
            out.append((a if isinstance(a, int) else 0, b, c if isinstance(c, int) else 0, "", d))
        else:
            out.append((0, str(q), 0, "", ""))
    out.sort(key=lambda x: x[0])
    return out


def _load_all_quests() -> list[dict]:
    """惰性 import 各模块 MAIN_QUESTS，归一化为统一结构。"""
    from .farm import MAIN_QUESTS as farm_q
    from .town import MAIN_QUESTS as town_q
    from .summon_data import MAIN_QUESTS as summon_q
    from .martial_data import MAIN_QUESTS as martial_q
    from .fengyun_data import MAIN_QUESTS as fengyun_q
    from .xyou_data import MAIN_QUESTS as xyou_q
    from .sea_data import MAIN_QUESTS as sea_q

    # (key, 名称, 前缀, quests, 玩法循环)
    sources = [
        ("farm",    "阳光农场",   "/games/farm/mainquests",    farm_q,    "农牧经营"),
        ("town",    "美味小镇",   "/games/town/mainquests",    town_q,    "餐厅经营"),
        ("garden",  "魔法花园",   "/games/garden/quest",       [],        "花种养成（7步魔法任务链）"),
        ("sea",     "纵横四海",   "/games/sea/mainquests",     sea_q,     "航海RPG"),
        ("summon",  "召唤之王",   "/games/summon/mainquests",  summon_q,  "幻兽养成"),
        ("martial", "精武堂",     "/games/martial/mainquests", martial_q, "武侠RPG"),
        ("fengyun", "风云三国",   "/games/fengyun/mainquests", fengyun_q, "三国RPG"),
        ("xyou",    "幻想西游",   "/games/xyou/mainquests",    xyou_q,    "西游RPG"),
    ]
    result = []
    for key, name, href, quests, loop in sources:
        norm = _normalize_quests(quests, key)
        result.append({
            "key": key, "name": name, "href": href, "loop": loop,
            "quests": norm,
            "total": len(norm),
            "max_level": max((q[2] for q in norm), default=0),
        })
    return result


@router.get("/story")
async def story_overview(request: Request, db: AsyncSession = Depends(get_db)):
    """平台层剧情总览：聚合 8 模块主线任务链，统一家园进度看板。"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    modules = _load_all_quests()
    total_quests = sum(m["total"] for m in modules)
    # v0.3.0：剧情弧线 + 平台功能清单总览
    feats = P.feature_stats()
    return await render(request, "story.html", db, user=user,
                        modules=modules, total_quests=total_quests, W=W, P=P, feats=feats)
