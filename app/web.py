import os
from functools import wraps
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from app.config import (
    SECRET_KEY, WEB_HOST, WEB_PORT, UPLOAD_DIR,
    MAX_CONTENT_LENGTH, ALLOWED_EXTENSIONS, ADMIN_PASSWORD
)
from app.models import (
    get_present_members, get_all_members, init_db,
    get_member_by_id, update_profile_picture, get_member_presence,
    get_pending_tags, create_member, delete_member, update_member,
    update_member_uuid, remove_pending_tag, set_lightweight_mode,
    get_lightweight_mode, get_leaderboard_stats, get_all_tables,
    get_table_data, update_table_row
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
        member_id = request.form.get("member_id", "").strip()

        member = get_member_by_id(member_id)
        if member:
            session["member_id"] = member_id
            session["member_name"] = member["name"]
            return redirect(url_for("profile"))
        else:
            flash("Invalid ID. Please try again.", "error")

    return render_template("login.html")


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


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")

        if password == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin"))
        else:
            flash("Invalid password", "error")

    return render_template("admin_login.html")


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
        boat_class = request.form.get("boat_class", "").strip() or None
        new_uuid = request.form.get("uuid", "").strip()

        if name and rowing_category:
            update_member(member_id, name=name, rowing_category=rowing_category, boat_class=boat_class)

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


@app.route("/leaderboard")
def leaderboard():
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
    set_presence_callback(notify_clients)
    start_scanner(use_rfid=use_rfid)
    return app


if __name__ == "__main__":
    app = create_app(use_rfid=False)
    app.run(host=WEB_HOST, port=WEB_PORT, debug=True)
