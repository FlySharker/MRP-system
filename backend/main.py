"""Local runner for the backend API."""

from __future__ import annotations
from backend.app import app
import uvicorn
import threading
import webbrowser
import time

def open_browser():
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:8000")

def main():
    threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        reload=False,
        access_log=False,
        log_config=None
    )

if __name__ == "__main__":
    main()
