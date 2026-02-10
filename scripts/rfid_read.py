#!/usr/bin/env python3
"""Read RFID tags and print to terminal."""
from mfrc522 import SimpleMFRC522

reader = SimpleMFRC522()
print("Tap a tag...")
try:
    while True:
        id, text = reader.read()
        print(f"ID: {id}  Text: [{text.strip() if text else ''}]")
except KeyboardInterrupt:
    print("\nDone")
