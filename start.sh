#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
exec uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
