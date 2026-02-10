#!/usr/bin/env python3
"""Read any RFID/NFC tag and dump all available data."""
import RPi.GPIO as GPIO
from mfrc522 import MFRC522

reader = MFRC522()
print("Tap any tag (Ctrl+C to quit)...")

try:
    while True:
        status, tag_type = reader.MFRC522_Request(reader.PICC_REQIDL)
        if status != reader.MI_OK:
            continue

        status, uid = reader.MFRC522_Anticoll()
        if status != reader.MI_OK:
            continue

        uid_hex = ''.join(format(b, '02X') for b in uid)
        uid_dec = int(uid_hex, 16)
        print(f"\n--- Tag Detected ---")
        print(f"UID (hex):  {uid_hex}")
        print(f"UID (dec):  {uid_dec}")
        print(f"Tag type:   0x{tag_type:02X}")

        reader.MFRC522_SelectTag(uid)

        # Try to read all 64 sectors (MIFARE 1K = 16 sectors x 4 blocks)
        # Default key for many cards including university IDs
        keys = [
            [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF],
            [0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5],
            [0xD3, 0xF7, 0xD3, 0xF7, 0xD3, 0xF7],
        ]

        for block in range(64):
            for key in keys:
                status = reader.MFRC522_Auth(reader.PICC_AUTHENT1A, block, key, uid)
                if status == reader.MI_OK:
                    data = reader.MFRC522_Read(block)
                    if data:
                        raw = ' '.join(format(b, '02X') for b in data)
                        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
                        print(f"Block {block:02d}: {raw}  |{ascii_str}|")
                    break

        reader.MFRC522_StopCrypto1()
        print("--- End ---\n")

except KeyboardInterrupt:
    print("\nDone")
finally:
    GPIO.cleanup()
