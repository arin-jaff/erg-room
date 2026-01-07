import os
from pathlib import Path

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

# Upload settings
MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB max upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Team members - edit this list!
# Format: {"id": "unique_code", "name": "Display Name"}
# The "id" should match what's written to the RFID tag
TEAM_MEMBERS = [
    {"id": "rower001", "name": "Arin"},
    {"id": "rower002", "name": "Teammate 2"},
    {"id": "rower003", "name": "Teammate 3"},
    {"id": "rower004", "name": "Teammate 4"},
    {"id": "rower005", "name": "Teammate 5"},
    {"id": "rower006", "name": "Teammate 6"},
    {"id": "rower007", "name": "Teammate 7"},
    {"id": "rower008", "name": "Teammate 8"},
    # Add more as needed...
]

# Auto-checkout: mark people as "out" after X hours of no activity
AUTO_CHECKOUT_HOURS = 5

# RFID RC522 GPIO pins (directly connected to Pi, these are default pins)
# SDA  -> GPIO 8  (CE0)
# SCK  -> GPIO 11 (SCLK)
# MOSI -> GPIO 10 (MOSI)
# MISO -> GPIO 9  (MISO)
# RST  -> GPIO 25
# GND  -> Ground
# 3.3V -> 3.3V (NOT 5V!)
