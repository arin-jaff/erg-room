# Erg Room

RFID-based attendance tracker for Columbia Lightweight Rowing's erg room. Users tap an RFID tag on an RC522 reader connected to a Raspberry Pi to check in/out, and a web interface displays who is currently present, tracks hours, and provides leaderboards.

## Tech Stack

- **Backend:** Flask, SQLite (WAL mode), Gunicorn
- **Frontend:** Jinja2, HTMX, custom CSS (Columbia blue theme)
- **Hardware:** RC522 RFID module on Raspberry Pi (SPI)
- **Auth:** SHA-256 password hashing, TOTP 2FA (pyotp), session-based auth
- **Monitoring:** Health check script with email alerting

## Requirements

- Raspberry Pi (tested on Zero 2 W)
- RC522 RFID module + 13.56MHz MIFARE tags
- Python 3.9+

## Installation

### Raspberry Pi Setup

```bash
# Enable SPI
sudo raspi-config  # Interface Options > SPI > Enable
sudo reboot

# Install system dependencies
sudo apt install -y python3-pip python3-venv python3-rpi.gpio

# Clone and setup
git clone <repo> erg-room
cd erg-room
python3 -m venv venv --system-site-packages
source venv/bin/activate
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root:

```
SECRET_KEY=your-secret-key-here
ADMIN_PASSWORD=your-admin-password-here
ADMIN_TOTP_SECRET=your-totp-secret-here   # optional, enables 2FA for admin
```

Generate a TOTP secret for 2FA:

```bash
python3 -c "import pyotp; print(pyotp.random_base32())"
```

Add the secret to your authenticator app (Google Authenticator, Authy, etc.) manually or via provisioning URI:

```bash
python3 -c "import pyotp; print(pyotp.totp.TOTP('YOUR_SECRET').provisioning_uri('admin', issuer_name='ErgRoom'))"
```

### RC522 Wiring

```
RC522 Pin    Pi GPIO
---------    -------
SDA          GPIO 8 (CE0)
SCK          GPIO 11
MOSI         GPIO 10
MISO         GPIO 9
RST          GPIO 25
GND          Ground
3.3V         3.3V (NOT 5V)
```

## Running

```bash
python run.py              # RFID enabled (production)
python run.py --no-rfid    # Test mode, no hardware needed
python run.py --debug      # Flask debug mode
python run.py --port 8080  # Custom port
```

The app runs on `http://0.0.0.0:5000` by default.

## User Guide

### Registering a New Member

1. Go to `/admin/login` and sign in
2. Click **Start Registration Mode**
3. Tap a blank RFID tag on the reader
4. The tag ID appears under **Pending Tags**
5. Enter the member's name, category, and boat class, then click **Create**

### Checking In / Out

Tap a registered tag on the reader. The system toggles the member's status between IN and OUT. Session time is tracked and accumulated on checkout.

If a member forgets to check out, they are automatically checked out after 5 hours with no time credited.

### User Accounts

Members sign in to the web UI for the first time using their card ID. They are then prompted to create a **username and password**, which becomes their primary login method going forward.

On their profile page, users can:
- Update their rowing category
- Upload a profile photo
- Change their password
- Check out virtually (without scanning)

### Leaderboard

The leaderboard at `/leaderboard` shows top rowers by total hours, broken down by boat class (1V, 2V, 3V+). It is password-protected.

### Operating Hours

The tracker enforces operating hours of **6 AM - 10 PM** (Pi's local timezone). Outside these hours, a static "closed" page is served to minimize network traffic. Admin pages remain accessible.

## Admin Features

- **Member management:** Create, edit, delete members. Change names, categories, boat classes, UUIDs, passwords, and passkeys.
- **Registration mode:** Write UUIDs to blank RFID tags.
- **Lightweight mode:** Filter the home page to only show lightweight (LM) rowers.
- **Scan simulation:** Test check-ins without hardware.
- **Device stats:** View CPU, memory, disk, temperature, and uptime.
- **Network status:** View WiFi SSID, signal strength, IP addresses, and connectivity.
- **Database viewer:** Browse and edit raw database tables.

### Admin Security

- Rate-limited login (5 attempts per 15 minutes per IP)
- Timing-safe password comparison
- Optional TOTP 2FA via authenticator app

## Deployment

### Syncing to Pi

The included `sync.sh` script deploys code without overwriting the database:

```bash
./sync.sh
```

This uses `rsync` to push to the Pi while excluding `data/`, `*.db`, `.env`, `__pycache__/`, and `venv/`.

### Health Check

`healthcheck.py` runs on a separate machine and monitors the public site periodically. If it detects a bad gateway or downtime, it sends an email alert via macOS Mail.

```bash
python3 healthcheck.py
```

### Setting Timezone

Ensure the Pi is set to EST for correct timestamps:

```bash
sudo timedatectl set-timezone America/New_York
```

## Database

SQLite with WAL journal mode and `synchronous=FULL` for crash safety. The database is created automatically at `data/presence.db` on first run.

**Tables:**

| Table | Purpose |
|-------|---------|
| `members` | User profiles, credentials, hours |
| `presence` | Current check-in/out state |
| `scan_log` | Activity history |
| `pending_tags` | Tags awaiting member assignment |
| `settings` | App settings (e.g. lightweight mode) |

On startup, the app runs migrations to add any new columns and repairs any missing presence records.

## Endpoints

### Public

| Path | Description |
|------|-------------|
| `/` | Home page - who's in the erg room |
| `/login` | User sign-in (username/password or card ID) |
| `/setup` | First-time account creation |
| `/profile` | User profile and settings |
| `/members` | Member directory |
| `/members/<id>` | Individual member profile |
| `/leaderboard` | Leaderboard (password-protected) |
| `/closed` | Closed hours page |

### API

| Path | Description |
|------|-------------|
| `/api/present` | JSON: currently present members |
| `/api/last_scan` | JSON: most recent scan info |
| `/api/scan_history` | JSON: last 10 scans |
| `/api/lightweight_mode` | JSON: lightweight mode status |

### Admin

| Path | Description |
|------|-------------|
| `/admin/login` | Admin authentication |
| `/admin` | Admin dashboard |
| `/admin/member/<id>/edit` | Edit member |
| `/admin/device` | Device statistics |
| `/admin/device/network` | Network status |
| `/admin/device/table/<name>` | Database table viewer |

## Project Structure

```
erg-room/
├── run.py                  # Entry point
├── healthcheck.py          # External monitoring
├── requirements.txt        # Dependencies
├── .env                    # Secrets (not committed)
├── app/
│   ├── config.py           # Configuration
│   ├── models.py           # Database operations
│   ├── rfid_scanner.py     # RFID hardware interface
│   └── web.py              # Flask routes & views
├── templates/              # 17 Jinja2 templates
├── static/
│   ├── style.css           # Stylesheet
│   ├── htmx.min.js         # HTMX library
│   ├── c150lion1.png       # Columbia Lions logo
│   └── uploads/            # User photos (runtime)
├── scripts/
│   ├── setup_rfid.sh       # Pi environment setup
│   ├── sync.sh             # Deploy to Pi
│   └── write_rfid_tag.py   # RFID tag writer utility
└── data/
    └── presence.db         # SQLite database (runtime)
```

## Configuration Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `SECRET_KEY` | (required) | Flask session secret |
| `ADMIN_PASSWORD` | (required) | Admin panel password |
| `ADMIN_TOTP_SECRET` | (optional) | TOTP secret for admin 2FA |
| `AUTO_CHECKOUT_HOURS` | 5 | Auto-checkout threshold |
| `DEBOUNCE_SECONDS` | 3 | Ignore repeat scans within window |
| `SCAN_INTERVAL` | 0.3s | RFID polling interval |
| `WEB_PORT` | 5000 | HTTP port |
| `MAX_CONTENT_LENGTH` | 5 MB | Max upload size |

## Test Mode

Run without RFID hardware for development:

```bash
python run.py --no-rfid
```

Use the admin panel to simulate scans and test registrations.
