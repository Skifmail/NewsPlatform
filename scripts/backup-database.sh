#!/usr/bin/env bash
# Создаёт дамп PostgreSQL из локального Docker Compose.
# Использование: ./scripts/backup-database.sh [путь/к/файлу.sql.gz]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
OUTPUT="${1:-$ROOT/deploy/backups/db-$(date +%Y%m%d-%H%M%S).sql.gz}"

mkdir -p "$(dirname "$OUTPUT")"

# shellcheck source=/dev/null
source <(grep -E '^(DB_USER|DB_NAME|DB_PASSWORD)=' .env 2>/dev/null || true)

DB_USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-content_platform}"

echo "→ Дамп БД ${DB_NAME} (compose: ${COMPOSE_FILE})"
docker compose -f "$COMPOSE_FILE" exec -T postgres \
  pg_dump -U "$DB_USER" -d "$DB_NAME" --no-owner --no-acl \
  | gzip -9 > "$OUTPUT"

echo "✓ Сохранено: $OUTPUT ($(du -h "$OUTPUT" | cut -f1))"
