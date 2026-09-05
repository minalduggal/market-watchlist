#!/usr/bin/env bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}
