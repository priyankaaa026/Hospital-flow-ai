import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DB_DIR / "hospital.db"


def get_connection():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS doctors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                specialization TEXT,
                department TEXT,
                available INTEGER,
                shift TEXT,
                current_load INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                age INTEGER,
                department TEXT,
                arrival_time TEXT,
                priority TEXT,
                status TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_name TEXT,
                age INTEGER,
                department TEXT,
                reason TEXT,
                doctor TEXT,
                appointment_time TEXT,
                status TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                department TEXT,
                doctors INTEGER,
                nurses INTEGER,
                beds INTEGER,
                capacity INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                department TEXT,
                predicted_arrivals INTEGER,
                risk_level TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS emergency_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                expected_patients INTEGER,
                severity TEXT,
                timestamp TEXT,
                status TEXT
            )
            """
        )
        conn.commit()

        seed_demo_data(conn)
    finally:
        conn.close()

    return DB_PATH


def seed_demo_data(conn):
    doctor_rows = [
        ("Dr. Ravi Kumar", "Cardiology", "Emergency", 1, "Morning", 4),
        ("Dr. Meera Shah", "Neurology", "Emergency", 1, "Morning", 3),
        ("Dr. Anil Verma", "Orthopedics", "Orthopedics", 0, "Evening", 7),
        ("Dr. Priya Nair", "General Medicine", "Medicine", 1, "Morning", 5),
        ("Dr. Arjun Singh", "General Surgery", "Surgery", 1, "Night", 2),
        ("Dr. Neha Joshi", "Pediatrics", "Pediatrics", 1, "Evening", 2),
        ("Dr. Faisal Khan", "Emergency Medicine", "Emergency", 1, "Night", 4),
    ]

    if conn.execute("SELECT COUNT(*) FROM doctors").fetchone()[0] == 0:
        conn.executemany(
            """
            INSERT INTO doctors (name, specialization, department, available, shift, current_load)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            doctor_rows,
        )

    if conn.execute("SELECT COUNT(*) FROM resources").fetchone()[0] == 0:
        resource_rows = [
            ("Emergency", 3, 5, 8, 40),
            ("Medicine", 2, 4, 10, 32),
            ("Surgery", 2, 3, 7, 26),
            ("Orthopedics", 1, 2, 6, 20),
            ("Pediatrics", 1, 2, 5, 18),
        ]
        conn.executemany(
            "INSERT INTO resources (department, doctors, nurses, beds, capacity) VALUES (?, ?, ?, ?, ?)",
            resource_rows,
        )

    if conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 0:
        departments = ["Emergency", "Medicine", "Surgery", "Orthopedics", "Pediatrics"]
        names = ["Asha", "Raj", "Riya", "Karan", "Nina", "Daniel", "Maya", "Suresh", "Pooja", "Vikram"]
        now = datetime.now()
        patient_rows = []
        for i in range(1, 31):
            dept = departments[(i - 1) % len(departments)]
            age = 18 + ((i * 7) % 52)
            name = names[(i - 1) % len(names)]
            arrival_time = (now - timedelta(hours=i * 2)).strftime("%Y-%m-%d %H:%M:%S")
            priority = ["Routine", "Urgent", "Critical"][i % 3]
            status = ["Waiting", "Checked In", "Admitted"][i % 3]
            patient_rows.append((name, age, dept, arrival_time, priority, status))

        conn.executemany(
            """
            INSERT INTO patients (name, age, department, arrival_time, priority, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            patient_rows,
        )

    if conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 0:
        now = datetime.now()
        prediction_rows = [
            (now.strftime("%Y-%m-%d %H:%M:%S"), "Emergency", 12, "HIGH"),
            (now.strftime("%Y-%m-%d %H:%M:%S"), "Medicine", 8, "MEDIUM"),
            (now.strftime("%Y-%m-%d %H:%M:%S"), "Surgery", 7, "MEDIUM"),
        ]
        conn.executemany(
            "INSERT INTO predictions (timestamp, department, predicted_arrivals, risk_level) VALUES (?, ?, ?, ?)",
            prediction_rows,
        )

    if conn.execute("SELECT COUNT(*) FROM emergency_events").fetchone()[0] == 0:
        now = datetime.now()
        conn.execute(
            """
            INSERT INTO emergency_events (event_type, expected_patients, severity, timestamp, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("Accident", 6, "Medium", now.strftime("%Y-%m-%d %H:%M:%S"), "Resolved"),
        )

    if conn.execute("SELECT COUNT(*) FROM appointments").fetchone()[0] == 0:
        now = datetime.now()
        appointment_rows = [
            ("Anu Sharma", 29, "Medicine", "Fever follow-up", "Dr. Priya Nair", (now + timedelta(days=1, hours=2)).strftime("%Y-%m-%d %H:%M:%S"), "Booked"),
            ("Harish Rao", 42, "Orthopedics", "Knee pain review", "Dr. Anil Verma", (now + timedelta(days=2, hours=9)).strftime("%Y-%m-%d %H:%M:%S"), "Booked"),
        ]
        conn.executemany(
            """
            INSERT INTO appointments (patient_name, age, department, reason, doctor, appointment_time, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            appointment_rows,
        )

    conn.commit()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at: {DB_PATH}")
