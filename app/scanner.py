"""
QR Code Scanner Module
Continuously scans for QR codes and toggles presence status.
Also provides frame streaming for live video feed.
"""

import time
import threading
from datetime import datetime, timedelta
from collections import defaultdict
import io

# pyzbar for QR decoding
from pyzbar import pyzbar
from PIL import Image
import numpy as np

from app.config import SCAN_INTERVAL, FRAME_WIDTH, FRAME_HEIGHT, DEBOUNCE_SECONDS
from app.models import toggle_presence, get_member_by_id, auto_checkout_stale

# Track last scan time per member for debouncing
last_scan_times: dict[str, datetime] = defaultdict(lambda: datetime.min)

# Global flag to control scanner thread
scanner_running = False
scanner_thread = None

# Callback for notifying web clients of changes
presence_callback = None

# Shared frame for video streaming
current_frame = None
frame_lock = threading.Lock()


def set_presence_callback(callback):
    """Set callback function to be called when presence changes."""
    global presence_callback
    presence_callback = callback


def get_current_frame():
    """Get the current frame for video streaming."""
    global current_frame
    with frame_lock:
        return current_frame


def process_frame(frame: np.ndarray) -> list[str]:
    """
    Process a single frame and return list of detected QR code data.
    """
    # Convert numpy array to PIL Image
    image = Image.fromarray(frame)
    
    # Convert to grayscale for faster processing
    image = image.convert("L")
    
    # Decode QR codes
    decoded_objects = pyzbar.decode(image)
    
    return [obj.data.decode("utf-8") for obj in decoded_objects]


def handle_scan(qr_data: str) -> dict | None:
    """
    Handle a QR code scan with debouncing.
    Returns member info if processed, None if debounced or invalid.
    """
    global last_scan_times
    
    now = datetime.now()
    
    # Check debounce
    if now - last_scan_times[qr_data] < timedelta(seconds=DEBOUNCE_SECONDS):
        return None
    
    # Update last scan time
    last_scan_times[qr_data] = now
    
    # Verify this is a valid member
    member = get_member_by_id(qr_data)
    if not member:
        print(f"Unknown QR code: {qr_data}")
        return None
    
    # Toggle presence
    result = toggle_presence(qr_data)
    if result:
        status = "IN" if result["is_present"] else "OUT"
        print(f"[{now.strftime('%H:%M:%S')}] {result['name']} checked {status}")
        
        # Notify callback if set
        if presence_callback:
            presence_callback(result)
    
    return result


def scanner_loop_picamera():
    """Main scanner loop using picamera2 (for Raspberry Pi)."""
    global scanner_running, current_frame
    
    try:
        from picamera2 import Picamera2
        
        picam2 = Picamera2()
        config = picam2.create_still_configuration(
            main={"size": (FRAME_WIDTH, FRAME_HEIGHT), "format": "RGB888"}
        )
        picam2.configure(config)
        picam2.start()
        
        print(f"Scanner started (picamera2) - {FRAME_WIDTH}x{FRAME_HEIGHT} @ {1/SCAN_INTERVAL:.1f} FPS")
        
        last_auto_checkout = datetime.now()
        
        while scanner_running:
            # Capture frame
            frame = picam2.capture_array()
            
            # Store frame for video streaming
            with frame_lock:
                current_frame = frame.copy()
            
            # Process for QR codes
            qr_codes = process_frame(frame)
            
            for qr_data in qr_codes:
                handle_scan(qr_data)
            
            # Auto-checkout check every 5 minutes
            if datetime.now() - last_auto_checkout > timedelta(minutes=5):
                stale_count = auto_checkout_stale()
                if stale_count:
                    print(f"Auto-checked out {stale_count} stale members")
                last_auto_checkout = datetime.now()
            
            time.sleep(SCAN_INTERVAL)
        
        picam2.stop()
        print("Scanner stopped")
        
    except ImportError:
        print("picamera2 not available - falling back to test mode")
        scanner_loop_test()


def scanner_loop_test():
    """Test scanner loop without camera (for development)."""
    global scanner_running, current_frame
    
    print("Scanner running in TEST MODE (no camera)")
    print("Simulating scans - press Ctrl+C to stop")
    
    # Create a placeholder frame for test mode
    placeholder = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)
    placeholder[:] = (240, 240, 240)  # Light gray
    
    # Add text to placeholder
    from PIL import ImageDraw, ImageFont
    img = Image.fromarray(placeholder)
    draw = ImageDraw.Draw(img)
    text = "No Camera"
    bbox = draw.textbbox((0, 0), text)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (FRAME_WIDTH - text_width) // 2
    y = (FRAME_HEIGHT - text_height) // 2
    draw.text((x, y), text, fill=(100, 100, 100))
    placeholder = np.array(img)
    
    with frame_lock:
        current_frame = placeholder
    
    while scanner_running:
        time.sleep(1)
    
    print("Test scanner stopped")


def generate_frames():
    """Generator function for MJPEG streaming."""
    while True:
        frame = get_current_frame()
        
        if frame is not None:
            # Convert numpy array to JPEG
            img = Image.fromarray(frame)
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=70)
            frame_bytes = buffer.getvalue()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        time.sleep(0.1)  # ~10 FPS for streaming


def start_scanner(use_camera: bool = True):
    """Start the scanner in a background thread."""
    global scanner_running, scanner_thread
    
    if scanner_running:
        print("Scanner already running")
        return
    
    scanner_running = True
    
    if use_camera:
        scanner_thread = threading.Thread(target=scanner_loop_picamera, daemon=True)
    else:
        scanner_thread = threading.Thread(target=scanner_loop_test, daemon=True)
    
    scanner_thread.start()


def stop_scanner():
    """Stop the scanner thread."""
    global scanner_running
    scanner_running = False


def simulate_scan(member_id: str) -> dict | None:
    """
    Manually simulate a scan (for testing/admin).
    Bypasses debounce.
    """
    member = get_member_by_id(member_id)
    if not member:
        return None
    
    result = toggle_presence(member_id)
    if result and presence_callback:
        presence_callback(result)
    
    return result


if __name__ == "__main__":
    # Test the scanner standalone
    from app.models import init_db
    init_db()
    
    scanner_running = True
    try:
        scanner_loop_picamera()
    except KeyboardInterrupt:
        scanner_running = False
