import os
from datetime import timedelta
from urllib.parse import quote_plus
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_PATH = BASE_DIR / 'instance'
INSTANCE_PATH.mkdir(exist_ok=True, parents=True)

# Force PostgreSQL database URL
POSTGRESQL_URL = "postgresql://codecraftco_db_user:84u1KfAY4jHElF1ISEVw4YNbtZM51691@dpg-d1lknv6r433s73drf130-a.oregon-postgres.render.com/codecraftco_db"

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'super-secret-key'
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
    
    #  FORCE PostgreSQL for development too
    SQLALCHEMY_DATABASE_URI = POSTGRESQL_URL
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    }
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    
    DATABASE_URL = os.environ.get('DATABASE_URL') or POSTGRESQL_URL
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
