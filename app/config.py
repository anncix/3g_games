"""应用配置"""
from pathlib import Path

# 版本号
VERSION = "0.1.8"

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "qq_home.db"
DB_URL = f"sqlite+aiosqlite:///{DB_PATH}"

SECRET_KEY = "qq-home-nostalgia-secret-please-change-in-production"
SESSION_TTL_SECONDS = 7 * 24 * 3600  # 7 天
SESSION_COOKIE = "qq_home_token"

PLATFORM_CURRENCY = "金币"  # 平台公共货币

# 物品堆叠上限
STACK_LIMIT = 999
