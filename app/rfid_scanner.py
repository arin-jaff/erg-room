"""
RFID Scanner Module (RC522)
Continuously scans for RFID tags and toggles presence status.
Supports registration mode for writing new UUIDs to tags.
"""

import time
import threading
from datetime import datetime, timedelta
from collections import defaultdict

from app.config import SCAN_INTERVAL, DEBOUNCE_SECONDS, generate_uuid
from app.models import (
    toggle_presence, get_member_by_id, auto_checkout_stale,
    add_pending_tag, is_pending_tag, is_registered_member
)

# Track last scan time per member for debouncing
last_scan_times: dict[str, datetime] = defaultdict(lambda: datetime.min)

# Global flag to control scanner thread
scanner_running = False
scanner_thread = None

# Callback for notifying web clients of changes
presence_callback = None

# Registration mode flag
registration_mode = False
registration_lock = threading.Lock()

# Last scanned info for display
last_scan_info = {
    "tag_id": None,
    "member_name": None,
    "action": None,
    "timestamp": None,
    "is_new_registration": False
}
scan_info_lock = threading.Lock()

# Scan history (rolling log of last 10 scans)
scan_history = []
MAX_HISTORY = 10
history_lock = threading.Lock()


def set_presence_callback(callback):
    """Set callback function to be called when presence changes."""
    global presence_callback
    presence_callback = callback


def get_last_scan_info():
    """Get info about the last scan for display."""
    with scan_info_lock:
        return last_scan_info.copy()


def get_scan_history():
    """Get the rolling history of recent scans."""
    with history_lock:
        return list(scan_history)


def add_to_history(scan_info: dict):
    """Add a scan to the rolling history."""
    global scan_history
    with history_lock:
        scan_history.insert(0, scan_info.copy())
        if len(scan_history) > MAX_HISTORY:
            scan_history = scan_history[:MAX_HISTORY]


def set_registration_mode(enabled: bool):
    """Enable or disable registration mode."""
    global registration_mode
    with registration_lock:
        registration_mode = enabled
        print(f"Registration mode: {'ENABLED' if enabled else 'DISABLED'}")


def is_registration_mode():
    """Check if registration mode is active."""
    with registration_lock:
        return registration_mode


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
    
    # Check if this is a registered member
    member = get_member_by_id(tag_id)
    
    if member:
        # Known member - toggle presence
        result = toggle_presence(tag_id)
        if result:
            status = "IN" if result["is_present"] else "OUT"
            print(f"[{now.strftime('%H:%M:%S')}] {result['name']} checked {status}")
            
            with scan_info_lock:
                last_scan_info = {
                    "tag_id": tag_id,
                    "member_name": result["name"],
                    "action": result["action"],
                    "timestamp": now.isoformat(),
                    "is_new_registration": False
                }
            
            # Add to rolling history
            add_to_history(last_scan_info)
            
            if presence_callback:
                presence_callback(result)
        
        return result
    
    elif is_pending_tag(tag_id):
        # Tag is pending registration
        print(f"[{now.strftime('%H:%M:%S')}] Pending tag scanned: {tag_id}")
        with scan_info_lock:
            last_scan_info = {
                "tag_id": tag_id,
                "member_name": None,
                "action": "pending",
                "timestamp": now.isoformat(),
                "is_new_registration": False
            }
        return None
    
    else:
        # Unknown tag
        print(f"[{now.strftime('%H:%M:%S')}] Unknown tag: {tag_id}")
        with scan_info_lock:
            last_scan_info = {
                "tag_id": tag_id,
                "member_name": None,
                "action": "unknown",
                "timestamp": now.isoformat(),
                "is_new_registration": False
            }
        return None


def handle_registration_scan(reader) -> dict | None:
    """
    Handle a scan in registration mode - write new UUID to tag.
    """
    global last_scan_info
    
    now = datetime.now()
    
    try:
        # Generate new UUID
        new_uuid = generate_uuid()
        
        print(f"[{now.strftime('%H:%M:%S')}] Writing UUID to tag: {new_uuid}")
        
        # Write UUID to tag
        reader.write(new_uuid)
        
        # Add to pending registrations
        add_pending_tag(new_uuid)
        
        print(f"[{now.strftime('%H:%M:%S')}] Tag registered with UUID: {new_uuid}")
        
        with scan_info_lock:
            last_scan_info = {
                "tag_id": new_uuid,
                "member_name": None,
                "action": "registered",
                "timestamp": now.isoformat(),
                "is_new_registration": True
            }
        
        return {"tag_id": new_uuid, "action": "registered"}
        
    except Exception as e:
        print(f"[{now.strftime('%H:%M:%S')}] Registration failed: {e}")
        return None


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
                # Check if we're in registration mode
                if is_registration_mode():
                    # Registration mode - write new UUID to tag
                    print("Waiting for tag to register...")
                    id, text = reader.read()  # Blocking read
                    if id:
                        handle_registration_scan(reader)
                        # Auto-disable registration mode after one write
                        set_registration_mode(False)
                else:
                    # Normal mode - read tag
                    id, text = reader.read_no_block()
                    
                    if id:
                        # Use the text content if available, otherwise use UID
                        tag_id = text.strip() if text and text.strip() else format(id, 'x')
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
    """Manually simulate a scan (for testing/admin)."""
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
                "timestamp": datetime.now().isoformat(),
                "is_new_registration": False
            }
        
        # Add to rolling history
        add_to_history(last_scan_info)
        
        if presence_callback:
            presence_callback(result)
    
    return result


def simulate_registration() -> dict | None:
    """Simulate tag registration in test mode."""
    new_uuid = generate_uuid()
    add_pending_tag(new_uuid)
    
    now = datetime.now()
    
    with scan_info_lock:
        global last_scan_info
        last_scan_info = {
            "tag_id": new_uuid,
            "member_name": None,
            "action": "registered",
            "timestamp": now.isoformat(),
            "is_new_registration": True
        }
    
    print(f"[{now.strftime('%H:%M:%S')}] Simulated registration: {new_uuid}")
    
    return {"tag_id": new_uuid, "action": "registered"}


if __name__ == "__main__":
    from app.models import init_db
    init_db()
    
    scanner_running = True
    try:
        scanner_loop_rfid()
    except KeyboardInterrupt:
        scanner_running = False
