import os
from datetime import timedelta
from urllib.parse import quote_plus

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'b7dcbf6e58e18e48a0d62c3d7890ab1322f73513e479dd8a7a4f0e3c3d90f947'
    
    # Use the SAME password that worked in test_new_password.py
    DB_PASSWORD = 'your_working_password_here'  # Replace with the password from test_new_password.py
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'postgresql://postgres.inkuwivfhqyplcuwjduu:{quote_plus(DB_PASSWORD)}@aws-0-eu-central-1.pooler.supabase.com:6543/postgres'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # Google OAuth Config
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
    
    # Application email settings
    APPLICATION_EMAIL = os.environ.get('APPLICATION_EMAIL', 'your-email@gmail.com')
    APPLICATION_EMAIL_PASSWORD = os.environ.get('APPLICATION_EMAIL_PASSWORD', 'your-app-password')
    
    # Development only
    if os.environ.get('FLASK_ENV') == 'development':
        OAUTHLIB_INSECURE_TRANSPORT = '1'