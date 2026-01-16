"""
Flask Web Application for "Who's In the Erg Room?"
RFID Version with registration mode and admin panel
"""

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
    get_lightweight_mode
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
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def admin_required(f):
    """Decorator to require admin login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function


def notify_clients(data: dict):
    """Notify all connected SSE clients of a presence change."""
    pass


# ============== Public Routes ==============

@app.route("/")
def index():
    """Main page showing who's in the erg room."""
    present = get_present_members()
    last_scan = get_last_scan_info()
    history = get_scan_history()
    return render_template("index.html", present=present, last_scan=last_scan, scan_history=history)


@app.route("/api/present")
def api_present():
    """API endpoint returning current presence list."""
    present = get_present_members()
    return jsonify({
        "count": len(present),
        "members": present
    })


@app.route("/api/last_scan")
def api_last_scan():
    """API endpoint returning last scan info."""
    return jsonify(get_last_scan_info())


@app.route("/api/scan_history")
def api_scan_history():
    """API endpoint returning rolling scan history."""
    return jsonify(get_scan_history())


@app.route("/api/lightweight_mode")
def api_lightweight_mode():
    """API endpoint returning lightweight mode status."""
    return jsonify({"enabled": get_lightweight_mode()})


# ============== User Login Routes ==============

@app.route("/login", methods=["GET", "POST"])
def login():
    """Login page - enter tag ID to access profile."""
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
    """Log out user (keep admin session if exists)."""
    session.pop("member_id", None)
    session.pop("member_name", None)
    return redirect(url_for("index"))


# ============== User Profile Routes ==============

@app.route("/profile")
def profile():
    """User profile page - can edit name and picture, not UUID."""
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
    """Handle profile updates."""
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
    """Handle profile picture upload."""
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


# ============== Admin Routes ==============

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Admin login page."""
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
    """Log out admin."""
    session.pop("is_admin", None)
    return redirect(url_for("index"))


@app.route("/admin")
@admin_required
def admin():
    """Admin dashboard."""
    members = get_all_members()
    pending = get_pending_tags()
    reg_mode = is_registration_mode()
    lw_mode = get_lightweight_mode()
    return render_template("admin.html", members=members, pending=pending, registration_mode=reg_mode, lightweight_mode=lw_mode)


@app.route("/admin/register/start", methods=["POST"])
@admin_required
def admin_start_registration():
    """Start registration mode."""
    set_registration_mode(True)
    flash("Registration mode enabled. Tap a tag to register it.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/register/stop", methods=["POST"])
@admin_required
def admin_stop_registration():
    """Stop registration mode."""
    set_registration_mode(False)
    flash("Registration mode disabled.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/register/simulate", methods=["POST"])
@admin_required
def admin_simulate_registration():
    """Simulate tag registration (test mode)."""
    result = simulate_registration()
    if result:
        flash(f"Simulated tag registered: {result['tag_id']}", "success")
    return redirect(url_for("admin"))


@app.route("/admin/lightweight_mode/enable", methods=["POST"])
@admin_required
def admin_enable_lightweight_mode():
    """Enable lightweight mode."""
    set_lightweight_mode(True)
    flash("Lightweight mode enabled. Home page will only show LM category.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/lightweight_mode/disable", methods=["POST"])
@admin_required
def admin_disable_lightweight_mode():
    """Disable lightweight mode."""
    set_lightweight_mode(False)
    flash("Lightweight mode disabled. Home page will show all categories.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/member/create", methods=["POST"])
@admin_required
def admin_create_member():
    """Create a new member from a pending tag."""
    tag_id = request.form.get("tag_id", "").strip()
    name = request.form.get("name", "").strip()
    rowing_category = request.form.get("rowing_category", "").strip()

    if not tag_id or not name or not rowing_category:
        flash("All fields are required", "error")
        return redirect(url_for("admin"))

    if create_member(tag_id, name, rowing_category):
        flash(f"Member '{name}' created successfully!", "success")
    else:
        flash("Failed to create member. Tag may already be registered.", "error")

    return redirect(url_for("admin"))


@app.route("/admin/member/<member_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_member(member_id):
    """Edit a member's details including UUID."""
    member = get_member_presence(member_id)
    if not member:
        flash("Member not found", "error")
        return redirect(url_for("admin"))
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        rowing_category = request.form.get("rowing_category", "").strip()
        new_uuid = request.form.get("uuid", "").strip()

        if name and rowing_category:
            update_member(member_id, name=name, rowing_category=rowing_category)

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
    """Delete a member."""
    if delete_member(member_id):
        flash("Member deleted", "success")
    else:
        flash("Failed to delete member", "error")
    
    return redirect(url_for("admin"))


@app.route("/admin/pending/<tag_id>/delete", methods=["POST"])
@admin_required
def admin_delete_pending(tag_id):
    """Delete a pending tag."""
    if remove_pending_tag(tag_id):
        flash("Pending tag removed", "success")
    else:
        flash("Failed to remove pending tag", "error")
    
    return redirect(url_for("admin"))


@app.route("/api/simulate/<member_id>", methods=["POST"])
@admin_required
def api_simulate(member_id: str):
    """Simulate a scan for testing."""
    result = simulate_scan(member_id)
    if result:
        return jsonify({"success": True, "result": result})
    return jsonify({"success": False, "error": "Member not found"}), 404


# ============== HTMX Fragments ==============

@app.route("/fragment/present-list")
def fragment_present_list():
    """Return just the presence list HTML fragment for HTMX."""
    present = get_present_members()
    return render_template("_present_list.html", present=present)


@app.route("/fragment/scan-status")
def fragment_scan_status():
    """Return the last scan status fragment for HTMX."""
    last_scan = get_last_scan_info()
    return render_template("_scan_status.html", last_scan=last_scan)


# ============== App Factory ==============

def create_app(use_rfid: bool = True):
    """Application factory."""
    init_db()
    set_presence_callback(notify_clients)
    start_scanner(use_rfid=use_rfid)
    return app


if __name__ == "__main__":
    app = create_app(use_rfid=False)
    app.run(host=WEB_HOST, port=WEB_PORT, debug=True)
