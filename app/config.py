import os
from pathlib import Path
import hashlib
import time
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
DB_PATH = DATA_DIR / "presence.db"

DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SCAN_INTERVAL = 0.3
DEBOUNCE_SECONDS = 3

WEB_HOST = "0.0.0.0"
WEB_PORT = 5000
SECRET_KEY = os.environ.get("SECRET_KEY")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

if not SECRET_KEY or not ADMIN_PASSWORD:
    raise ValueError("SECRET_KEY and ADMIN_PASSWORD must be set in .env file")

MAX_CONTENT_LENGTH = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

AUTO_CHECKOUT_HOURS = 5


def generate_uuid() -> str:
    seed = f"{time.time_ns()}-{id(object())}-{os.getpid()}"
    hash_hex = hashlib.sha256(seed.encode()).hexdigest()
    return hash_hex[:12]


# RC522 GPIO pin reference (directly connected to Raspberry Pi)
# SDA->GPIO8, SCK->GPIO11, MOSI->GPIO10, MISO->GPIO9, RST->GPIO25, 3.3V (not 5V)
