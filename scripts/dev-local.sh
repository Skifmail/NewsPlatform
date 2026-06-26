#!/usr/bin/env bash
# Локальный запуск backend + frontend в одном терминале.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  if [[ -n "${FRONTEND_PID}" ]]; then
    kill "${FRONTEND_PID}" 2>/dev/null || true
  fi
  if [[ -n "${BACKEND_PID}" ]]; then
    kill "${BACKEND_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if [[ ! -f "${ROOT}/.env" ]]; then
  echo "Создайте .env: cp .env.example .env"
  exit 1
fi

# backend читает .env из корня репозитория (см. app/core/config.py)
ln -sf "${ROOT}/.env" "${ROOT}/backend/.env"

# Переменные для backend на хосте (не внутри docker-сети)
set -a
# shellcheck disable=SC1091
source "${ROOT}/.env"
set +a

export DB_HOST=localhost
export REDIS_URL=redis://127.0.0.1:6379/0
export DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
export DATABASE_URL_SYNC="postgresql+psycopg2://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

echo "==> Redis (docker, если доступен)"
if command -v docker >/dev/null 2>&1; then
  docker compose -f "${ROOT}/docker-compose.yml" up -d redis 2>/dev/null || true
fi

if ss -tln 2>/dev/null | grep -q ':5432'; then
  echo "==> PostgreSQL: порт 5432 занят (локальный или docker)"
  echo "    Убедитесь, что DB_PASSWORD в .env совпадает с паролем пользователя ${DB_USER}"
else
  echo "==> PostgreSQL (docker)"
  if command -v docker >/dev/null 2>&1; then
    docker compose -f "${ROOT}/docker-compose.yml" up -d postgres || true
  fi
fi

echo "==> Backend (http://127.0.0.1:8000)"
cd "${ROOT}/backend"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi
PYTHONPATH=. .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

echo "==> Frontend (http://127.0.0.1:5173)"
cd "${ROOT}/frontend"
if [[ ! -d node_modules ]]; then
  npm install
fi
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Панель:   http://127.0.0.1:5173"
echo "Вход:     ADMIN_USERNAME / ADMIN_PASSWORD из ${ROOT}/.env"
echo "API docs: http://127.0.0.1:8000/docs"
echo ""
echo "Если 500 на /api/* — проверьте пароль PostgreSQL (DB_PASSWORD) и миграции:"
echo "  cd backend && PYTHONPATH=. .venv/bin/alembic upgrade head"
echo "Ctrl+C — остановить backend и frontend"
echo ""

wait "${BACKEND_PID}" "${FRONTEND_PID}"
