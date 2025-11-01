# passenger_wsgi.py
import sys, os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("FLASK_ENV", "production")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
from wsgi import app as application
