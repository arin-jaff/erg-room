import os
from functools import wraps
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from app.config import (
    SECRET_KEY, WEB_HOST, WEB_PORT, UPLOAD_DIR,
    MAX_CONTENT_LENGTH, ALLOWED_EXTENSIONS, ADMIN_PASSWORD, ADMIN_TOTP_SECRET
)
from app.models import (
    get_present_members, get_all_members, init_db,
    get_member_by_id, get_member_by_id_or_passkey, get_member_by_username,
    update_profile_picture, get_member_presence,
    get_pending_tags, create_member, delete_member, update_member,
    update_member_uuid, remove_pending_tag, set_lightweight_mode,
    get_lightweight_mode, get_leaderboard_stats, get_all_tables,
    get_table_data, update_table_row, auto_checkout_stale, toggle_presence,
    hash_password, check_password
)
from app.rfid_scanner import (
    start_scanner, stop_scanner, simulate_scan, set_presence_callback,
    get_last_scan_info, set_registration_mode, is_registration_mode,
    simulate_registration, get_scan_history
)

app = Flask(__name__,
            template_folder="../templates",
            static_folder="../static")
app.secret_key = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH


@app.template_filter('fmt_hours')
def fmt_hours_filter(seconds):
    seconds = int(seconds or 0)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours == 0:
        return f"{minutes}m"
    return f"{hours}h {minutes}m"


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function


def notify_clients(data: dict):
    pass


def is_open_hours():
    from datetime import datetime
    hour = datetime.now().hour
    return 6 <= hour < 22


@app.before_request
def check_open_hours():
    open_paths = ['/static/', '/admin', '/closed']
    path = request.path
    if any(path.startswith(p) for p in open_paths):
        return None
    if not is_open_hours():
        return render_template("closed.html"), 200


@app.route("/closed")
def closed_preview():
    return render_template("closed.html")


@app.route("/")
def index():
    present = get_present_members()
    last_scan = get_last_scan_info()
    history = get_scan_history()
    return render_template("index.html", present=present, last_scan=last_scan, scan_history=history)


@app.route("/api/present")
def api_present():
    present = get_present_members()
    return jsonify({
        "count": len(present),
        "members": present
    })


@app.route("/api/last_scan")
def api_last_scan():
    return jsonify(get_last_scan_info())


@app.route("/api/scan_history")
def api_scan_history():
    return jsonify(get_scan_history())


@app.route("/api/lightweight_mode")
def api_lightweight_mode():
    return jsonify({"enabled": get_lightweight_mode()})


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        card_id = request.form.get("member_id", "").strip()

        # Username/password login (primary)
        if username and password:
            member = get_member_by_username(username)
            if member and member["password_hash"] and check_password(password, member["password_hash"]):
                session["member_id"] = member["id"]
                session["member_name"] = member["name"]
                return redirect(url_for("profile"))
            else:
                flash("Invalid username or password.", "error")
        # Card ID / passkey login (fallback for first-time setup)
        elif card_id:
            member = get_member_by_id_or_passkey(card_id)
            if member:
                session["member_id"] = member["id"]
                session["member_name"] = member["name"]
                if not member["password_hash"]:
                    return redirect(url_for("setup_account"))
                return redirect(url_for("profile"))
            else:
                flash("Invalid card ID or passkey.", "error")
        else:
            flash("Please enter your credentials.", "error")

    return render_template("login.html")


@app.route("/setup", methods=["GET", "POST"])
def setup_account():
    if "member_id" not in session:
        return redirect(url_for("login"))

    member = get_member_by_id(session["member_id"])
    if not member:
        return redirect(url_for("login"))

    if member["password_hash"]:
        return redirect(url_for("profile"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm_password", "").strip()

        if not username or not password:
            flash("Username and password are required.", "error")
        elif len(username) < 3:
            flash("Username must be at least 3 characters.", "error")
        elif len(password) < 4:
            flash("Password must be at least 4 characters.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        else:
            existing = get_member_by_username(username)
            if existing and existing["id"] != member["id"]:
                flash("Username already taken.", "error")
            else:
                update_member(member["id"], username=username, password_hash=hash_password(password))
                flash("Account created! You can now sign in with your username and password.", "success")
                return redirect(url_for("profile"))

    return render_template("setup_account.html", member=member)


@app.route("/logout")
def logout():
    session.pop("member_id", None)
    session.pop("member_name", None)
    return redirect(url_for("index"))


@app.route("/profile")
def profile():
    if "member_id" not in session:
        return redirect(url_for("login"))

    member = get_member_presence(session["member_id"])
    if not member:
        session.pop("member_id", None)
        session.pop("member_name", None)
        return redirect(url_for("login"))

    return render_template("profile.html", member=member)


@app.route("/profile/update", methods=["POST"])
def update_profile():
    if "member_id" not in session:
        return redirect(url_for("login"))

    rowing_category = request.form.get("rowing_category", "").strip()

    if not rowing_category:
        flash("Rowing category is required", "error")
        return redirect(url_for("profile"))

    update_member(session["member_id"], rowing_category=rowing_category)
    flash("Category updated!", "success")

    return redirect(url_for("profile"))


@app.route("/profile/checkout", methods=["POST"])
def virtual_checkout():
    if "member_id" not in session:
        return redirect(url_for("login"))

    member = get_member_presence(session["member_id"])
    if member and member["is_present"]:
        toggle_presence(session["member_id"])
        flash("You've been checked out!", "success")
    else:
        flash("You're not currently checked in", "error")

    return redirect(url_for("profile"))


@app.route("/profile/passkey", methods=["POST"])
def update_passkey():
    if "member_id" not in session:
        return redirect(url_for("login"))

    passkey = request.form.get("passkey", "").strip()

    if passkey and len(passkey) < 4:
        flash("Passkey must be at least 4 characters", "error")
        return redirect(url_for("profile"))

    update_member(session["member_id"], passkey=passkey if passkey else None)
    flash("Passkey updated!" if passkey else "Passkey removed!", "success")

    return redirect(url_for("profile"))


@app.route("/profile/password", methods=["POST"])
def change_password():
    if "member_id" not in session:
        return redirect(url_for("login"))

    password = request.form.get("password", "").strip()
    confirm = request.form.get("confirm_password", "").strip()

    if not password or len(password) < 4:
        flash("Password must be at least 4 characters", "error")
    elif password != confirm:
        flash("Passwords do not match", "error")
    else:
        update_member(session["member_id"], password_hash=hash_password(password))
        flash("Password updated!", "success")

    return redirect(url_for("profile"))


@app.route("/profile/upload", methods=["POST"])
def upload_photo():
    if "member_id" not in session:
        return redirect(url_for("login"))

    if "photo" not in request.files:
        flash("No file selected", "error")
        return redirect(url_for("profile"))

    file = request.files["photo"]

    if file.filename == "":
        flash("No file selected", "error")
        return redirect(url_for("profile"))

    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{session['member_id']}.{ext}"

        for old_ext in ALLOWED_EXTENSIONS:
            old_file = UPLOAD_DIR / f"{session['member_id']}.{old_ext}"
            if old_file.exists() and old_ext != ext:
                old_file.unlink()

        filepath = UPLOAD_DIR / filename
        file.save(filepath)

        update_profile_picture(session["member_id"], filename)

        flash("Profile picture updated!", "success")
    else:
        flash("Invalid file type. Use PNG, JPG, GIF, or WebP.", "error")

    return redirect(url_for("profile"))


_admin_attempts = {}

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    import time
    ip = request.remote_addr

    if request.method == "POST":
        # Rate limiting: max 5 attempts per 15 minutes
        now = time.time()
        attempts = _admin_attempts.get(ip, [])
        attempts = [t for t in attempts if now - t < 900]
        _admin_attempts[ip] = attempts

        if len(attempts) >= 5:
            flash("Too many attempts. Try again later.", "error")
            return render_template("admin_login.html")

        password = request.form.get("password", "")
        totp_code = request.form.get("totp_code", "").strip()

        import hmac
        if not hmac.compare_digest(password, ADMIN_PASSWORD):
            attempts.append(now)
            _admin_attempts[ip] = attempts
            flash("Invalid password", "error")
        elif ADMIN_TOTP_SECRET:
            import pyotp
            totp = pyotp.TOTP(ADMIN_TOTP_SECRET)
            if totp.verify(totp_code, valid_window=1):
                session["is_admin"] = True
                _admin_attempts.pop(ip, None)
                return redirect(url_for("admin"))
            else:
                attempts.append(now)
                _admin_attempts[ip] = attempts
                flash("Invalid 2FA code", "error")
        else:
            session["is_admin"] = True
            _admin_attempts.pop(ip, None)
            return redirect(url_for("admin"))

    return render_template("admin_login.html", totp_enabled=bool(ADMIN_TOTP_SECRET))


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("index"))


@app.route("/admin")
@admin_required
def admin():
    members = get_all_members()
    pending = get_pending_tags()
    reg_mode = is_registration_mode()
    lw_mode = get_lightweight_mode()
    return render_template("admin.html", members=members, pending=pending, registration_mode=reg_mode, lightweight_mode=lw_mode)


@app.route("/admin/register/start", methods=["POST"])
@admin_required
def admin_start_registration():
    set_registration_mode(True)
    flash("Registration mode enabled. Tap a tag to register it.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/register/stop", methods=["POST"])
@admin_required
def admin_stop_registration():
    set_registration_mode(False)
    flash("Registration mode disabled.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/register/simulate", methods=["POST"])
@admin_required
def admin_simulate_registration():
    result = simulate_registration()
    if result:
        flash(f"Simulated tag registered: {result['tag_id']}", "success")
    return redirect(url_for("admin"))


@app.route("/admin/lightweight_mode/enable", methods=["POST"])
@admin_required
def admin_enable_lightweight_mode():
    set_lightweight_mode(True)
    flash("Lightweight mode enabled. Home page will only show LM category.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/lightweight_mode/disable", methods=["POST"])
@admin_required
def admin_disable_lightweight_mode():
    set_lightweight_mode(False)
    flash("Lightweight mode disabled. Home page will show all categories.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/member/create", methods=["POST"])
@admin_required
def admin_create_member():
    tag_id = request.form.get("tag_id", "").strip()
    name = request.form.get("name", "").strip()
    rowing_category = request.form.get("rowing_category", "").strip()
    boat_class = request.form.get("boat_class", "").strip() or None

    if not tag_id or not name or not rowing_category:
        flash("All fields are required", "error")
        return redirect(url_for("admin"))

    if create_member(tag_id, name, rowing_category, boat_class):
        flash(f"Member '{name}' created successfully!", "success")
    else:
        flash("Failed to create member. Tag may already be registered.", "error")

    return redirect(url_for("admin"))


@app.route("/admin/member/<member_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_member(member_id):
    member = get_member_by_id(member_id)
    if not member:
        flash("Member not found", "error")
        return redirect(url_for("admin"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        rowing_category = request.form.get("rowing_category", "").strip()
        boat_class_raw = request.form.get("boat_class", "").strip()
        passkey = request.form.get("passkey", "").strip()
        username = request.form.get("username", "").strip()
        new_password = request.form.get("new_password", "").strip()
        new_uuid = request.form.get("uuid", "").strip()

        kwargs = dict(name=name, rowing_category=rowing_category, boat_class=boat_class_raw or None, passkey=passkey or None)

        if username:
            existing = get_member_by_username(username)
            if existing and existing["id"] != member_id:
                flash("Username already taken.", "error")
                return redirect(url_for("admin_edit_member", member_id=member_id))
            kwargs["username"] = username
        else:
            kwargs["username"] = None

        if new_password:
            kwargs["password_hash"] = hash_password(new_password)

        if name and rowing_category:
            update_member(member_id, **kwargs)

        if new_uuid and new_uuid != member_id:
            if update_member_uuid(member_id, new_uuid):
                flash(f"UUID updated to {new_uuid}", "success")
                return redirect(url_for("admin_edit_member", member_id=new_uuid))
            else:
                flash("Failed to update UUID. It may already be in use.", "error")

        flash("Member updated!", "success")
        return redirect(url_for("admin"))

    return render_template("admin_edit_member.html", member=member)


@app.route("/admin/member/<member_id>/delete", methods=["POST"])
@admin_required
def admin_delete_member(member_id):
    if delete_member(member_id):
        flash("Member deleted", "success")
    else:
        flash("Failed to delete member", "error")

    return redirect(url_for("admin"))


@app.route("/admin/pending/<tag_id>/delete", methods=["POST"])
@admin_required
def admin_delete_pending(tag_id):
    if remove_pending_tag(tag_id):
        flash("Pending tag removed", "success")
    else:
        flash("Failed to remove pending tag", "error")

    return redirect(url_for("admin"))


@app.route("/api/simulate/<member_id>", methods=["POST"])
@admin_required
def api_simulate(member_id: str):
    result = simulate_scan(member_id)
    if result:
        return jsonify({"success": True, "result": result})
    return jsonify({"success": False, "error": "Member not found"}), 404


@app.route("/members")
def members_directory():
    members = get_all_members()
    return render_template("members.html", members=members)


@app.route("/members/<member_id>")
def member_profile(member_id):
    member = get_member_by_id(member_id)
    if not member:
        return redirect(url_for("members_directory"))
    return render_template("member_profile.html", member=member)


LEADERBOARD_PASSWORD = "c150-2026"

@app.route("/leaderboard", methods=["GET", "POST"])
def leaderboard():
    if request.method == "POST":
        if request.form.get("password", "") == LEADERBOARD_PASSWORD:
            session["leaderboard_ok"] = True
        else:
            flash("Invalid password", "error")
        return redirect(url_for("leaderboard"))

    if not session.get("leaderboard_ok") and not session.get("is_admin"):
        return render_template("leaderboard_login.html")

    stats = get_leaderboard_stats()
    return render_template("leaderboard.html", stats=stats)


@app.route("/admin/device")
@admin_required
def admin_device():
    device_stats = get_device_stats()
    tables = get_all_tables()
    return render_template("admin_device.html", device=device_stats, tables=tables)


@app.route("/admin/device/table/<table_name>")
@admin_required
def admin_table_view(table_name):
    data = get_table_data(table_name)
    return render_template("admin_table.html", data=data)


@app.route("/admin/device/table/<table_name>/update", methods=["POST"])
@admin_required
def admin_table_update(table_name):
    pk_value = request.form.get("pk_value", "").strip()
    updates = {}
    for key, value in request.form.items():
        if key not in ['pk_value', 'pk_column']:
            updates[key] = value

    pk_column = request.form.get("pk_column", "id")
    if update_table_row(table_name, pk_column, pk_value, updates):
        flash("Row updated successfully", "success")
    else:
        flash("Failed to update row", "error")

    return redirect(url_for("admin_table_view", table_name=table_name))


@app.route("/api/device_stats")
@admin_required
def api_device_stats():
    return jsonify(get_device_stats())


def get_device_stats() -> dict:
    import platform
    import subprocess
    from app.config import DB_PATH

    stats = {
        'platform': platform.system(),
        'platform_release': platform.release(),
        'platform_version': platform.version(),
        'architecture': platform.machine(),
        'processor': platform.processor(),
        'python_version': platform.python_version(),
        'hostname': platform.node()
    }

    try:
        db_size = DB_PATH.stat().st_size if DB_PATH.exists() else 0
        stats['db_size_bytes'] = db_size
        stats['db_size_formatted'] = format_bytes(db_size)
    except:
        stats['db_size_formatted'] = 'Unknown'

    try:
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.read()
            for line in meminfo.split('\n'):
                if 'MemTotal' in line:
                    stats['mem_total'] = line.split()[1]
                elif 'MemAvailable' in line:
                    stats['mem_available'] = line.split()[1]
    except:
        pass

    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.read().split()[0])
            stats['uptime_seconds'] = uptime_seconds
            stats['uptime_formatted'] = format_uptime(uptime_seconds)
    except:
        pass

    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = int(f.read().strip()) / 1000
            stats['cpu_temp'] = f"{temp:.1f}C"
    except:
        pass

    try:
        result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                stats['disk_total'] = parts[1]
                stats['disk_used'] = parts[2]
                stats['disk_available'] = parts[3]
                stats['disk_percent'] = parts[4]
    except:
        pass

    try:
        result = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            stats['ip_addresses'] = result.stdout.strip().split()
    except:
        pass

    return stats


def format_bytes(size: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def format_uptime(seconds: float) -> str:
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def get_network_info() -> dict:
    import subprocess
    import platform
    import socket

    info = {'hostname': platform.node(), 'interfaces': []}

    try:
        info['local_ip'] = socket.gethostbyname(socket.gethostname())
    except:
        info['local_ip'] = 'Unknown'

    is_linux = platform.system() == 'Linux'

    # WiFi SSID
    try:
        if is_linux:
            result = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                info['ssid'] = result.stdout.strip() or 'Not connected'
        else:
            result = subprocess.run(
                ['/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport', '-I'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if ' SSID:' in line:
                        info['ssid'] = line.split(':', 1)[1].strip()
    except:
        info['ssid'] = 'Unknown'

    # Signal strength and link quality (Linux/Pi)
    if is_linux:
        try:
            result = subprocess.run(['iwconfig', 'wlan0'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                output = result.stdout
                for line in output.split('\n'):
                    if 'Bit Rate' in line:
                        for part in line.split('  '):
                            part = part.strip()
                            if part.startswith('Bit Rate'):
                                info['bit_rate'] = part.split('=')[1] if '=' in part else part.split(':')[1]
                    if 'Link Quality' in line:
                        for part in line.split('  '):
                            part = part.strip()
                            if part.startswith('Link Quality'):
                                info['link_quality'] = part.split('=')[1].split(' ')[0]
                            if part.startswith('Signal level'):
                                info['signal_level'] = part.split('=')[1]
        except:
            pass

        # Traffic stats
        try:
            with open('/sys/class/net/wlan0/statistics/rx_bytes') as f:
                info['rx_bytes'] = format_bytes(int(f.read().strip()))
            with open('/sys/class/net/wlan0/statistics/tx_bytes') as f:
                info['tx_bytes'] = format_bytes(int(f.read().strip()))
        except:
            pass

    # IP addresses per interface
    try:
        if is_linux:
            result = subprocess.run(['ip', '-brief', 'addr'], capture_output=True, text=True, timeout=5)
        else:
            result = subprocess.run(['ifconfig'], capture_output=True, text=True, timeout=5)

        if result.returncode == 0:
            if is_linux:
                for line in result.stdout.strip().split('\n'):
                    parts = line.split()
                    if len(parts) >= 3:
                        info['interfaces'].append({
                            'name': parts[0],
                            'state': parts[1],
                            'addresses': parts[2:]
                        })
            else:
                current_iface = None
                for line in result.stdout.split('\n'):
                    if line and not line.startswith('\t') and not line.startswith(' '):
                        current_iface = line.split(':')[0]
                    elif current_iface and 'inet ' in line:
                        addr = line.strip().split()[1]
                        info['interfaces'].append({
                            'name': current_iface,
                            'state': 'UP',
                            'addresses': [addr]
                        })
    except:
        pass

    # Internet connectivity check
    try:
        result = subprocess.run(['ping', '-c', '1', '-W', '2', '8.8.8.8'], capture_output=True, text=True, timeout=5)
        info['internet'] = 'Connected' if result.returncode == 0 else 'No connection'
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'time=' in line:
                    time_part = line.split('time=')[1].split()[0]
                    info['ping_ms'] = time_part
    except:
        info['internet'] = 'Unknown'

    return info


@app.route("/admin/device/network")
@admin_required
def admin_network():
    net_info = get_network_info()
    return render_template("admin_network.html", net=net_info)


@app.route("/fragment/present-list")
def fragment_present_list():
    present = get_present_members()
    return render_template("_present_list.html", present=present)


@app.route("/fragment/scan-status")
def fragment_scan_status():
    last_scan = get_last_scan_info()
    return render_template("_scan_status.html", last_scan=last_scan)


def create_app(use_rfid: bool = True):
    init_db()
    stale = auto_checkout_stale()
    if stale:
        print(f"Auto-checked out {stale} stale members from previous session")
    set_presence_callback(notify_clients)
    start_scanner(use_rfid=use_rfid)
    return app


if __name__ == "__main__":
    app = create_app(use_rfid=False)
    app.run(host=WEB_HOST, port=WEB_PORT, debug=True)
