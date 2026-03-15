# Health Monitoring Backend

Backend API for a health monitoring system with:

- Admin dashboard APIs
- Doctor dashboard APIs
- Patient dashboard APIs
- JWT authentication
- MongoDB storage
- Prescription PDF download

## Tech Stack

- Python Flask
- MongoDB
- PyJWT
- ReportLab

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python run.py
```

## Create Initial Admin

The app auto-creates the first admin from `.env` on startup using:

- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`

## API Modules

- `/api/auth` authentication routes
- `/api/admin` admin-only routes
- `/api/doctor` doctor-only routes
- `/api/patient` patient-only routes
- `/api/common` authenticated shared routes

## Main Features

- Admin can create doctors
- Admin can create patients and assign doctors
- Doctor can create prescriptions for assigned patients
- Patient can view their prescriptions
- Prescription PDF can be downloaded by doctor, patient, or admin

## Maintenance

Backfill legacy patient reports that are missing `doctor_user_id`:

```bash
python scripts/backfill_report_doctors.py --dry-run
python scripts/backfill_report_doctors.py
```
