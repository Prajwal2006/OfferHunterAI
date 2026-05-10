"""Root ASGI entrypoint for local development.

This keeps `uvicorn main:app` working when launched from the repository root.
The actual FastAPI app lives in `backend/main.py`.
"""
from pathlib import Path
import sys

backend_root = Path(__file__).resolve().parent / "backend"
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from backend.main import app
