from datetime import datetime, timezone

from flask import Blueprint, g, request

from app.extensions import get_db
from app.utils.decorators import token_required
from app.utils.helpers import public_user_data
from app.utils.security import create_access_token, verify_password


auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/login")
def login():
    db = get_db()
    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", "")).strip()

    if not email or not password:
        return {"error": "Email and password are required"}, 400

    user = db.users.find_one({"email": email, "is_active": True})
    if not user or not verify_password(password, user["password_hash"]):
        return {"error": "Invalid credentials"}, 401

    token = create_access_token(user)
    return {
        "message": "Login successful",
        "token": token,
        "user": public_user_data(user),
    }


@auth_bp.get("/me")
@token_required()
def me():
    return {"user": g.current_user_public}


@auth_bp.get("/logout")
@token_required()
def logout():
    # This API is stateless JWT; logout is implemented client-side by discarding the token.
    return {"message": "Logout successful"}


@auth_bp.post("/change-password")
@token_required()
def change_password():
    from app.utils.security import hash_password

    db = get_db()
    payload = request.get_json(silent=True) or {}
    current_password = str(payload.get("current_password", "")).strip()
    new_password = str(payload.get("new_password", "")).strip()

    if not current_password or not new_password:
        return {"error": "Current password and new password are required"}, 400

    if not verify_password(current_password, g.current_user["password_hash"]):
        return {"error": "Current password is incorrect"}, 400

    db.users.update_one(
        {"_id": g.current_user["_id"]},
        {
            "$set": {
                "password_hash": hash_password(new_password),
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    return {"message": "Password updated successfully"}
