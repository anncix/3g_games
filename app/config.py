"""应用配置"""
import os
from pathlib import Path

# 版本号
VERSION = "0.3.1"

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "qq_home.db"
DB_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# v0.3.1 安全：SECRET_KEY 优先读环境变量，未配置时用默认值（仅本地开发）
SECRET_KEY = os.environ.get("QQ_HOME_SECRET_KEY", "qq-home-nostalgia-secret-please-change-in-production")
SESSION_TTL_SECONDS = 7 * 24 * 3600  # 7 天
SESSION_COOKIE = "qq_home_token"
# v0.3.1 安全：cookie samesite=lax 防 CSRF（POST 表单跨站不自动带 cookie）
SESSION_COOKIE_SAMESITE = os.environ.get("QQ_HOME_COOKIE_SAMESITE", "lax")
SESSION_COOKIE_SECURE = os.environ.get("QQ_HOME_COOKIE_SECURE", "0") == "1"

# v0.3.1 工程化：启动是否自动跑 seed（生产建议关，改用 CLI）
SEED_ON_START = os.environ.get("QQ_HOME_SEED_ON_START", "1") == "1"

# v0.3.1 安全：登录限流（同 IP 每窗口最大失败次数）
LOGIN_RATE_LIMIT = int(os.environ.get("QQ_HOME_LOGIN_RATE_LIMIT", "10"))  # 次
LOGIN_RATE_WINDOW = int(os.environ.get("QQ_HOME_LOGIN_RATE_WINDOW", "600"))  # 秒

PLATFORM_CURRENCY = "金币"  # 平台公共货币

# 物品堆叠上限
STACK_LIMIT = 999
