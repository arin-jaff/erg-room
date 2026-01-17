#!/bin/bash
# Pi Setup Script for RFID RC522 - "Who's In the Erg Room?"

set -e

echo "Setting up Erg Room RFID Presence Tracker..."

# Enable SPI if not already enabled
echo "Checking SPI..."
if ! lsmod | grep -q spi_bcm2835; then
    echo "Enabling SPI interface..."
    sudo raspi-config nonint do_spi 0
    echo "SPI enabled. A reboot may be required."
fi

# Verify SPI is available
if [ ! -e /dev/spidev0.0 ]; then
    echo "SPI device not found. Please reboot and run this script again."
    echo "   Run: sudo reboot"
    exit 1
fi

echo "✓ SPI is enabled"

# Update system
echo "Updating system packages..."
sudo apt update

# Install system dependencies
echo "Installing system dependencies..."
sudo apt install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    python3-rpi.gpio

# Create virtual environment with system packages
echo "Creating Python virtual environment..."
cd /home/arin/git/erg-room
rm -rf venv
python3 -m venv venv --system-site-packages
source venv/bin/activate

# Install Python dependencies
echo "Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

# Download HTMX
echo "Downloading HTMX..."
curl -sL https://unpkg.com/htmx.org@1.9.10/dist/htmx.min.js -o static/htmx.min.js

# Initialize database
echo "🗃️  Initializing database..."
python -c "from app.models import init_db; init_db()"

echo ""
echo "Setup complete!"
echo ""
echo "RC522 Wiring (Pi Zero 2 W):"
echo "  ┌─────────────┬─────────────┐"
echo "  │ RC522 Pin   │ Pi GPIO     │"
echo "  ├─────────────┼─────────────┤"
echo "  │ SDA         │ GPIO 8 (CE0)│"
echo "  │ SCK         │ GPIO 11     │"
echo "  │ MOSI        │ GPIO 10     │"
echo "  │ MISO        │ GPIO 9      │"
echo "  │ IRQ         │ (not used)  │"
echo "  │ GND         │ Ground      │"
echo "  │ RST         │ GPIO 25     │"
echo "  │ 3.3V        │ 3.3V ONLY!  │"
echo "  └─────────────┴─────────────┘"
echo ""
echo "To write IDs to RFID tags:"
echo "  python scripts/write_rfid_tag.py"
echo ""
echo "To run the app:"
echo "  cd /home/arin/git/erg-room"
echo "  source venv/bin/activate"
echo "  python run.py"
echo ""
echo "Then visit: http://$(hostname -I | awk '{print $1}'):5000"
