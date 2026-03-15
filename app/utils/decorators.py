from functools import wraps

from flask import g, request

from app.extensions import get_db
from app.utils.helpers import parse_object_id, public_user_data
from app.utils.security import decode_access_token


def token_required(roles=None):
    roles = roles or []

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            db = get_db()
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return {"error": "Authorization token is missing"}, 401

            token = auth_header.split(" ", 1)[1].strip()
            try:
                payload = decode_access_token(token)
            except Exception:
                return {"error": "Invalid or expired token"}, 401

            user_id = parse_object_id(payload.get("sub"))
            if not user_id:
                return {"error": "Invalid token subject"}, 401

            user = db.users.find_one({"_id": user_id, "is_active": True})
            if not user:
                return {"error": "User not found or inactive"}, 401

            if roles and user["role"] not in roles:
                return {"error": "Access denied"}, 403

            g.current_user = user
            g.current_user_public = public_user_data(user)
            return func(*args, **kwargs)

        return wrapper

    return decorator
