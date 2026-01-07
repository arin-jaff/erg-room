import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522

reader = SimpleMFRC522()

try:
    text = input('Enter new data to write (up to 16 characters): ')
    print("Now place your RFID tag on the reader to write...")
    reader.write(text)
    print("Data successfully written.")
finally:
    # Clean up GPIO pins to prevent issues with future scripts
    GPIO.cleanup() 