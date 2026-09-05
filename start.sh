#!/usr/bin/env bash
set -e

echo "==> Starting NEXUS Terminal application..."

if [ -f "/opt/render/project/src/.venv/bin/uvicorn" ]; then
    echo "==> Using Render virtualenv uvicorn at /opt/render/project/src/.venv/bin/uvicorn"
    exec /opt/render/project/src/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
elif [ -n "$VIRTUAL_ENV" ] && [ -f "$VIRTUAL_ENV/bin/uvicorn" ]; then
    echo "==> Using VIRTUAL_ENV uvicorn at $VIRTUAL_ENV/bin/uvicorn"
    exec "$VIRTUAL_ENV/bin/uvicorn" app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
elif command -v uvicorn >/dev/null 2>&1; then
    echo "==> Using PATH uvicorn"
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
elif [ -f "/opt/render/project/src/.venv/bin/python" ]; then
    echo "==> Using Render virtualenv python at /opt/render/project/src/.venv/bin/python"
    exec /opt/render/project/src/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
else
    echo "==> Searching for python with uvicorn..."
    for py in python3 python /usr/bin/python3; do
        if $py -c "import uvicorn" >/dev/null 2>&1; then
            echo "==> Found uvicorn with $py"
            exec $py -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
        fi
    done
    echo "==> ERROR: Could not find uvicorn in any python environment."
    exit 1
fi
