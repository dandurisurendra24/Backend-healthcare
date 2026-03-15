import os

from dotenv import load_dotenv


load_dotenv()


class Config:
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-secret")
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB = os.getenv("MONGODB_DB", "health_monitoring")
    ACCESS_TOKEN_EXPIRES_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRES_MINUTES", "1440"))
    CORS_ORIGINS = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@health.local")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin@123")
    REPORT_UPLOAD_DIR = os.getenv(
        "REPORT_UPLOAD_DIR",
        os.path.join(BASE_DIR, "uploads", "reports"),
    )
