"""
RFID Scanner Module (RC522)
Continuously scans for RFID tags and toggles presence status.
"""

import time
import threading
from datetime import datetime, timedelta
from collections import defaultdict

from app.config import SCAN_INTERVAL, DEBOUNCE_SECONDS
from app.models import toggle_presence, get_member_by_id, auto_checkout_stale

# Track last scan time per member for debouncing
last_scan_times: dict[str, datetime] = defaultdict(lambda: datetime.min)

# Global flag to control scanner thread
scanner_running = False
scanner_thread = None

# Callback for notifying web clients of changes
presence_callback = None

# Last scanned info for display
last_scan_info = {
    "tag_id": None,
    "member_name": None,
    "action": None,
    "timestamp": None
}
scan_info_lock = threading.Lock()


def set_presence_callback(callback):
    """Set callback function to be called when presence changes."""
    global presence_callback
    presence_callback = callback


def get_last_scan_info():
    """Get info about the last scan for display."""
    with scan_info_lock:
        return last_scan_info.copy()


def uid_to_string(uid: list) -> str:
    """Convert UID bytes to a hex string."""
    return ''.join(format(x, '02x') for x in uid)


def handle_scan(tag_id: str) -> dict | None:
    """
    Handle an RFID tag scan with debouncing.
    Returns member info if processed, None if debounced or invalid.
    """
    global last_scan_times, last_scan_info
    
    now = datetime.now()
    
    # Check debounce
    if now - last_scan_times[tag_id] < timedelta(seconds=DEBOUNCE_SECONDS):
        return None
    
    # Update last scan time
    last_scan_times[tag_id] = now
    
    # Verify this is a valid member
    member = get_member_by_id(tag_id)
    if not member:
        print(f"[{now.strftime('%H:%M:%S')}] Unknown RFID tag: {tag_id}")
        with scan_info_lock:
            last_scan_info = {
                "tag_id": tag_id,
                "member_name": None,
                "action": "unknown",
                "timestamp": now.isoformat()
            }
        return None
    
    # Toggle presence
    result = toggle_presence(tag_id)
    if result:
        status = "IN" if result["is_present"] else "OUT"
        print(f"[{now.strftime('%H:%M:%S')}] {result['name']} checked {status}")
        
        with scan_info_lock:
            last_scan_info = {
                "tag_id": tag_id,
                "member_name": result["name"],
                "action": result["action"],
                "timestamp": now.isoformat()
            }
        
        # Notify callback if set
        if presence_callback:
            presence_callback(result)
    
    return result


def scanner_loop_rfid():
    """Main scanner loop using RC522 RFID reader."""
    global scanner_running
    
    try:
        from mfrc522 import SimpleMFRC522
        import RPi.GPIO as GPIO
        
        reader = SimpleMFRC522()
        
        print("RFID Scanner started (RC522)")
        print("Waiting for RFID tags...")
        
        last_auto_checkout = datetime.now()
        
        while scanner_running:
            try:
                # Read RFID tag (non-blocking approach)
                # SimpleMFRC522.read() is blocking, so we use read_no_block()
                id, text = reader.read_no_block()
                
                if id:
                    # Convert ID to hex string for consistency
                    tag_id = format(id, 'x')
                    handle_scan(tag_id)
                
                # Auto-checkout check every 5 minutes
                if datetime.now() - last_auto_checkout > timedelta(minutes=5):
                    stale_count = auto_checkout_stale()
                    if stale_count:
                        print(f"Auto-checked out {stale_count} stale members")
                    last_auto_checkout = datetime.now()
                
                time.sleep(SCAN_INTERVAL)
                
            except Exception as e:
                print(f"RFID read error: {e}")
                time.sleep(1)
        
        GPIO.cleanup()
        print("RFID Scanner stopped")
        
    except ImportError as e:
        print(f"RFID libraries not available: {e}")
        print("Falling back to test mode")
        scanner_loop_test()


def scanner_loop_test():
    """Test scanner loop without RFID hardware (for development)."""
    global scanner_running
    
    print("Scanner running in TEST MODE (no RFID reader)")
    print("Use /admin to simulate scans")
    
    while scanner_running:
        # Auto-checkout check every 5 minutes
        time.sleep(60)
        stale_count = auto_checkout_stale()
        if stale_count:
            print(f"Auto-checked out {stale_count} stale members")
    
    print("Test scanner stopped")


def start_scanner(use_rfid: bool = True):
    """Start the scanner in a background thread."""
    global scanner_running, scanner_thread
    
    if scanner_running:
        print("Scanner already running")
        return
    
    scanner_running = True
    
    if use_rfid:
        scanner_thread = threading.Thread(target=scanner_loop_rfid, daemon=True)
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
    
    if result:
        with scan_info_lock:
            global last_scan_info
            last_scan_info = {
                "tag_id": member_id,
                "member_name": result["name"],
                "action": result["action"],
                "timestamp": datetime.now().isoformat()
            }
        
        if presence_callback:
            presence_callback(result)
    
    return result


if __name__ == "__main__":
    # Test the scanner standalone
    from app.models import init_db
    init_db()
    
    scanner_running = True
    try:
        scanner_loop_rfid()
    except KeyboardInterrupt:
        scanner_running = False
