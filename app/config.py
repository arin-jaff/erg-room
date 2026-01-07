import os
from pathlib import Path
import hashlib
import time

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
DB_PATH = DATA_DIR / "presence.db"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Scanner settings
SCAN_INTERVAL = 0.3          # Seconds between RFID reads
DEBOUNCE_SECONDS = 3         # Ignore same tag within this window

# Web settings
WEB_HOST = "0.0.0.0"         # Accessible from network
WEB_PORT = 5000
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")

# Admin password (change this!)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ergroom2024")

# Upload settings
MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB max upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Auto-checkout: mark people as "out" after X hours of no activity
AUTO_CHECKOUT_HOURS = 5


def generate_uuid() -> str:
    """Generate a unique ID using timestamp and hash (no external modules)."""
    # Combine timestamp with some randomness from memory address
    seed = f"{time.time_ns()}-{id(object())}-{os.getpid()}"
    hash_hex = hashlib.sha256(seed.encode()).hexdigest()
    # Return first 12 chars for a readable UUID
    return hash_hex[:12]


# RFID RC522 GPIO pins (directly connected to Pi, these are default pins)
# SDA  -> GPIO 8  (CE0)
# SCK  -> GPIO 11 (SCLK)
# MOSI -> GPIO 10 (MOSI)
# MISO -> GPIO 9  (MISO)
# RST  -> GPIO 25
# GND  -> Ground
# 3.3V -> 3.3V (NOT 5V!)
