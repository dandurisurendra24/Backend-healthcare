from pymongo import MongoClient


mongo_client = None
db = None


def init_db(app):
    global mongo_client, db

    mongodb_uri = app.config["MONGODB_URI"]
    try:
        mongo_client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        # Force server selection to validate connection early.
        mongo_client.server_info()
    except Exception as exc:
        raise RuntimeError(
            "Unable to connect to MongoDB.\n"
            f"Configured URI: {mongodb_uri}\n"
            "Check your MONGODB_URI in .env or environment variables. "
            "For local development use: mongodb://localhost:27017\n"
            f"Original error: {exc}"
        ) from exc

    db = mongo_client[app.config["MONGODB_DB"]]
    app.extensions["mongo_db"] = db

    db.users.create_index("email", unique=True)
    db.doctors.create_index("user_id", unique=True)
    db.patients.create_index("user_id", unique=True)
    db.prescriptions.create_index("patient_user_id")
    db.prescriptions.create_index("doctor_user_id")
    db.patient_profiles.create_index("patient_user_id", unique=True)
    db.patient_reports.create_index("patient_user_id")
    db.patient_reports.create_index("doctor_user_id")
    db.patient_reports.create_index("created_by")
    db.patient_health.create_index("patient_user_id")


def get_db():
    return db
