from flask import Blueprint

from app.utils.decorators import token_required


common_bp = Blueprint("common", __name__)


@common_bp.get("/health")
def health():
    return {"status": "ok"}


@common_bp.get("/dashboard")
@token_required()
def dashboard():
    return {"message": "Authenticated route working"}
