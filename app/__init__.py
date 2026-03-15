from flask import Flask
from flask_cors import CORS

from app.config import Config
from app.extensions import init_db
from app.routes.admin import admin_bp
from app.routes.auth import auth_bp
from app.routes.common import common_bp
from app.routes.doctor import doctor_bp
from app.routes.patient import patient_bp
from app.seed import ensure_default_admin


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        supports_credentials=False,
    )

    init_db(app)
    ensure_default_admin(app)

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(doctor_bp, url_prefix="/api/doctor")
    app.register_blueprint(patient_bp, url_prefix="/api/patient")
    app.register_blueprint(common_bp, url_prefix="/api/common")

    @app.get("/")
    def index():
        return {
            "message": "Health Monitoring Backend is running",
            "version": "1.0.0",
        }

    return app
