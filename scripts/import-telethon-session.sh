#!/usr/bin/env bash
# Импорт Telethon-сессии в production volume на VPS.
# Использование: ./scripts/import-telethon-session.sh deploy/backups/telethon-session.tar.gz
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <telethon-session.tar.gz>" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ARCHIVE="$1"

if [[ ! -f "$ARCHIVE" ]]; then
  echo "Файл не найден: $ARCHIVE" >&2
  exit 1
fi

PROJECT="$(docker compose -f "$COMPOSE_FILE" ps -q backend 2>/dev/null | head -1)"
if [[ -z "$PROJECT" ]]; then
  echo "Сначала запустите stack: docker compose -f $COMPOSE_FILE up -d" >&2
  exit 1
fi

VOLUME="$(docker compose -f "$COMPOSE_FILE" volume ls -q | grep telethon_session | head -1)"
if [[ -z "$VOLUME" ]]; then
  echo "Volume telethon_session не найден" >&2
  exit 1
fi

echo "→ Импорт в volume: $VOLUME"
docker run --rm -v "${VOLUME}:/data" -v "$(realpath "$ARCHIVE"):/archive.tar.gz:ro" alpine \
  sh -c "cd /data && tar xzf /archive.tar.gz"

docker compose -f "$COMPOSE_FILE" restart celery_worker backend
echo "✓ Telethon session импортирована"
