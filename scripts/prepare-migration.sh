#!/usr/bin/env bash
# Полный экспорт для миграции на VPS: БД + Telethon session.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="$ROOT/deploy/backups/migration-$STAMP"

mkdir -p "$DEST"

"$ROOT/scripts/backup-database.sh" "$DEST/database.sql.gz"
"$ROOT/scripts/export-telethon-session.sh" "$DEST/telethon-session.tar.gz" || true

if [[ -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env" "$DEST/env.backup"
  echo "✓ Копия .env: $DEST/env.backup (храните в безопасном месте!)"
fi

echo ""
echo "════════════════════════════════════════"
echo " Пакет миграции: $DEST"
echo "════════════════════════════════════════"
echo "Скопируйте на VPS:"
echo "  scp -r $DEST user@YOUR_VPS:/opt/newsplatform-migration/"
echo ""
