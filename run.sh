#!/usr/bin/env bash
# 启动 QQ家园平台
set -e
cd "$(dirname "$0")"

# v0.3.1 检测 Python ≥ 3.10（项目使用 AsyncSession | None 等 3.10+ 语法）
PY_BIN="python3"
if command -v python3.10 >/dev/null 2>&1; then PY_BIN="python3.10"; fi
if command -v python3.11 >/dev/null 2>&1; then PY_BIN="python3.11"; fi
if command -v python3.12 >/dev/null 2>&1; then PY_BIN="python3.12"; fi
if command -v python3.13 >/dev/null 2>&1; then PY_BIN="python3.13"; fi
VER=$("$PY_BIN" -c 'import sys;print(sys.version_info[1])' 2>/dev/null || echo 0)
if [ "$VER" -lt 10 ]; then
  echo "需要 Python ≥ 3.10（当前 $("$PY_BIN" --version 2>&1)），请安装高版本或使用 .venv" >&2
  exit 1
fi

"$PY_BIN" -m pip install -q -r requirements.txt
# seed 由应用 lifespan 按 SEED_ON_START 控制，此处不再单独跑
exec "$PY_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
