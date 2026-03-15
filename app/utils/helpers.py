from datetime import date, datetime

from bson import ObjectId


def parse_object_id(value):
    try:
        return ObjectId(value)
    except Exception:
        return None


def serialize_document(document):
    if not document:
        return None

    serialized = {}
    for key, value in document.items():
        if isinstance(value, ObjectId):
            serialized[key] = str(value)
        elif isinstance(value, datetime):
            serialized[key] = value.isoformat()
        elif isinstance(value, date):
            serialized[key] = value.isoformat()
        elif isinstance(value, list):
            serialized[key] = [serialize_document(item) if isinstance(item, dict) else item for item in value]
        elif isinstance(value, dict):
            serialized[key] = serialize_document(value)
        else:
            serialized[key] = value
    return serialized


def public_user_data(user):
    user_data = serialize_document(user)
    user_data.pop("password_hash", None)
    return user_data
