import pickle
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from database import DB_PATH, get_connection

MODEL_PATH = Path(__file__).resolve().parent / "models" / "model.pkl"

# Prototype-only thresholds for operational decision support.
# They are not clinical standards and must not be used for diagnosis.
PROTOTYPE_THRESHOLDS = {
    "LOW": 0.70,
    "MEDIUM": 0.90,
}


def load_ml_model():
    path = MODEL_PATH
    if not path.exists():
        return None
    try:
        with open(path, "rb") as file:
            return pickle.load(file)
    except Exception:
        return None


def get_recent_arrivals(department=None, limit=12):
    conn = get_connection()
    try:
        if department:
            rows = conn.execute(
                """
                SELECT arrival_time, department
                FROM patients
                WHERE department = ?
                ORDER BY arrival_time DESC
                LIMIT ?
                """,
                (department, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT arrival_time, department FROM patients ORDER BY arrival_time DESC LIMIT ?",
                (limit,),
            ).fetchall()

        data = []
        for row in rows:
            data.append({"arrival_time": row["arrival_time"], "department": row["department"]})
        return data
    finally:
        conn.close()


def _department_baseline(department):
    defaults = {
        "Emergency": 9,
        "Medicine": 6,
        "Surgery": 5,
        "Orthopedics": 4,
        "Pediatrics": 3,
    }
    return defaults.get(department, 5)


def predict_arrivals(recent_data=None, department="Emergency"):
    """Prototype prediction function. If an ML model is available, it is used when possible;
    otherwise, a simple operational fallback is applied with recent-arrival trends."""
    if recent_data is None:
        recent_data = get_recent_arrivals(department=department, limit=20)

    if isinstance(recent_data, pd.DataFrame):
        recent_values = recent_data["count"] if "count" in recent_data.columns else [len(recent_data)]
    elif isinstance(recent_data, list):
        recent_values = []
        for item in recent_data:
            if isinstance(item, dict):
                if "count" in item:
                    recent_values.append(float(item["count"]))
                elif "arrival_time" in item:
                    recent_values.append(1.0)
            elif isinstance(item, (int, float, np.number)):
                recent_values.append(float(item))
    else:
        recent_values = [float(recent_data)]

    if len(recent_values) == 0:
        recent_values = [_department_baseline(department)]

    model = load_ml_model()
    if model is not None:
        try:
            features = np.array([[len(recent_values), float(np.mean(recent_values)), float(np.std(recent_values))]], dtype=float)
            if hasattr(model, "predict"):
                prediction = model.predict(features)[0]
                return max(0, int(round(float(prediction))))
        except Exception:
            pass

    average_recent = float(np.mean(recent_values))
    trend = 0.0
    if len(recent_values) > 1:
        trend = (recent_values[-1] - recent_values[0]) * 0.7
    fallback = average_recent + trend + (_department_baseline(department) * 0.15)
    return max(0, int(round(fallback)))


def calculate_risk(predicted_arrivals, capacity):
    """Prototype-only operational thresholds. These should be treated as configurable settings,
    not medical standards."""
    if capacity <= 0:
        utilization = 1.0
    else:
        utilization = predicted_arrivals / capacity

    if utilization < PROTOTYPE_THRESHOLDS["LOW"]:
        level = "LOW"
    elif utilization < PROTOTYPE_THRESHOLDS["MEDIUM"]:
        level = "MEDIUM"
    else:
        level = "HIGH"

    return round(utilization, 2), level


def _get_doctor_by_name(name):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM doctors WHERE name = ?",
            (name,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def find_substitute_doctor(assigned_doctor_name=None, department=None, specialization=None):
    conn = get_connection()
    try:
        if assigned_doctor_name:
            assigned = _get_doctor_by_name(assigned_doctor_name)
            if assigned:
                department = assigned.get("department") or department
                specialization = assigned.get("specialization") or specialization

        rows = conn.execute(
            "SELECT * FROM doctors WHERE available = 1 ORDER BY current_load ASC, name ASC"
        ).fetchall()
        doctors = [dict(row) for row in rows]

        if assigned_doctor_name:
            doctors = [doc for doc in doctors if doc["name"] != assigned_doctor_name]

        if not doctors:
            return None

        if department:
            same_department = [doc for doc in doctors if doc["department"] == department]
            if same_department:
                doctors = same_department

        if specialization:
            same_specialization = [doc for doc in doctors if doc["specialization"] == specialization]
            if same_specialization:
                doctors = same_specialization

        best = sorted(doctors, key=lambda d: (d.get("current_load", 0), d.get("name", "")))[0]
        return {
            "name": best["name"],
            "specialization": best["specialization"],
            "department": best["department"],
            "shift": best["shift"],
            "current_load": best["current_load"],
        }
    finally:
        conn.close()


def emergency_surge(expected_additional_patients, severity):
    conn = get_connection()
    try:
        resources = conn.execute("SELECT SUM(doctors) AS doctors, SUM(nurses) AS nurses, SUM(beds) AS beds, SUM(capacity) AS capacity FROM resources").fetchone()
        total_doctors = int(resources["doctors"] or 0)
        total_nurses = int(resources["nurses"] or 0)
        total_beds = int(resources["beds"] or 0)
        total_capacity = int(resources["capacity"] or 0)

        current_queue = conn.execute("SELECT COUNT(*) AS total FROM patients WHERE status IN ('Waiting', 'Checked In')").fetchone()["total"]
        recent_prediction = conn.execute("SELECT predicted_arrivals FROM predictions ORDER BY id DESC LIMIT 1").fetchone()
        base_load = int(recent_prediction["predicted_arrivals"]) if recent_prediction else 12

        predicted_load = base_load + int(expected_additional_patients)
        predicted_load += max(0, current_queue // 3)

        utilization, risk_level = calculate_risk(predicted_load, total_capacity)

        shortage = []
        if total_doctors < 3:
            shortage.append("doctor")
        if total_nurses < 6:
            shortage.append("nurse")
        if total_beds < 8:
            shortage.append("bed")

        suggested = []
        severity_multiplier = {"Medium": 1, "High": 2, "Critical": 3}[str(severity).capitalize()]
        if "doctor" in shortage:
            suggested.append(f"+{severity_multiplier} Doctor")
        if "nurse" in shortage:
            suggested.append(f"+{severity_multiplier} Nurse")
        if "bed" in shortage:
            suggested.append(f"+{max(1, severity_multiplier - 1)} Bed")

        if not suggested:
            suggested = ["No immediate operational shortage detected. Continue monitoring patient flow."]

        return {
            "expected_additional_patients": int(expected_additional_patients),
            "current_queue": current_queue,
            "predicted_load": predicted_load,
            "risk_level": risk_level,
            "resource_shortage": shortage,
            "suggested_additional_resources": suggested,
            "available_doctors": total_doctors,
            "available_nurses": total_nurses,
            "available_beds": total_beds,
            "capacity": total_capacity,
        }
    finally:
        conn.close()


def what_if_simulation():
    conn = get_connection()
    try:
        current = conn.execute("SELECT SUM(doctors) AS doctors, SUM(nurses) AS nurses, SUM(beds) AS beds, SUM(capacity) AS capacity FROM resources").fetchone()
        capacity = int(current["capacity"] or 0)
        current_doctors = int(current["doctors"] or 0)
        current_nurses = int(current["nurses"] or 0)

        latest_prediction = conn.execute("SELECT predicted_arrivals FROM predictions ORDER BY id DESC LIMIT 1").fetchone()
        predicted_arrivals = int(latest_prediction["predicted_arrivals"]) if latest_prediction else 12

        scenarios = []
        for label, d_delta, n_delta in [("No Change", 0, 0), ("+1 Doctor", 1, 0), ("+1 Nurse", 0, 1)]:
            effective_capacity = capacity + (d_delta * 12) + (n_delta * 8)
            utilization, risk_level = calculate_risk(predicted_arrivals, effective_capacity)
            scenarios.append(
                {
                    "Scenario": label,
                    "Doctors Added": d_delta,
                    "Nurses Added": n_delta,
                    "Estimated Capacity": effective_capacity,
                    "Risk": risk_level,
                    "Utilization": utilization,
                }
            )

        return {
            "current_doctors": current_doctors,
            "current_nurses": current_nurses,
            "current_capacity": capacity,
            "predicted_arrivals": predicted_arrivals,
            "scenarios": scenarios,
        }
    finally:
        conn.close()


def get_available_slots():
    conn = get_connection()
    try:
        doctors = conn.execute("SELECT * FROM doctors WHERE available = 1 ORDER BY name ASC").fetchall()
        booked = conn.execute("SELECT doctor, appointment_time FROM appointments").fetchall()
        booked_map = {(row["doctor"], row["appointment_time"]) for row in booked}

        slots = []
        for doc in doctors:
            start = datetime.now().replace(minute=0, second=0, microsecond=0)
            for offset in range(0, 7):
                for hour in [9, 13, 16]:
                    slot_time = (start + timedelta(days=offset, hours=hour - start.hour)).replace(minute=0)
                    if slot_time < start:
                        continue
                    key = (doc["name"], slot_time.strftime("%Y-%m-%d %H:%M:%S"))
                    if key not in booked_map:
                        slots.append({
                            "doctor": doc["name"],
                            "specialization": doc["specialization"],
                            "department": doc["department"],
                            "slot": slot_time.strftime("%Y-%m-%d %H:%M:%S"),
                            "status": "Available",
                        })

        return slots[:20]
    finally:
        conn.close()


def book_appointment(patient_name, age, department, reason, doctor, appointment_time):
    if not patient_name or not department or not doctor or not appointment_time:
        return {"success": False, "message": "Please complete all required appointment details."}

    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT COUNT(*) AS count FROM appointments WHERE doctor = ? AND appointment_time = ?",
            (doctor, appointment_time),
        ).fetchone()
        if existing["count"] > 0:
            return {"success": False, "message": "That appointment slot is already booked."}

        conn.execute(
            """
            INSERT INTO appointments (patient_name, age, department, reason, doctor, appointment_time, status)
            VALUES (?, ?, ?, ?, ?, ?, 'Booked')
            """,
            (patient_name, str(age), department, reason, doctor, appointment_time),
        )
        conn.commit()
        return {
            "success": True,
            "message": "Appointment confirmed.",
            "doctor": doctor,
            "department": department,
            "appointment_time": appointment_time,
            "status": "Booked",
        }
    finally:
        conn.close()


def save_prediction(department, predicted_arrivals, risk_level):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO predictions (timestamp, department, predicted_arrivals, risk_level) VALUES (?, ?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), department, predicted_arrivals, risk_level),
        )
        conn.commit()
    finally:
        conn.close()


def get_dashboard_data():
    conn = get_connection()
    try:
        latest_prediction = conn.execute(
            "SELECT department, predicted_arrivals, risk_level FROM predictions ORDER BY id DESC LIMIT 1"
        ).fetchone()

        total_resources = conn.execute(
            "SELECT SUM(doctors) AS doctors, SUM(nurses) AS nurses, SUM(beds) AS beds, SUM(capacity) AS capacity FROM resources"
        ).fetchone()

        current_queue = conn.execute(
            "SELECT COUNT(*) AS total FROM patients WHERE status IN ('Waiting', 'Checked In')"
        ).fetchone()["total"]

        actual_arrivals = conn.execute(
            "SELECT COUNT(*) AS total FROM patients WHERE arrival_time >= datetime('now', '-24 hours')"
        ).fetchone()["total"]

        risk_value = "LOW"
        predicted_arrivals = 0
        if latest_prediction:
            predicted_arrivals = int(latest_prediction["predicted_arrivals"])
            risk_value = latest_prediction["risk_level"]

        utilization, risk = calculate_risk(predicted_arrivals, int(total_resources["capacity"] or 1))

        reasons = []
        if predicted_arrivals >= 20:
            reasons.append("Recent patient arrivals increased")
        if current_queue > 10:
            reasons.append("Current queue is high")
        if total_resources["capacity"] and predicted_arrivals / total_resources["capacity"] >= 0.7:
            reasons.append("Available capacity is limited")
        if not reasons:
            reasons = ["Operations remain stable and monitoring continues"]

        return {
            "predicted_arrivals": predicted_arrivals,
            "current_queue": current_queue,
            "available_doctors": int(total_resources["doctors"] or 0),
            "available_nurses": int(total_resources["nurses"] or 0),
            "available_beds": int(total_resources["beds"] or 0),
            "risk_level": risk_value,
            "utilization": utilization,
            "current_arrivals": actual_arrivals,
            "reasons": reasons,
        }
    finally:
        conn.close()


def get_db_status():
    conn = get_connection()
    try:
        counts = {
            "patients": conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0],
            "doctors": conn.execute("SELECT COUNT(*) FROM doctors").fetchone()[0],
            "appointments": conn.execute("SELECT COUNT(*) FROM appointments").fetchone()[0],
            "predictions": conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0],
            "emergency_events": conn.execute("SELECT COUNT(*) FROM emergency_events").fetchone()[0],
        }
        return counts
    finally:
        conn.close()


def get_recent_patient_counts_by_department():
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT department, COUNT(*) AS count
            FROM patients
            WHERE arrival_time >= datetime('now', '-24 hours')
            GROUP BY department
            ORDER BY count DESC
            """
        ).fetchall()
        df = pd.DataFrame([dict(row) for row in rows], columns=["department", "count"])
        return df
    finally:
        conn.close()


def get_department_prediction_snapshot(department):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT arrival_time, department FROM patients WHERE department = ? ORDER BY arrival_time DESC LIMIT 24",
            (department,),
        ).fetchall()
        data = []
        for row in rows:
            data.append({"arrival_time": row["arrival_time"], "department": row["department"]})
        return data
    finally:
        conn.close()
