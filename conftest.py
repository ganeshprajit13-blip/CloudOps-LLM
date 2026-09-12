import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "backend"

# Ensure backend directory is first in sys.path so 'app' imports resolve to backend/app
if str(BACKEND_DIR) in sys.path:
    sys.path.remove(str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR))

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
