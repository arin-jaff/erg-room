import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
QRCODE_DIR = BASE_DIR / "qrcodes"
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
DB_PATH = DATA_DIR / "presence.db"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
QRCODE_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Scanner settings
SCAN_INTERVAL = 0.5          # Seconds between scans (2 FPS)
FRAME_WIDTH = 320            # Low res for efficiency
FRAME_HEIGHT = 240
DEBOUNCE_SECONDS = 5         # Ignore same QR within this window

# Web settings
WEB_HOST = "0.0.0.0"         # Accessible from network
WEB_PORT = 5000
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")

# Upload settings
MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB max upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Team members - edit this list!
# Format: {"id": "unique_code", "name": "Display Name"}
TEAM_MEMBERS = [
    {"id": "sallen", "name": "Sam Allen"},
    {"id": "oanawalt", "name": "Owen Anawalt"},
    {"id": "ebayer", "name": "Eli Bayer"},
    {"id": "jbiton", "name": "Jaime Biton"},
    {"id": "ablelloch", "name": "Andrew Blelloch"},
    {"id": "obletoux", "name": "Oscar Bletoux"},
    {"id": "acallanan", "name": "Avril Callanan"},
    {"id": "mchilkoti", "name": "Mrin Chilkoti"},
    {"id": "rclaytor", "name": "Ross Claytor"},
    {"id": "rconway", "name": "Ravi Conway"},
    {"id": "gcortes", "name": "Gonzalo Cortes"},
    {"id": "jdodman", "name": "James Dodman"},
    {"id": "sengland", "name": "Sydney England"},
    {"id": "pfinnerty", "name": "Patrick Finnerty"},
    {"id": "sfleming", "name": "Spencer Fleming"},
    {"id": "ogeiger", "name": "Owen Geiger"},
    {"id": "wgokey", "name": "William Gokey"},
    {"id": "ehabboosh", "name": "Edward Habboosh"},
    {"id": "eholmes", "name": "Ethan Holmes"},
    {"id": "ajaff", "name": "Arin Jaff"},
    {"id": "pjosenhaus", "name": "Paul Josenhaus"},
    {"id": "alagasse", "name": "Amir LaGasse"},
    {"id": "dlasso", "name": "Diego Lasso"},
    {"id": "elee", "name": "Ethan Lee"},
    {"id": "jmoncur", "name": "James Moncur"},
    {"id": "dmullick", "name": "Diya Mullick"},
    {"id": "nnacic", "name": "Nikola Nacic"},
    {"id": "jpark", "name": "Jane Park"},
    {"id": "bpesin", "name": "Barnett Pesin"},
    {"id": "gpesin", "name": "George Pesin"},
    {"id": "nrao", "name": "Nitin Rao"},
    {"id": "fregan", "name": "Finn Regan"},
    {"id": "bsavell", "name": "Brendan Savell"},
    {"id": "dschaffer", "name": "Danny Schaffer"},
    {"id": "bsommer", "name": "Ben Sommer"},
    {"id": "ssubramaniam", "name": "Sam Subramaniam"},
    {"id": "stharp", "name": "Sam Tharp"},
    {"id": "atimblo", "name": "Adi Timblo"},
    {"id": "tvalentino", "name": "Tony Valentino"},
    {"id": "pwalter", "name": "Peter Walter"},
    {"id": "jwang", "name": "Josh Wang"},
    {"id": "kwilliams", "name": "Kuba Williams"},
    {"id": "swilson", "name": "Sam Wilson"},
    {"id": "rwu", "name": "Ray Wu"},
]

# Auto-checkout: mark people as "out" after X hours of no activity
AUTO_CHECKOUT_HOURS = 5
