#!/usr/bin/env sh
set -eu
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
printf 'Environment ready. Set secrets in .env and start with python backend/app.py\n'
