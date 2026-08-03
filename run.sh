#!/usr/bin/env bash
# 启动 QQ家园平台
set -e
cd "$(dirname "$0")"
pip install -q -r requirements.txt
python3 -c "import asyncio; from app import seed; asyncio.run(seed.seed())" 2>/dev/null || true
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
