import os
from datetime import datetime, timezone
from uuid import uuid4

from flask import Blueprint, Response, current_app, g, request, send_file
from werkzeug.utils import secure_filename

from app.extensions import get_db
from app.utils.decorators import token_required
from app.utils.helpers import parse_object_id, public_user_data, serialize_document
from app.utils.pdf import build_prescription_pdf


doctor_bp = Blueprint("doctor", __name__)


def _matches_user_id(value, user_id):
    if value is None:
        return False
    return str(value) == str(user_id)


def _assigned_patient_ids(db, doctor_id):
    profiles = list(
        db.patient_profiles.find({"assigned_doctor_id": {"$in": [doctor_id, str(doctor_id)]}})
    )
    return [profile["patient_user_id"] for profile in profiles if profile.get("patient_user_id")]


def _report_accessible_by_doctor(db, report, doctor_id):
    if _matches_user_id(report.get("doctor_user_id"), doctor_id):
        return True
    patient_id = report.get("patient_user_id")
    if not patient_id:
        return False
    profile = db.patient_profiles.find_one({"patient_user_id": patient_id})
    return bool(profile and _matches_user_id(profile.get("assigned_doctor_id"), doctor_id))


def _ensure_upload_dir():
    upload_dir = current_app.config.get("REPORT_UPLOAD_DIR")
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


@doctor_bp.get("/profile")
@token_required(roles=["doctor"])
def doctor_profile():
    return {"doctor": g.current_user_public}


@doctor_bp.get("/patients")
@token_required(roles=["doctor"])
def assigned_patients():
    db = get_db()
    doctor_id = g.current_user["_id"]
    profiles = list(
        db.patient_profiles.find({"assigned_doctor_id": {"$in": [doctor_id, str(doctor_id)]}})
    )
    patients = []
    for profile in profiles:
        patient = db.users.find_one(
            {"_id": profile["patient_user_id"], "role": "patient", "is_active": True}
        )
        if patient:
            patient_data = public_user_data(patient)
            patient_data["profile"] = serialize_document(profile)
            patients.append(patient_data)
    return {"count": len(patients), "patients": patients}


@doctor_bp.post("/reports")
@token_required(roles=["doctor"])
def create_patient_report():
    db = get_db()
    payload = request.get_json(silent=True) or {}
    patient_id = parse_object_id(payload.get("patient_user_id", ""))
    if not patient_id:
        return {"error": "patient_user_id is required"}, 400

    patient = db.users.find_one({"_id": patient_id, "role": "patient", "is_active": True})
    if not patient:
        return {"error": "Patient not found"}, 404

    profile = db.patient_profiles.find_one({"patient_user_id": patient_id})
    if not profile or not _matches_user_id(profile.get("assigned_doctor_id"), g.current_user["_id"]):
        return {"error": "Patient is not assigned to this doctor"}, 403

    title = str(payload.get("title", "")).strip()
    details = str(payload.get("details", "")).strip()
    if not title and not details:
        return {"error": "Either title or details is required"}, 400

    now = datetime.now(timezone.utc)
    report = {
        "patient_user_id": patient_id,
        "doctor_user_id": g.current_user["_id"],
        "created_by": g.current_user["_id"],
        "created_by_role": "doctor",
        "title": title,
        "details": details,
        "report_type": str(payload.get("report_type", "clinical")).strip(),
        "vitals": payload.get("vitals", {}),
        "created_at": now,
        "updated_at": now,
    }
    result = db.patient_reports.insert_one(report)
    report["_id"] = result.inserted_id
    return {"message": "Patient report created", "report": serialize_document(report)}, 201


@doctor_bp.post("/reports/upload")
@token_required(roles=["doctor"])
def upload_patient_report_file():
    db = get_db()
    patient_id = parse_object_id(request.form.get("patient_user_id", ""))
    if not patient_id:
        return {"error": "patient_user_id is required"}, 400

    patient = db.users.find_one({"_id": patient_id, "role": "patient", "is_active": True})
    if not patient:
        return {"error": "Patient not found"}, 404

    profile = db.patient_profiles.find_one({"patient_user_id": patient_id})
    if not profile or not _matches_user_id(profile.get("assigned_doctor_id"), g.current_user["_id"]):
        return {"error": "Patient is not assigned to this doctor"}, 403

    upload = request.files.get("file")
    if not upload or not upload.filename:
        return {"error": "file is required"}, 400

    filename = secure_filename(upload.filename)
    if not filename:
        return {"error": "Invalid file name"}, 400

    upload_dir = _ensure_upload_dir()
    ext = os.path.splitext(filename)[1].lower()
    stored_name = f"report-{uuid4().hex}{ext}"
    stored_path = os.path.join(upload_dir, stored_name)
    upload.save(stored_path)

    now = datetime.now(timezone.utc)
    report = {
        "patient_user_id": patient_id,
        "doctor_user_id": g.current_user["_id"],
        "created_by": g.current_user["_id"],
        "created_by_role": "doctor",
        "title": str(request.form.get("title", "")).strip(),
        "details": str(request.form.get("details", "")).strip(),
        "report_type": str(request.form.get("report_type", "file")).strip() or "file",
        "vitals": {},
        "file": {
            "original_name": upload.filename,
            "stored_name": stored_name,
            "content_type": upload.mimetype,
            "size_bytes": os.path.getsize(stored_path),
        },
        "created_at": now,
        "updated_at": now,
    }
    result = db.patient_reports.insert_one(report)
    report["_id"] = result.inserted_id
    return {"message": "Report file uploaded", "report": serialize_document(report)}, 201


@doctor_bp.get("/reports")
@token_required(roles=["doctor"])
def list_patient_reports():
    db = get_db()
    doctor_id = g.current_user["_id"]
    patient_ids = _assigned_patient_ids(db, doctor_id)
    query = {"doctor_user_id": {"$in": [doctor_id, str(doctor_id)]}}
    if patient_ids:
        query = {
            "$or": [
                query,
                {
                    "$and": [
                        {
                            "$or": [
                                {"doctor_user_id": {"$exists": False}},
                                {"doctor_user_id": None},
                                {"doctor_user_id": ""},
                            ]
                        },
                        {"patient_user_id": {"$in": patient_ids}},
                    ]
                },
            ]
        }
    reports = [
        serialize_document(r)
        for r in db.patient_reports.find(query).sort("created_at", -1)
    ]
    return {"count": len(reports), "reports": reports}


@doctor_bp.get("/reports/<report_id>")
@token_required(roles=["doctor"])
def get_patient_report(report_id):
    db = get_db()
    report_object_id = parse_object_id(report_id)
    if not report_object_id:
        return {"error": "Invalid report ID"}, 400
    report = db.patient_reports.find_one({"_id": report_object_id})
    if not report:
        return {"error": "Patient report not found"}, 404
    if not _report_accessible_by_doctor(db, report, g.current_user["_id"]):
        return {"error": "Access denied"}, 403
    return {"report": serialize_document(report)}


@doctor_bp.get("/reports/<report_id>/download")
@token_required(roles=["doctor"])
def download_patient_report_file(report_id):
    db = get_db()
    report_object_id = parse_object_id(report_id)
    if not report_object_id:
        return {"error": "Invalid report ID"}, 400

    report = db.patient_reports.find_one({"_id": report_object_id})
    if not report:
        return {"error": "Patient report not found"}, 404
    if not _report_accessible_by_doctor(db, report, g.current_user["_id"]):
        return {"error": "Access denied"}, 403

    file_info = report.get("file") or {}
    stored_name = file_info.get("stored_name")
    if not stored_name:
        return {"error": "No file attached to this report"}, 404

    upload_dir = current_app.config.get("REPORT_UPLOAD_DIR")
    stored_path = os.path.join(upload_dir, stored_name)
    if not os.path.exists(stored_path):
        return {"error": "File not found on server"}, 404

    download_name = file_info.get("original_name") or stored_name
    return send_file(stored_path, as_attachment=True, download_name=download_name)


@doctor_bp.patch("/reports/<report_id>")
@token_required(roles=["doctor"])
def update_patient_report(report_id):
    db = get_db()
    report_object_id = parse_object_id(report_id)
    if not report_object_id:
        return {"error": "Invalid report ID"}, 400
    report = db.patient_reports.find_one({"_id": report_object_id})
    if not report:
        return {"error": "Patient report not found"}, 404
    if not _report_accessible_by_doctor(db, report, g.current_user["_id"]):
        return {"error": "Access denied"}, 403

    payload = request.get_json(silent=True) or {}
    allowed_fields = ["title", "details", "report_type", "vitals"]
    update_data = {k: payload[k] for k in allowed_fields if k in payload}
    if not update_data:
        return {"error": "No updatable fields provided"}, 400
    update_data["updated_at"] = datetime.now(timezone.utc)
    db.patient_reports.update_one({"_id": report_object_id}, {"$set": update_data})
    updated = db.patient_reports.find_one({"_id": report_object_id})
    return {"message": "Patient report updated", "report": serialize_document(updated)}


@doctor_bp.get("/patients/<patient_id>/health")
@token_required(roles=["doctor"])
def list_patient_health_for_doctor(patient_id):
    db = get_db()
    patient_object_id = parse_object_id(patient_id)
    if not patient_object_id:
        return {"error": "Invalid patient ID"}, 400

    patient = db.users.find_one({"_id": patient_object_id, "role": "patient", "is_active": True})
    if not patient:
        return {"error": "Patient not found"}, 404

    profile = db.patient_profiles.find_one({"patient_user_id": patient_object_id})
    if not profile or not _matches_user_id(profile.get("assigned_doctor_id"), g.current_user["_id"]):
        return {"error": "Patient is not assigned to this doctor"}, 403

    health_records = [
        serialize_document(h)
        for h in db.patient_health.find({"patient_user_id": patient_object_id}).sort("created_at", -1)
    ]
    return {"count": len(health_records), "health_records": health_records}


@doctor_bp.post("/prescriptions")
@token_required(roles=["doctor"])
def create_prescription():
    db = get_db()
    payload = request.get_json(silent=True) or {}
    patient_id = parse_object_id(payload.get("patient_user_id", ""))
    patient = db.users.find_one({"_id": patient_id, "role": "patient", "is_active": True})
    if not patient:
        return {"error": "Patient not found"}, 404

    patient_profile = db.patient_profiles.find_one({"patient_user_id": patient["_id"]})
    if not patient_profile or not _matches_user_id(
        patient_profile.get("assigned_doctor_id"), g.current_user["_id"]
    ):
        return {"error": "This patient is not assigned to the current doctor"}, 403

    medicines = payload.get("medicines", [])
    if not medicines:
        return {"error": "At least one medicine is required"}, 400

    now = datetime.now(timezone.utc)
    prescription = {
        "prescription_code": f"RX-{uuid4().hex[:10].upper()}",
        "patient_user_id": patient["_id"],
        "doctor_user_id": g.current_user["_id"],
        "diagnosis": str(payload.get("diagnosis", "")).strip(),
        "medicines": medicines,
        "advice": str(payload.get("advice", "")).strip(),
        "next_visit_date": str(payload.get("next_visit_date", "")).strip(),
        "created_at": now,
        "updated_at": now,
    }
    result = db.prescriptions.insert_one(prescription)
    prescription["_id"] = result.inserted_id

    return {
        "message": "Prescription created successfully",
        "prescription": serialize_document(prescription),
    }, 201


@doctor_bp.get("/prescriptions")
@token_required(roles=["doctor"])
def list_prescriptions():
    db = get_db()
    doctor_id = g.current_user["_id"]
    prescriptions = [
        serialize_document(p)
        for p in db.prescriptions.find({"doctor_user_id": {"$in": [doctor_id, str(doctor_id)]}}).sort(
            "created_at", -1
        )
    ]
    return {"count": len(prescriptions), "prescriptions": prescriptions}


@doctor_bp.get("/prescriptions/<prescription_id>/download")
@token_required(roles=["doctor", "admin", "patient"])
def download_prescription(prescription_id):
    db = get_db()
    prescription_object_id = parse_object_id(prescription_id)
    prescription = db.prescriptions.find_one({"_id": prescription_object_id})
    if not prescription:
        return {"error": "Prescription not found"}, 404

    if g.current_user["role"] == "doctor" and not _matches_user_id(
        prescription.get("doctor_user_id"), g.current_user["_id"]
    ):
        return {"error": "Access denied"}, 403
    if g.current_user["role"] == "patient" and not _matches_user_id(
        prescription.get("patient_user_id"), g.current_user["_id"]
    ):
        return {"error": "Access denied"}, 403

    patient = db.users.find_one({"_id": prescription["patient_user_id"]})
    doctor = db.users.find_one({"_id": prescription["doctor_user_id"]})
    pdf_buffer = build_prescription_pdf(prescription, patient or {}, doctor or {})

    filename = f"{prescription['prescription_code']}.pdf"
    return Response(
        pdf_buffer.getvalue(),
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@doctor_bp.patch("/prescriptions/<prescription_id>")
@token_required(roles=["doctor"])
def update_prescription(prescription_id):
    db = get_db()
    prescription_object_id = parse_object_id(prescription_id)
    if not prescription_object_id:
        return {"error": "Invalid prescription ID"}, 400

    prescription = db.prescriptions.find_one({"_id": prescription_object_id})
    if not prescription:
        return {"error": "Prescription not found"}, 404
    if not _matches_user_id(prescription.get("doctor_user_id"), g.current_user["_id"]):
        return {"error": "Access denied"}, 403

    payload = request.get_json(silent=True) or {}
    allowed_fields = ["diagnosis", "medicines", "advice", "next_visit_date"]
    update_data = {k: payload[k] for k in allowed_fields if k in payload}
    if not update_data:
        return {"error": "No updatable fields provided"}, 400

    update_data["updated_at"] = datetime.now(timezone.utc)
    db.prescriptions.update_one({"_id": prescription_object_id}, {"$set": update_data})
    updated_prescription = db.prescriptions.find_one({"_id": prescription_object_id})
    return {
        "message": "Prescription updated successfully",
        "prescription": serialize_document(updated_prescription),
    }
