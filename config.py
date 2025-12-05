import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_PATH = BASE_DIR / "instance"
INSTANCE_PATH.mkdir(exist_ok=True, parents=True)

POSTGRESQL_URL = (
    os.environ.get("DATABASE_URL")
    or "postgresql://codecraftco_db_user:84u1KfAY4jHElF1ISEVw4YNbtZM51691@"
       "dpg-d1lknv6r433s73drf130-a.oregon-postgres.render.com:5432/"
       "codecraftco_db"
)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "super-secret-key")

    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
    GOOGLE_DISCOVERY_URL = (
        "https://accounts.google.com/.well-known/openid-configuration"
    )

    APPLICATION_EMAIL = os.environ.get("APPLICATION_EMAIL")
    APPLICATION_EMAIL_PASSWORD = os.environ.get("APPLICATION_EMAIL_PASSWORD")

    SQLALCHEMY_DATABASE_URI = POSTGRESQL_URL
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 5,
        "pool_recycle": 3600,
        "pool_pre_ping": True,
    }


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{INSTANCE_PATH / 'dev.db'}"


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 10,
        "pool_recycle": 3600,
        "pool_pre_ping": True,
        "connect_args": {
            "sslmode": "require",
            "connect_timeout": 10,
        },
    }