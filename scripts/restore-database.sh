#!/usr/bin/env bash
# Восстанавливает дамп PostgreSQL в production/staging compose.
# Использование: ./scripts/restore-database.sh deploy/backups/db-....sql.gz
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <dump.sql.gz>" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
DUMP="$1"

if [[ ! -f "$DUMP" ]]; then
  echo "Файл не найден: $DUMP" >&2
  exit 1
fi

DB_USER="$(grep -E '^DB_USER=' .env 2>/dev/null | cut -d= -f2- | tr -d '"' || echo postgres)"
DB_NAME="$(grep -E '^DB_NAME=' .env 2>/dev/null | cut -d= -f2- | tr -d '"' || echo content_platform)"

echo "→ Остановка backend и workers..."
docker compose -f "$COMPOSE_FILE" stop celery_worker celery_beat backend 2>/dev/null || true

echo "→ Пересоздание БД ${DB_NAME}..."
docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1 <<-PSQL
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '${DB_NAME}' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS ${DB_NAME};
CREATE DATABASE ${DB_NAME};
PSQL

echo "→ Импорт дампа..."
gunzip -c "$DUMP" | docker compose -f "$COMPOSE_FILE" exec -T postgres \
  psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -q

echo "→ Запуск сервисов..."
docker compose -f "$COMPOSE_FILE" up -d

echo "✓ Восстановление завершено"
