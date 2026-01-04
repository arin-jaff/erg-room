import sqlite3
from datetime import datetime, timedelta
from contextlib import contextmanager
from app.config import DB_PATH, TEAM_MEMBERS, AUTO_CHECKOUT_HOURS


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Initialize database tables and seed team members."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Team members table (with profile picture)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS members (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                profile_picture TEXT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Presence status table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS presence (
                member_id TEXT PRIMARY KEY,
                is_present BOOLEAN DEFAULT 0,
                last_scan TIMESTAMP,
                checked_in_at TIMESTAMP,
                FOREIGN KEY (member_id) REFERENCES members(id)
            )
        """)
        
        # Scan history log (optional, for analytics)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id TEXT,
                action TEXT,  -- 'in' or 'out'
                scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (member_id) REFERENCES members(id)
            )
        """)
        
        # Add profile_picture column if it doesn't exist (migration)
        try:
            cursor.execute("ALTER TABLE members ADD COLUMN profile_picture TEXT DEFAULT NULL")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Add checked_in_at column if it doesn't exist (migration)
        try:
            cursor.execute("ALTER TABLE presence ADD COLUMN checked_in_at TIMESTAMP")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Seed team members from config
        for member in TEAM_MEMBERS:
            cursor.execute(
                "INSERT OR IGNORE INTO members (id, name) VALUES (?, ?)",
                (member["id"], member["name"])
            )
            cursor.execute(
                "INSERT OR IGNORE INTO presence (member_id, is_present) VALUES (?, 0)",
                (member["id"],)
            )
        
        conn.commit()
        print(f"Database initialized at {DB_PATH}")


def toggle_presence(member_id: str) -> dict | None:
    """
    Toggle a member's presence status.
    Returns the member info with new status, or None if not found.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get current status
        cursor.execute("""
            SELECT m.id, m.name, m.profile_picture, p.is_present 
            FROM members m 
            JOIN presence p ON m.id = p.member_id 
            WHERE m.id = ?
        """, (member_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        new_status = not row["is_present"]
        action = "in" if new_status else "out"
        now = datetime.now()
        
        # Update presence
        if new_status:  # Checking IN
            cursor.execute("""
                UPDATE presence 
                SET is_present = ?, last_scan = ?, checked_in_at = ?
                WHERE member_id = ?
            """, (new_status, now, now, member_id))
        else:  # Checking OUT
            cursor.execute("""
                UPDATE presence 
                SET is_present = ?, last_scan = ?, checked_in_at = NULL
                WHERE member_id = ?
            """, (new_status, now, member_id))
        
        # Log the scan
        cursor.execute(
            "INSERT INTO scan_log (member_id, action) VALUES (?, ?)",
            (member_id, action)
        )
        
        conn.commit()
        
        return {
            "id": row["id"],
            "name": row["name"],
            "profile_picture": row["profile_picture"],
            "is_present": new_status,
            "action": action
        }


def get_present_members() -> list[dict]:
    """Get all members currently marked as present with time info."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.id, m.name, m.profile_picture, p.last_scan, p.checked_in_at
            FROM members m
            JOIN presence p ON m.id = p.member_id
            WHERE p.is_present = 1
            ORDER BY p.checked_in_at DESC
        """)
        
        members = []
        now = datetime.now()
        
        for row in cursor.fetchall():
            member = dict(row)
            
            # Calculate time in room
            if member["checked_in_at"]:
                checked_in = datetime.fromisoformat(member["checked_in_at"])
                duration = now - checked_in
                member["duration_seconds"] = duration.total_seconds()
                member["duration_formatted"] = format_duration(duration)
            else:
                member["duration_seconds"] = 0
                member["duration_formatted"] = "just arrived"
            
            members.append(member)
        
        return members


def format_duration(duration: timedelta) -> str:
    """Format a timedelta into human-readable string."""
    total_seconds = int(duration.total_seconds())
    
    if total_seconds < 60:
        return "less than a minute"
    
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    
    if hours == 0:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    elif minutes == 0:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    else:
        return f"{hours} hour{'s' if hours != 1 else ''}, {minutes} minute{'s' if minutes != 1 else ''}"


def get_all_members() -> list[dict]:
    """Get all team members with their presence status."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.id, m.name, m.profile_picture, p.is_present, p.last_scan, p.checked_in_at
            FROM members m
            JOIN presence p ON m.id = p.member_id
            ORDER BY m.name
        """)
        return [dict(row) for row in cursor.fetchall()]


def auto_checkout_stale():
    """Mark members as 'out' if they haven't scanned in AUTO_CHECKOUT_HOURS."""
    cutoff = datetime.now() - timedelta(hours=AUTO_CHECKOUT_HOURS)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE presence 
            SET is_present = 0, checked_in_at = NULL
            WHERE is_present = 1 AND checked_in_at < ?
        """, (cutoff,))
        affected = cursor.rowcount
        conn.commit()
        return affected


def get_member_by_id(member_id: str) -> dict | None:
    """Look up a member by their QR code ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, profile_picture FROM members WHERE id = ?", 
            (member_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def update_profile_picture(member_id: str, filename: str) -> bool:
    """Update a member's profile picture."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE members SET profile_picture = ? WHERE id = ?",
            (filename, member_id)
        )
        conn.commit()
        return cursor.rowcount > 0


def get_member_presence(member_id: str) -> dict | None:
    """Get a member's full info including presence status."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.id, m.name, m.profile_picture, p.is_present, p.last_scan, p.checked_in_at
            FROM members m
            JOIN presence p ON m.id = p.member_id
            WHERE m.id = ?
        """, (member_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


if __name__ == "__main__":
    init_db()
