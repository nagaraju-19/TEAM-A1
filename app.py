import os
import re
import secrets
import sqlite3
from datetime import date, datetime
from functools import wraps
from html import escape
from pathlib import Path
from typing import Any

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

try:
    from twilio.rest import Client
except ImportError:  # The app still runs in simulation mode without Twilio installed.
    Client = None


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "database.db"))
PERIODS = range(1, 9)
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,40}$")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def init_db() -> None:
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                year INTEGER NOT NULL UNIQUE CHECK(year BETWEEN 1 AND 4)
            );

            CREATE TABLE IF NOT EXISTS sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                section_name TEXT NOT NULL CHECK(section_name IN ('A', 'B', 'C')),
                UNIQUE(class_id, section_name),
                FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS branches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                branch_name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                roll TEXT NOT NULL UNIQUE,
                branch TEXT NOT NULL DEFAULT 'CSE',
                "class" INTEGER NOT NULL,
                section INTEGER NOT NULL,
                parent_name TEXT NOT NULL DEFAULT 'Parent',
                parent_phone TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY("class") REFERENCES classes(id) ON DELETE RESTRICT,
                FOREIGN KEY(section) REFERENCES sections(id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('faculty', 'student')),
                student_id INTEGER UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                period INTEGER NOT NULL CHECK(period BETWEEN 1 AND 8),
                status TEXT NOT NULL CHECK(status IN ('Present', 'Absent')),
                faculty_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(student_id, date, period),
                FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY(faculty_id) REFERENCES users(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                attendance_id INTEGER,
                date TEXT NOT NULL,
                period INTEGER NOT NULL,
                channel TEXT NOT NULL CHECK(channel IN ('sms', 'call')),
                status TEXT NOT NULL,
                message TEXT NOT NULL,
                provider_response TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY(attendance_id) REFERENCES attendance(id) ON DELETE SET NULL
            );
            """
        )
        migrate_student_columns(conn)
        seed_branches(conn)
        seed_academic_structure(conn)
        seed_demo_data(conn)


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def migrate_student_columns(conn: sqlite3.Connection) -> None:
    columns = table_columns(conn, "students")
    if "branch" not in columns:
        conn.execute("ALTER TABLE students ADD COLUMN branch TEXT NOT NULL DEFAULT 'CSE'")
    if "parent_name" not in columns:
        conn.execute("ALTER TABLE students ADD COLUMN parent_name TEXT NOT NULL DEFAULT 'Parent'")

    demo_parent_names = {
        "BT24A001": "Ramesh Rao",
        "BT24A002": "Suresh Kumar",
        "BT24B001": "Kavita Singh",
    }
    for roll, parent_name in demo_parent_names.items():
        conn.execute(
            "UPDATE students SET parent_name = ? WHERE roll = ? AND parent_name = 'Parent'",
            (parent_name, roll),
        )

    demo_branches = {
        "BT24A001": "CSE",
        "BT24A002": "CSE",
        "BT24B001": "ECE",
    }
    for roll, branch in demo_branches.items():
        conn.execute(
            "UPDATE students SET branch = ? WHERE roll = ? AND branch = 'CSE'",
            (branch, roll),
        )


def seed_branches(conn: sqlite3.Connection) -> None:
    for branch in ("CSE", "ECE", "EEE", "IT", "MECH", "CIVIL", "AIML", "DS"):
        conn.execute(
            "INSERT OR IGNORE INTO branches (branch_name) VALUES (?)",
            (branch,),
        )


def seed_academic_structure(conn: sqlite3.Connection) -> None:
    years = [
        (1, "B.Tech 1st Year"),
        (2, "B.Tech 2nd Year"),
        (3, "B.Tech 3rd Year"),
        (4, "B.Tech 4th Year"),
    ]
    for year, name in years:
        conn.execute(
            "INSERT OR IGNORE INTO classes (name, year) VALUES (?, ?)",
            (name, year),
        )

    classes = conn.execute("SELECT id FROM classes").fetchall()
    for class_row in classes:
        for section_name in ("A", "B", "C"):
            conn.execute(
                """
                INSERT OR IGNORE INTO sections (class_id, section_name)
                VALUES (?, ?)
                """,
                (class_row["id"], section_name),
            )


def seed_demo_data(conn: sqlite3.Connection) -> None:
    if not conn.execute("SELECT id FROM users WHERE role = 'faculty' LIMIT 1").fetchone():
        conn.execute(
            """
            INSERT INTO users (username, password, role, created_at)
            VALUES (?, ?, 'faculty', ?)
            """,
            ("faculty", generate_password_hash("faculty123"), now_iso()),
        )

    student_count = conn.execute("SELECT COUNT(*) AS count FROM students").fetchone()["count"]
    if student_count:
        return

    class_one = conn.execute("SELECT id FROM classes WHERE year = 1").fetchone()["id"]
    section_a = conn.execute(
        "SELECT id FROM sections WHERE class_id = ? AND section_name = 'A'",
        (class_one,),
    ).fetchone()["id"]
    section_b = conn.execute(
        "SELECT id FROM sections WHERE class_id = ? AND section_name = 'B'",
        (class_one,),
    ).fetchone()["id"]

    demo_students = [
        ("Ananya Rao", "BT24A001", "CSE", class_one, section_a, "Ramesh Rao", "+15551230001"),
        ("Arjun Kumar", "BT24A002", "CSE", class_one, section_a, "Suresh Kumar", "+15551230002"),
        ("Meera Singh", "BT24B001", "ECE", class_one, section_b, "Kavita Singh", "+15551230003"),
    ]
    for name, roll, branch, class_id, section_id, parent_name, parent_phone in demo_students:
        cur = conn.execute(
            """
            INSERT INTO students (name, roll, branch, "class", section, parent_name, parent_phone)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, roll, branch, class_id, section_id, parent_name, parent_phone),
        )
        if roll == "BT24A001":
            conn.execute(
                """
                INSERT INTO users (username, password, role, student_id, created_at)
                VALUES (?, ?, 'student', ?, ?)
                """,
                ("student", generate_password_hash("student123"), cur.lastrowid, now_iso()),
            )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def current_user() -> dict[str, Any] | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    with get_db() as conn:
        user = conn.execute(
            "SELECT id, username, role, student_id FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if not user:
        session.clear()
        return None
    return dict(user)


def login_required(role: str | None = None):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                flash("Please log in to continue.", "error")
                return redirect(url_for("login", role=role or "faculty"))
            if role and user["role"] != role:
                flash("You do not have access to that page.", "error")
                return redirect(url_for("home"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


def validate_username(username: str) -> str | None:
    username = username.strip().lower()
    if not USERNAME_RE.match(username):
        return None
    return username


def validate_password(password: str, confirm_password: str | None = None) -> str | None:
    if len(password) < 6:
        return "Password must be at least 6 characters."
    if confirm_password is not None and password != confirm_password:
        return "Passwords do not match."
    return None


def valid_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def get_classes(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return rows_to_dicts(
        conn.execute("SELECT id, name, year FROM classes ORDER BY year").fetchall()
    )


def get_sections(conn: sqlite3.Connection, class_id: int | None = None) -> list[dict[str, Any]]:
    if class_id:
        rows = conn.execute(
            """
            SELECT sec.id, sec.class_id, sec.section_name, cls.name AS class_name, cls.year
            FROM sections sec
            JOIN classes cls ON cls.id = sec.class_id
            WHERE sec.class_id = ?
            ORDER BY sec.section_name
            """,
            (class_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT sec.id, sec.class_id, sec.section_name, cls.name AS class_name, cls.year
            FROM sections sec
            JOIN classes cls ON cls.id = sec.class_id
            ORDER BY cls.year, sec.section_name
            """
        ).fetchall()
    return rows_to_dicts(rows)


def get_branches(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return rows_to_dicts(
        conn.execute("SELECT id, branch_name FROM branches ORDER BY branch_name").fetchall()
    )


def branch_names(conn: sqlite3.Connection) -> set[str]:
    return {row["branch_name"] for row in conn.execute("SELECT branch_name FROM branches").fetchall()}


def section_belongs_to_class(conn: sqlite3.Connection, class_id: int, section_id: int) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sections WHERE id = ? AND class_id = ?",
            (section_id, class_id),
        ).fetchone()
        is not None
    )


def student_query() -> str:
    return """
        SELECT
            s.id,
            s.name,
            s.roll,
            s.branch,
            s.parent_name,
            s.parent_phone,
            s."class" AS class_id,
            s.section AS section_id,
            cls.name AS class_name,
            cls.year,
            sec.section_name,
            u.id AS login_user_id,
            u.username AS login_username,
            COALESCE(att.total, 0) AS total_classes,
            COALESCE(att.present_count, 0) AS present_count,
            CASE
                WHEN COALESCE(att.total, 0) = 0 THEN 0
                ELSE ROUND((COALESCE(att.present_count, 0) * 100.0) / att.total, 2)
            END AS attendance_percentage
        FROM students s
        JOIN classes cls ON cls.id = s."class"
        JOIN sections sec ON sec.id = s.section
        LEFT JOIN users u ON u.student_id = s.id AND u.role = 'student'
        LEFT JOIN (
            SELECT
                student_id,
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS present_count
            FROM attendance
            GROUP BY student_id
        ) att ON att.student_id = s.id
    """


def get_students(
    conn: sqlite3.Connection,
    class_id: int | None = None,
    section_id: int | None = None,
    branch: str | None = None,
) -> list[dict[str, Any]]:
    filters: list[str] = []
    params: list[Any] = []
    if class_id:
        filters.append('s."class" = ?')
        params.append(class_id)
    if section_id:
        filters.append("s.section = ?")
        params.append(section_id)
    if branch:
        filters.append("s.branch = ?")
        params.append(branch)

    sql = student_query()
    if filters:
        sql += " WHERE " + " AND ".join(filters)
    sql += " ORDER BY cls.year, sec.section_name, s.roll COLLATE NOCASE"
    return rows_to_dicts(conn.execute(sql, params).fetchall())


def grouped_students(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    groups: dict[int, dict[str, Any]] = {}
    for student in get_students(conn):
        class_group = groups.setdefault(
            student["class_id"],
            {
                "class_id": student["class_id"],
                "class_name": student["class_name"],
                "year": student["year"],
                "branches": {},
            },
        )
        branch_group = class_group["branches"].setdefault(
            student["branch"],
            {
                "branch": student["branch"],
                "sections": {},
            },
        )
        section_group = branch_group["sections"].setdefault(
            student["section_id"],
            {
                "section_id": student["section_id"],
                "section_name": student["section_name"],
                "students": [],
            },
        )
        section_group["students"].append(student)

    output = []
    for class_group in groups.values():
        branches = []
        for branch_group in class_group["branches"].values():
            sections = list(branch_group["sections"].values())
            sections.sort(key=lambda section: section["section_name"])
            branches.append({**branch_group, "sections": sections})
        branches.sort(key=lambda branch_group: branch_group["branch"])
        output.append({**class_group, "branches": branches})
    output.sort(key=lambda group: group["year"])
    return output


def attendance_summary(
    conn: sqlite3.Connection,
    class_id: int | None = None,
    section_id: int | None = None,
    branch: str | None = None,
    attendance_date: str | None = None,
) -> dict[str, Any]:
    filters: list[str] = []
    params: list[Any] = []
    if class_id:
        filters.append('s."class" = ?')
        params.append(class_id)
    if section_id:
        filters.append("s.section = ?")
        params.append(section_id)
    if branch:
        filters.append("s.branch = ?")
        params.append(branch)
    if attendance_date:
        filters.append("a.date = ?")
        params.append(attendance_date)

    where = " WHERE " + " AND ".join(filters) if filters else ""
    row = conn.execute(
        f"""
        SELECT
            COUNT(a.id) AS total,
            SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present,
            SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent
        FROM attendance a
        JOIN students s ON s.id = a.student_id
        {where}
        """,
        params,
    ).fetchone()
    total = row["total"] or 0
    present = row["present"] or 0
    absent = row["absent"] or 0
    percentage = round((present / total) * 100, 2) if total else 0
    return {
        "total": total,
        "present": present,
        "absent": absent,
        "percentage": percentage,
    }


def get_attendance_rows(
    conn: sqlite3.Connection,
    class_id: int | None = None,
    section_id: int | None = None,
    branch: str | None = None,
    attendance_date: str | None = None,
) -> list[dict[str, Any]]:
    filters: list[str] = []
    params: list[Any] = []
    if class_id:
        filters.append('s."class" = ?')
        params.append(class_id)
    if section_id:
        filters.append("s.section = ?")
        params.append(section_id)
    if branch:
        filters.append("s.branch = ?")
        params.append(branch)
    if attendance_date:
        filters.append("a.date = ?")
        params.append(attendance_date)

    where = " WHERE " + " AND ".join(filters) if filters else ""
    return rows_to_dicts(
        conn.execute(
            f"""
            SELECT
                a.id,
                a.date,
                a.period,
                a.status,
                s.id AS student_id,
                s.name,
                s.roll,
                s.branch,
                s.parent_name,
                s.parent_phone,
                cls.name AS class_name,
                cls.year,
                sec.section_name
            FROM attendance a
            JOIN students s ON s.id = a.student_id
            JOIN classes cls ON cls.id = s."class"
            JOIN sections sec ON sec.id = s.section
            {where}
            ORDER BY a.date DESC, a.period ASC, cls.year, sec.section_name, s.roll
            LIMIT 500
            """,
            params,
        ).fetchall()
    )


def get_attendance_map(
    conn: sqlite3.Connection,
    class_id: int,
    section_id: int,
    attendance_date: str,
    period: int,
) -> dict[int, str]:
    rows = conn.execute(
        """
        SELECT a.student_id, a.status
        FROM attendance a
        JOIN students s ON s.id = a.student_id
        WHERE s."class" = ? AND s.section = ? AND a.date = ? AND a.period = ?
        """,
        (class_id, section_id, attendance_date, period),
    ).fetchall()
    return {row["student_id"]: row["status"] for row in rows}


def get_student_stats(conn: sqlite3.Connection, student_id: int) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS present,
            SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) AS absent
        FROM attendance
        WHERE student_id = ?
        """,
        (student_id,),
    ).fetchone()
    total = row["total"] or 0
    present = row["present"] or 0
    absent = row["absent"] or 0
    return {
        "total": total,
        "present": present,
        "absent": absent,
        "percentage": round((present / total) * 100, 2) if total else 0,
    }


def get_student_records(conn: sqlite3.Connection, student_id: int) -> list[dict[str, Any]]:
    return rows_to_dicts(
        conn.execute(
            """
            SELECT id, date, period, status, updated_at
            FROM attendance
            WHERE student_id = ?
            ORDER BY date DESC, period ASC
            """,
            (student_id,),
        ).fetchall()
    )


def get_period_summary(conn: sqlite3.Connection, student_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            period,
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS present
        FROM attendance
        WHERE student_id = ?
        GROUP BY period
        ORDER BY period
        """,
        (student_id,),
    ).fetchall()
    summaries = []
    existing = {row["period"]: row for row in rows}
    for period in PERIODS:
        row = existing.get(period)
        total = row["total"] if row else 0
        present = row["present"] if row else 0
        summaries.append(
            {
                "period": period,
                "total": total,
                "present": present,
                "percentage": round((present / total) * 100, 2) if total else 0,
            }
        )
    return summaries


def get_recent_alerts(conn: sqlite3.Connection, limit: int = 12) -> list[dict[str, Any]]:
    return rows_to_dicts(
        conn.execute(
            """
            SELECT
                al.id,
                al.date,
                al.period,
                al.channel,
                al.status,
                al.message,
                al.provider_response,
                al.created_at,
                s.name,
                s.roll,
                s.branch,
                s.parent_name,
                s.parent_phone
            FROM alerts al
            JOIN students s ON s.id = al.student_id
            ORDER BY al.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    )


def get_faculty_accounts(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return rows_to_dicts(
        conn.execute(
            """
            SELECT id, username, created_at
            FROM users
            WHERE role = 'faculty'
            ORDER BY username COLLATE NOCASE
            """
        ).fetchall()
    )


def save_faculty_login(conn: sqlite3.Connection, username: str, password: str) -> None:
    username = validate_username(username or "")
    password_error = validate_password(password or "")
    if not username:
        raise ValueError("Faculty username must be 3-40 valid characters.")
    if password_error:
        raise ValueError(password_error)
    conn.execute(
        """
        INSERT INTO users (username, password, role, created_at)
        VALUES (?, ?, 'faculty', ?)
        """,
        (username, generate_password_hash(password), now_iso()),
    )


def update_faculty_login(
    conn: sqlite3.Connection, faculty_id: int, username: str, password: str
) -> None:
    username = validate_username(username or "")
    password_error = validate_password(password or "")
    if not username:
        raise ValueError("Faculty username must be 3-40 valid characters.")
    if password_error:
        raise ValueError(password_error)
    cur = conn.execute(
        """
        UPDATE users
        SET username = ?, password = ?
        WHERE id = ? AND role = 'faculty'
        """,
        (username, generate_password_hash(password), faculty_id),
    )
    if cur.rowcount == 0:
        raise ValueError("Faculty account was not found.")


def upsert_student_login(
    conn: sqlite3.Connection, student_id: int, username: str, password: str
) -> None:
    username = validate_username(username or "")
    password_error = validate_password(password or "")
    if not username:
        raise ValueError("Student username must be 3-40 valid characters.")
    if password_error:
        raise ValueError(password_error)

    student = conn.execute("SELECT id FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        raise ValueError("Student was not found.")

    existing = conn.execute(
        "SELECT id FROM users WHERE role = 'student' AND student_id = ?",
        (student_id,),
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE users
            SET username = ?, password = ?
            WHERE id = ? AND role = 'student'
            """,
            (username, generate_password_hash(password), existing["id"]),
        )
    else:
        conn.execute(
            """
            INSERT INTO users (username, password, role, student_id, created_at)
            VALUES (?, ?, 'student', ?, ?)
            """,
            (username, generate_password_hash(password), student_id, now_iso()),
        )


def twilio_ready() -> bool:
    return bool(
        Client
        and os.environ.get("TWILIO_ACCOUNT_SID")
        and os.environ.get("TWILIO_AUTH_TOKEN")
        and os.environ.get("TWILIO_FROM_NUMBER")
    )


def alert_mode() -> str:
    return "Live Twilio" if twilio_ready() else "Simulation"


def send_absent_alerts(
    conn: sqlite3.Connection,
    student: dict[str, Any],
    attendance_id: int,
    attendance_date: str,
    period: int,
) -> list[dict[str, Any]]:
    sms_message = (
        f"Your son/daughter {student['name']} (Roll No: {student['roll']}) "
        f"is absent to the college today on {attendance_date}."
    )
    call_message = (
        f"Hello, your son or daughter {student['name']} is absent to the college today."
    )
    results = [
        deliver_alert("sms", student["parent_phone"], sms_message),
        deliver_alert("call", student["parent_phone"], call_message),
    ]

    saved_alerts = []
    for result in results:
        cur = conn.execute(
            """
            INSERT INTO alerts
                (student_id, attendance_id, date, period, channel, status, message, provider_response, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                student["id"],
                attendance_id,
                attendance_date,
                period,
                result["channel"],
                result["status"],
                result["message"],
                result["provider_response"],
                now_iso(),
            ),
        )
        saved_alerts.append({**result, "id": cur.lastrowid})
    return saved_alerts


def deliver_alert(channel: str, destination: str, message: str) -> dict[str, str]:
    if not twilio_ready():
        return {
            "channel": channel,
            "status": "simulated",
            "message": message,
            "provider_response": "Twilio credentials are not configured. Alert was logged only.",
        }

    client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
    from_number = os.environ.get("TWILIO_FROM_NUMBER", "")
    voice_from_number = os.environ.get("TWILIO_VOICE_FROM_NUMBER", from_number)
    try:
        if channel == "sms":
            response = client.messages.create(
                body=message,
                from_=from_number,
                to=destination,
            )
        else:
            twiml = f"<Response><Say>{escape(message)}</Say></Response>"
            response = client.calls.create(
                twiml=twiml,
                from_=voice_from_number,
                to=destination,
            )
        return {
            "channel": channel,
            "status": "sent",
            "message": message,
            "provider_response": getattr(response, "sid", "sent"),
        }
    except Exception as exc:
        return {
            "channel": channel,
            "status": "failed",
            "message": message,
            "provider_response": str(exc),
        }


def parse_int_arg(name: str) -> int | None:
    value = request.args.get(name, "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def selected_or_default(conn: sqlite3.Connection) -> tuple[int | None, str | None, int | None]:
    class_id = parse_int_arg("class_id")
    branch = request.args.get("branch", "").strip().upper() or None
    section_id = parse_int_arg("section_id")
    branches = branch_names(conn)
    if not branch or branch not in branches:
        first_branch = conn.execute("SELECT branch_name FROM branches ORDER BY branch_name LIMIT 1").fetchone()
        branch = first_branch["branch_name"] if first_branch else None
    if class_id and section_id and section_belongs_to_class(conn, class_id, section_id):
        return class_id, branch, section_id
    if class_id:
        first_section = conn.execute(
            "SELECT id FROM sections WHERE class_id = ? ORDER BY section_name LIMIT 1",
            (class_id,),
        ).fetchone()
        return class_id, branch, first_section["id"] if first_section else None
    first_class = conn.execute("SELECT id FROM classes ORDER BY year LIMIT 1").fetchone()
    if not first_class:
        return None, branch, None
    first_section = conn.execute(
        "SELECT id FROM sections WHERE class_id = ? ORDER BY section_name LIMIT 1",
        (first_class["id"],),
    ).fetchone()
    return first_class["id"], branch, first_section["id"] if first_section else None


@app.context_processor
def inject_globals() -> dict[str, Any]:
    return {
        "current_user": current_user(),
        "alert_mode": alert_mode(),
        "today": date.today().isoformat(),
    }


@app.route("/")
def home():
    user = current_user()
    if not user:
        return redirect(url_for("login", role="faculty"))
    if user["role"] == "faculty":
        return redirect(url_for("faculty_dashboard"))
    return redirect(url_for("student_dashboard"))


@app.route("/login/<role>", methods=["GET", "POST"])
@app.route("/<role>/login", methods=["GET", "POST"])
def login(role: str):
    if role not in {"faculty", "student"}:
        return redirect(url_for("login", role="faculty"))

    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        if not username or not password:
            flash("Username and password are required.", "error")
        else:
            with get_db() as conn:
                user = row_to_dict(
                    conn.execute(
                        "SELECT id, username, password, role, student_id FROM users WHERE lower(username) = ?",
                        (username,),
                    ).fetchone()
                )
            if not user or not check_password_hash(user["password"], password):
                flash("Invalid username or password.", "error")
            elif user["role"] != role:
                flash("This account does not match the selected login type.", "error")
            else:
                session.clear()
                session["user_id"] = user["id"]
                session["role"] = user["role"]
                flash("Logged in successfully.", "success")
                return redirect(url_for("home"))

    return render_template("login.html", role=role, mode="login")


@app.route("/signup/<role>", methods=["GET", "POST"])
@app.route("/<role>/signup", methods=["GET", "POST"])
def signup(role: str):
    if role not in {"faculty", "student"}:
        return redirect(url_for("signup", role="faculty"))

    if request.method == "POST":
        username = validate_username(request.form.get("username", ""))
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        password_error = validate_password(password, confirm_password)

        if not username:
            flash("Username must be 3-40 characters and use only letters, numbers, dot, dash, or underscore.", "error")
        elif password_error:
            flash(password_error, "error")
        else:
            try:
                with get_db() as conn:
                    if role == "faculty":
                        conn.execute(
                            """
                            INSERT INTO users (username, password, role, created_at)
                            VALUES (?, ?, 'faculty', ?)
                            """,
                            (username, generate_password_hash(password), now_iso()),
                        )
                    else:
                        roll = request.form.get("roll", "").strip().upper()
                        parent_phone = request.form.get("parent_phone", "").strip()
                        student = conn.execute(
                            """
                            SELECT id FROM students
                            WHERE upper(roll) = ? AND parent_phone = ?
                            """,
                            (roll, parent_phone),
                        ).fetchone()
                        if not student:
                            flash("Student record not found. Ask faculty to add your details first.", "error")
                            return render_template("login.html", role=role, mode="signup")
                        existing = conn.execute(
                            "SELECT id FROM users WHERE role = 'student' AND student_id = ?",
                            (student["id"],),
                        ).fetchone()
                        if existing:
                            flash("A login already exists for this student.", "error")
                            return render_template("login.html", role=role, mode="signup")
                        conn.execute(
                            """
                            INSERT INTO users (username, password, role, student_id, created_at)
                            VALUES (?, ?, 'student', ?, ?)
                            """,
                            (username, generate_password_hash(password), student["id"], now_iso()),
                        )
                flash("Account created. Please log in.", "success")
                return redirect(url_for("login", role=role))
            except sqlite3.IntegrityError:
                flash("That username is already taken.", "error")

    return render_template("login.html", role=role, mode="signup")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login", role="faculty"))


@app.route("/dashboard")
@login_required("faculty")
def faculty_dashboard():
    with get_db() as conn:
        total_students = conn.execute("SELECT COUNT(*) AS count FROM students").fetchone()["count"]
        total_users = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
        today_summary = attendance_summary(conn, attendance_date=date.today().isoformat())
        overall_summary = attendance_summary(conn)
        alerts = get_recent_alerts(conn, 8)
        groups = grouped_students(conn)

    return render_template(
        "dashboard.html",
        view="dashboard",
        total_students=total_students,
        total_users=total_users,
        today_summary=today_summary,
        overall_summary=overall_summary,
        alerts=alerts,
        groups=groups,
    )


@app.route("/accounts")
@login_required("faculty")
def accounts():
    with get_db() as conn:
        faculty_accounts = get_faculty_accounts(conn)
        student_accounts = get_students(conn)

    return render_template(
        "accounts.html",
        faculty_accounts=faculty_accounts,
        student_accounts=student_accounts,
    )


@app.post("/accounts/faculty")
@login_required("faculty")
def add_faculty_account():
    try:
        with get_db() as conn:
            save_faculty_login(
                conn,
                request.form.get("username", ""),
                request.form.get("password", ""),
            )
        flash("Faculty login created successfully.", "success")
    except sqlite3.IntegrityError:
        flash("That username is already in use.", "error")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("accounts"))


@app.post("/accounts/faculty/<int:faculty_id>/password")
@login_required("faculty")
def change_faculty_password(faculty_id: int):
    try:
        with get_db() as conn:
            update_faculty_login(
                conn,
                faculty_id,
                request.form.get("username", ""),
                request.form.get("password", ""),
            )
        flash("Faculty login updated successfully.", "success")
    except sqlite3.IntegrityError:
        flash("That username is already in use.", "error")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("accounts"))


@app.post("/accounts/student/<int:student_id>/password")
@login_required("faculty")
def change_student_password(student_id: int):
    try:
        with get_db() as conn:
            upsert_student_login(
                conn,
                student_id,
                request.form.get("username", ""),
                request.form.get("password", ""),
            )
        flash("Student login updated successfully.", "success")
    except sqlite3.IntegrityError:
        flash("That username is already in use.", "error")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("accounts"))


@app.route("/reports")
@login_required("faculty")
def reports():
    class_id = parse_int_arg("class_id")
    branch = request.args.get("branch", "").strip().upper() or None
    section_id = parse_int_arg("section_id")
    attendance_date = request.args.get("date", "").strip()
    if attendance_date and not valid_date(attendance_date):
        flash("Date filter must be a valid date.", "error")
        attendance_date = ""
    if section_id and not class_id:
        section_id = None

    with get_db() as conn:
        if branch and branch not in branch_names(conn):
            branch = None
        if class_id and section_id and not section_belongs_to_class(conn, class_id, section_id):
            section_id = None
        classes = get_classes(conn)
        branches = get_branches(conn)
        sections = get_sections(conn, class_id)
        summary = attendance_summary(conn, class_id, section_id, branch, attendance_date or None)
        rows = get_attendance_rows(conn, class_id, section_id, branch, attendance_date or None)

    return render_template(
        "dashboard.html",
        view="reports",
        classes=classes,
        branches=branches,
        sections=sections,
        selected_class_id=class_id,
        selected_branch=branch,
        selected_section_id=section_id,
        selected_date=attendance_date,
        report_summary=summary,
        report_rows=rows,
    )


@app.route("/students")
@login_required("faculty")
def students():
    with get_db() as conn:
        class_id, branch, section_id = selected_or_default(conn)
        classes = get_classes(conn)
        branches = get_branches(conn)
        sections = get_sections(conn, class_id)
        selected_students = get_students(conn, class_id, section_id, branch) if class_id and section_id and branch else []
        groups = grouped_students(conn)

    return render_template(
        "students.html",
        classes=classes,
        branches=branches,
        sections=sections,
        selected_class_id=class_id,
        selected_branch=branch,
        selected_section_id=section_id,
        students=selected_students,
        groups=groups,
    )


@app.post("/students/add")
@login_required("faculty")
def add_student():
    name = request.form.get("name", "").strip()
    roll = request.form.get("roll", "").strip().upper()
    branch = request.form.get("branch", "").strip().upper()
    parent_name = request.form.get("parent_name", "").strip()
    parent_phone = request.form.get("parent_phone", "").strip()
    class_id = request.form.get("class_id", type=int)
    section_id = request.form.get("section_id", type=int)

    if not all([name, roll, branch, parent_name, parent_phone, class_id, section_id]):
        flash("All student fields are required.", "error")
        return redirect(url_for("students", class_id=class_id or "", section_id=section_id or ""))

    with get_db() as conn:
        if branch not in branch_names(conn):
            flash("Select a valid branch.", "error")
            return redirect(url_for("students", class_id=class_id, branch="", section_id=section_id))
        if not section_belongs_to_class(conn, class_id, section_id):
            flash("Selected section does not belong to the selected year.", "error")
            return redirect(url_for("students", class_id=class_id, branch=branch))
        try:
            conn.execute(
                """
                INSERT INTO students (name, roll, branch, "class", section, parent_name, parent_phone)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (name, roll, branch, class_id, section_id, parent_name, parent_phone),
            )
            flash("Student added successfully.", "success")
        except sqlite3.IntegrityError:
            flash("A student with this roll number already exists.", "error")
    return redirect(url_for("students", class_id=class_id, branch=branch, section_id=section_id))


@app.route("/attendance")
@login_required("faculty")
def attendance():
    attendance_date = request.args.get("date", date.today().isoformat())
    if not valid_date(attendance_date):
        flash("Date must be valid.", "error")
        attendance_date = date.today().isoformat()
    period = request.args.get("period", default=1, type=int)
    if period not in PERIODS:
        period = 1

    with get_db() as conn:
        class_id, branch, section_id = selected_or_default(conn)
        classes = get_classes(conn)
        branches = get_branches(conn)
        sections = get_sections(conn, class_id)
        students_for_section = get_students(conn, class_id, section_id, branch) if class_id and section_id and branch else []
        attendance_map = (
            get_attendance_map(conn, class_id, section_id, attendance_date, period)
            if class_id and section_id
            else {}
        )
        table_rows = get_attendance_rows(conn, class_id, section_id, branch, attendance_date)
        summary = attendance_summary(conn, class_id, section_id, branch, attendance_date)
        alerts = get_recent_alerts(conn, 8)

    return render_template(
        "attendance.html",
        classes=classes,
        branches=branches,
        sections=sections,
        selected_class_id=class_id,
        selected_branch=branch,
        selected_section_id=section_id,
        selected_date=attendance_date,
        selected_period=period,
        periods=list(PERIODS),
        students=students_for_section,
        attendance_map=attendance_map,
        table_rows=table_rows,
        summary=summary,
        alerts=alerts,
    )


@app.post("/attendance/mark")
@login_required("faculty")
def mark_attendance():
    user = current_user()
    class_id = request.form.get("class_id", type=int)
    branch = request.form.get("branch", "").strip().upper()
    section_id = request.form.get("section_id", type=int)
    attendance_date = request.form.get("date", date.today().isoformat())
    period = request.form.get("period", type=int)

    if not class_id or not branch or not section_id or not period:
        flash("Select year, branch, section, date, and period before saving.", "error")
        return redirect(url_for("attendance"))
    if period not in PERIODS:
        flash("Period must be between 1 and 8.", "error")
        return redirect(url_for("attendance", class_id=class_id, branch=branch, section_id=section_id, date=attendance_date))
    if not valid_date(attendance_date):
        flash("Date must be valid.", "error")
        return redirect(url_for("attendance", class_id=class_id, branch=branch, section_id=section_id))

    sent_alerts = 0
    with get_db() as conn:
        if branch not in branch_names(conn):
            flash("Select a valid branch.", "error")
            return redirect(url_for("attendance", class_id=class_id, section_id=section_id))
        if not section_belongs_to_class(conn, class_id, section_id):
            flash("Selected section does not belong to the selected year.", "error")
            return redirect(url_for("attendance", class_id=class_id, branch=branch))

        students_for_section = get_students(conn, class_id, section_id, branch)
        if not students_for_section:
            flash("No students found for this year and section.", "error")
            return redirect(url_for("attendance", class_id=class_id, branch=branch, section_id=section_id, date=attendance_date, period=period))

        for student in students_for_section:
            submitted_status = request.form.get(f"status_{student['id']}", "Present")
            status = "Absent" if submitted_status == "Absent" else "Present"
            previous = conn.execute(
                """
                SELECT id, status FROM attendance
                WHERE student_id = ? AND date = ? AND period = ?
                """,
                (student["id"], attendance_date, period),
            ).fetchone()

            if previous:
                conn.execute(
                    """
                    UPDATE attendance
                    SET status = ?, faculty_id = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (status, user["id"], now_iso(), previous["id"]),
                )
                attendance_id = previous["id"]
            else:
                cur = conn.execute(
                    """
                    INSERT INTO attendance (student_id, date, period, status, faculty_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (student["id"], attendance_date, period, status, user["id"], now_iso(), now_iso()),
                )
                attendance_id = cur.lastrowid

            was_absent = previous is not None and previous["status"] == "Absent"
            if status == "Absent" and not was_absent:
                alerts = send_absent_alerts(conn, student, attendance_id, attendance_date, period)
                sent_alerts += len(alerts)

    message = "Attendance saved successfully."
    if sent_alerts:
        message += f" {sent_alerts} alert attempt(s) logged."
    flash(message, "success")
    return redirect(
        url_for(
            "attendance",
            class_id=class_id,
            branch=branch,
            section_id=section_id,
            date=attendance_date,
            period=period,
        )
    )


@app.route("/student/dashboard")
@login_required("student")
def student_dashboard():
    user = current_user()
    with get_db() as conn:
        student = row_to_dict(
            conn.execute(
                f"""
                {student_query()}
                WHERE s.id = ?
                """,
                (user["student_id"],),
            ).fetchone()
        )
        if not student:
            flash("Student profile not found. Ask faculty to add your details.", "error")
            return redirect(url_for("logout"))
        records = get_student_records(conn, student["id"])
        stats = get_student_stats(conn, student["id"])
        period_summary = get_period_summary(conn, student["id"])

    return render_template(
        "student_dashboard.html",
        student=student,
        records=records,
        stats=stats,
        period_summary=period_summary,
    )


@app.errorhandler(404)
def not_found(_error):
    flash("The page you requested was not found.", "error")
    return redirect(url_for("home"))


@app.errorhandler(500)
def server_error(error):
    app.logger.exception("Unhandled server error: %s", error)
    flash("Something went wrong. Please try again.", "error")
    return redirect(url_for("home"))


init_db()


import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
