#!/bin/bash
set -e

echo "Setting up Erg Room Presence Tracker..."

echo "Updating system packages..."
sudo apt update

echo "Installing system dependencies..."
sudo apt install -y \
    python3-pip \
    python3-venv \
    libzbar0 \
    python3-picamera2

echo "Checking camera..."
if ! vcgencmd get_camera | grep -q "detected=1"; then
    echo "Camera not detected. Enable it with: sudo raspi-config"
    echo "   Go to: Interface Options -> Camera -> Enable"
fi

echo "Creating Python virtual environment..."
cd /home/arin/git/erg-room
python3 -m venv venv
source venv/bin/activate

echo "Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Downloading HTMX..."
curl -sL https://unpkg.com/htmx.org@1.9.10/dist/htmx.min.js -o static/htmx.min.js

echo "Initializing database..."
python -c "from app.models import init_db; init_db()"

echo "Generating QR codes..."
python scripts/generate_qrcodes.py

echo ""
echo "Setup complete!"
echo ""
echo "To run the app:"
echo "  cd /home/arin/git/erg-room"
echo "  source venv/bin/activate"
echo "  python run.py"
echo ""
echo "Then visit: http://$(hostname -I | awk '{print $1}'):5000"
