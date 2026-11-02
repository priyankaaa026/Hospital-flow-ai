import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from backend import (
    book_appointment,
    calculate_risk,
    emergency_surge,
    find_substitute_doctor,
    get_available_slots,
    get_dashboard_data,
    get_db_status,
    get_department_prediction_snapshot,
    get_recent_patient_counts_by_department,
    predict_arrivals,
    save_prediction,
    what_if_simulation,
)
from database import init_db


st.set_page_config(page_title="HospitalFlow AI", page_icon="🏥", layout="wide")


def apply_dashboard_theme():
    st.markdown(
        """
        <style>
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        .metric-box {
            background: linear-gradient(135deg, #f8fbff, #eef4ff);
            border: 1px solid #d9e4f5;
            border-radius: 16px;
            padding: 18px 18px 14px 18px;
            min-height: 120px;
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04);
        }
        .metric-title {
            font-size: 13px;
            color: #4a5a6a;
            font-weight: 600;
            margin-bottom: 8px;
        }
        .metric-value {
            font-size: 2rem;
            font-weight: 800;
            color: #0f172a;
            line-height: 1.1;
        }
        .status-pill {
            display: inline-block;
            border-radius: 999px;
            padding: 8px 14px;
            font-weight: 700;
            font-size: 12px;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }
        .info-panel {
            background: #f8fafc;
            border: 1px solid #dfeaf5;
            border-radius: 14px;
            padding: 18px;
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.03);
        }
        .warning-banner {
            background: linear-gradient(135deg, #fff7ed, #ffedd5);
            border: 1px solid #fdba74;
            border-radius: 12px;
            padding: 14px 16px;
            color: #9a5b00;
            font-weight: 600;
            margin-bottom: 16px;
        }
        .sidebar .sidebar-content {
            background: #f5f9ff;
        }
        div[data-testid="stSidebarNav"] {
            background: linear-gradient(180deg, #ecf5ff, #f8fbff);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(title, value, icon, accent="#2563eb"):
    st.markdown(
        f"""
        <div class="metric-box">
            <div class="metric-title">{icon} {title}</div>
            <div class="metric-value" style="color:{accent};">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def risk_badge(level):
    colors = {"LOW": "#16a34a", "MEDIUM": "#d97706", "HIGH": "#dc2626"}
    return f"<span class='status-pill' style='background:{colors.get(level, '#64748b')}; color:white;'>{level}</span>"


def sidebar_navigation():
    st.sidebar.title("🏥 HospitalFlow AI")
    st.sidebar.caption("Intelligent Hospital Operations & Emergency Support")
    page = st.sidebar.radio(
        "Navigation",
        [
            "Dashboard",
            "Patient Prediction",
            "Doctor Management",
            "Emergency Surge",
            "What-If Simulation",
            "Online Appointment",
            "Database / System Status",
        ],
    )
    return page


def dashboard_page():
    apply_dashboard_theme()
    st.title("🏥 HospitalFlow AI")
    st.subheader("Intelligent Hospital Operations & Emergency Support")
    data = get_dashboard_data()

    top_row = st.columns(6)
    metric_values = [
        ("Predicted Arrivals", data["predicted_arrivals"], "📈", "#2563eb"),
        ("Current Queue", data["current_queue"], "🧍", "#0f766e"),
        ("Available Doctors", data["available_doctors"], "👨‍⚕️", "#7c3aed"),
        ("Available Nurses", data["available_nurses"], "👩‍🍼", "#db2777"),
        ("Available Beds", data["available_beds"], "🛏️", "#f59e0b"),
        ("Risk Level", data["risk_level"], "⚠️", "#dc2626"),
    ]

    for col, (label, value, icon, accent) in zip(top_row, metric_values):
        with col:
            render_metric_card(label, value, icon, accent)

    st.markdown("---")

    left_col, right_col = st.columns([2, 1])
    with left_col:
        st.markdown("### Operational overview")
        recent_df = get_recent_patient_counts_by_department()
        chart_df = pd.DataFrame(
            {
                "Metric": ["Current Arrivals", "Predicted Arrivals"],
                "Value": [data["current_arrivals"], data["predicted_arrivals"]],
            }
        )
        st.bar_chart(chart_df.set_index("Metric"))

        if not recent_df.empty:
            fig = px.bar(
                recent_df,
                x="department",
                y="count",
                color="department",
                title="Department patient volume",
                labels={"department": "Department", "count": "Patients"},
            )
            fig.update_layout(margin=dict(l=20, r=20, t=40, b=20), paper_bgcolor="white", plot_bgcolor="#f8fafc")
            st.plotly_chart(fig, use_container_width=True)

    with right_col:
        st.markdown("### Risk status")
        st.markdown(
            f"<div class='info-panel'><h4>Current Risk</h4>{risk_badge(data['risk_level'])}</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<div class='warning-banner'>Prototype prediction only — not a medical diagnosis.</div>", unsafe_allow_html=True)
        with st.expander("Why is the risk high?", expanded=True):
            for reason in data["reasons"]:
                st.markdown(f"- {reason}")

        st.markdown("### Quick actions")
        if st.button("Refresh Dashboard", use_container_width=True):
            st.rerun()
        if st.button("Open Patient Prediction", use_container_width=True):
            st.session_state.page = "Patient Prediction"
            st.rerun()

    st.warning("Final clinical decisions remain with hospital staff. This dashboard is for operational support only.")


def prediction_page():
    st.title("📈 Patient Prediction")
    departments = ["Emergency", "Medicine", "Surgery", "Orthopedics", "Pediatrics"]
    department = st.selectbox("Select Department", departments)

    recent_data = get_department_prediction_snapshot(department)
    if recent_data:
        df = pd.DataFrame(recent_data)
        df["hour"] = pd.to_datetime(df["arrival_time"]).dt.strftime("%H:00")
        st.write(f"Current arrivals: {len(df)}")
        st.write(f"Recent arrivals: {df.shape[0]}")
        st.line_chart(df.groupby("hour").size())
    else:
        st.info("No recent patient arrival records available for this department.")

    if st.button("Run Prediction"):
        prediction = predict_arrivals(recent_data=recent_data, department=department)
        capacity = 35 if department == "Emergency" else 25
        utilization, risk = calculate_risk(prediction, capacity)
        save_prediction(department, prediction, risk)

        st.success(f"Prototype Prediction for {department}: {prediction} arrivals next hour")
        st.metric("Risk Level", risk)
        st.metric("Utilization", f"{utilization:.2f}")
        st.caption("This is a prototype operational estimate, not a clinical diagnosis.")


def doctor_management_page():
    st.title("👩‍⚕️ Doctor Management")
    conn = sqlite3.connect(Path(__file__).resolve().parent / "data" / "hospital.db")
    try:
        doctors_df = pd.read_sql_query("SELECT name, specialization, department, available, shift, current_load FROM doctors ORDER BY department, name", conn)
    finally:
        conn.close()

    st.dataframe(doctors_df, use_container_width=True)

    unavailable_doctors = doctors_df[doctors_df["available"] == 0]
    if unavailable_doctors.empty:
        st.info("No unavailable doctors to review at the moment.")
        return

    selected_doctor = st.selectbox("Select unavailable doctor", unavailable_doctors["name"].tolist())

    assigned_doc = doctors_df[doctors_df["name"] == selected_doctor].iloc[0]
    st.markdown(f"**Assigned Doctor:** {selected_doctor}")
    st.markdown(f"**Status:** Unavailable")

    substitute = find_substitute_doctor(
        assigned_doctor_name=str(selected_doctor),
        department=str(assigned_doc["department"]),
        specialization=str(assigned_doc["specialization"]),
    )

    if substitute:
        st.success("Suggested Substitute")
        st.markdown(f"- Name: {substitute['name']}")
        st.markdown(f"- Specialization: {substitute['specialization']}")
        st.markdown(f"- Department: {substitute['department']}")
        st.markdown(f"- Current Load: {substitute['current_load']}")
    else:
        st.warning("No suitable substitute doctor is currently available.")

    if st.button("Assign Substitute"):
        if substitute:
            conn = sqlite3.connect(Path(__file__).resolve().parent / "data" / "hospital.db")
            try:
                cur = conn.cursor()
                cur.execute("UPDATE doctors SET available = 1, current_load = current_load + 1 WHERE name = ?", (substitute["name"],))
                cur.execute("UPDATE doctors SET available = 0 WHERE name = ?", (selected_doctor,))
                conn.commit()
            finally:
                conn.close()
            st.success(f"Substitute assigned: {substitute['name']} for {selected_doctor}.")
            st.caption("Administrator confirmation required before final assignment changes are recorded.")


def emergency_page():
    st.title("🚨 Emergency Surge Mode")
    st.warning("This is an operational decision-support workflow only. It does not diagnose patients or replace clinical judgment.")

    event_type = st.selectbox("Event Type", ["Accident", "Mass Casualty Event", "Other Emergency"])
    expected_patients = st.number_input("Expected Additional Patients", min_value=1, max_value=200, value=10)
    severity = st.selectbox("Severity", ["Medium", "High", "Critical"])

    if st.button("ACTIVATE EMERGENCY SURGE"):
        result = emergency_surge(expected_patients, severity)

        conn = sqlite3.connect(Path(__file__).resolve().parent / "data" / "hospital.db")
        try:
            conn.execute(
                "INSERT INTO emergency_events (event_type, expected_patients, severity, timestamp, status) VALUES (?, ?, ?, datetime('now'), 'Active')",
                (event_type, expected_patients, severity),
            )
            conn.commit()
        finally:
            conn.close()

        st.markdown(f"**Risk:** {result['risk_level']}")
        st.markdown(f"**Predicted Load:** {result['predicted_load']}")
        st.markdown(f"**Available Doctors:** {result['available_doctors']}")
        st.markdown(f"**Available Nurses:** {result['available_nurses']}")
        st.markdown(f"**Available Beds:** {result['available_beds']}")

        if result["resource_shortage"]:
            st.warning(f"Resource shortage: {', '.join(result['resource_shortage'])}")
        st.info(f"Suggested additional resources: {', '.join(result['suggested_additional_resources'])}")
        st.caption("Recommendations are operational prototype guidance for administrators and should be validated by staff.")


def simulation_page():
    st.title("⚙️ Resource What-If Simulator")
    sim = what_if_simulation()
    st.subheader("Current Situation")
    col1, col2, col3 = st.columns(3)
    col1.metric("Doctors", sim["current_doctors"])
    col2.metric("Nurses", sim["current_nurses"])
    col3.metric("Capacity", sim["current_capacity"])

    scenario_df = pd.DataFrame(sim["scenarios"])
    st.table(scenario_df)
    st.bar_chart(scenario_df.set_index("Scenario")["Estimated Capacity"])

    decision = st.selectbox("Administrator Decision", ["No action", "+1 Doctor", "+1 Nurse"])
    if st.button("Confirm Resource Decision"):
        if decision == "+1 Doctor":
            conn = sqlite3.connect(Path(__file__).resolve().parent / "data" / "hospital.db")
            try:
                conn.execute("UPDATE resources SET doctors = doctors + 1, capacity = capacity + 12")
                conn.commit()
            finally:
                conn.close()
            st.success("Administrator confirmed: +1 Doctor added to the operational scenario.")
        elif decision == "+1 Nurse":
            conn = sqlite3.connect(Path(__file__).resolve().parent / "data" / "hospital.db")
            try:
                conn.execute("UPDATE resources SET nurses = nurses + 1, capacity = capacity + 8")
                conn.commit()
            finally:
                conn.close()
            st.success("Administrator confirmed: +1 Nurse added to the operational scenario.")
        else:
            st.info("No change applied. Scenario remains as a decision support option only.")


def appointment_page():
    st.title("📅 Online Appointment / Urgent Care")
    st.markdown("<div style='background:#fff3cd; border: 1px solid #ffeeba; border-radius: 10px; padding: 12px; color:#856404;'>🚨 If this is a life-threatening emergency, do not wait for an online appointment. Seek immediate emergency medical care.</div>", unsafe_allow_html=True)
    st.caption("This booking flow is intended for non-life-threatening urgent-care scheduling only.")

    with st.form("appointment_form"):
        name = st.text_input("Patient Name")
        age = st.number_input("Age", min_value=0, max_value=120, value=30)
        department = st.selectbox("Department", ["Emergency", "Medicine", "Surgery", "Orthopedics", "Pediatrics"])
        reason = st.text_area("Reason for visit")

        slots = get_available_slots()
        if not slots:
            st.warning("No appointment slots are currently available.")
            st.stop()

        slot_options = [f"{s['doctor']} - {s['slot']}" for s in slots]
        selected_slot = st.selectbox("Available slot", slot_options)
        submitted = st.form_submit_button("Book Appointment")

    if submitted:
        selected = next(item for item in slots if f"{item['doctor']} - {item['slot']}" == selected_slot)
        result = book_appointment(name, age, department, reason, selected["doctor"], selected["slot"])
        if result["success"]:
            st.success("Appointment Confirmed")
            st.write(f"Doctor: {result['doctor']}")
            st.write(f"Department: {result['department']}")
            st.write(f"Date/Time: {result['appointment_time']}")
            st.write(f"Status: {result['status']}")
        else:
            st.error(result["message"])


def database_page():
    st.title("🗃️ Database / System Status")
    st.success("Database connection: Connected")

    counts = get_db_status()
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Patients", counts["patients"])
    col2.metric("Doctors", counts["doctors"])
    col3.metric("Appointments", counts["appointments"])
    col4.metric("Predictions", counts["predictions"])
    col5.metric("Emergency Events", counts["emergency_events"])

    conn = sqlite3.connect(Path(__file__).resolve().parent / "data" / "hospital.db")
    try:
        recent_patients = pd.read_sql_query("SELECT * FROM patients ORDER BY id DESC LIMIT 5", conn)
        recent_predictions = pd.read_sql_query("SELECT * FROM predictions ORDER BY id DESC LIMIT 5", conn)
        recent_events = pd.read_sql_query("SELECT * FROM emergency_events ORDER BY id DESC LIMIT 5", conn)
    finally:
        conn.close()

    st.subheader("Recent Patients")
    st.dataframe(recent_patients, use_container_width=True)
    st.subheader("Recent Predictions")
    st.dataframe(recent_predictions, use_container_width=True)
    st.subheader("Recent Emergency Events")
    st.dataframe(recent_events, use_container_width=True)


def main():
    init_db()
    page = sidebar_navigation()

    if page == "Dashboard":
        dashboard_page()
    elif page == "Patient Prediction":
        prediction_page()
    elif page == "Doctor Management":
        doctor_management_page()
    elif page == "Emergency Surge":
        emergency_page()
    elif page == "What-If Simulation":
        simulation_page()
    elif page == "Online Appointment":
        appointment_page()
    elif page == "Database / System Status":
        database_page()


if __name__ == "__main__":
    main()
