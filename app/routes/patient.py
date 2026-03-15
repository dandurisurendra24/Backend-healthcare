from datetime import datetime, timezone

from flask import Blueprint, g, request

from app.extensions import get_db
from app.utils.decorators import token_required
from app.utils.helpers import parse_object_id, serialize_document


patient_bp = Blueprint("patient", __name__)


@patient_bp.get("/profile")
@token_required(roles=["patient"])
def patient_profile():
    db = get_db()
    profile = db.patient_profiles.find_one({"patient_user_id": g.current_user["_id"]}) or {}
    user = dict(g.current_user_public)
    user["profile"] = serialize_document(profile)
    return {"patient": user}


@patient_bp.post("/reports")
@token_required(roles=["patient"])
def create_own_report():
    db = get_db()
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title", "")).strip()
    details = str(payload.get("details", "")).strip()
    if not title and not details:
        return {"error": "Either title or details is required"}, 400

    profile = db.patient_profiles.find_one({"patient_user_id": g.current_user["_id"]})
    assigned_doctor = profile.get("assigned_doctor_id") if profile else None

    now = datetime.now(timezone.utc)
    report = {
        "patient_user_id": g.current_user["_id"],
        "doctor_user_id": assigned_doctor,
        "created_by": g.current_user["_id"],
        "created_by_role": "patient",
        "title": title,
        "details": details,
        "report_type": str(payload.get("report_type", "self_report")).strip(),
        "vitals": payload.get("vitals", {}),
        "created_at": now,
        "updated_at": now,
    }
    result = db.patient_reports.insert_one(report)
    report["_id"] = result.inserted_id
    return {"message": "Report created", "report": serialize_document(report)}, 201


@patient_bp.get("/reports")
@token_required(roles=["patient"])
def list_own_reports():
    db = get_db()
    reports = [
        serialize_document(r)
        for r in db.patient_reports.find({"patient_user_id": g.current_user["_id"]}).sort("created_at", -1)
    ]
    return {"count": len(reports), "reports": reports}


@patient_bp.get("/reports/<report_id>")
@token_required(roles=["patient"])
def get_own_report(report_id):
    db = get_db()
    report_object_id = parse_object_id(report_id)
    if not report_object_id:
        return {"error": "Invalid report ID"}, 400
    report = db.patient_reports.find_one({"_id": report_object_id})
    if not report:
        return {"error": "Report not found"}, 404
    if report.get("patient_user_id") != g.current_user["_id"]:
        return {"error": "Access denied"}, 403
    return {"report": serialize_document(report)}


@patient_bp.patch("/reports/<report_id>")
@token_required(roles=["patient"])
def update_own_report(report_id):
    db = get_db()
    report_object_id = parse_object_id(report_id)
    if not report_object_id:
        return {"error": "Invalid report ID"}, 400
    report = db.patient_reports.find_one({"_id": report_object_id})
    if not report:
        return {"error": "Report not found"}, 404
    if report.get("patient_user_id") != g.current_user["_id"]:
        return {"error": "Access denied"}, 403

    payload = request.get_json(silent=True) or {}
    allowed_fields = ["title", "details", "report_type", "vitals"]
    update_data = {k: payload[k] for k in allowed_fields if k in payload}
    if not update_data:
        return {"error": "No updatable fields provided"}, 400

    update_data["updated_at"] = datetime.now(timezone.utc)
    db.patient_reports.update_one({"_id": report_object_id}, {"$set": update_data})
    updated = db.patient_reports.find_one({"_id": report_object_id})
    return {"message": "Report updated", "report": serialize_document(updated)}


@patient_bp.get("/prescriptions")
@token_required(roles=["patient"])
def patient_prescriptions():
    db = get_db()
    doctor_cache = {}
    prescriptions = []
    for prescription in db.prescriptions.find({"patient_user_id": g.current_user["_id"]}).sort("created_at", -1):
        prescription_data = serialize_document(prescription)
        doctor_id = prescription.get("doctor_user_id")

        doctor_name = None
        if doctor_id:
            doctor_key = str(doctor_id)
            if doctor_key not in doctor_cache:
                doctor_object_id = parse_object_id(str(doctor_id))
                doctor = (
                    db.users.find_one({"_id": doctor_object_id, "role": "doctor"})
                    if doctor_object_id
                    else None
                )
                doctor_cache[doctor_key] = doctor.get("full_name") if doctor else None
            doctor_name = doctor_cache[doctor_key]

        prescription_data["doctor_name"] = doctor_name
        prescriptions.append(prescription_data)

    return {"count": len(prescriptions), "prescriptions": prescriptions}


@patient_bp.patch("/profile")
@token_required(roles=["patient"])
def update_patient_profile():
    db = get_db()
    payload = request.get_json(silent=True) or {}
    allowed_fields = [
        "gender",
        "date_of_birth",
        "blood_group",
        "address",
        "emergency_contact",
        "medical_history",
    ]
    update_data = {k: payload[k] for k in allowed_fields if k in payload}
    if not update_data:
        return {"error": "No profile fields provided"}, 400

    update_data["updated_at"] = datetime.now(timezone.utc)
    db.patient_profiles.update_one(
        {"patient_user_id": g.current_user["_id"]},
        {"$set": update_data},
        upsert=True,
    )
    profile = db.patient_profiles.find_one({"patient_user_id": g.current_user["_id"]})
    return {
        "message": "Patient profile updated successfully",
        "profile": serialize_document(profile),
    }


@patient_bp.post("/health")
@token_required(roles=["patient"])
def create_patient_health():
    db = get_db()
    payload = request.get_json(silent=True) or {}
    vitals = payload.get("vitals", {})
    if not isinstance(vitals, dict) or not vitals:
        return {"error": "vitals must be a non-empty object"}, 400

    now = datetime.now(timezone.utc)
    health = {
        "patient_user_id": g.current_user["_id"],
        "entered_by": g.current_user["_id"],
        "entered_by_role": "patient",
        "vitals": vitals,
        "notes": str(payload.get("notes", "")).strip(),
        "created_at": now,
        "updated_at": now,
    }
    result = db.patient_health.insert_one(health)
    health["_id"] = result.inserted_id
    return {"message": "Patient health data stored", "health": serialize_document(health)}, 201


@patient_bp.get("/health")
@token_required(roles=["patient"])
def list_patient_health():
    db = get_db()
    health_records = [
        serialize_document(h)
        for h in db.patient_health.find({"patient_user_id": g.current_user["_id"]}).sort("created_at", -1)
    ]
    return {"count": len(health_records), "health_records": health_records}
