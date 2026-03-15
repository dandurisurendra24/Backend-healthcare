from datetime import datetime, timezone

from flask import Blueprint, g, request

from app.extensions import get_db
from app.utils.decorators import token_required
from app.utils.helpers import parse_object_id, public_user_data, serialize_document
from app.utils.security import hash_password


admin_bp = Blueprint("admin", __name__)


def _validate_required_fields(payload, fields):
    missing = [field for field in fields if not str(payload.get(field, "")).strip()]
    return missing


def _resolve_doctor_user_id(db, raw_id):
    doctor_object_id = parse_object_id(raw_id)
    if not doctor_object_id:
        return None

    # First try direct user id (preferred)
    doctor_user = db.users.find_one({"_id": doctor_object_id, "role": "doctor", "is_active": True})
    if doctor_user:
        return doctor_user["_id"]

    # Fallback: id might be from doctors collection
    doctor_info = db.doctors.find_one({"_id": doctor_object_id})
    if doctor_info and doctor_info.get("user_id"):
        doctor_user = db.users.find_one(
            {"_id": doctor_info["user_id"], "role": "doctor", "is_active": True}
        )
        if doctor_user:
            return doctor_user["_id"]

    return None


@admin_bp.post("/doctors")
@token_required(roles=["admin"])
def create_doctor():
    db = get_db()
    payload = request.get_json(silent=True) or {}
    missing = _validate_required_fields(
        payload,
        ["full_name", "email", "password", "phone", "specialization", "license_number"],
    )
    if missing:
        return {"error": f"Missing fields: {', '.join(missing)}"}, 400

    email = payload["email"].strip().lower()
    if db.users.find_one({"email": email}):
        return {"error": "Doctor email already exists"}, 409

    now = datetime.now(timezone.utc)
    doctor = {
        "full_name": payload["full_name"].strip(),
        "email": email,
        "password_hash": hash_password(payload["password"].strip()),
        "phone": payload["phone"].strip(),
        "role": "doctor",
        "specialization": payload["specialization"].strip(),
        "license_number": payload["license_number"].strip(),
        "experience_years": payload.get("experience_years", 0),
        "department": payload.get("department", "").strip(),
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    result = db.users.insert_one(doctor)
    doctor_id = result.inserted_id
    doctor["_id"] = doctor_id

    doctor_info = {
        "user_id": doctor_id,
        "full_name": doctor["full_name"],
        "email": doctor["email"],
        "phone": doctor["phone"],
        "specialization": doctor["specialization"],
        "license_number": doctor["license_number"],
        "experience_years": doctor["experience_years"],
        "department": doctor["department"],
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    db.doctors.insert_one(doctor_info)

    return {"message": "Doctor created successfully", "doctor": public_user_data(doctor)}, 201


@admin_bp.post("/patients")
@token_required(roles=["admin"])
def create_patient():
    db = get_db()
    payload = request.get_json(silent=True) or {}
    missing = _validate_required_fields(
        payload,
        ["full_name", "email", "password", "phone", "assigned_doctor_id"],
    )
    if missing:
        return {"error": f"Missing fields: {', '.join(missing)}"}, 400

    email = payload["email"].strip().lower()
    if db.users.find_one({"email": email}):
        return {"error": "Patient email already exists"}, 409

    doctor_user_id = _resolve_doctor_user_id(db, payload["assigned_doctor_id"])
    if not doctor_user_id:
        return {"error": "Assigned doctor not found"}, 404

    now = datetime.now(timezone.utc)
    patient_user = {
        "full_name": payload["full_name"].strip(),
        "email": email,
        "password_hash": hash_password(payload["password"].strip()),
        "phone": payload["phone"].strip(),
        "role": "patient",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    user_result = db.users.insert_one(patient_user)
    patient_user["_id"] = user_result.inserted_id

    profile = {
        "patient_user_id": patient_user["_id"],
        "assigned_doctor_id": doctor_user_id,
        "gender": payload.get("gender", "").strip(),
        "date_of_birth": payload.get("date_of_birth", "").strip(),
        "blood_group": payload.get("blood_group", "").strip(),
        "address": payload.get("address", "").strip(),
        "emergency_contact": payload.get("emergency_contact", "").strip(),
        "medical_history": payload.get("medical_history", []),
        "created_by": "admin",
        "created_at": now,
        "updated_at": now,
    }
    db.patient_profiles.insert_one(profile)

    patient_info = {
        "user_id": patient_user["_id"],
        "full_name": patient_user["full_name"],
        "email": patient_user["email"],
        "phone": patient_user["phone"],
        "assigned_doctor_id": doctor_user_id,
        "gender": profile["gender"],
        "date_of_birth": profile["date_of_birth"],
        "blood_group": profile["blood_group"],
        "address": profile["address"],
        "emergency_contact": profile["emergency_contact"],
        "medical_history": profile["medical_history"],
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    db.patients.insert_one(patient_info)

    return {
        "message": "Patient created successfully",
        "patient": public_user_data(patient_user),
        "profile": serialize_document(profile),
    }, 201


@admin_bp.get("/users")
@token_required(roles=["admin"])
def list_users():
    db = get_db()
    role = request.args.get("role", "").strip().lower()
    query = {"is_active": True}
    if role:
        query["role"] = role

    users = [public_user_data(user) for user in db.users.find(query).sort("created_at", -1)]
    return {"count": len(users), "users": users}


@admin_bp.get("/doctors")
@token_required(roles=["admin"])
def list_doctors():
    db = get_db()
    doctors = [serialize_document(d) for d in db.doctors.find().sort("created_at", -1)]
    return {"count": len(doctors), "doctors": doctors}


@admin_bp.get("/patients/list")
@token_required(roles=["admin"])
def list_patients_data():
    db = get_db()
    patients = [serialize_document(p) for p in db.patients.find().sort("created_at", -1)]
    return {"count": len(patients), "patients": patients}


@admin_bp.patch("/doctors/<doctor_id>")
@token_required(roles=["admin"])
def update_doctor(doctor_id):
    db = get_db()
    doctor_object_id = parse_object_id(doctor_id)
    if not doctor_object_id:
        return {"error": "Invalid doctor ID"}, 400

    doctor_user = db.users.find_one({"_id": doctor_object_id, "role": "doctor"})
    if not doctor_user:
        return {"error": "Doctor not found"}, 404

    payload = request.get_json(silent=True) or {}
    allowed_user_fields = ["full_name", "email", "phone", "is_active", "password"]
    update_user_data = {}
    for field in allowed_user_fields:
        if field in payload:
            value = payload.get(field)
            if isinstance(value, str):
                value = value.strip()
            if field == "email" and value:
                value = value.lower()
            if field == "password":
                value = hash_password(value)
                field = "password_hash"
            update_user_data[field if field != "password" else "password_hash"] = value

    allowed_doc_fields = ["specialization", "license_number", "experience_years", "department", "is_active"]
    update_doc_data = {k: payload[k] for k in allowed_doc_fields if k in payload}

    if not update_user_data and not update_doc_data:
        return {"error": "No updatable fields provided"}, 400

    if "email" in update_user_data:
        existing = db.users.find_one({"email": update_user_data["email"], "_id": {"$ne": doctor_object_id}})
        if existing:
            return {"error": "Email already in use"}, 409

    update_user_data["updated_at"] = datetime.now(timezone.utc)
    db.users.update_one({"_id": doctor_object_id}, {"$set": update_user_data})
    if update_doc_data:
        update_doc_data["updated_at"] = datetime.now(timezone.utc)
        db.doctors.update_one({"user_id": doctor_object_id}, {"$set": update_doc_data}, upsert=True)

    updated = db.users.find_one({"_id": doctor_object_id})
    return {"message": "Doctor updated", "doctor": public_user_data(updated)}


@admin_bp.delete("/doctors/<doctor_id>")
@token_required(roles=["admin"])
def delete_doctor(doctor_id):
    db = get_db()
    doctor_object_id = parse_object_id(doctor_id)
    if not doctor_object_id:
        return {"error": "Invalid doctor ID"}, 400

    doctor_user = db.users.find_one({"_id": doctor_object_id, "role": "doctor"})
    if not doctor_user:
        return {"error": "Doctor not found"}, 404

    db.users.delete_one({"_id": doctor_object_id})
    db.doctors.delete_one({"user_id": doctor_object_id})
    db.patient_profiles.update_many({"assigned_doctor_id": doctor_object_id}, {"$set": {"assigned_doctor_id": None, "updated_at": datetime.now(timezone.utc)}})
    db.patients.update_many({"assigned_doctor_id": doctor_object_id}, {"$set": {"assigned_doctor_id": None, "updated_at": datetime.now(timezone.utc)}})
    return {"message": "Doctor deleted"}


@admin_bp.patch("/patients/<patient_id>")
@token_required(roles=["admin"])
def update_patient(patient_id):
    db = get_db()
    patient_object_id = parse_object_id(patient_id)
    if not patient_object_id:
        return {"error": "Invalid patient ID"}, 400

    patient_user = db.users.find_one({"_id": patient_object_id, "role": "patient"})
    if not patient_user:
        return {"error": "Patient not found"}, 404

    payload = request.get_json(silent=True) or {}
    allowed_user_fields = ["full_name", "email", "phone", "is_active", "password"]
    update_user_data = {}
    for field in allowed_user_fields:
        if field in payload:
            value = payload.get(field)
            if isinstance(value, str):
                value = value.strip()
            if field == "email" and value:
                value = value.lower()
            if field == "password":
                value = hash_password(value)
                field = "password_hash"
            update_user_data[field if field != "password" else "password_hash"] = value

    profile_fields = [
        "assigned_doctor_id",
        "gender",
        "date_of_birth",
        "blood_group",
        "address",
        "emergency_contact",
        "medical_history",
    ]
    update_profile_data = {}
    for field in profile_fields:
        if field in payload:
            value = payload.get(field)
            if field == "assigned_doctor_id":
                doctor_user_id = _resolve_doctor_user_id(db, value)
                if not doctor_user_id:
                    return {"error": "Assigned doctor not found"}, 404
                update_profile_data[field] = doctor_user_id
            else:
                update_profile_data[field] = value

    if not update_user_data and not update_profile_data:
        return {"error": "No updatable fields provided"}, 400

    if "email" in update_user_data:
        existing = db.users.find_one({"email": update_user_data["email"], "_id": {"$ne": patient_object_id}})
        if existing:
            return {"error": "Email already in use"}, 409

    if update_user_data:
        update_user_data["updated_at"] = datetime.now(timezone.utc)
        db.users.update_one({"_id": patient_object_id}, {"$set": update_user_data})

    if update_profile_data:
        update_profile_data["updated_at"] = datetime.now(timezone.utc)
        db.patient_profiles.update_one({"patient_user_id": patient_object_id}, {"$set": update_profile_data}, upsert=True)
        db.patients.update_one({"user_id": patient_object_id}, {"$set": update_profile_data}, upsert=True)

    updated = db.users.find_one({"_id": patient_object_id})
    return {"message": "Patient updated", "patient": public_user_data(updated)}


@admin_bp.delete("/patients/<patient_id>")
@token_required(roles=["admin"])
def delete_patient(patient_id):
    db = get_db()
    patient_object_id = parse_object_id(patient_id)
    if not patient_object_id:
        return {"error": "Invalid patient ID"}, 400

    patient_user = db.users.find_one({"_id": patient_object_id, "role": "patient"})
    if not patient_user:
        return {"error": "Patient not found"}, 404

    db.users.delete_one({"_id": patient_object_id})
    db.patient_profiles.delete_one({"patient_user_id": patient_object_id})
    db.patients.delete_one({"user_id": patient_object_id})
    db.prescriptions.delete_many({"patient_user_id": patient_object_id})
    db.patient_reports.delete_many({"patient_user_id": patient_object_id})
    db.patient_health.delete_many({"patient_user_id": patient_object_id})
    return {"message": "Patient deleted"}


@admin_bp.patch("/users/<user_id>")
@token_required(roles=["admin"])
def update_user(user_id):
    db = get_db()
    user_object_id = parse_object_id(user_id)
    if not user_object_id:
        return {"error": "Invalid user ID"}, 400

    user = db.users.find_one({"_id": user_object_id})
    if not user:
        return {"error": "User not found"}, 404

    payload = request.get_json(silent=True) or {}
    allowed_fields = [
        "full_name",
        "email",
        "phone",
        "is_active",
        "role",
        "specialization",
        "license_number",
        "experience_years",
        "department",
    ]
    update_data = {}
    for field in allowed_fields:
        if field in payload:
            value = payload.get(field)
            if isinstance(value, str):
                value = value.strip()
            if field == "email" and value:
                value = value.lower()
            update_data[field] = value

    if not update_data:
        return {"error": "No updatable fields provided"}, 400

    if "email" in update_data:
        existing = db.users.find_one({"email": update_data["email"], "_id": {"$ne": user_object_id}})
        if existing:
            return {"error": "Email already in use"}, 409

    if "role" in update_data and update_data["role"] not in ["admin", "doctor", "patient"]:
        return {"error": "Invalid role"}, 400

    update_data["updated_at"] = datetime.now(timezone.utc)
    db.users.update_one({"_id": user_object_id}, {"$set": update_data})
    updated_user = db.users.find_one({"_id": user_object_id})
    return {"message": "User updated successfully", "user": public_user_data(updated_user)}


@admin_bp.patch("/patients/<patient_id>/profile")
@token_required(roles=["admin"])
def update_patient_profile(patient_id):
    db = get_db()
    patient_object_id = parse_object_id(patient_id)
    if not patient_object_id:
        return {"error": "Invalid patient ID"}, 400

    patient = db.users.find_one({"_id": patient_object_id, "role": "patient"})
    if not patient:
        return {"error": "Patient not found"}, 404

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
        {"patient_user_id": patient_object_id},
        {"$set": update_data},
        upsert=True,
    )

    profile = db.patient_profiles.find_one({"patient_user_id": patient_object_id})
    return {
        "message": "Patient profile updated successfully",
        "profile": serialize_document(profile),
    }


@admin_bp.patch("/prescriptions/<prescription_id>")
@token_required(roles=["admin"])
def update_prescription(prescription_id):
    db = get_db()
    prescription_object_id = parse_object_id(prescription_id)
    if not prescription_object_id:
        return {"error": "Invalid prescription ID"}, 400

    prescription = db.prescriptions.find_one({"_id": prescription_object_id})
    if not prescription:
        return {"error": "Prescription not found"}, 404

    payload = request.get_json(silent=True) or {}
    allowed_fields = ["diagnosis", "medicines", "advice", "next_visit_date"]
    update_data = {k: payload[k] for k in allowed_fields if k in payload}
    if not update_data:
        return {"error": "No prescription fields provided"}, 400

    update_data["updated_at"] = datetime.now(timezone.utc)
    db.prescriptions.update_one({"_id": prescription_object_id}, {"$set": update_data})
    updated = db.prescriptions.find_one({"_id": prescription_object_id})
    return {
        "message": "Prescription updated successfully",
        "prescription": serialize_document(updated),
    }


@admin_bp.get("/patients")
@token_required(roles=["admin"])
def list_patients():
    db = get_db()
    patients = []
    for user in db.users.find({"role": "patient", "is_active": True}):
        profile = db.patient_profiles.find_one({"patient_user_id": user["_id"]}) or {}
        patient_data = public_user_data(user)
        patient_data["profile"] = serialize_document(profile)
        patients.append(patient_data)
    return {"count": len(patients), "patients": patients}


@admin_bp.patch("/patients/<patient_id>/assign-doctor")
@token_required(roles=["admin"])
def assign_doctor(patient_id):
    db = get_db()
    patient_object_id = parse_object_id(patient_id)
    patient = db.users.find_one({"_id": patient_object_id, "role": "patient", "is_active": True})
    if not patient:
        return {"error": "Patient not found"}, 404

    payload = request.get_json(silent=True) or {}
    doctor_user_id = _resolve_doctor_user_id(db, payload.get("doctor_id", ""))
    if not doctor_user_id:
        return {"error": "Doctor not found"}, 404

    db.patient_profiles.update_one(
        {"patient_user_id": patient["_id"]},
        {
            "$set": {
                "assigned_doctor_id": doctor_user_id,
                "updated_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )

    return {"message": "Doctor assigned successfully"}


@admin_bp.post("/patients/<patient_id>/reports")
@token_required(roles=["admin"])
def create_admin_patient_report(patient_id):
    db = get_db()
    patient_object_id = parse_object_id(patient_id)
    if not patient_object_id:
        return {"error": "Invalid patient ID"}, 400

    patient = db.users.find_one({"_id": patient_object_id, "role": "patient", "is_active": True})
    if not patient:
        return {"error": "Patient not found"}, 404

    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title", "")).strip()
    details = str(payload.get("details", "")).strip()
    if not title and not details:
        return {"error": "Either title or details is required"}, 400

    profile = db.patient_profiles.find_one({"patient_user_id": patient_object_id}) or {}
    assigned_doctor_id = profile.get("assigned_doctor_id")

    now = datetime.now(timezone.utc)
    report = {
        "patient_user_id": patient_object_id,
        "doctor_user_id": assigned_doctor_id,
        "created_by": g.current_user["_id"],
        "created_by_role": "admin",
        "title": title,
        "details": details,
        "report_type": str(payload.get("report_type", "admin_note")).strip(),
        "vitals": payload.get("vitals", {}),
        "created_at": now,
        "updated_at": now,
    }
    result = db.patient_reports.insert_one(report)
    report["_id"] = result.inserted_id
    return {"message": "Patient report created by admin", "report": serialize_document(report)}, 201


@admin_bp.get("/patients/<patient_id>/reports")
@token_required(roles=["admin"])
def list_admin_patient_reports(patient_id):
    db = get_db()
    patient_object_id = parse_object_id(patient_id)
    if not patient_object_id:
        return {"error": "Invalid patient ID"}, 400

    patient = db.users.find_one({"_id": patient_object_id, "role": "patient", "is_active": True})
    if not patient:
        return {"error": "Patient not found"}, 404

    reports = [
        serialize_document(r)
        for r in db.patient_reports.find({"patient_user_id": patient_object_id}).sort("created_at", -1)
    ]
    return {"count": len(reports), "reports": reports}


@admin_bp.post("/patients/<patient_id>/health")
@token_required(roles=["admin"])
def create_admin_patient_health(patient_id):
    db = get_db()
    patient_object_id = parse_object_id(patient_id)
    if not patient_object_id:
        return {"error": "Invalid patient ID"}, 400

    patient = db.users.find_one({"_id": patient_object_id, "role": "patient", "is_active": True})
    if not patient:
        return {"error": "Patient not found"}, 404

    payload = request.get_json(silent=True) or {}
    vitals = payload.get("vitals", {})
    if not isinstance(vitals, dict) or not vitals:
        return {"error": "vitals must be a non-empty object"}, 400

    now = datetime.now(timezone.utc)
    health = {
        "patient_user_id": patient_object_id,
        "entered_by": g.current_user["_id"],
        "entered_by_role": "admin",
        "vitals": vitals,
        "notes": str(payload.get("notes", "")).strip(),
        "created_at": now,
        "updated_at": now,
    }
    result = db.patient_health.insert_one(health)
    health["_id"] = result.inserted_id
    return {"message": "Patient health data stored", "health": serialize_document(health)}, 201
