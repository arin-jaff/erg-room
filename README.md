# 🚣 Who's In the Erg Room?

A Raspberry Pi-powered presence tracker for your team's workout room. Teammates scan their personal QR code to check in/out, and a live webpage shows who's currently erging.

## Features

- **QR Code scanning** - Low-power continuous scanning (~1-2 FPS)
- **Toggle in/out** - One scan checks in, next scan checks out
- **Live web display** - Updates every 3 seconds via HTMX
- **Auto-checkout** - Automatically marks people as "out" after 4 hours
- **Mobile-friendly** - Works great on phones and tablets

## Hardware Requirements

- Raspberry Pi Zero 2 W (or any Pi with camera support)
- Pi Camera Module (v2 or HQ Camera)
- Power supply
- Optional: Case with camera mount

## Quick Start

### 1. Clone to your Pi

```bash
cd /home/arin/git
# rsync from your dev machine, or:
git clone <your-repo> erg-room
cd erg-room
```

### 2. Run the install script

```bash
chmod +x scripts/install.sh
./scripts/install.sh
```

### 3. Edit team members

```bash
nano app/config.py
# Update TEAM_MEMBERS list with your teammates
```

### 4. Regenerate QR codes

```bash
source venv/bin/activate
python scripts/generate_qrcodes.py
```

### 5. Start the app

```bash
python run.py
```

Visit `http://<pi-ip>:5000` to see the display!

## Configuration

Edit `app/config.py` to customize:

```python
# Team members - add your whole crew!
TEAM_MEMBERS = [
    {"id": "rower001", "name": "Arin"},
    {"id": "rower002", "name": "Alex"},
    # ...
]

# Scanner settings
SCAN_INTERVAL = 0.5      # Seconds between scans
DEBOUNCE_SECONDS = 5     # Ignore repeated scans within this window
AUTO_CHECKOUT_HOURS = 4  # Auto-checkout after this many hours
```

## Auto-Start on Boot

```bash
sudo cp erg-room.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable erg-room
sudo systemctl start erg-room
```

## Development

Run without camera (test mode):

```bash
python run.py --no-camera --debug
```

Use the admin panel at `/admin` to simulate scans.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main presence display |
| `/admin` | GET | Admin panel |
| `/api/present` | GET | JSON list of present members |
| `/api/all` | GET | JSON list of all members |
| `/api/simulate/<id>` | POST | Simulate a scan (testing) |

## QR Code Distribution

After running `generate_qrcodes.py`, you'll find PNG files in `qrcodes/`:

- Print them on cardstock for lanyards
- Or have teammates save the image to their phone's home screen
- Each code is just the member ID (e.g., "rower001")

## Troubleshooting

**Camera not detected:**
```bash
sudo raspi-config
# Interface Options -> Camera -> Enable
sudo reboot
```

**Web page not loading:**
```bash
# Check if service is running
sudo systemctl status erg-room

# View logs
journalctl -u erg-room -f
```

**QR codes not scanning:**
- Ensure good lighting
- Hold QR code 6-12 inches from camera
- Check camera focus (Pi Camera v2 has fixed focus)

## Power Consumption

The Pi Zero 2 W with camera running this app draws approximately:
- Idle (waiting for QR): ~1.0W
- Active scanning: ~1.2-1.5W

A standard USB power bank will run this for 10+ hours.

## License

MIT - Do whatever you want with it! 🚣
