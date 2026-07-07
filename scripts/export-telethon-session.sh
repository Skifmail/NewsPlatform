#!/usr/bin/env bash
# Экспорт Telethon-сессии из Docker volume (для переноса на VPS).
# Использование: ./scripts/export-telethon-session.sh [путь/к/archive.tar.gz]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
OUTPUT="${1:-$ROOT/deploy/backups/telethon-session-$(date +%Y%m%d).tar.gz}"

mkdir -p "$(dirname "$OUTPUT")"

PROJECT="$(basename "$ROOT" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9_-')"
VOLUME="${PROJECT}_telethon_session"

if ! docker volume inspect "$VOLUME" >/dev/null 2>&1; then
  VOLUME="$(docker volume ls -q | grep telethon_session | head -1)"
fi

if [[ -z "${VOLUME:-}" ]]; then
  echo "Volume telethon_session не найден. Пропускаем экспорт." >&2
  exit 0
fi

echo "→ Экспорт volume: $VOLUME"
docker run --rm -v "${VOLUME}:/data:ro" -v "$(dirname "$OUTPUT"):/out" alpine \
  sh -c "cd /data && tar czf /out/$(basename "$OUTPUT") . 2>/dev/null || true"

if [[ -f "$OUTPUT" ]] && [[ -s "$OUTPUT" ]]; then
  echo "✓ Сохранено: $OUTPUT ($(du -h "$OUTPUT" | cut -f1))"
else
  echo "⚠ Сессия пуста или не авторизована — перенос не требуется"
  rm -f "$OUTPUT"
fi
