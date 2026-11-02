# HospitalFlow AI

## Project name
HospitalFlow AI

## Problem statement
Hospitals need a practical decision-support tool to monitor patient flow, doctor capacity, and emergency surges while avoiding operational overload. Many hospitals still rely on manual review and fragmented spreadsheets, especially during rapid demand spikes.

## Solution
HospitalFlow AI is a lightweight prototype that helps administrators:
- predict patient arrivals for the next hour
- monitor risk and bottlenecks
- check doctor and nurse availability
- support emergency surge planning
- simulate resource changes
- book non-life-threatening urgent-care appointments
- maintain all operational activity in SQLite

## Features
- Streamlit dashboard with operational metrics
- SQLite database with seeded demo data
- Prototype arrival prediction using recent patient data and optional ML model support
- Dynamic risk scoring based on utilization thresholds
- Doctor substitute suggestion workflow
- Emergency surge response support
- Resource what-if simulation for +1 doctor and +1 nurse scenarios
- Appointment booking for non-emergency cases
- Database and status monitoring

## Technology stack
- Python
- Streamlit
- SQLite
- Pandas
- NumPy
- Plotly
- Scikit-learn (optional integration)
- XGBoost (optional integration)

## Architecture
Frontend (Streamlit) -> backend.py -> SQLite database -> dashboard updates

## Database structure
Tables:
- doctors
- patients
- appointments
- resources
- predictions
- emergency_events

## How to install
```bash
cd HospitalFlow_AI
pip install -r requirements.txt
```

## How to run
```bash
streamlit run app.py
```

## Responsible AI statement
This project is operational decision support only. It is not a medical diagnosis system and does not replace clinical judgment or emergency care. In genuine life-threatening emergencies, patients should seek immediate emergency medical care instead of waiting for an online appointment.

## Future improvements
- connect to real-time hospital systems
- integrate actual patient arrival forecasting models
- add staff scheduling and bed utilization analytics
- build more advanced emergency triage support
- improve dashboard alerts and role-based workflow

---

This prototype is designed to be simple, fast, and demonstrable for a hackathon Phase 2 application demo.
