from datetime import datetime, timezone

from app.extensions import get_db
from app.utils.security import hash_password


def ensure_default_admin(app):
    db = get_db()
    if db is None:
        return

    email = app.config["ADMIN_EMAIL"].lower().strip()
    password = app.config["ADMIN_PASSWORD"]

    existing_admin = db.users.find_one({"email": email})
    if existing_admin:
        return

    db.users.insert_one(
        {
            "full_name": "System Admin",
            "email": email,
            "password_hash": hash_password(password),
            "role": "admin",
            "phone": "",
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )
