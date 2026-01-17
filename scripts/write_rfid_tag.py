#!/usr/bin/env python3
"""
Write member IDs to RFID tags.
Run this script and tap a blank tag to write a member ID to it.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Hardcoded test team members
TEAM_MEMBERS = [
    {"id": "test001", "name": "Alice (LW)"},
    {"id": "test002", "name": "Bob (HW)"},
    {"id": "test003", "name": "Charlie (W)"},
    {"id": "test004", "name": "Diana (LW)"},
    {"id": "test005", "name": "Eve (HW)"},
]


def list_members():
    """Display all team members and their IDs."""
    print("\n=== Team Members ===")
    for i, member in enumerate(TEAM_MEMBERS, 1):
        print(f"  {i}. {member['name']} (ID: {member['id']})")
    print()


def write_tag_interactive():
    """Interactive mode to write tags."""
    try:
        from mfrc522 import SimpleMFRC522
        import RPi.GPIO as GPIO
        
        reader = SimpleMFRC522()
        
        print("=" * 50)
        print("  RFID Tag Writer for Erg Room")
        print("=" * 50)
        
        list_members()
        
        while True:
            print("\nOptions:")
            print("  1. Write a member ID to a tag")
            print("  2. Read a tag")
            print("  3. List members")
            print("  4. Write custom ID")
            print("  q. Quit")
            
            choice = input("\nChoice: ").strip().lower()
            
            if choice == 'q':
                break
            elif choice == '1':
                write_member_tag(reader)
            elif choice == '2':
                read_tag(reader)
            elif choice == '3':
                list_members()
            elif choice == '4':
                write_custom_tag(reader)
            else:
                print("Invalid choice")
        
        GPIO.cleanup()
        print("\nGoodbye!")
        
    except ImportError:
        print("ERROR: mfrc522 library not installed.")
        print("Run: pip install mfrc522")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


def write_member_tag(reader):
    """Write a team member's ID to a tag."""
    list_members()
    
    try:
        choice = int(input("Enter member number: ")) - 1
        if 0 <= choice < len(TEAM_MEMBERS):
            member = TEAM_MEMBERS[choice]
            member_id = member['id']
            member_name = member['name']
            
            print(f"\nReady to write ID '{member_id}' for {member_name}")
            print("Place the RFID tag on the reader...")
            
            # Write the member ID as text data
            reader.write(member_id)
            
            print(f"✓ Successfully wrote '{member_id}' to tag!")
            print(f"  This tag is now assigned to: {member_name}")
            
        else:
            print("Invalid member number")
    except ValueError:
        print("Please enter a number")
    except Exception as e:
        print(f"Write failed: {e}")


def write_custom_tag(reader):
    """Write a custom ID to a tag."""
    custom_id = input("Enter custom ID to write: ").strip()
    
    if not custom_id:
        print("ID cannot be empty")
        return
    
    print(f"\nReady to write ID '{custom_id}'")
    print("Place the RFID tag on the reader...")
    
    try:
        reader.write(custom_id)
        print(f"✓ Successfully wrote '{custom_id}' to tag!")
    except Exception as e:
        print(f"Write failed: {e}")


def read_tag(reader):
    """Read and display tag information."""
    print("\nPlace the RFID tag on the reader...")
    
    try:
        id, text = reader.read()
        
        tag_id_hex = format(id, 'x')
        text = text.strip() if text else ""
        
        print(f"\n=== Tag Information ===")
        print(f"  UID (decimal): {id}")
        print(f"  UID (hex):     {tag_id_hex}")
        print(f"  Stored text:   '{text}'")
        
        # Check if this matches a team member
        # First check by stored text (member_id)
        for member in TEAM_MEMBERS:
            if member['id'] == text:
                print(f"  Assigned to:   {member['name']}")
                break
        else:
            # Check by hex UID
            for member in TEAM_MEMBERS:
                if member['id'] == tag_id_hex:
                    print(f"  Assigned to:   {member['name']} (by UID)")
                    break
            else:
                print("  Assigned to:   (not registered)")
        
    except Exception as e:
        print(f"Read failed: {e}")


def quick_write(member_id: str):
    """Quick write mode - write a specific ID without interactive menu."""
    try:
        from mfrc522 import SimpleMFRC522
        import RPi.GPIO as GPIO
        
        reader = SimpleMFRC522()
        
        # Find member name if it exists
        member_name = None
        for member in TEAM_MEMBERS:
            if member['id'] == member_id:
                member_name = member['name']
                break
        
        if member_name:
            print(f"Ready to write ID '{member_id}' for {member_name}")
        else:
            print(f"Ready to write ID '{member_id}' (not in team list)")
        
        print("Place the RFID tag on the reader...")
        
        reader.write(member_id)
        
        print(f"✓ Successfully wrote '{member_id}' to tag!")
        
        GPIO.cleanup()
        
    except ImportError:
        print("ERROR: mfrc522 library not installed.")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Quick write mode: python write_rfid_tag.py <member_id>
        quick_write(sys.argv[1])
    else:
        # Interactive mode
        write_tag_interactive()
