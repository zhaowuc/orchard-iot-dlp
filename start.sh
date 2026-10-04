#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
fi
.venv/bin/python manage.py migrate
exec .venv/bin/python manage.py runserver 127.0.0.1:8000

