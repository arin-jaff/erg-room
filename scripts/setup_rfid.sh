#!/bin/bash
set -e

echo "Setting up Erg Room RFID Presence Tracker..."

echo "Checking SPI..."
if ! lsmod | grep -q spi_bcm2835; then
    echo "Enabling SPI interface..."
    sudo raspi-config nonint do_spi 0
    echo "SPI enabled. A reboot may be required."
fi

if [ ! -e /dev/spidev0.0 ]; then
    echo "SPI device not found. Please reboot and run this script again."
    echo "   Run: sudo reboot"
    exit 1
fi

echo "SPI is enabled"

echo "Updating system packages..."
sudo apt update

echo "Installing system dependencies..."
sudo apt install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    python3-rpi.gpio

echo "Creating Python virtual environment..."
cd /home/arin/git/erg-room
rm -rf venv
python3 -m venv venv --system-site-packages
source venv/bin/activate

echo "Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Downloading HTMX..."
curl -sL https://unpkg.com/htmx.org@1.9.10/dist/htmx.min.js -o static/htmx.min.js

echo "Initializing database..."
python -c "from app.models import init_db; init_db()"

echo ""
echo "Setup complete!"
echo ""
echo "RC522 Wiring (Pi Zero 2 W):"
echo "  SDA->GPIO8, SCK->GPIO11, MOSI->GPIO10, MISO->GPIO9, RST->GPIO25, 3.3V (not 5V)"
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
