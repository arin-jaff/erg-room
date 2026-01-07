# erg-room-rfid

RFID-based tracker for a shared workout space. Users tap an RFID tag to a MC522 module connected to a RasPi to check in/out, and a web interface displays who is currently present.

## Requirements

- Raspberry Pi (tested on Zero 2 W)
- RC522 RFID module
- RFID tags (13.56MHz MIFARE)
- Python 3.9+

## Installation

```bash
# Enable SPI
sudo raspi-config  # Interface Options > SPI > Enable
sudo reboot

# Install system dependencies
sudo apt install -y python3-pip python3-venv python3-rpi.gpio

# Clone and setup
cd /home/pi/git
git clone <repo> erg-room
cd erg-room
python3 -m venv venv --system-site-packages
source venv/bin/activate
pip install -r requirements.txt

# Initialize database
python -c "from app.models import init_db; init_db()"

# Run
python run.py
```

## Wiring

```
RC522 Pin    Pi GPIO
---------    -------
SDA          GPIO 8 (CE0)
SCK          GPIO 11
MOSI         GPIO 10
MISO         GPIO 9
RST          GPIO 25
GND          Ground
3.3V         3.3V (not 5V)
```

## Usage

### Registering a new tag

1. Go to `/admin/login` and enter the admin password (default: `REDACTED_PASSWORD`)
2. Click "Start Registration Mode"
3. Tap a blank RFID tag on the reader
4. The tag ID appears under "Pending Tags"
5. Enter a name and click "Create"

### Checking in/out

Users tap their registered tag on the reader. The system toggles their status between in and out.

### Editing profiles

Users can log in at `/login` with their tag ID to change their name or upload a profile picture. They cannot change their tag ID.

Admins can edit any field including the tag ID at `/admin/member/<id>/edit`.

## Configuration

Edit `app/config.py`:

- `ADMIN_PASSWORD` - password for admin panel
- `AUTO_CHECKOUT_HOURS` - automatically check out users after this many hours (default: 5)
- `DEBOUNCE_SECONDS` - ignore repeat scans within this window (default: 3)

## Endpoints

| Path | Description |
|------|-------------|
| `/` | Main display showing who is present |
| `/login` | User login to edit profile |
| `/profile` | User profile page |
| `/admin/login` | Admin login |
| `/admin` | Admin panel for registration and member management |

## File structure

```
app/
  config.py      - Configuration
  models.py      - Database operations
  rfid_scanner.py - RFID reading logic
  web.py         - Flask routes
templates/       - HTML templates
static/          - CSS and JS
data/            - SQLite database (created at runtime)
```

## Test mode

Run without RFID hardware:

```bash
python run.py --no-rfid
```

Use the admin panel to simulate scans.
