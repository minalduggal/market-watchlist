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
    print("=========================================================")
    print("⚡ NEXUS TERMINAL // QUANTITATIVE WATCHLIST & TEMPORAL INTELLIGENCE")
    print("🚀 Launching server at: http://127.0.0.1:8000")
    print("💡 Open your web browser and navigate to the address above.")
    print("=========================================================")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False, log_level="info")
