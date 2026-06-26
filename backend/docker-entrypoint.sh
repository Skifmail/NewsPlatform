#!/bin/sh
set -e

if [ "${SKIP_MIGRATIONS:-0}" != "1" ]; then
  echo "Waiting for PostgreSQL..."
  until python -c "
import sys
from sqlalchemy import create_engine, text
from app.core.config import get_settings
engine = create_engine(get_settings().database_url_sync, pool_pre_ping=True)
with engine.connect() as conn:
    conn.execute(text('SELECT 1'))
" 2>/dev/null; do
    sleep 2
  done

  echo "Running Alembic migrations..."
  alembic upgrade head
fi

exec "$@"
