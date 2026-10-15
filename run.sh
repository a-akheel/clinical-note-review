#!/bin/sh
set -eu
umask 077
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
fi
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi
exec .venv/bin/python -m uvicorn app.main:app --no-access-log --host 127.0.0.1 --port "${PORT:-8765}"
