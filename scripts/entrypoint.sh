#!/usr/bin/env bash
set -euo pipefail

echo "Waiting for PostgreSQL at ${DB_HOST:-localhost}:${DB_PORT:-5432}..."
python - <<'PY'
import asyncio
import os
import sys

import asyncpg

host = os.environ.get("DB_HOST", "localhost")
port = int(os.environ.get("DB_PORT", "5432"))
user = os.environ.get("DB_USER", "crickbuzz")
password = os.environ.get("DB_PASSWORD", "crickbuzz")
database = os.environ.get("DB_NAME", "crickbuzz")

async def wait() -> None:
    for attempt in range(60):
        try:
            conn = await asyncpg.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                timeout=3,
            )
            await conn.close()
            print("PostgreSQL is ready.")
            return
        except Exception as exc:
            print(f"  attempt {attempt + 1}/60: {exc}", file=sys.stderr)
            await asyncio.sleep(2)
    print("Timed out waiting for PostgreSQL.", file=sys.stderr)
    sys.exit(1)

asyncio.run(wait())
PY

echo "Running database bootstrap (create tables if missing)..."
python -m app.db.init_db

echo "Starting FastAPI..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
