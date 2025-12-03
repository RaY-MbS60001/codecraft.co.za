import os
from datetime import timedelta
from urllib.parse import quote_plus
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_PATH = BASE_DIR / 'instance'
INSTANCE_PATH.mkdir(exist_ok=True, parents=True)

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'super-secret-key'

    # Session config
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # Google OAuth
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

    # Application email
    APPLICATION_EMAIL = os.environ.get('APPLICATION_EMAIL', 'your-email@gmail.com')
    APPLICATION_EMAIL_PASSWORD = os.environ.get('APPLICATION_EMAIL_PASSWORD', 'your-app-password')

class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{INSTANCE_PATH / 'codecraft.db'}"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    DB_PASSWORD = os.environ.get('DB_PASSWORD') or 'your_working_password_here'
    DATABASE_URL = os.environ.get('DATABASE_URL') or \
        f"postgresql://postgres:{quote_plus(DB_PASSWORD)}@aws-0-eu-central-1.pooler.supabase.com:6543/postgres"
    
    # Engine options only for PostgreSQL
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'connect_args': {
            'sslmode': 'require',
            'connect_timeout': 10,
        }
    }
