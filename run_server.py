"""
Runner script for Smart Market Watchlist.
Boots the FastAPI application on http://127.0.0.1:8000.
"""

import uvicorn
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"
    print("=========================================================")
    print("⚡ NEXUS TERMINAL // QUANTITATIVE WATCHLIST & TEMPORAL INTELLIGENCE")
    print(f"🚀 Launching server on {host}:{port}")
    print("=========================================================")
    uvicorn.run("app.main:app", host=host, port=port, reload=False, log_level="info")
