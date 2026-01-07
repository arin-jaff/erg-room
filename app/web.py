"""
Flask Web Application for "Who's In the Erg Room?"
RFID Version - Uses RC522 RFID reader instead of camera/QR codes
"""

import os
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
from app.config import (
    SECRET_KEY, WEB_HOST, WEB_PORT, UPLOAD_DIR, 
    MAX_CONTENT_LENGTH, ALLOWED_EXTENSIONS
)
from app.models import (
    get_present_members, get_all_members, init_db,
    get_member_by_id, update_profile_picture, get_member_presence
)
from app.rfid_scanner import start_scanner, stop_scanner, simulate_scan, set_presence_callback, get_last_scan_info

app = Flask(__name__, 
            template_folder="../templates",
            static_folder="../static")
app.secret_key = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def notify_clients(data: dict):
    """Notify all connected SSE clients of a presence change."""
    pass  # Implemented via polling for simplicity


# ============== Public Routes ==============

@app.route("/")
def index():
    """Main page showing who's in the erg room."""
    present = get_present_members()
    last_scan = get_last_scan_info()
    return render_template("index.html", present=present, last_scan=last_scan)


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


# ============== Login Routes ==============

@app.route("/login", methods=["GET", "POST"])
def login():
    """Login page - enter RFID tag ID to access profile."""
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
    """Log out and clear session."""
    session.clear()
    return redirect(url_for("index"))


# ============== Profile Routes ==============

@app.route("/profile")
def profile():
    """User profile page."""
    if "member_id" not in session:
        return redirect(url_for("login"))
    
    member = get_member_presence(session["member_id"])
    if not member:
        session.clear()
        return redirect(url_for("login"))
    
    return render_template("profile.html", member=member)


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
        # Create unique filename using member ID
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{session['member_id']}.{ext}"
        
        # Remove old profile pictures with different extensions
        for old_ext in ALLOWED_EXTENSIONS:
            old_file = UPLOAD_DIR / f"{session['member_id']}.{old_ext}"
            if old_file.exists() and old_ext != ext:
                old_file.unlink()
        
        # Save new file
        filepath = UPLOAD_DIR / filename
        file.save(filepath)
        
        # Update database
        update_profile_picture(session["member_id"], filename)
        
        flash("Profile picture updated!", "success")
    else:
        flash("Invalid file type. Use PNG, JPG, GIF, or WebP.", "error")
    
    return redirect(url_for("profile"))


# ============== Admin Routes ==============

@app.route("/admin")
def admin():
    """Admin page for testing and managing."""
    members = get_all_members()
    return render_template("admin.html", members=members)


@app.route("/api/all")
def api_all():
    """API endpoint returning all members with status."""
    members = get_all_members()
    return jsonify({"members": members})


@app.route("/api/simulate/<member_id>", methods=["POST"])
def api_simulate(member_id: str):
    """Simulate a scan for testing (admin use)."""
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
    app = create_app(use_rfid=False)  # Test mode without RFID
    app.run(host=WEB_HOST, port=WEB_PORT, debug=True)
