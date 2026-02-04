import sqlite3
from datetime import datetime, timedelta
from contextlib import contextmanager
from app.config import DB_PATH, AUTO_CHECKOUT_HOURS


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS members (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                profile_picture TEXT DEFAULT NULL,
                rowing_category TEXT DEFAULT NULL,
                boat_class TEXT DEFAULT NULL,
                total_seconds INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS presence (
                member_id TEXT PRIMARY KEY,
                is_present BOOLEAN DEFAULT 0,
                last_scan TIMESTAMP,
                checked_in_at TIMESTAMP,
                FOREIGN KEY (member_id) REFERENCES members(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id TEXT,
                action TEXT,
                scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (member_id) REFERENCES members(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_tags (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        migrate_db(conn)
        repair_presence(conn)
        conn.commit()
        print(f"Database initialized at {DB_PATH}")


def migrate_db(conn):
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(members)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'boat_class' not in columns:
        cursor.execute("ALTER TABLE members ADD COLUMN boat_class TEXT DEFAULT NULL")

    if 'total_seconds' not in columns:
        cursor.execute("ALTER TABLE members ADD COLUMN total_seconds INTEGER DEFAULT 0")

    if 'passkey' not in columns:
        cursor.execute("ALTER TABLE members ADD COLUMN passkey TEXT DEFAULT NULL")


def repair_presence(conn):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO presence (member_id, is_present)
        SELECT id, 0 FROM members
        WHERE id NOT IN (SELECT member_id FROM presence)
    """)
    repaired = cursor.rowcount
    if repaired > 0:
        print(f"Repaired {repaired} members missing presence records")


def add_pending_tag(tag_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO pending_tags (id) VALUES (?)",
                (tag_id,)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def get_pending_tags() -> list[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, created_at FROM pending_tags ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]


def remove_pending_tag(tag_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pending_tags WHERE id = ?", (tag_id,))
        conn.commit()
        return cursor.rowcount > 0


def create_member(member_id: str, name: str, rowing_category: str = None, boat_class: str = None) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO members (id, name, rowing_category, boat_class) VALUES (?, ?, ?, ?)",
                (member_id, name, rowing_category, boat_class)
            )
            cursor.execute(
                "INSERT INTO presence (member_id, is_present) VALUES (?, 0)",
                (member_id,)
            )
            cursor.execute("DELETE FROM pending_tags WHERE id = ?", (member_id,))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


_UNSET = object()


def update_member(member_id: str, name: str = None, profile_picture: str = None, rowing_category: str = None, boat_class=_UNSET, passkey=_UNSET) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()

        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)

        if profile_picture is not None:
            updates.append("profile_picture = ?")
            params.append(profile_picture)

        if rowing_category is not None:
            updates.append("rowing_category = ?")
            params.append(rowing_category)

        if boat_class is not _UNSET:
            updates.append("boat_class = ?")
            params.append(boat_class)

        if passkey is not _UNSET:
            updates.append("passkey = ?")
            params.append(passkey)

        if not updates:
            return False

        params.append(member_id)
        cursor.execute(
            f"UPDATE members SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()
        return cursor.rowcount > 0


def delete_member(member_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM presence WHERE member_id = ?", (member_id,))
        cursor.execute("DELETE FROM scan_log WHERE member_id = ?", (member_id,))
        cursor.execute("DELETE FROM members WHERE id = ?", (member_id,))
        conn.commit()
        return cursor.rowcount > 0


def update_member_uuid(old_id: str, new_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE scan_log SET member_id = ? WHERE member_id = ?", (new_id, old_id))
            cursor.execute("UPDATE presence SET member_id = ? WHERE member_id = ?", (new_id, old_id))
            cursor.execute("UPDATE members SET id = ? WHERE id = ?", (new_id, old_id))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.IntegrityError:
            return False


def toggle_presence(member_id: str) -> dict | None:
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT m.id, m.name, m.profile_picture, m.rowing_category, p.is_present, p.checked_in_at
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

        if new_status:
            cursor.execute("""
                UPDATE presence
                SET is_present = ?, last_scan = ?, checked_in_at = ?
                WHERE member_id = ?
            """, (new_status, now, now, member_id))
        else:
            if row["checked_in_at"]:
                checked_in = datetime.fromisoformat(row["checked_in_at"])
                session_seconds = int((now - checked_in).total_seconds())
                cursor.execute("""
                    UPDATE members
                    SET total_seconds = total_seconds + ?
                    WHERE id = ?
                """, (session_seconds, member_id))

            cursor.execute("""
                UPDATE presence
                SET is_present = ?, last_scan = ?, checked_in_at = NULL
                WHERE member_id = ?
            """, (new_status, now, member_id))

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
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.id, m.name, m.profile_picture, m.rowing_category, p.last_scan, p.checked_in_at
            FROM members m
            JOIN presence p ON m.id = p.member_id
            WHERE p.is_present = 1
            ORDER BY p.checked_in_at DESC
        """)

        members = []
        now = datetime.now()

        for row in cursor.fetchall():
            member = dict(row)

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
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.id, m.name, m.profile_picture, m.rowing_category, p.is_present, p.last_scan, p.checked_in_at
            FROM members m
            JOIN presence p ON m.id = p.member_id
            ORDER BY m.name
        """)
        return [dict(row) for row in cursor.fetchall()]


def auto_checkout_stale():
    cutoff = datetime.now() - timedelta(hours=AUTO_CHECKOUT_HOURS)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT member_id, checked_in_at FROM presence
            WHERE is_present = 1 AND checked_in_at < ?
        """, (cutoff,))
        stale = cursor.fetchall()

        cursor.execute("""
            UPDATE presence
            SET is_present = 0, checked_in_at = NULL
            WHERE is_present = 1 AND checked_in_at < ?
        """, (cutoff,))
        conn.commit()
        return len(stale)


def get_member_by_id(member_id: str) -> dict | None:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, profile_picture, rowing_category, boat_class, total_seconds, passkey FROM members WHERE id = ?",
            (member_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_member_by_id_or_passkey(identifier: str) -> dict | None:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, profile_picture, rowing_category, boat_class, total_seconds, passkey FROM members WHERE id = ? OR passkey = ?",
            (identifier, identifier)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def update_profile_picture(member_id: str, filename: str) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE members SET profile_picture = ? WHERE id = ?",
            (filename, member_id)
        )
        conn.commit()
        return cursor.rowcount > 0


def get_member_presence(member_id: str) -> dict | None:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.id, m.name, m.profile_picture, m.rowing_category, p.is_present, p.last_scan, p.checked_in_at
            FROM members m
            JOIN presence p ON m.id = p.member_id
            WHERE m.id = ?
        """, (member_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def is_pending_tag(tag_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM pending_tags WHERE id = ?", (tag_id,))
        return cursor.fetchone() is not None


def is_registered_member(tag_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM members WHERE id = ?", (tag_id,))
        return cursor.fetchone() is not None


def set_lightweight_mode(enabled: bool) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        cursor.execute("""
            INSERT OR REPLACE INTO settings (key, value)
            VALUES ('lightweight_mode', ?)
        """, ('1' if enabled else '0',))
        conn.commit()
        return True


def get_lightweight_mode() -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        cursor.execute("SELECT value FROM settings WHERE key = 'lightweight_mode'")
        row = cursor.fetchone()
        return row and row[0] == '1' if row else False


def get_leaderboard_stats() -> dict:
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT boat_class, SUM(total_seconds) as total, COUNT(*) as count
            FROM members
            WHERE boat_class IS NOT NULL
            GROUP BY boat_class
        """)
        boat_stats = {}
        for row in cursor.fetchall():
            boat_stats[row['boat_class']] = {
                'total_seconds': row['total'] or 0,
                'member_count': row['count']
            }

        cursor.execute("""
            SELECT id, name, boat_class, rowing_category, total_seconds, profile_picture
            FROM members
            WHERE total_seconds > 0
            ORDER BY total_seconds DESC
            LIMIT 10
        """)
        top_individuals = [dict(row) for row in cursor.fetchall()]

        cursor.execute("SELECT SUM(total_seconds) as total FROM members")
        row = cursor.fetchone()
        total_all = row['total'] or 0

        cursor.execute("SELECT COUNT(*) as count FROM members")
        member_count = cursor.fetchone()['count']

        return {
            'boat_stats': boat_stats,
            'top_individuals': top_individuals,
            'total_seconds': total_all,
            'member_count': member_count
        }


def get_all_tables() -> list[str]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        return [row['name'] for row in cursor.fetchall()]


def get_table_data(table_name: str, limit: int = 100) -> dict:
    with get_db() as conn:
        cursor = conn.cursor()

        safe_tables = ['members', 'presence', 'scan_log', 'pending_tags', 'settings']
        if table_name not in safe_tables:
            return {'error': 'Invalid table name'}

        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]

        cursor.execute(f"SELECT * FROM {table_name} LIMIT ?", (limit,))
        rows = [dict(row) for row in cursor.fetchall()]

        cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
        total = cursor.fetchone()['count']

        return {
            'table': table_name,
            'columns': columns,
            'rows': rows,
            'total': total
        }


def update_table_row(table_name: str, primary_key: str, pk_value: str, updates: dict) -> bool:
    safe_tables = {'members': 'id', 'presence': 'member_id', 'pending_tags': 'id', 'settings': 'key'}
    if table_name not in safe_tables:
        return False

    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute(f"PRAGMA table_info({table_name})")
        valid_columns = [col[1] for col in cursor.fetchall()]

        set_parts = []
        params = []
        for col, val in updates.items():
            if col in valid_columns and col != primary_key:
                set_parts.append(f"{col} = ?")
                params.append(val)

        if not set_parts:
            return False

        params.append(pk_value)
        cursor.execute(
            f"UPDATE {table_name} SET {', '.join(set_parts)} WHERE {primary_key} = ?",
            params
        )
        conn.commit()
        return cursor.rowcount > 0


if __name__ == "__main__":
    init_db()
