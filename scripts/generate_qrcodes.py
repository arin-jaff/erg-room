#!/usr/bin/env python3
"""
Generate QR codes for all team members.
Run once after updating TEAM_MEMBERS in config.py
"""

import qrcode
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import TEAM_MEMBERS, QRCODE_DIR


def generate_qrcodes():
    """Generate a QR code image for each team member."""
    
    QRCODE_DIR.mkdir(exist_ok=True)
    
    print(f"Generating QR codes in {QRCODE_DIR}/\n")
    
    for member in TEAM_MEMBERS:
        member_id = member["id"]
        name = member["name"]
        
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(member_id)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save with member name in filename
        filename = f"{name.lower().replace(' ', '_')}_{member_id}.png"
        filepath = QRCODE_DIR / filename
        img.save(filepath)
        
        print(f"  ✓ {name}: {filename}")
    
    print(f"\n✅ Generated {len(TEAM_MEMBERS)} QR codes!")
    print("\nNext steps:")
    print("  1. Print these QR codes or send to teammates")
    print("  2. Teammates can save the image to their phone")
    print("  3. Or print them on lanyards/cards for the erg room")


if __name__ == "__main__":
    generate_qrcodes()
