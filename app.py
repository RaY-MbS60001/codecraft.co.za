"""
Flask Application for Learnership Management System
A comprehensive platform for managing learnership applications with OAuth authentication,
document management, and bulk email functionality.
"""

# =============================================================================
# IMPORTS
# =============================================================================

# Standard library imports
import os
import json
import time
import logging
import socket
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import quote_plus

# Flask imports
from flask import (
    Flask, render_template, redirect, url_for, flash, request,
    jsonify, session, send_file, g, jsonify
)
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from gmail_status_checker import GmailStatusChecker
from flask_wtf import FlaskForm
from werkzeug.utils import secure_filename
from wtforms import TextAreaField, SubmitField, SelectMultipleField, widgets
from wtforms.validators import Optional


# ADD THESE IMPORTS at the top of app.py:
from decorators import corporate_required, verified_corporate_required, admin_or_corporate_required
import uuid

# Third-party imports
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv

# Add these imports at the top of your app.py file (around line 10-20)
from decorators import admin_required, premium_required, check_application_limit, track_application_usage

# Load .env
load_dotenv('.env.production')

# Debug DB URL print
DATABASE_URL = os.getenv('DATABASE_URL')
print(f"DEBUG: DATABASE_URL is '{DATABASE_URL}'")

# Local imports
from models import (
    db, User, Application, Document,
    GoogleToken,LearnershipEmail,
    CalendarEvent, ApplicationMessage,
    Conversation, ConversationMessage,PremiumTransaction
)
from forms import (
    AdminLoginForm, EditProfileForm, ChangePasswordForm,
    ApplicationForm, DocumentUploadForm, LearnershipSearchForm
)
from decorators import admin_required
from tasks import launch_bulk_send
from security_middleware import add_security_headers

# =============================================================================
# FLASK APP INITIALIZATION
# =============================================================================

app = Flask(__name__)

# Base directory
BASE_DIR = Path(__file__).resolve().parent
instance_path = BASE_DIR / 'instance'
instance_path.mkdir(exist_ok=True, parents=True)

# Upload configuration
UPLOAD_FOLDER = BASE_DIR / 'uploads'
UPLOAD_FOLDER.mkdir(exist_ok=True)
(UPLOAD_FOLDER / 'documents').mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'}

app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

# =============================================================================
# CONFIGURATION CLASSES
# =============================================================================

from config import Config

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False

class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False


# =============================================================================
# DATABASE SELECTION (SQLite for dev, PostgreSQL for prod)
# =============================================================================
def get_database_url_and_options():
    env = os.environ.get("FLASK_ENV", "development")
    instance_path = Path(__file__).parent / "instance"
    instance_path.mkdir(exist_ok=True)

    if env == "development":
        sqlite_path = instance_path / "codecraft.db"
        print("✓ Development mode: Using SQLite DB:", sqlite_path)
        return f"sqlite:///{sqlite_path}", {}

    # Production → PostgreSQL
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL must be set in production")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    engine_options = {
        "pool_size": 10,
        "pool_recycle": 3600,
        "pool_pre_ping": True,
        "connect_args": {
            "sslmode": "require",
            "connect_timeout": 10
        }
    }
    return database_url, engine_options

# =============================================================================
# APPLY CONFIGURATION
# =============================================================================

if os.environ.get("FLASK_ENV") == "production":
    app.config.from_object(ProductionConfig)
else:
    app.config.from_object(DevelopmentConfig)

db_url, engine_options = get_database_url_and_options()
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_options


# =============================================================================
# INITIALIZE EXTENSIONS
# =============================================================================

add_security_headers(app)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "info"

oauth = OAuth(app)
google = None


# =============================================================================
# DATABASE INIT (RUN ONCE)
# =============================================================================

with app.app_context():
    try:
        db.create_all()
        db.session.commit()
        print("✓ Database initialized successfully")
    except Exception as e:
        print("✗ Database initialization error:", e)
        raise SystemExit(e)
    
# =============================================================================
# CUSTOM FORM FIELDS
# =============================================================================

class MultiCheckBoxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


# =============================================================================
# OAUTH SETUP
# =============================================================================

def setup_oauth():
    global google

    try:
        cid = app.config.get("GOOGLE_CLIENT_ID")
        secret = app.config.get("GOOGLE_CLIENT_SECRET")

        if cid and secret:
            # Get scopes from config, with fallback to basic scopes
            oauth_scopes = app.config.get('GOOGLE_OAUTH_SCOPES', [
                'openid',
                'email', 
                'profile',
                'https://www.googleapis.com/auth/gmail.send',
                'https://www.googleapis.com/auth/gmail.readonly',
                'https://www.googleapis.com/auth/gmail.modify'
            ])
            
            google = oauth.register(
                name="google",
                client_id=cid,
                client_secret=secret,
                server_metadata_url=app.config["GOOGLE_DISCOVERY_URL"],
                client_kwargs={
                    "scope": " ".join(oauth_scopes),  # 🔥 USE CONFIG SCOPES
                    "access_type": "offline",
                    "prompt": "consent"
                }
            )
            print("✓ Google OAuth configured")
            print(f"📊 OAuth scopes: {oauth_scopes}")  # 🔥 DEBUG INFO
        else:
            print("⚠️ Google OAuth credentials missing")

    except Exception as e:
        print(f"OAuth setup error: {e}")

setup_oauth()


# =============================================================================
# LOGIN MANAGER LOADER
# =============================================================================

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# =============================================================================
# SESSION VALIDATION (Before Request)
# =============================================================================

@app.before_request
def validate_session():
    """Validate user session on each request."""

    # ✅ FIXED: Use correct function names that match your routes
    excluded = {
        "static", 
        "index", 
        "feed", 
        "home", 
        "login",
        "register", 
        "forgot_password", 
        "reset_password",
        "google_login", 
        "google_callback",
        "privacy_policy",      # ✅ Changed from "privacy"
        "terms_of_service",    # ✅ Changed from "terms"
        "help_center",         # ✅ Added
        "contact_us",          # ✅ Changed from "contact"
        "submit_contact",      # ✅ Added for form submission
        "admin_login"
    }

    # Skip static & public routes
    if request.endpoint in excluded:
        return

    # Skip if no endpoint (shouldn't happen, but safety check)
    if request.endpoint is None:
        return

    # Skip AJAX/JSON
    if request.is_json:
        return

    # ✅ FIXED: Only validate session if user IS authenticated
    if current_user.is_authenticated:
        client_ip = request.environ.get("HTTP_X_REAL_IP", request.remote_addr)
        session_token = session.get("session_token")
        session_uid = session.get("user_id")

        # Missing or mismatched session
        if not session_token or not session_uid or session_uid != current_user.id:
            session.clear()
            logout_user()
            flash("Session expired. Please log in again.", "warning")
            return redirect(url_for("login"))

        # DB-side validation
        if not current_user.is_session_valid(session_token, client_ip):
            session.clear()
            logout_user()
            flash("Session expired. Please log in again.", "warning")
            return redirect(url_for("login"))

        # User inactive
        if not current_user.is_active:
            session.clear()
            logout_user()
            flash("Your account has been deactivated.", "error")
            return redirect(url_for("login"))

        # Extend session (auto-refresh)
        if current_user.session_expires:
            remaining = current_user.session_expires - datetime.utcnow()
            if remaining.total_seconds() < 1800:  # 30 min
                current_user.extend_session()

        g.current_user = current_user

    else:
        # ✅ FIXED: Only redirect for protected routes, not public ones
        # The excluded check above should handle this, but this is a fallback
        # for routes that require authentication (like dashboard, profile, etc.)
        
        # List of route prefixes that REQUIRE authentication
        protected_prefixes = [
            '/dashboard',
            '/profile',
            '/admin',
            '/apply',
            '/applications',
            '/my-applications',
            '/document',
            '/edit',
            '/add',
            '/delete',
            '/user',
        ]
        
        # Check if current path requires authentication
        requires_auth = any(request.path.startswith(prefix) for prefix in protected_prefixes)
        
        if requires_auth:
            flash("Please log in to access this page.", "info")
            return redirect(url_for("login", next=request.url))

# =============================================================================
# BASIC ROUTES
# =============================================================================

@app.route("/")
def index():
    return render_template("home.html", current_year=datetime.now().year)


@app.route("/feed")
@login_required
def feed():
    return render_template("feed.html")


# =============================================================================
# LOGIN ROUTE (USER)
# =============================================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        if not email or not password:
            flash("Please enter both email and password.", "error")
            return render_template("login.html")

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):

            if not user.is_active:
                flash("Your account has been deactivated.", "error")
                return render_template("login.html")

            client_ip = request.environ.get("HTTP_X_REAL_IP", request.remote_addr)
            user_agent = request.headers.get("User-Agent", "")

            user.clear_session()
            session.clear()

            session_token = user.generate_session_token(client_ip, user_agent)
            login_user(user, remember=False)

            session["user_id"] = user.id
            session["user_email"] = user.email
            session["user_role"] = user.role
            session["session_token"] = session_token
            session.permanent = True

            user.last_login = datetime.utcnow()
            db.session.commit()

            flash(f"Welcome back, {user.full_name or user.email}!", "success")

            if user.role == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("feed"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


# =============================================================================
# LOGIN ROUTE (ADMIN)
# =============================================================================
@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if current_user.is_authenticated:
        # Redirect based on current user role
        if current_user.role == "admin":
            return redirect(url_for("admin_dashboard"))
        elif current_user.role == "corporate":
            return redirect(url_for("corporate_dashboard"))
        else:
            return redirect(url_for("index"))

    form = AdminLoginForm()

    if form.validate_on_submit():
        # Check for both admin and corporate users
        user = User.query.filter_by(username=form.username.data).filter(
            User.role.in_(["admin", "corporate"])
        ).first()

        if user and user.check_password(form.password.data):
            
            # Check if corporate user is verified
            if user.role == "corporate" and not user.is_verified:
                flash("Your corporate account is pending admin verification. Please wait for approval.", "warning")
                return render_template("admin_login.html", form=form)

            client_ip = request.environ.get("HTTP_X_REAL_IP", request.remote_addr)
            user_agent = request.headers.get("User-Agent", "")

            user.clear_session()
            session.clear()

            session_token = user.generate_session_token(client_ip, user_agent)
            login_user(user, remember=False)

            session["user_id"] = user.id
            session["user_email"] = user.email
            session["user_role"] = user.role
            session["session_token"] = session_token
            session.permanent = True

            # Set role-specific session data
            if user.role == "corporate":
                session['company_name'] = user.company_name or user.full_name
                session['is_verified'] = user.is_verified
                session['is_premium'] = user.is_premium_active()

            user.last_login = datetime.utcnow()
            db.session.commit()

            # Role-based welcome message and redirect
            if user.role == "admin":
                flash("Welcome back, Admin!", "success")
                return redirect(url_for("admin_dashboard"))
            elif user.role == "corporate":
                flash(f"Welcome back, {user.company_name or user.full_name}!", "success")
                return redirect(url_for("corporate_dashboard"))

        # Generic error message for security
        flash("Invalid username or password", "error")

    return render_template("admin_login.html", form=form)


# =============================================================================
# DOMAIN CHECKER SERVICE INSTANCE
# =============================================================================
import os
import smtplib
import socket
import time
from datetime import datetime, timedelta
import threading
import json

# Add this after your existing imports
try:
    import dns.resolver
except ImportError:
    print("⚠️  dnspython not installed. Install with: pip install dnspython")
    dns = None

# Email checking functions
def check_email_reachability(email_address):
    """Check if an email address is reachable via SMTP"""
    if not dns:
        return False, None
        
    try:
        start_time = time.time()
        
        # Extract domain
        if '@' not in email_address:
            return False, None
            
        domain = email_address.split('@')[1].lower()
        
        # Check MX records
        try:
            mx_records = dns.resolver.resolve(domain, 'MX')
            if not mx_records:
                return False, None
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, Exception):
            return False, None
        
        # Get the first MX record
        mx_record = str(mx_records[0].exchange).rstrip('.')
        
        # Try SMTP connection
        try:
            # Connect to mail server
            server = smtplib.SMTP(timeout=15)
            server.connect(mx_record, 25)
            server.helo('codecraft.co.za')
            
            # Test the email
            server.mail('noreply@codecraft.co.za')
            code, message = server.rcpt(email_address)
            server.quit()
            
            response_time = time.time() - start_time
            
            # Check if email is accepted (codes 250, 251, 252 are usually OK)
            is_valid = code in [250, 251, 252]
            
            return is_valid, response_time
            
        except (smtplib.SMTPException, socket.error, ConnectionRefusedError):
            return False, None
            
    except Exception as e:
        print(f"Error checking {email_address}: {e}")
        return False, None

def check_email_batch(limit=50):
    """Check a batch of emails for reachability"""
    with app.app_context():
        try:
            # Get unchecked emails or emails that haven't been checked in 24 hours
            emails_to_check = LearnershipEmail.query.filter(
                db.or_(
                    LearnershipEmail.is_reachable.is_(None),
                    db.and_(
                        LearnershipEmail.last_checked.isnot(None),
                        LearnershipEmail.last_checked < datetime.utcnow() - timedelta(hours=24)
                    )
                )
            ).limit(limit).all()
            
            print(f"Checking {len(emails_to_check)} emails...")
            
            for i, email in enumerate(emails_to_check):
                try:
                    print(f"Checking {i+1}/{len(emails_to_check)}: {email.email_address}")
                    
                    is_reachable, response_time = check_email_reachability(email.email_address)
                    
                    # Update email record
                    email.is_reachable = is_reachable
                    email.response_time = response_time
                    email.last_checked = datetime.utcnow()
                    email.check_count = (email.check_count or 0) + 1
                    
                    # Commit each update
                    db.session.commit()
                    
                    result = "✓" if is_reachable else "✗"
                    time_str = f" ({response_time:.2f}s)" if response_time else ""
                    print(f"  Result: {result}{time_str}")
                    
                    # Small delay to avoid being blocked
                    time.sleep(2)
                    
                except Exception as e:
                    print(f"Error checking {email.email_address}: {e}")
                    db.session.rollback()
                    continue
            
            print("Email check batch completed!")
            
        except Exception as e:
            print(f"Error in check_email_batch: {e}")

# API Routes
@app.route('/api/email-status')
@login_required
def get_email_status():
    """API endpoint to get email reachability status"""
    try:
        # Get all emails from database
        emails = LearnershipEmail.query.all()
        
        # If no emails have been checked yet, start a background check
        unchecked_count = LearnershipEmail.query.filter_by(is_reachable=None).count()
        
        if unchecked_count > 0:
            # Start background check for unchecked emails (limit to first 50)
            threading.Thread(target=check_email_batch, args=(50,), daemon=True).start()
        
        # Get reachable emails
        reachable_emails = LearnershipEmail.query.filter_by(is_reachable=True).all()
        
        # Format email data
        email_list = []
        for email in reachable_emails:
            email_list.append({
                'id': email.id,
                'company_name': email.company_name,
                'email_address': email.email_address,
                'status': 'reachable',
                'response_time': email.response_time
            })
        
        # Calculate stats
        total_count = len(emails)
        reachable_count = len(reachable_emails)
        checked_count = LearnershipEmail.query.filter(LearnershipEmail.is_reachable.isnot(None)).count()
        
        stats = {
            'total': total_count,
            'reachable': reachable_count,
            'unreachable': checked_count - reachable_count,
            'unchecked': total_count - checked_count
        }
        
        # Get last update time
        last_checked_email = LearnershipEmail.query.filter(
            LearnershipEmail.last_checked.isnot(None)
        ).order_by(LearnershipEmail.last_checked.desc()).first()
        
        last_updated = last_checked_email.last_checked.isoformat() if last_checked_email and last_checked_email.last_checked else None
        
        return jsonify({
            'emails': email_list,
            'stats': stats,
            'last_updated': last_updated,
            'status': 'success'
        })
        
    except Exception as e:
        print(f"Error in get_email_status: {e}")
        return jsonify({
            'emails': [],
            'stats': {'total': 0, 'reachable': 0, 'unreachable': 0},
            'error': str(e)
        }), 500


# Manual email check route (for testing)
@app.route('/admin/check-emails')
@login_required
def admin_check_emails():
    """Manual trigger for email checking"""
    if not current_user.is_admin:
        flash('Access denied.', 'error')
        return redirect(url_for('feed'))
    
    # Start background email check
    threading.Thread(target=check_email_batch, args=(100,), daemon=True).start()
    
    flash('Email checking started in background. Check back in a few minutes.', 'info')
    return redirect(url_for('admin_dashboard'))


# Add these imports at the top if not already present
import threading
try:
    import dns.resolver
except ImportError:
    print("⚠️  dnspython not installed. Install with: pip install dnspython")
    dns = None

# Add these functions (only if they don't exist already)
def check_email_reachability(email_address):
    """Check if an email address is reachable via SMTP"""
    if not dns:
        return True, None  # Default to True if DNS checking is unavailable
        
    try:
        start_time = time.time()
        
        if '@' not in email_address:
            return False, None
            
        domain = email_address.split('@')[1].lower()
        
        # Check MX records
        try:
            mx_records = dns.resolver.resolve(domain, 'MX')
            if not mx_records:
                return False, None
        except:
            return False, None
        
        response_time = time.time() - start_time
        return True, response_time  # Simplified - assume reachable if MX exists
            
    except Exception as e:
        print(f"Error checking {email_address}: {e}")
        return False, None

def check_email_batch_background(limit=20):
    """Check a batch of emails for reachability in background"""
    with app.app_context():
        try:
            # Get unchecked emails
            emails_to_check = LearnershipEmail.query.filter_by(is_reachable=None).limit(limit).all()
            
            print(f"Background checking {len(emails_to_check)} emails...")
            
            for email in emails_to_check:
                try:
                    is_reachable, response_time = check_email_reachability(email.email_address)
                    
                    email.is_reachable = is_reachable
                    email.response_time = response_time
                    email.last_checked = datetime.utcnow()
                    email.check_count = (email.check_count or 0) + 1
                    
                    db.session.commit()
                    
                    time.sleep(1)  # Small delay
                    
                except Exception as e:
                    print(f"Error checking {email.email_address}: {e}")
                    db.session.rollback()
                    continue
            
            print(f"Completed background email check")
            
        except Exception as e:
            print(f"Error in background email check: {e}")

# Add ONLY this new route (with unique name)
@app.route('/api/email-status')
@login_required
def api_email_status():
    """API endpoint to get email reachability status"""
    try:
        # Get all emails
        emails = LearnershipEmail.query.all()
        
        # Start background check if needed
        unchecked_count = LearnershipEmail.query.filter_by(is_reachable=None).count()
        if unchecked_count > 0:
            threading.Thread(target=check_email_batch_background, args=(50,), daemon=True).start()
        
        # Get reachable emails
        reachable_emails = LearnershipEmail.query.filter_by(is_reachable=True).all()
        
        # Format email data
        email_list = []
        for email in reachable_emails:
            email_list.append({
                'id': email.id,
                'company_name': email.company_name,
                'email_address': email.email_address,
                'status': 'reachable',
                'response_time': email.response_time
            })
        
        # Calculate stats
        total_count = len(emails)
        reachable_count = len(reachable_emails)
        checked_count = LearnershipEmail.query.filter(LearnershipEmail.is_reachable.isnot(None)).count()
        
        stats = {
            'total': total_count,
            'reachable': reachable_count,
            'unreachable': checked_count - reachable_count,
            'unchecked': total_count - checked_count
        }
        
        # Get last update time
        last_checked_email = LearnershipEmail.query.filter(
            LearnershipEmail.last_checked.isnot(None)
        ).order_by(LearnershipEmail.last_checked.desc()).first()
        
        last_updated = last_checked_email.last_checked.isoformat() if last_checked_email and last_checked_email.last_checked else None
        
        return jsonify({
            'emails': email_list,
            'stats': stats,
            'last_updated': last_updated,
            'status': 'success'
        })
        
    except Exception as e:
        print(f"Error in api_email_status: {e}")
        return jsonify({
            'emails': [],
            'stats': {'total': 0, 'reachable': 0, 'unreachable': 0},
            'error': str(e)
        }), 500
# =============================================================================
# GOOGLE LOGIN
# =============================================================================

@app.route("/login/google")
def google_login():
    """Initiate Google OAuth login."""
    if not google:
        # Dev fallback
        demo_user = User.query.filter_by(email="demo@codecraftco.com").first()

        if not demo_user:
            demo_user = User(
                email="demo@codecraftco.com",
                full_name="Demo User",
                role="user",
                auth_method="google",
                is_active=True,
            )
            db.session.add(demo_user)
            db.session.commit()

        demo_user.clear_session()
        session.clear()

        client_ip = request.environ.get("HTTP_X_REAL_IP", request.remote_addr)
        user_agent = request.headers.get("User-Agent", "")
        session_token = demo_user.generate_session_token(client_ip, user_agent)

        login_user(demo_user, remember=False)

        session["user_id"] = demo_user.id
        session["user_email"] = demo_user.email
        session["user_role"] = demo_user.role
        session["session_token"] = session_token
        session.permanent = True

        demo_user.last_login = datetime.utcnow()
        db.session.commit()

        flash("Logged in as Demo User (Google OAuth not configured)", "warning")
        return redirect(url_for("user_dashboard"))

    return google.authorize_redirect(
        url_for("google_callback", _external=True),
        prompt="consent",
        access_type="offline"
    )



# =============================================================================
# LOGOUT
# =============================================================================

@app.route("/logout")
def logout():
    if current_user.is_authenticated:
        current_user.clear_session()
        session.clear()
        logout_user()
        flash("You have been logged out successfully.", "success")

    return redirect(url_for("index"))

# =============================================================================
# GOOGLE OAUTH CALLBACK
# =============================================================================

@app.route("/google/callback")
def google_callback():
    try:
        token = google.authorize_access_token()

        # Extract user info
        userinfo = token.get("userinfo")
        if not userinfo:
            resp = google.get(
                "https://www.googleapis.com/oauth2/v1/userinfo", token=token
            )
            userinfo = resp.json()

        email = userinfo.get("email")
        full_name = userinfo.get("name")
        picture_url = userinfo.get("picture")

        # Validate picture URL
        if picture_url and not picture_url.startswith(("http://", "https://")):
            picture_url = None

        # Look up or create user
        user = User.query.filter_by(email=email).first()

        if not user:
            user = User(
                email=email,
                full_name=full_name,
                role="user",
                auth_method="google",
                is_active=True
            )
            db.session.add(user)
            db.session.flush()

        # Download profile picture (optional)
        if picture_url:
            saved_path = download_and_save_profile_picture(picture_url, user.id)
            if saved_path:
                user.profile_picture = saved_path

        # Store or update Google token
        token_data = {
            "access_token": token.get("access_token"),
            "refresh_token": token.get("refresh_token"),
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": app.config.get("GOOGLE_CLIENT_ID"),
            "client_secret": app.config.get("GOOGLE_CLIENT_SECRET"),
            "scopes": token.get("scope", "").split(),
            "expires_at": token.get("expires_at"),
            "token_type": token.get("token_type", "Bearer"),
            "expires_in": token.get("expires_in")
        }

        google_token = GoogleToken.query.filter_by(user_id=user.id).first()

        if google_token:
            google_token.token_json = json.dumps(token_data)
            google_token.refreshed_at = datetime.utcnow()
        else:
            google_token = GoogleToken(
                user_id=user.id,
                token_json=json.dumps(token_data),
                refreshed_at=datetime.utcnow()
            )
            db.session.add(google_token)

        # Finalize login
        user.last_login = datetime.utcnow()
        db.session.commit()

        # Replace existing session
        client_ip = request.environ.get("HTTP_X_REAL_IP", request.remote_addr)
        user_agent = request.headers.get("User-Agent", "")

        user.clear_session()
        session.clear()

        session_token = user.generate_session_token(client_ip, user_agent)

        login_user(user, remember=False)

        session["user_id"] = user.id
        session["user_email"] = user.email
        session["user_role"] = user.role
        session["session_token"] = session_token
        session["login_time"] = datetime.utcnow().isoformat()
        session.permanent = True

        db.session.commit()

        flash(f"Welcome, {user.full_name or user.email}!", "success")
        return redirect(url_for("feed", login="success"))

    except Exception as e:
        print("OAuth callback error:", e)
        flash("Authentication failed. Please try again.", "error")
        return redirect(url_for("login"))


# =============================================================================
# CONTENT SECURITY POLICY HEADERS
# =============================================================================

@app.after_request
def add_csp_headers(response):
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-src 'none'; "
    )
    return response


# =============================================================================
# USER DASHBOARD
# =============================================================================
@app.route("/user/dashboard")
@login_required
def user_dashboard():
    try:
        # Get recent applications - use submitted_at instead of created_at
        recent_apps = (
            Application.query.filter_by(user_id=current_user.id)
            .order_by(Application.submitted_at.desc())  # Fixed: use submitted_at
            .limit(5)
            .all()
        )

        # Get documents count
        doc_count = Document.query.filter_by(
            user_id=current_user.id, is_active=True
        ).count()

        # Get application statistics
        total_apps = Application.query.filter_by(user_id=current_user.id).count()
        pending_apps = Application.query.filter_by(
            user_id=current_user.id, status="pending"
        ).count()
        submitted_apps = Application.query.filter_by(
            user_id=current_user.id, status="submitted"
        ).count()
        responded = Application.query.filter_by(
            user_id=current_user.id, has_response=True  # Fixed: use has_response instead of email_status
        ).count()

        # Calculate response rate
        response_rate = round((responded / total_apps * 100) if total_apps > 0 else 0)

        stats = {
            "total": total_apps,
            "pending": pending_apps,
            "submitted": submitted_apps,  # Added submitted count
            "responses": responded,
            "response_rate": response_rate,  # Fixed: calculate actual rate
        }

        profile_completion = calculate_profile_completion(current_user)

        # Debug output
        print(f"📊 Dashboard Stats for user {current_user.id}:")
        print(f"   Total Applications: {total_apps}")
        print(f"   Pending: {pending_apps}")
        print(f"   Submitted: {submitted_apps}")
        print(f"   Responses: {responded}")
        print(f"   Documents: {doc_count}")
        print(f"   Profile Completion: {profile_completion}%")

        # Enhanced applications - Fixed to work with your Application model
        enhanced = []
        for app_item in recent_apps:
            enhanced.append({
                "id": app_item.id,
                "company_name": app_item.company_name or "Unknown Company",
                "position_title": app_item.learnership_name or "Email Application",
                "company_logo": None,  # Your model doesn't have this field
                "location": None,      # Your model doesn't have this field
                "status": app_item.status,
                "email_status": app_item.email_status,
                "created_at": app_item.submitted_at,  # Use submitted_at
                "submitted_at": app_item.submitted_at,
            })

        return render_template(
            "user_dashboard.html",  # ✅ FIXED: Use correct template name
            user=current_user,
            recent_applications=enhanced,
            application_stats=stats,
            profile_completion=profile_completion,
            documents_count=doc_count,
            current_year=datetime.now().year
        )

    except Exception as e:
        print(f"Dashboard error: {e}")
        import traceback
        traceback.print_exc()

        fallback_stats = {
            "total": 0,
            "pending": 0,
            "submitted": 0,
            "responses": 0,
            "response_rate": 0,
        }

        return render_template(
            "user_dashboard.html",  # ✅ FIXED: Use correct template name
            user=current_user,
            recent_applications=[],
            application_stats=fallback_stats,
            profile_completion=calculate_profile_completion(current_user),
            documents_count=0,
            current_year=datetime.now().year
        )


def calculate_profile_completion(user):
    """Calculate user profile completion percentage"""
    try:
        # Define the fields that make a complete profile
        profile_fields = [
            user.full_name,
            user.email,
            user.phone,
            user.address,
            user.profile_picture,
        ]
        
        # Check if user has uploaded documents
        has_documents = Document.query.filter_by(
            user_id=user.id, 
            is_active=True
        ).count() > 0
        
        # Add document check to profile completion
        profile_fields.append(has_documents)
        
        # Count completed fields
        completed_fields = sum(1 for field in profile_fields if field)
        total_fields = len(profile_fields)
        
        completion_percentage = round((completed_fields / total_fields) * 100)
        
        print(f"📋 Profile completion for {user.email}: {completed_fields}/{total_fields} = {completion_percentage}%")
        
        return completion_percentage
    
    except Exception as e:
        print(f"Profile completion calculation error: {e}")
        return 50  # Return reasonable defaultc

# =============================================================================
#filter inbox to codecraft having signature email
# =============================================================================
# When sending emails from your corporate interface, automatically add signature
def send_corporate_email_with_signature(to_email, subject, body, corporate_user):
    """Send email with CodeCraftCo signature"""
    
    signature = f"""

---
Best regards,
CodeCraftCo Team
{corporate_user.company_name}
{corporate_user.company_email}

This email was sent from CodeCraftCo - Empowering careers through technology
Visit us: https://codecraft.co.za
"""
    
    # Add signature to email body
    email_body_with_signature = body + signature
    
    # Send email with signature
    # Your existing email sending logic here
    pass


@app.route('/corporate/inbox/sync')
@corporate_required
def sync_filtered_inbox():
    """Manually sync inbox with Gmail - only CodeCraftCo signature emails"""
    try:
        # Get Gmail service - you'll need to implement this
        gmail_service = get_gmail_service_for_user(current_user)
        filtered_inbox = FilteredInboxService(gmail_service)
        
        synced_count = filtered_inbox.sync_codecraftco_conversations_only(current_user.id)
        
        flash(f'Synced {synced_count} CodeCraftCo conversations from Gmail', 'success')
        
    except Exception as e:
        print(f"Error syncing filtered inbox: {e}")
        flash('Error syncing with Gmail', 'error')
    
    return redirect(url_for('corporate_inbox'))

def has_codecraftco_signature_check(message_body):
    """Helper function to check for CodeCraftCo signature"""
    if not message_body:
        return False
    
    codecraftco_signatures = [
        'codecraftco',
        'codecraft',
        'code craft',
        'codecraft.co.za',
        '@codecraftco',
        'best regards,\ncodecraftco',
        'kind regards,\ncodecraftco',
        'sent from codecraftco',
        'codecraftco team'
    ]
    
    message_lower = message_body.lower()
    return any(signature.lower() in message_lower for signature in codecraftco_signatures)

def get_gmail_service_for_user(user):
    """Get Gmail service for specific user - implement based on your OAuth setup"""
    try:
        # This depends on how you store OAuth tokens
        # You'll need to adapt this to your OAuth implementation
        token = GoogleToken.query.filter_by(user_id=user.id).first()
        if not token:
            return None
        
        # Reconstruct credentials and return service
        # Implementation depends on your OAuth setup
        pass
    except Exception as e:
        print(f"Error getting Gmail service: {e}")
        return None
# =============================================================================
# filtering inbox to codecraft having signature email
# =============================================================================

# Add these functions to your gmail_service.py or create a new file

class FilteredInboxService:
    def __init__(self, gmail_service):
        self.service = gmail_service
        self.codecraftco_signatures = [
            'codecraftco',
            'codecraft',
            'code craft',
            'codecraft.co.za',
            '@codecraftco',
            'best regards,\ncodecraftco',
            'kind regards,\ncodecraftco'
        ]
    
    def has_codecraftco_signature(self, message_body):
        """Check if email contains CodeCraftCo signature"""
        if not message_body:
            return False
        
        message_lower = message_body.lower()
        return any(signature.lower() in message_lower for signature in self.codecraftco_signatures)
    
    def get_filtered_thread_messages(self, thread_id):
        """Get only messages with CodeCraftCo signature from a thread"""
        try:
            thread = self.service.users().threads().get(
                userId='me', 
                id=thread_id,
                format='full'
            ).execute()
            
            filtered_messages = []
            for msg in thread.get('messages', []):
                message_data = self.parse_message(msg)
                
                # Only include if has CodeCraftCo signature
                if self.has_codecraftco_signature(message_data.get('body', '')):
                    filtered_messages.append(message_data)
            
            return filtered_messages
        except Exception as e:
            print(f"Error getting filtered thread messages: {e}")
            return []
    
    def sync_codecraftco_conversations_only(self, corporate_user_id):
        """Sync only conversations that contain CodeCraftCo signature"""
        try:
            # Get applications for this corporate user
            applications = Application.query.filter_by(
                company_email=current_user.company_email
            ).filter(Application.gmail_thread_id.isnot(None)).all()
            
            synced_count = 0
            for app in applications:
                if app.gmail_thread_id:
                    # Get thread messages
                    thread_messages = self.get_filtered_thread_messages(app.gmail_thread_id)
                    
                    # Only proceed if thread has CodeCraftCo signature messages
                    if thread_messages:
                        conversation = self.create_or_update_conversation(
                            app.gmail_thread_id,
                            app.id,
                            thread_messages,
                            corporate_user_id
                        )
                        if conversation:
                            synced_count += 1
            
            return synced_count
            
        except Exception as e:
            print(f"Error syncing CodeCraftCo conversations: {e}")
            return 0
    
    def create_or_update_conversation(self, thread_id, application_id, messages, corporate_user_id):
        """Create or update conversation with filtered messages"""
        try:
            # Get or create conversation
            conversation = Conversation.query.filter_by(
                gmail_thread_id=thread_id
            ).first()
            
            if not conversation:
                application = Application.query.get(application_id)
                if not application:
                    return None
                
                conversation = Conversation(
                    application_id=application_id,
                    gmail_thread_id=thread_id,
                    subject=messages[0]['subject'] if messages else 'No Subject',
                    corporate_user_id=corporate_user_id,
                    applicant_user_id=application.user_id
                )
                db.session.add(conversation)
                db.session.flush()
            
            # Add only CodeCraftCo signature messages
            codecraftco_message_count = 0
            for msg in messages:
                existing_msg = ConversationMessage.query.filter_by(
                    gmail_message_id=msg['id']
                ).first()
                
                if not existing_msg:
                    sender_type = self.determine_sender_type(msg['from'], conversation)
                    sender_id = self.get_sender_id(msg['from'], conversation)
                    
                    conv_message = ConversationMessage(
                        conversation_id=conversation.id,
                        gmail_message_id=msg['id'],
                        sender_id=sender_id,
                        sender_type=sender_type,
                        subject=msg['subject'],
                        body=msg['body'],
                        html_body=msg['html_body'],
                        gmail_timestamp=msg['timestamp'],
                        has_attachments=msg['has_attachments']
                    )
                    
                    db.session.add(conv_message)
                    codecraftco_message_count += 1
            
            # Update conversation metadata only if we have CodeCraftCo messages
            if codecraftco_message_count > 0:
                conversation.last_message_at = max(msg['timestamp'] for msg in messages)
                conversation.updated_at = datetime.utcnow()
                db.session.commit()
                return conversation
            else:
                # If no CodeCraftCo messages, don't create/keep conversation
                if conversation.id:
                    db.session.delete(conversation)
                    db.session.commit()
                return None
                
        except Exception as e:
            db.session.rollback()
            print(f"Error creating filtered conversation: {e}")
            return None
    
    def parse_message(self, message):
        """Parse Gmail message into structured data"""
        headers = {h['name']: h['value'] for h in message['payload'].get('headers', [])}
        
        # Get message body
        body = self.extract_message_body(message['payload'])
        
        return {
            'id': message['id'],
            'thread_id': message['threadId'],
            'subject': headers.get('Subject', ''),
            'from': headers.get('From', ''),
            'to': headers.get('To', ''),
            'date': headers.get('Date', ''),
            'timestamp': self.parse_gmail_date(headers.get('Date', '')),
            'body': body.get('text', ''),
            'html_body': body.get('html', ''),
            'snippet': message.get('snippet', ''),
            'has_attachments': self.has_attachments(message['payload'])
        }
    
    def extract_message_body(self, payload):
        """Extract text and HTML body from message payload"""
        body = {'text': '', 'html': ''}
        
        if payload.get('body', {}).get('data'):
            # Simple message
            data = payload['body']['data']
            text = base64.urlsafe_b64decode(data).decode('utf-8')
            body['text'] = text
        elif payload.get('parts'):
            # Multipart message
            for part in payload['parts']:
                mime_type = part.get('mimeType', '')
                if mime_type == 'text/plain' and part.get('body', {}).get('data'):
                    data = part['body']['data']
                    body['text'] = base64.urlsafe_b64decode(data).decode('utf-8')
                elif mime_type == 'text/html' and part.get('body', {}).get('data'):
                    data = part['body']['data']
                    body['html'] = base64.urlsafe_b64decode(data).decode('utf-8')
        
        return body
    
    def has_attachments(self, payload):
        """Check if message has attachments"""
        if payload.get('parts'):
            for part in payload['parts']:
                if part.get('filename') and part['filename'] != '':
                    return True
        return False
    
    def parse_gmail_date(self, date_str):
        """Parse Gmail date string to datetime"""
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except:
            return datetime.utcnow()
    
    def determine_sender_type(self, from_email, conversation):
        """Determine if sender is corporate or applicant"""
        corporate_user = User.query.get(conversation.corporate_user_id)
        if corporate_user and corporate_user.company_email in from_email:
            return 'corporate'
        return 'applicant'
    
    def get_sender_id(self, from_email, conversation):
        """Get sender user ID"""
        corporate_user = User.query.get(conversation.corporate_user_id)
        if corporate_user and corporate_user.company_email in from_email:
            return conversation.corporate_user_id
        return conversation.applicant_user_id
# =============================================================================
# CORPORATE CALENDAR & ANALYTICS ROUTES
# =============================================================================
@app.route('/corporate/calendar')
@corporate_required
def corporate_calendar():
    """Get all calendar events for this corporate user"""
    from datetime import datetime
    import json
    
    # Get only UPCOMING events
    events = CalendarEvent.query.filter(
        CalendarEvent.corporate_user_id == current_user.id,
        CalendarEvent.start_datetime >= datetime.utcnow()
    ).order_by(CalendarEvent.start_datetime.asc()).all()
    
    # Convert to dict for JSON serialization
    events_json = []
    for event in events:
        events_json.append({
            'id': event.id,
            'title': event.title,
            'start_datetime': event.start_datetime.isoformat(),
            'end_datetime': event.end_datetime.isoformat(),
            'event_type': event.event_type,
            'location': event.location,
            'application_id': event.application_id,
            'description': event.description
        })
    
    upcoming_count = len(events_json)
    
    return render_template('corporate_calendar.html', 
                         events=events,  # For template display
                         events_json=json.dumps(events_json),  # For JavaScript
                         upcoming_count=upcoming_count)

@app.route('/corporate/calendar/event/<int:event_id>/complete', methods=['POST'])
@verified_corporate_required
def complete_calendar_event(event_id):
    event = CalendarEvent.query.filter_by(
        id=event_id,
        corporate_user_id=current_user.id
    ).first_or_404()
    
    try:
        event.status = 'completed'
        
        # Update related application
        if event.application:
            event.application.application_stage = 'interview_completed'
            event.application.last_corporate_action = datetime.utcnow()
        
        db.session.commit()
        
        return {'success': True, 'message': 'Event marked as completed'}
    
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'message': 'Error updating event'}, 500

@app.route('/corporate/analytics')
@corporate_required
def corporate_analytics():
    """Calculate analytics data for this corporate user"""
    # Get applications managed by this corporate user
    applications = Application.query.filter_by(
        corporate_user_id=current_user.id
    ).all()
    
    # Application stages distribution
    stage_counts = {}
    for app in applications:
        stage = app.application_stage or 'applied'
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
    
    application_stages = [
        {'label': 'Applied', 'value': stage_counts.get('applied', 0)},
        {'label': 'Reviewed', 'value': stage_counts.get('reviewed', 0)},
        {'label': 'Interview', 'value': stage_counts.get('interview_scheduled', 0)},
        {'label': 'Completed', 'value': stage_counts.get('interview_completed', 0)},
        {'label': 'Accepted', 'value': stage_counts.get('accepted', 0)},
        {'label': 'Rejected', 'value': stage_counts.get('rejected', 0)},
    ]
    
    # Weekly trends (last 7 days)
    weekly_trends = []
    for i in range(7):
        day = datetime.utcnow() - timedelta(days=6-i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        day_count = len([app for app in applications if 
                        app.submitted_at and day_start <= app.submitted_at < day_end])
        weekly_trends.append(day_count)
    
    # Opportunity performance
    opportunities = LearnearshipOpportunity.query.filter_by(
        company_id=current_user.id
    ).all()
    
    active_ops = len([op for op in opportunities if op.is_active])
    inactive_ops = len([op for op in opportunities if not op.is_active])
    expired_ops = len([op for op in opportunities if op.is_expired()])
    
    opportunity_performance = [
        {'label': 'Active', 'value': active_ops},
        {'label': 'Inactive', 'value': inactive_ops},
        {'label': 'Expired', 'value': expired_ops}
    ]
    
    # Calculate metrics
    total_opportunities = len(opportunities)
    total_applications = len(applications)
    interviews_scheduled = len([app for app in applications if app.application_stage == 'interview_scheduled'])
    candidates_hired = len([app for app in applications if app.application_stage == 'hired'])
    
    # Calculate changes
    this_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    new_opportunities_this_month = len([op for op in opportunities if 
                                      op.created_at and op.created_at >= this_month])
    
    this_week = datetime.utcnow() - timedelta(days=7)
    applications_this_week = len([app for app in applications if 
                                 app.submitted_at and app.submitted_at >= this_week])
    
    upcoming_interviews = CalendarEvent.query.filter(
        CalendarEvent.corporate_user_id == current_user.id,
        CalendarEvent.start_datetime > datetime.utcnow(),
        CalendarEvent.event_type == 'interview'
    ).count()
    
    hire_rate = round((candidates_hired / max(total_applications, 1)) * 100, 1)
    
    return render_template('corporate_analytics.html',
                         application_stages=application_stages,
                         weekly_trends=weekly_trends,
                         opportunity_performance=opportunity_performance,
                         total_opportunities=total_opportunities,
                         total_applications=total_applications,
                         interviews_scheduled=interviews_scheduled,
                         candidates_hired=candidates_hired,
                         new_opportunities_this_month=new_opportunities_this_month,
                         applications_this_week=applications_this_week,
                         upcoming_interviews=upcoming_interviews,
                         hire_rate=hire_rate)

@app.route('/corporate/analytics/data')
@corporate_required
def corporate_analytics_data():
    """API endpoint for real-time analytics data"""
    # Same calculation as above, return JSON
    # This allows for auto-refresh without page reload
    # ... implement similar logic as corporate_analytics route
    return {
        'success': True,
        'application_stages': [],  # calculated data
        'weekly_trends': [],       # calculated data  
        'opportunity_performance': []  # calculated data
    }



# =============================================================================
# ENHANCED EMAIL WORKFLOW ROUTES
# =============================================================================

@app.route('/corporate/application/<int:app_id>/schedule-interview', methods=['POST'])
@verified_corporate_required
def schedule_interview(app_id):
    application = Application.query.filter_by(
        id=app_id,
        company_email=current_user.company_email
    ).first_or_404()
    
    try:
        from datetime import datetime as dt
        
        # Get form data
        interview_date_str = request.form.get('interview_date')
        interview_time_str = request.form.get('interview_time')
        interview_type = request.form.get('interview_type')
        interview_location = request.form.get('interview_location')
        interview_notes = request.form.get('interview_notes')
        
        # Combine date and time
        interview_datetime = dt.strptime(
            f"{interview_date_str} {interview_time_str}", 
            "%Y-%m-%d %H:%M"
        )
        
        # Update application
        application.interview_date = interview_datetime
        application.interview_time = interview_time_str
        application.interview_type = interview_type
        application.interview_location = interview_location
        application.interview_notes = interview_notes
        application.application_stage = 'interview_scheduled'
        application.last_corporate_action = datetime.utcnow()
        application.corporate_user_id = current_user.id
        
        # Create calendar event
        calendar_event = CalendarEvent(
            application_id=application.id,
            corporate_user_id=current_user.id,
            applicant_user_id=application.user_id,
            title=f"Interview: {application.full_name} - {current_user.company_name}",
            description=f"Interview for {application.company_name} learnership position",
            start_datetime=interview_datetime,
            end_datetime=interview_datetime + timedelta(hours=1),  # Default 1 hour
            location=interview_location,
            event_type='interview'
        )
        
        db.session.add(calendar_event)
        db.session.commit()
        
        # Send interview notification email
        send_interview_notification_email(application, interview_datetime, interview_type, interview_location, interview_notes)
        
        flash('Interview scheduled successfully! Notification sent to applicant.', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"Error scheduling interview: {e}")
        flash('Error scheduling interview. Please try again.', 'error')
    
    return redirect(url_for('corporate_application_detail', app_id=app_id))

@app.route('/corporate/application/<int:app_id>/send-message', methods=['POST'])
@verified_corporate_required
def send_application_message(app_id):
    application = Application.query.filter_by(
        id=app_id,
        company_email=current_user.company_email
    ).first_or_404()
    
    try:
        subject = request.form.get('subject')
        message = request.form.get('message')
        
        # Create message record
        app_message = ApplicationMessage(
            application_id=application.id,
            sender_id=current_user.id,
            sender_type='corporate',
            subject=subject,
            message=message,
            message_type='general'
        )
        
        db.session.add(app_message)
        
        # Send email via Gmail API
        gmail_message_id = send_corporate_message_email(
            application, 
            subject, 
            message, 
            current_user
        )
        
        if gmail_message_id:
            app_message.gmail_message_id = gmail_message_id
        
        application.last_corporate_action = datetime.utcnow()
        db.session.commit()
        
        flash('Message sent successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"Error sending message: {e}")
        flash('Error sending message. Please try again.', 'error')
    
    return redirect(url_for('corporate_application_detail', app_id=app_id))

@app.route('/corporate/application/<int:app_id>/update-stage', methods=['POST'])
@verified_corporate_required
def update_application_stage(app_id):
    application = Application.query.filter_by(
        id=app_id,
        company_email=current_user.company_email
    ).first_or_404()
    
    try:
        data = request.get_json()
        new_stage = data.get('stage')
        
        if new_stage not in ['applied', 'reviewed', 'interview_scheduled', 'interview_completed', 'accepted', 'rejected', 'hired']:
            return {'success': False, 'message': 'Invalid stage'}, 400
        
        old_stage = application.application_stage
        application.update_stage(new_stage, current_user.id)
        
        # Send notification email based on stage
        if new_stage == 'accepted':
            send_acceptance_email(application, current_user)
        elif new_stage == 'rejected':
            send_rejection_email(application, current_user)
        elif new_stage == 'reviewed':
            send_status_update_email(application, 'under review', current_user)
        
        return {
            'success': True, 
            'message': f'Application updated from {old_stage} to {new_stage}'
        }
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating stage: {e}")
        return {'success': False, 'message': 'Error updating stage'}, 500

@app.route('/corporate/application/<int:app_id>/update-notes', methods=['POST'])
@verified_corporate_required
def update_application_notes(app_id):
    application = Application.query.filter_by(
        id=app_id,
        company_email=current_user.company_email
    ).first_or_404()
    
    try:
        notes = request.form.get('corporate_notes')
        application.corporate_notes = notes
        application.last_corporate_action = datetime.utcnow()
        db.session.commit()
        
        flash('Notes updated successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating notes: {e}")
        flash('Error updating notes. Please try again.', 'error')
    
    return redirect(url_for('corporate_application_detail', app_id=app_id))


@app.route('/corporate/calendar/events')
@corporate_required
def get_calendar_events():
    # API endpoint for calendar widget
    events = CalendarEvent.query.join(Application).filter(
        Application.company_email == current_user.company_email,
        CalendarEvent.start_datetime >= datetime.utcnow() - timedelta(days=30),
        CalendarEvent.start_datetime <= datetime.utcnow() + timedelta(days=90)
    ).all()
    
    events_data = [event.to_dict() for event in events]
    return {'events': events_data}


# =============================================================================
# COPORATE !!!!!!!!!!!!!!!!!!!!
# =============================================================================


# Add these routes to your app.py

@app.route('/corporate/inbox')
@corporate_required
def corporate_inbox():
    """Corporate inbox showing only CodeCraftCo conversations"""
    conversations = Conversation.query.filter_by(
        corporate_user_id=current_user.id,
        is_active=True
    ).order_by(Conversation.last_message_at.desc()).all()
    
    # Filter to only show conversations with CodeCraftCo signature
    filtered_conversations = []
    for conv in conversations:
        # Check if conversation has any CodeCraftCo messages
        codecraftco_messages = ConversationMessage.query.filter_by(
            conversation_id=conv.id
        ).all()
        
        has_codecraftco_signature = False
        for msg in codecraftco_messages:
            if has_codecraftco_signature_check(msg.body):
                has_codecraftco_signature = True
                break
        
        if has_codecraftco_signature:
            filtered_conversations.append(conv)
    
    return render_template('corporate/inbox.html', conversations=filtered_conversations)


@app.route('/conversation/<int:conversation_id>')
@login_required
def view_conversation(conversation_id):
    try:
        # Get conversation and verify ownership
        conversation = Conversation.query.filter_by(
            id=conversation_id,
            applicant_user_id=current_user.id
        ).first()
        
        if not conversation:
            flash('Conversation not found.', 'error')
            return redirect(url_for('user_inbox'))
        
        # Get messages for this conversation using ConversationMessage model
        messages = ConversationMessage.query.filter_by(
            conversation_id=conversation_id
        ).order_by(ConversationMessage.gmail_timestamp.asc()).all()
        
        # Debug: Print message content to see what's available
        for message in messages:
            print(f"Message ID: {message.id}")
            print(f"Body: {message.body[:100] if message.body else 'None'}...")
            print(f"HTML Body: {message.html_body[:100] if message.html_body else 'None'}...")
            print(f"Subject: {message.subject}")
            print("---")
        
        # Mark messages as read when viewing
        for message in messages:
            if not message.is_read_by_applicant:
                message.is_read_by_applicant = True
        
        # Reset unread count and update last read time
        conversation.applicant_unread_count = 0
        if hasattr(conversation, 'last_read_at'):
            conversation.last_read_at = datetime.utcnow()
        db.session.commit()
        
        return render_template('user_conversation.html', 
                             conversation=conversation, 
                             messages=messages)
                             
    except Exception as e:
        app.logger.error(f"Error viewing conversation: {str(e)}")
        flash('Error loading conversation.', 'error')
        return redirect(url_for('user_inbox'))

@app.route('/api/conversations/<int:conversation_id>/mark-read', methods=['POST'])
@login_required
def mark_conversation_read(conversation_id):
    try:
        # Get the conversation and verify it belongs to the current user
        conversation = Conversation.query.filter_by(
            id=conversation_id,
            applicant_user_id=current_user.id
        ).first()
        
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Reset the unread count for this conversation
        conversation.applicant_unread_count = 0
        
        # Only set last_read_at if the column exists
        try:
            conversation.last_read_at = datetime.utcnow()
        except:
            pass  # Column might not exist, skip it
        
        # Mark all messages as read by applicant
        messages = ConversationMessage.query.filter_by(
            conversation_id=conversation_id
        ).all()
        
        for message in messages:
            try:
                message.is_read_by_applicant = True
            except:
                pass  # Column might not exist
        
        db.session.commit()
        
        return jsonify({'success': True, 'marked_read': len(messages)})
        
    except Exception as e:
        app.logger.error(f"Error marking conversation as read: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/conversations/<int:conversation_id>/messages')
@login_required
def api_get_conversation_messages(conversation_id):  # Renamed to avoid conflict
    try:
        conversation = Conversation.query.get(conversation_id)
        
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Verify user is part of this conversation
        user_is_participant = (
            conversation.applicant_user_id == current_user.id or 
            conversation.corporate_user_id == current_user.id
        )
        
        if not user_is_participant:
            return jsonify({'error': 'Access denied'}), 403
        
        since_count = request.args.get('since', 0, type=int)
        
        # Get all messages for this conversation
        messages = ConversationMessage.query.filter_by(
            conversation_id=conversation_id
        ).order_by(ConversationMessage.gmail_timestamp.asc()).all()
        
        # Return only new messages if since parameter is provided
        new_messages = messages[since_count:] if since_count < len(messages) else []
        
        messages_data = []
        for msg in new_messages:
            messages_data.append({
                'id': msg.id,
                'body': msg.body,
                'html_body': msg.html_body,
                'sender_type': msg.sender_type,
                'sender_id': msg.sender_id,
                'gmail_timestamp': msg.gmail_timestamp.isoformat() if msg.gmail_timestamp else None
            })
        
        return jsonify({
            'messages': messages_data,
            'total_count': len(messages)
        })
        
    except Exception as e:
        app.logger.error(f'Error fetching messages: {str(e)}')
        return jsonify({'error': 'Failed to fetch messages'}), 500

@app.route('/api/user/inbox/unread-count')
@login_required  
def api_get_inbox_unread_count():  # Renamed to avoid conflict
    try:
        # Count unread conversations for current user
        if current_user.role == 'corporate':
            # Corporate user - count conversations where they have unread messages
            unread_count = Conversation.query.filter_by(
                corporate_user_id=current_user.id
            ).filter(Conversation.corporate_unread_count > 0).count()
        else:
            # Regular user (applicant) - count conversations where they have unread messages
            unread_count = Conversation.query.filter_by(
                applicant_user_id=current_user.id
            ).filter(Conversation.applicant_unread_count > 0).count()
        
        return jsonify({'unread_count': unread_count})
        
    except Exception as e:
        app.logger.error(f'Error getting unread count: {str(e)}')
        return jsonify({'unread_count': 0})
    



@app.route('/api/conversations/<int:conversation_id>/messages')
@login_required
def get_conversation_messages(conversation_id):
    try:
        conversation = Conversation.query.get(conversation_id)
        
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Verify user is part of this conversation
        user_is_participant = (
            conversation.applicant_user_id == current_user.id or 
            conversation.corporate_user_id == current_user.id
        )
        
        if not user_is_participant:
            return jsonify({'error': 'Access denied'}), 403
        
        since_count = request.args.get('since', 0, type=int)
        
        # Get all messages for this conversation
        messages = ConversationMessage.query.filter_by(
            conversation_id=conversation_id
        ).order_by(ConversationMessage.gmail_timestamp.asc()).all()
        
        # Return only new messages if since parameter is provided
        new_messages = messages[since_count:] if since_count < len(messages) else []
        
        messages_data = []
        for msg in new_messages:
            messages_data.append({
                'id': msg.id,
                'body': msg.body,
                'html_body': msg.html_body,
                'sender_type': msg.sender_type,
                'sender_id': msg.sender_id,
                'gmail_timestamp': msg.gmail_timestamp.isoformat() if msg.gmail_timestamp else None
            })
        
        return jsonify({
            'messages': messages_data,
            'total_count': len(messages)
        })
        
    except Exception as e:
        app.logger.error(f'Error fetching messages: {str(e)}')
        return jsonify({'error': 'Failed to fetch messages'}), 500

@app.route('/api/user/inbox/unread-count')
@login_required
def get_inbox_unread_count():
    try:
        # Count unread conversations for current user
        if current_user.role == 'corporate':
            # Corporate user - count conversations where they have unread messages
            unread_count = Conversation.query.filter_by(
                corporate_user_id=current_user.id
            ).filter(Conversation.corporate_unread_count > 0).count()
        else:
            # Regular user (applicant) - count conversations where they have unread messages
            unread_count = Conversation.query.filter_by(
                applicant_user_id=current_user.id
            ).filter(Conversation.applicant_unread_count > 0).count()
        
        return jsonify({'unread_count': unread_count})
        
    except Exception as e:
        app.logger.error(f'Error getting unread count: {str(e)}')
        return jsonify({'unread_count': 0})
@app.route('/user/inbox')
@login_required
def user_inbox():
    try:
        # Get conversations for current user
        if current_user.role == 'corporate':
            # Corporate user sees conversations where they are the corporate participant
            conversations = Conversation.query.filter_by(
                corporate_user_id=current_user.id,
                is_active=True
            ).order_by(Conversation.last_message_at.desc()).all()
            
            # Count unread conversations
            unread_count = Conversation.query.filter_by(
                corporate_user_id=current_user.id
            ).filter(Conversation.corporate_unread_count > 0).count()
            
        else:
            # Regular user (applicant) sees conversations where they are the applicant
            conversations = Conversation.query.filter_by(
                applicant_user_id=current_user.id,
                is_active=True
            ).order_by(Conversation.last_message_at.desc()).all()
            
            # Count unread conversations
            unread_count = Conversation.query.filter_by(
                applicant_user_id=current_user.id
            ).filter(Conversation.applicant_unread_count > 0).count()
        
        return render_template(
            'user_inbox.html', 
            conversations=conversations,
            unread_count=unread_count,
            current_year=datetime.now().year
        )
        
    except Exception as e:
        app.logger.error(f'Error loading inbox: {str(e)}')
        flash('Error loading inbox.', 'error')
        return redirect(url_for('user_dashboard'))
    


def update_conversation_read_status(conversation_id, user_id, sender_type):
    """Update read status when new message is added to conversation"""
    try:
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return
        
        # Update unread counts based on who sent the message
        if sender_type == 'applicant':
            # Applicant sent message, increment corporate unread count
            conversation.corporate_unread_count += 1
        else:
            # Corporate sent message, increment applicant unread count
            conversation.applicant_unread_count += 1
        
        conversation.last_message_at = datetime.utcnow()
        db.session.commit()
        
    except Exception as e:
        app.logger.error(f'Error updating conversation read status: {str(e)}')

@app.route('/corporate/inbox/conversation/<int:conversation_id>/reply', methods=['POST'])
@corporate_required
def send_conversation_reply(conversation_id):
    """Send reply in conversation"""
    conversation = Conversation.query.filter_by(
        id=conversation_id,
        corporate_user_id=current_user.id
    ).first_or_404()
    
    try:
        body = request.form.get('message')
        if not body:
            flash('Message cannot be empty', 'error')
            return redirect(url_for('view_conversation', conversation_id=conversation_id))
        
        # Get Gmail service
        gmail_service = get_gmail_service(current_user)
        conv_service = ConversationService(gmail_service)
        
        # Send reply via Gmail
        applicant = User.query.get(conversation.applicant_user_id)
        result = conv_service.send_reply(
            thread_id=conversation.gmail_thread_id,
            to_email=applicant.email,
            subject=conversation.subject,
            body=body,
            from_email=current_user.company_email
        )
        
        if result:
            # Sync the conversation to get the new message
            conv_service.sync_conversation_from_thread(
                conversation.gmail_thread_id,
                conversation.application_id
            )
            
            flash('Reply sent successfully!', 'success')
        else:
            flash('Failed to send reply', 'error')
            
    except Exception as e:
        print(f"Error sending reply: {e}")
        flash('Error sending reply', 'error')
    
    return redirect(url_for('view_conversation', conversation_id=conversation_id))

@app.route('/corporate/inbox/sync')
@corporate_required
def sync_inbox():
    """Manually sync inbox with Gmail"""
    try:
        # Get all applications for this corporate user
        applications = Application.query.filter_by(
            company_email=current_user.company_email
        ).filter(Application.gmail_thread_id.isnot(None)).all()
        
        gmail_service = get_gmail_service(current_user)
        conv_service = ConversationService(gmail_service)
        
        synced_count = 0
        for app in applications:
            if app.gmail_thread_id:
                conversation = conv_service.sync_conversation_from_thread(
                    app.gmail_thread_id,
                    app.id
                )
                if conversation:
                    synced_count += 1
        
        flash(f'Synced {synced_count} conversations from Gmail', 'success')
        
    except Exception as e:
        print(f"Error syncing inbox: {e}")
        flash('Error syncing with Gmail', 'error')
    
    return redirect(url_for('corporate_inbox'))

@app.route('/api/user/inbox/unread-count')
@login_required
def get_unread_count():
    try:
        # Use your existing unread count column
        unread_count = Conversation.query.filter_by(
            applicant_user_id=current_user.id,
        ).filter(Conversation.applicant_unread_count > 0).count()
        
        return jsonify({'unread_count': unread_count})
    except Exception as e:
        app.logger.error(f"Error getting unread count: {str(e)}")
        return jsonify({'unread_count': 0})

from models import LearnearshipOpportunity

@app.route('/corporate/application/<int:app_id>/status', methods=['POST'])
@corporate_required
def update_application_status(app_id):
    application = Application.query.filter_by(
        id=app_id,
        company_email=current_user.company_email
    ).first_or_404()
    
    data = request.get_json()
    new_status = data.get('status')
    
    if new_status in ['new', 'reviewed', 'accepted', 'rejected']:
        application.status = new_status
        db.session.commit()
        return {'success': True, 'message': f'Application marked as {new_status}'}
    
    return {'success': False, 'message': 'Invalid status'}, 400

@app.route('/corporate/opportunity/<int:opp_id>/delete', methods=['DELETE'])
@verified_corporate_required
def delete_opportunity(opp_id):
    opportunity = LearnearshipOpportunity.query.filter_by(
        id=opp_id,
        company_id=current_user.id
    ).first_or_404()
    
    db.session.delete(opportunity)
    db.session.commit()
    
    flash(f'Opportunity "{opportunity.title}" has been deleted.', 'success')
    return {'success': True}

    
@app.route('/corporate/register', methods=['GET', 'POST'])
def corporate_register():
    if request.method == 'POST':
        data = request.form
        
        # Check if email exists
        existing_user = User.query.filter_by(email=data['company_email']).first()
        if existing_user:
            flash('Email already registered. Please use a different email.', 'error')
            return render_template('corporate_register.html')
        
        # Create corporate user
        corporate_user = User(
            email=data['company_email'],
            full_name=data['contact_person'],
            username=data['company_email'].split('@')[0] + '_' + str(uuid.uuid4())[:8],
            role='corporate',
            company_name=data['company_name'],
            company_email=data['company_email'],
            contact_person=data['contact_person'],
            company_phone=data.get('phone'),
            company_website=data.get('website'),
            company_address=data.get('company_address'),
            is_verified=False,
            auth_method='corporate_form'
        )
        
        # Set a temporary password (they'll change it on first login)
        corporate_user.set_password('temp_' + str(uuid.uuid4())[:12])
        
        db.session.add(corporate_user)
        db.session.commit()
        
        flash('Registration successful! Your username is: ' + corporate_user.username + '. An admin will verify your account soon.', 'success')
        return redirect(url_for('admin_login'))
    
    return render_template('corporate_register.html')

@app.route('/corporate/dashboard')
@corporate_required
def corporate_dashboard():
    stats = current_user.get_corporate_stats()
    
    # Get recent applications to company
    recent_applications = Application.query.filter_by(
        company_email=current_user.company_email
    ).order_by(Application.created_at.desc()).limit(5).all() if current_user.company_email else []
    
    # Get upcoming interviews count
    upcoming_interviews = 0
    if hasattr(current_user, 'id'):
        try:
            from models import CalendarEvent
            upcoming_interviews = CalendarEvent.query.filter(
                CalendarEvent.corporate_user_id == current_user.id,
                CalendarEvent.start_datetime > datetime.utcnow(),
                CalendarEvent.event_type == 'interview'
            ).count()
        except:
            upcoming_interviews = 0
    
    return render_template('corporate_dashboard.html',
                         corporate_user=current_user,
                         active_posts=stats.get('opportunities', 0),
                         total_applications=stats.get('applications', 0),
                         total_views=stats.get('views', 0),
                         upcoming_interviews=upcoming_interviews,
                         recent_applications=recent_applications)


@app.route('/corporate/post-opportunity', methods=['GET', 'POST'])
@verified_corporate_required
def post_opportunity():
    if request.method == 'POST':
        data = request.form
        
        opportunity = LearnearshipOpportunity(
            company_id=current_user.id,
            title=data['title'],
            description=data['description'],
            requirements=data.get('requirements'),
            benefits=data.get('benefits'),
            location=data['location'],
            duration=data.get('duration'),
            stipend=data.get('stipend'),
            application_email=data['application_email'],
            expire_date=datetime.strptime(data['expire_date'], '%Y-%m-%d'),
            is_recurring=bool(data.get('is_recurring')),
            recurring_frequency=data.get('recurring_frequency')
        )
        
        if data.get('deadline'):
            opportunity.application_deadline = datetime.strptime(data['deadline'], '%Y-%m-%d')
        
        if data.get('max_applicants'):
            opportunity.max_applicants = int(data['max_applicants'])
        
        db.session.add(opportunity)
        db.session.commit()
        
        flash('Learnership opportunity posted successfully!', 'success')
        return redirect(url_for('corporate_dashboard'))
    
    # ADD THIS LINE - pass corporate_user to template
    return render_template('corporate_post_opportunity.html', corporate_user=current_user)

@app.route('/corporate/applications')
@corporate_required
def corporate_applications():
    """Get all applications for this corporate user"""
    try:
        # Get applications managed by this corporate user
        applications = Application.query.filter_by(
            corporate_user_id=current_user.id
        ).order_by(Application.submitted_at.desc()).all()
        
        return render_template('corporate_applications.html', 
                             applications=applications,
                             corporate_user=current_user)
    except Exception as e:
        print(f"Error: {e}")
        flash(f'Error loading applications: {str(e)}', 'error')
        return redirect(url_for('corporate_dashboard'))

@app.route('/corporate/application/<int:app_id>')
@corporate_required
def corporate_application_detail(app_id):
    """View detailed application"""
    application = Application.query.filter_by(
        id=app_id,
        corporate_user_id=current_user.id
    ).first_or_404()
    
    return render_template('corporate_application_detail_enhanced.html', 
                         application=application)


@app.route('/corporate/opportunities')
@corporate_required
def corporate_opportunities():
    opportunities = LearnearshipOpportunity.query.filter_by(
        company_id=current_user.id
    ).order_by(LearnearshipOpportunity.created_at.desc()).all()
    
    return render_template('corporate_opportunities.html',
                         opportunities=opportunities)

@app.route('/corporate/opportunity/<int:opp_id>/toggle')
@verified_corporate_required
def toggle_opportunity(opp_id):
    opportunity = LearnearshipOpportunity.query.filter_by(
        id=opp_id,
        company_id=current_user.id
    ).first_or_404()
    
    opportunity.is_active = not opportunity.is_active
    db.session.commit()
    
    status = "activated" if opportunity.is_active else "deactivated"
    flash(f'Opportunity "{opportunity.title}" has been {status}.', 'success')
    
    return redirect(url_for('corporate_opportunities'))

# =============================================================================
# PROFILE COMPLETION UTILITY
# =============================================================================

def calculate_profile_completion(user):
    score = 0
    total = 6

    if user.full_name: score += 1
    if user.email: score += 1
    if user.profile_picture: score += 1
    if getattr(user, "phone", None): score += 1
    if getattr(user, "address", None): score += 1

    has_docs = Document.query.filter_by(
        user_id=user.id, is_active=True
    ).count() > 0

    if has_docs:
        score += 1

    percentage = round((score / total) * 100)
    print(f"Profile completion for {user.full_name}: {score}/{total} = {percentage}%")

    return percentage


    # =============================================================================
# DASHBOARD API ROUTES
# =============================================================================

@app.route("/api/dashboard-stats")
@login_required
def api_dashboard_stats():
    try:
        total = Application.query.filter_by(user_id=current_user.id).count()
        pending = Application.query.filter_by(
            user_id=current_user.id, status="pending"
        ).count()

        week_ago = datetime.utcnow() - timedelta(days=7)
        recent = Application.query.filter(
            Application.user_id == current_user.id,
            Application.created_at >= week_ago
        ).count()

        responses = Application.query.filter_by(
            user_id=current_user.id, email_status="responded"
        ).count()

        sent_count = Application.query.filter(
            Application.user_id == current_user.id,
            Application.email_status.in_(
                ["sent", "delivered", "read", "responded"]
            ),
        ).count()

        response_rate = (responses / sent_count * 100) if sent_count else 0
        profile_completion = calculate_profile_completion(current_user)

        return jsonify(
            success=True,
            stats={
                "total": total,
                "pending": pending,
                "recent_count": recent,
                "responses": responses,
                "response_rate": response_rate,
                "profile_completion": profile_completion,
            },
        )

    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@app.route("/api/recent-applications")
@login_required
def api_recent_applications():
    try:
        recent = (
            Application.query.filter_by(user_id=current_user.id)
            .order_by(Application.created_at.desc())
            .limit(3)
            .all()
        )

        out = []
        for app_item in recent:
            lr = app_item.learnership

            out.append(
                {
                    "id": app_item.id,
                    "learnership_title": lr.title if lr else getattr(app_item, "position", "Application"),
                    "company_name": lr.company if lr else (app_item.company_name or "Unknown"),
                    "company_logo": lr.company_logo if lr else getattr(app_item, "company_logo", None),
                    "location": lr.location if lr else getattr(app_item, "location", None),
                    "status": app_item.status,
                    "email_status": app_item.email_status,
                    "created_at": app_item.created_at.isoformat() if app_item.created_at else None,
                    "gmail_thread_id": app_item.gmail_thread_id,
                    "gmail_tracked": bool(app_item.gmail_message_id),
                    "has_response": app_item.email_status == "responded",
                }
            )

        return jsonify(success=True, applications=out)

    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


# =============================================================================
# API: INDIVIDUAL APPLICATION STATUS
# =============================================================================

@app.route("/api/application-status/<int:app_id>")
@login_required
def api_application_status(app_id):
    try:
        application = Application.query.filter_by(
            id=app_id, user_id=current_user.id
        ).first()

        if not application:
            return jsonify(success=False, error="Application not found"), 404

        return jsonify(
            success=True,
            status=application.status,
            email_status=application.email_status,
            has_response=application.email_status == "responded",
            gmail_thread_id=application.gmail_thread_id,
            last_updated=datetime.utcnow().isoformat()
        )

    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


# =============================================================================
# DOWNLOAD & SAVE GOOGLE PROFILE PICTURE
# =============================================================================

import requests

def download_and_save_profile_picture(url, user_id):
    if not url:
        return None

    try:
        response = requests.get(url)

        if response.status_code == 200:
            filename = secure_filename(f"profile_{user_id}.jpg")
            folder = os.path.join(app.root_path, "static/uploads")
            os.makedirs(folder, exist_ok=True)
            filepath = os.path.join(folder, filename)

            with open(filepath, "wb") as f:
                f.write(response.content)

            return f"/static/uploads/{filename}"
    except Exception as e:
        print("Profile picture download failed:", e)

    return None

# =============================================================================
# PROFILE EDIT ROUTE
# =============================================================================

@app.route("/user/edit-profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    form = EditProfileForm()

    if form.validate_on_submit():
        current_user.full_name = form.full_name.data
        current_user.phone = form.phone.data
        current_user.address = form.address.data
        db.session.commit()

        flash("Profile updated successfully!", "success")
        return redirect(url_for("user_dashboard"))

    # Pre-fill
    form.full_name.data = current_user.full_name
    form.phone.data = current_user.phone
    form.address.data = current_user.address

    return render_template("edit_profile.html", form=form)

# =============================================================================
# DOCUMENT VIEW ROUTES
# =============================================================================

@app.route("/user/documents/view/<int:document_id>")
@login_required
def view_document(document_id):
    try:
        document = Document.query.filter_by(
            id=document_id, user_id=current_user.id
        ).first()

        if not document:
            flash("Document not found.", "error")
            return redirect(url_for("document_center"))

        file_path = os.path.join(
            app.config["UPLOAD_FOLDER"], "documents", document.filename
        )

        if not os.path.exists(file_path):
            flash("Document file not found.", "error")
            return redirect(url_for("document_center"))

        ext = document.filename.lower().split(".")[-1]

        if ext in ["jpg", "jpeg", "png", "gif"]:
            return send_file(file_path, as_attachment=False)

        if ext == "pdf":
            return send_file(file_path, as_attachment=False, mimetype="application/pdf")

        return send_file(file_path, as_attachment=True)

    except Exception as e:
        print("Error viewing document:", e)
        flash("Error viewing document.", "error")
        return redirect(url_for("document_center"))


@app.route("/user/documents/preview/<int:document_id>")
@login_required
def preview_document(document_id):
    try:
        document = Document.query.filter_by(
            id=document_id, user_id=current_user.id
        ).first()

        if not document:
            return jsonify(error="Document not found"), 404

        file_path = os.path.join(
            app.config["UPLOAD_FOLDER"], "documents", document.filename
        )

        if not os.path.exists(file_path):
            return jsonify(error="Document file not found"), 404

        ext = document.filename.lower().split(".")[-1]

        return jsonify(
            id=document.id,
            filename=document.filename,
            original_name=document.original_filename,
            file_type=ext,
            upload_date=document.uploaded_at.strftime("%Y-%m-%d %H:%M:%S"),
            view_url=url_for("view_document", document_id=document.id),
            download_url=url_for("download_document", document_id=document.id),
        )

    except Exception as e:
        return jsonify(error=str(e)), 500
    

# =============================================================================
# DOCUMENT CENTER
# =============================================================================

@app.route("/user/documents", methods=["GET", "POST"])
@login_required
def document_center():
    form = DocumentUploadForm()

    if form.validate_on_submit():
        file = form.document.data

        if file:
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique = f"{current_user.id}_{timestamp}_{filename}"

            file_path = os.path.join(
                app.config["UPLOAD_FOLDER"], "documents", unique
            )
            file.save(file_path)

            doc = Document(
                user_id=current_user.id,
                document_type=form.document_type.data,
                filename=unique,
                original_filename=filename,
                file_path=file_path,
                file_size=os.path.getsize(file_path),
            )
            db.session.add(doc)
            db.session.commit()

            flash("Document uploaded successfully!", "success")
            return redirect(url_for("document_center"))

    documents = (
        Document.query.filter_by(user_id=current_user.id, is_active=True)
        .order_by(Document.uploaded_at.desc())
        .all()
    )

    grouped = {}
    for doc in documents:
        group = doc.document_type.replace("_", " ").title()
        grouped.setdefault(group, []).append(doc)

    return render_template(
        "document_center.html", form=form, documents=documents, grouped_documents=grouped
    )


@app.route("/user/document/delete/<int:doc_id>", methods=["POST"])
@login_required
def delete_document(doc_id):
    document = Document.query.filter_by(
        id=doc_id, user_id=current_user.id
    ).first_or_404()

    document.is_active = False
    db.session.commit()

    flash("Document removed successfully!", "success")
    return redirect(url_for("document_center"))



# =============================================================================
# LOAD LEARNERSHIPS FROM JSON
# =============================================================================

def load_learnerships_from_json():
    json_path = os.path.join(app.static_folder, "data", "learnerships.json")

    try:
        with open(json_path, "r") as f:
            data = json.load(f)

        # Convert dates
        for item in data:
            if isinstance(item.get("closing_date"), str):
                try:
                    item["closing_date"] = datetime.strptime(
                        item["closing_date"], "%Y-%m-%d"
                    )
                except:
                    # Fallback: 1 year from now
                    item["closing_date"] = datetime.now().replace(
                        year=datetime.now().year + 1
                    )

        return data

    except Exception as e:
        print("Error loading learnership JSON:", e)
        return []

# =============================================================================
# LEARNERSHIP LISTING + SEARCH
# =============================================================================

@app.route("/user/learnerships", methods=["GET", "POST"])
@login_required
def learnerships():
    """Display learnership opportunities"""
    try:
        # Get learnership emails
        learnership_emails = LearnershipEmail.query.filter_by(is_active=True).all()
        
        # Convert to JSON-serializable format for template
        emails_for_template = []
        for email in learnership_emails:
            emails_for_template.append({
                'id': email.id,
                'company_name': email.company_name,
                'email_address': email.email_address,
                'is_reachable': email.is_reachable,
                'response_time': email.response_time,
                'last_checked': email.last_checked.isoformat() if email.last_checked else None
            })
        
        return render_template(
            "learnerships.html",
            learnership_emails=emails_for_template,
            title="Available Learnership Opportunities"
        )
        
    except Exception as e:
        print(f"Error in learnerships route: {e}")
        flash("Error loading learnership opportunities. Please try again.", "error")
        return redirect(url_for('user_dashboard'))

         
@app.route("/cv-template/<template>")
@login_required
def cv_generator(template):
    mapping = {
        "classic": "classic.html",
        "modern": "modern.html",
        "creative": "creative.html",
        "minimal": "minimal.html",
        "sidebar": "sidebar.html",
    }

    template_file = mapping.get(template, "classic.html")

    try:
        return render_template(template_file)
    except Exception as e:
        print(f"Error loading CV template {template_file}:", e)
        return (
            f"<h1>Error loading CV template</h1><p>{template_file}</p><p>{e}</p>",
            500,
        )

# =============================================================================
# USER INBOX ROUTES - FIXED FOR YOUR TEMPLATES
# =============================================================================

import logging
logger = logging.getLogger(__name__)  # Add this at the top of your app.py

@app.route('/user/inbox/<int:conversation_id>')
@login_required
def user_conversation(conversation_id):
    """View a specific conversation"""
    try:
        from models import Conversation, ConversationMessage
        
        # Get conversation and verify ownership
        conversation = Conversation.query.filter_by(
            id=conversation_id
        ).filter(
            (Conversation.applicant_user_id == current_user.id) |
            (Conversation.corporate_user_id == current_user.id)
        ).first()
        
        if not conversation:
            flash('Conversation not found', 'error')
            return redirect(url_for('user_inbox'))
        
        # Get all messages in the conversation, ordered by timestamp
        messages = ConversationMessage.query.filter_by(
            conversation_id=conversation_id
        ).order_by(ConversationMessage.gmail_timestamp.asc()).all()
        
        # Mark messages as read for current user
        unread_messages = []
        if current_user.id == conversation.applicant_user_id:
            # Mark as read by applicant
            unread_messages = [m for m in messages if not m.is_read_by_applicant]
            for msg in unread_messages:
                msg.is_read_by_applicant = True
            conversation.applicant_unread_count = 0
        elif current_user.id == conversation.corporate_user_id:
            # Mark as read by corporate
            unread_messages = [m for m in messages if not m.is_read_by_corporate]
            for msg in unread_messages:
                msg.is_read_by_corporate = True
            conversation.corporate_unread_count = 0
        
        if unread_messages:
            db.session.commit()
        
        return render_template(
            'user_conversation.html',  # ← Your actual template name
            conversation=conversation,
            messages=messages,
            current_year=datetime.now().year
        )
        
    except Exception as e:
        app.logger.error(f"Error viewing conversation: {e}")
        flash('Error loading conversation', 'error')
        return redirect(url_for('user_inbox'))


@app.route('/user/inbox/sync', methods=['POST'])
@login_required
def user_inbox_sync():
    """Trigger a Gmail sync for the current user"""
    try:
        checker = GmailStatusChecker(current_user.id)
        updated, has_new = checker.sync_inbox_and_statuses()
        app.logger.info(f"Sync complete: {updated} apps updated, has_new: {has_new}")
        return ('', 204)  # Success, no content
    except Exception as e:
        app.logger.error(f"Error syncing inbox: {e}")
        return jsonify({'error': 'Sync failed'}), 500


@app.route('/api/user/inbox/unread-count')
@login_required
def api_user_inbox_unread_count():
    """Get unread conversation count for current user"""
    try:
        from models import Conversation
        from sqlalchemy import func
        
        # Sum all unread counts for this user's conversations
        total_unread = db.session.query(
            func.coalesce(func.sum(Conversation.applicant_unread_count), 0)
        ).filter(
            Conversation.applicant_user_id == current_user.id,
            Conversation.is_active == True
        ).scalar()
        
        return jsonify({
            'unread_count': int(total_unread or 0),
            'status': 'success'
        })
        
    except Exception as e:
        app.logger.error(f"Error getting unread count: {e}")
        return jsonify({
            'unread_count': 0,
            'status': 'error',
            'message': str(e)
        })


@app.route('/api/user/inbox/conversations')
@login_required
def api_user_inbox_conversations():
    """Check for new conversations and activity"""
    try:
        from models import Conversation
        from sqlalchemy import func
        
        # Get conversation stats
        conversation_count = Conversation.query.filter_by(
            applicant_user_id=current_user.id,
            is_active=True
        ).count()
        
        # Get latest message time
        latest_message_time = db.session.query(
            func.max(Conversation.last_message_at)
        ).filter(
            Conversation.applicant_user_id == current_user.id,
            Conversation.is_active == True
        ).scalar()
        
        # Check if there are any unread messages
        has_unread = db.session.query(
            func.sum(Conversation.applicant_unread_count)
        ).filter(
            Conversation.applicant_user_id == current_user.id,
            Conversation.is_active == True
        ).scalar() or 0
        
        return jsonify({
            'conversation_count': conversation_count,
            'has_new_messages': bool(has_unread > 0),
            'latest_message_time': latest_message_time.isoformat() if latest_message_time else None,
            'status': 'success'
        })
        
    except Exception as e:
        app.logger.error(f"Error checking conversations: {e}")
        return jsonify({
            'conversation_count': 0,
            'has_new_messages': False,
            'latest_message_time': None,
            'status': 'error'
        })



@app.route('/api/user/inbox/mark-all-read', methods=['POST'])
@login_required
def api_mark_all_conversations_read():
    """Mark all conversations as read for current user"""
    try:
        from models import Conversation, ConversationMessage
        
        # Get all user's conversations
        user_conversations = Conversation.query.filter_by(
            applicant_user_id=current_user.id,
            is_active=True
        ).all()
        
        conversation_ids = [c.id for c in user_conversations]
        
        if conversation_ids:
            # Mark all messages in user's conversations as read
            ConversationMessage.query.filter(
                ConversationMessage.conversation_id.in_(conversation_ids)
            ).update({
                'is_read_by_applicant': True
            }, synchronize_session=False)
            
            # Reset all unread counts
            Conversation.query.filter_by(
                applicant_user_id=current_user.id
            ).update({
                'applicant_unread_count': 0
            })
            
            db.session.commit()
        
        return jsonify({'success': True, 'message': 'All conversations marked as read'})
        
    except Exception as e:
        app.logger.error(f"Error marking all conversations as read: {e}")
        return jsonify({'error': 'Failed to mark all as read'}), 500


@app.route('/conversation/<int:conversation_id>')
@login_required
def conversation_detail(conversation_id):
    """View a specific conversation - matches template url_for calls"""
    try:
        from models import Conversation, ConversationMessage
        
        # Get conversation and verify ownership
        conversation = Conversation.query.filter_by(
            id=conversation_id
        ).filter(
            (Conversation.applicant_user_id == current_user.id) |
            (Conversation.corporate_user_id == current_user.id)
        ).first()
        
        if not conversation:
            flash('Conversation not found', 'error')
            return redirect(url_for('user_inbox'))
        
        # Get all messages in the conversation, ordered by timestamp
        messages = ConversationMessage.query.filter_by(
            conversation_id=conversation_id
        ).order_by(ConversationMessage.gmail_timestamp.asc()).all()
        
        # Mark messages as read for current user
        unread_messages = []
        if current_user.id == conversation.applicant_user_id:
            # Mark as read by applicant
            unread_messages = [m for m in messages if not m.is_read_by_applicant]
            for msg in unread_messages:
                msg.is_read_by_applicant = True
            conversation.applicant_unread_count = 0
        elif current_user.id == conversation.corporate_user_id:
            # Mark as read by corporate
            unread_messages = [m for m in messages if not m.is_read_by_corporate]
            for msg in unread_messages:
                msg.is_read_by_corporate = True
            conversation.corporate_unread_count = 0
        
        if unread_messages:
            db.session.commit()
        
        return render_template(
            'user_conversation.html',
            conversation=conversation,
            messages=messages,
            current_year=datetime.now().year
        )
        
    except Exception as e:
        app.logger.error(f"Error viewing conversation: {e}")
        flash('Error loading conversation', 'error')
        return redirect(url_for('user_inbox'))

@app.route('/api/conversations/<int:conversation_id>/messages', methods=['POST'])
@login_required
def send_conversation_message(conversation_id):
    data = request.get_json()
    message = data.get('message', '').strip()
    
    if not message:
        return jsonify({'error': 'Message is required'}), 400
    
    # Save message and send via Gmail API
    # Return message_id for status tracking
    return jsonify({'success': True, 'message_id': 'new_msg_id'})

@app.route('/api/conversations/<int:conversation_id>/messages')
@login_required  
def get_new_messages(conversation_id):
    since = request.args.get('since', 0, type=int)
    # Return new messages since 'since' count
    return jsonify({'messages': []})

# Add this to your Flask app initialization
from markupsafe import Markup
import re

@app.template_filter('nl2br')
def nl2br_filter(text):
    """Convert newlines to <br> tags"""
    if not text:
        return ''
    # Replace \n with <br> and wrap in Markup to mark as safe HTML
    return Markup(re.sub(r'\n', '<br>', str(text)))



# Helper function to avoid code duplication
def view_conversation_helper(conversation_id):
    """Shared logic for viewing conversations"""
    try:
        from models import Conversation, ConversationMessage
        
        conversation = Conversation.query.filter_by(
            id=conversation_id
        ).filter(
            (Conversation.applicant_user_id == current_user.id) |
            (Conversation.corporate_user_id == current_user.id)
        ).first()
        
        if not conversation:
            flash('Conversation not found', 'error')
            return redirect(url_for('user_inbox'))
        
        messages = ConversationMessage.query.filter_by(
            conversation_id=conversation_id
        ).order_by(ConversationMessage.gmail_timestamp.asc()).all()
        
        # Mark as read logic
        unread_messages = []
        if current_user.id == conversation.applicant_user_id:
            unread_messages = [m for m in messages if not m.is_read_by_applicant]
            for msg in unread_messages:
                msg.is_read_by_applicant = True
            conversation.applicant_unread_count = 0
        elif current_user.id == conversation.corporate_user_id:
            unread_messages = [m for m in messages if not m.is_read_by_corporate]
            for msg in unread_messages:
                msg.is_read_by_corporate = True
            conversation.corporate_unread_count = 0
        
        if unread_messages:
            db.session.commit()
        
        return render_template(
            'user_conversation.html',
            conversation=conversation,
            messages=messages,
            current_year=datetime.now().year
        )
        
    except Exception as e:
        app.logger.error(f"Error viewing conversation: {e}")
        flash('Error loading conversation', 'error')
        return redirect(url_for('user_inbox'))
    

# =============================================================================
# APPLY TO MULTIPLE LEARNERSHIPS
# =============================================================================

@app.route("/user/apply", methods=["GET", "POST"])
@login_required
@check_application_limit  # ADD THIS LINE
def apply_learnership():
    selected_ids = request.args.getlist("selected")

    if not selected_ids:
        flash("Please select at least one learnership.", "warning")
        return redirect(url_for("learnerships"))

    selected_ids = [int(x) for x in selected_ids if x.isdigit()]

    if not selected_ids:
        flash("Invalid selection.", "warning")
        return redirect(url_for("learnerships"))

    # ADD THIS PREMIUM LIMIT CHECK FOR BULK LEARNERSHIPS
    if not current_user.is_premium_active():
        remaining = current_user.get_remaining_applications()
        if remaining == 0:
            flash("Daily application limit reached (24 applications). Upgrade to premium for unlimited applications!", "warning")
            return redirect(url_for('upgrade_to_premium'))
        elif len(selected_ids) > remaining:
            flash(f"You can only apply to {remaining} more learnerships today. Selected {len(selected_ids)} learnerships. Upgrade to premium for unlimited applications!", "warning")
            return redirect(url_for('upgrade_to_premium'))

    all_data = load_learnerships_from_json()

    # Add fallback emails if missing
    for item in all_data:
        if not item.get("apply_email"):
            item["apply_email"] = (
                f"applications@{item['company'].lower().replace(' ', '')}.co.za"
            )

    selected_learnerships = [i for i in all_data if i["id"] in selected_ids]

    if not selected_learnerships:
        flash("No valid learnerships selected.", "warning")
        return redirect(url_for("learnerships"))

    user_docs = Document.query.filter_by(
        user_id=current_user.id, is_active=True
    ).all()

    form = ApplicationForm()

    if form.validate_on_submit():
        created = []
        applications_sent = 0  # ADD THIS COUNTER

        for lr in selected_learnerships:
            try:
                app_record = Application(
                    user_id=current_user.id,
                    learnership_id=lr.get("id"),
                    learnership_name=lr.get("title", "Unknown"),
                    company_name=lr.get("company", "Unknown"),
                    status="pending",
                )
                db.session.add(app_record)
                db.session.commit()

                created.append(app_record)
                
                # ADD THIS: Track each application
                current_user.use_application()
                applications_sent += 1
                print(f"📊 Application #{applications_sent} counted for user")
                
            except Exception as e:
                print("Error creating application:", e)
                db.session.rollback()

        if created:
            try:
                attachment_ids = []
                if hasattr(form, "attachments"):
                    attachment_ids = [int(x) for x in form.attachments.data]

                current_user.email_body = form.email_body.data

                launch_bulk_send(current_user, selected_learnerships, attachment_ids)

                # ADD PREMIUM MESSAGE
                remaining_today = current_user.get_remaining_applications()
                success_msg = f"Created {len(created)} applications. Sending emails..."
                if not current_user.is_premium_active():
                    success_msg += f" You have {remaining_today} applications remaining today."
                
                flash(success_msg, "success")
                
            except Exception as e:
                flash(f"Applications created but email sending failed: {e}", "warning")

        else:
            flash("Failed to create applications.", "error")

        return redirect(url_for("my_applications"))

    return render_template(
        "apply_learnership.html",
        form=form,
        selected_learnerships=selected_learnerships,
        user_documents=user_docs,
    )
# =============================================================================
# GMAIL STATUS TRACKING — MAIN APPLICATION PAGE
# =============================================================================

@app.route("/user/applications")
@login_required
def my_applications():
    """Display user's applications with Gmail tracking information."""
    
    applications = (
        Application.query.filter_by(user_id=current_user.id)
        .order_by(Application.updated_at.desc())
        .all()
    )

    grouped_status = {
        "pending": [],
        "submitted": [],
        "reviewed": [],
        "accepted": [],
        "rejected": [],
    }

    email_groups = {
        "draft": [],
        "sent": [],
        "delivered": [],
        "read": [],
        "responded": [],
        "failed": [],
    }

    stats = {
        "total": len(applications),
        "sent_emails": 0,
        "responses_received": 0,
        "pending_responses": 0,
        "gmail_tracked": 0,
        "failed_emails": 0,
        "recent_activity": 0,
    }

    for app_item in applications:

        # Application status grouping
        if app_item.status in grouped_status:
            grouped_status[app_item.status].append(app_item)

        # Email status grouping
        es = app_item.email_status or "draft"
        if es in email_groups:
            email_groups[es].append(app_item)

        # Stats
        if app_item.sent_at:
            stats["sent_emails"] += 1

        if app_item.has_response:
            stats["responses_received"] += 1

        if app_item.gmail_message_id:
            stats["gmail_tracked"] += 1

        if es == "failed":
            stats["failed_emails"] += 1

        if es == "sent" and not app_item.has_response:
            stats["pending_responses"] += 1

        if app_item.is_recent(7):
            stats["recent_activity"] += 1

    # Check if some applications need status updates
    recent_cutoff = datetime.utcnow() - timedelta(days=30)

    needs_update = (
        Application.query.filter_by(user_id=current_user.id)
        .filter(Application.gmail_message_id.isnot(None))
        .filter(Application.sent_at >= recent_cutoff)
        .filter(Application.email_status.in_(["sent", "delivered"]))
        .count()
    )

    return render_template(
        "my_applications.html",
        applications=applications,
        grouped_applications=grouped_status,
        email_status_groups=email_groups,
        stats=stats,
        needs_update=needs_update,
    )


# =============================================================================
# API: UPDATE GMAIL STATUS FOR ALL APPLICATIONS
# =============================================================================

@app.route("/update_application_statuses", methods=["POST"])
@login_required
def update_application_statuses():
    try:
        from gmail_status_checker import GmailStatusChecker

        checker = GmailStatusChecker(current_user.id)
        updated_count = checker.update_application_statuses()

        return jsonify(
            success=True,
            updated_count=updated_count,
            message=f"Updated {updated_count} application statuses",
        )

    except Exception as e:
        print("Error updating statuses:", e)
        return jsonify(success=False, error=str(e)), 500


# =============================================================================
# API: LIVE GMAIL CHECK FOR ONE APPLICATION
# =============================================================================

@app.route("/api/application_status/<int:app_id>")
@login_required
def get_application_status(app_id):
    app_item = Application.query.filter_by(
        id=app_id, user_id=current_user.id
    ).first_or_404()

    live_status = None

    if app_item.gmail_message_id:
        try:
            from gmail_status_checker import GmailStatusChecker

            checker = GmailStatusChecker(current_user.id)
            live_status = checker.check_message_status(app_item.gmail_message_id)

        except Exception as e:
            print("Live Gmail check error:", e)

    return jsonify(
        id=app_item.id,
        status=app_item.status,
        email_status=app_item.email_status,
        sent_at=app_item.sent_at.isoformat() if app_item.sent_at else None,
        has_response=app_item.has_response,
        response_count=app_item.response_thread_count,
        response_received_at=(
            app_item.response_received_at.isoformat()
            if app_item.response_received_at
            else None
        ),
        gmail_message_id=app_item.gmail_message_id,
        gmail_thread_id=app_item.gmail_thread_id,
        gmail_url=app_item.get_gmail_url(),
        days_since_sent=app_item.days_since_sent(),
        live_status=live_status,
    )


# =============================================================================
# AUTO-UPDATE: ONLY RECENT APPLICATIONS
# =============================================================================

@app.route("/auto-update-gmail-status")
@login_required
def auto_update_gmail_status():
    """Auto-update Gmail statuses for recent applications."""
    try:
        from gmail_status_checker import GmailStatusChecker

        cut_off = datetime.utcnow() - timedelta(days=7)

        recent_apps = (
            Application.query.filter_by(user_id=current_user.id)
            .filter(Application.gmail_message_id.isnot(None))
            .filter(Application.sent_at >= cut_off)
            .all()
        )

        if not recent_apps:
            return jsonify(
                success=True,
                message="No recent applications to update.",
                updated_count=0,
            )

        checker = GmailStatusChecker(current_user.id)
        updated_count = 0

        for app_item in recent_apps:
            try:
                status_info = checker.check_message_status(app_item.gmail_message_id)
                if status_info:
                    app_item.update_from_gmail_status(status_info)
                    updated_count += 1

                time.sleep(0.2)

            except Exception as e:
                print("Error updating:", e)

        db.session.commit()

        return jsonify(
            success=True,
            updated_count=updated_count,
            total_checked=len(recent_apps),
            message=f"Updated {updated_count} of {len(recent_apps)} recent applications",
        )

    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


# =============================================================================
# BULK CHECK: FIND RESPONSES IN LAST 30 DAYS
# =============================================================================

@app.route("/bulk-check-responses")
@login_required
def bulk_check_responses():
    try:
        from gmail_status_checker import GmailStatusChecker

        checker = GmailStatusChecker(current_user.id)
        responses = checker.check_recent_responses(days=30)

        return jsonify(
            success=True,
            responses_found=responses,
            message=f"Found {responses} new responses!"
        )
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


# =============================================================================
# GMAIL STATUS DASHBOARD
# =============================================================================

@app.route("/gmail-status-dashboard")
@login_required
def gmail_status_dashboard():
    apps = (
        Application.query.filter_by(user_id=current_user.id)
        .filter(Application.gmail_message_id.isnot(None))
        .order_by(Application.sent_at.desc())
        .all()
    )

    status_groups = {
        "sent": [],
        "delivered": [],
        "read": [],
        "responded": [],
        "failed": [],
    }

    stats = {
        "total_tracked": len(apps),
        "awaiting_response": 0,
        "got_responses": 0,
        "avg_response_time": None,
    }

    response_times = []

    for a in apps:
        if a.email_status in status_groups:
            status_groups[a.email_status].append(a)

        if a.has_response and a.sent_at and a.response_received_at:
            diff = (a.response_received_at - a.sent_at).days
            response_times.append(diff)
            stats["got_responses"] += 1
        elif a.email_status == "sent" and not a.has_response:
            stats["awaiting_response"] += 1

    if response_times:
        stats["avg_response_time"] = sum(response_times) / len(response_times)

    return render_template(
        "gmail_status_dashboard.html",
        applications=apps,
        status_groups=status_groups,
        response_stats=stats,
    )


# =============================================================================
# EMAIL SENDING HELPERS (GMAIL API)
# =============================================================================
def send_application_email(recipient_email, company_name, user):
    """
    Send an application email with plain text body and HTML signature
    """
    from mailer import (
        build_credentials,
        create_message_with_attachments,
        send_gmail_message,
    )
    from models import GoogleToken
    from flask import render_template
    from socket import timeout
    import os

    result = {
        "success": False,
        "message": "",
        "gmail_data": {}
    }

    subject = f"Application for Learnership Opportunity - {user.full_name or user.email}"

    try:
        token_row = GoogleToken.query.filter_by(user_id=user.id).first()
        if not token_row:
            print("No Google token found.")
            result["message"] = "Google authentication required."  
            return result

        credentials = build_credentials(token_row.token_json)

        # Get documents
        docs = Document.query.filter_by(user_id=user.id, is_active=True).all()
        file_paths = []

        for doc in docs:
            if doc.file_path and isinstance(doc.file_path, str) and os.path.exists(doc.file_path):
                file_paths.append({
                    "path": doc.file_path,
                    "filename": doc.original_filename
                })

        print(f"📎 Found {len(file_paths)} valid documents to attach")

        # Document status for plain text
        if file_paths:
            docs_plain = f"✓ Documents Attached: {len(file_paths)} file(s)\n"
        else:
            docs_plain = "⚠️ No Documents Attached\nPlease reply with your CV, resume, and supporting documents to strengthen your application.\n"

        # ✅ PLAIN TEXT BODY
        body = f"""Dear Hiring Team,

I hope this message finds you well. I am writing to express my genuine interest in learnership opportunities within your organization.

Please find my CV and supporting documents attached for your review. I am eager to develop professionally and contribute positively to your team.

Contact Information:
Name: {user.full_name or 'Not provided'}
Email: {user.email}
Phone: {user.phone or 'Not provided'}

{docs_plain}
Thank you for your time and consideration.

Kind regards,
{user.full_name or user.email}
"""

        # ✅ GET HTML SIGNATURE
        signature_html = render_template('emails/email_signature.html')
        
        # ✅ COMBINE BODY + SIGNATURE IN HTML - LEFT ALIGNED
        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6; margin: 0; padding: 0;">
    <pre style="white-space: pre-wrap; word-wrap: break-word; font-family: Arial, sans-serif; margin: 0; padding: 0; font-size: 14px; color: #333; text-align: left;">{body}</pre>
    {signature_html}
</body>
</html>"""

        message = create_message_with_attachments(
            user.email,
            recipient_email,
            subject,
            body,
            file_paths,
            html_body=html_body
        )

        try:
            sent_message = send_gmail_message(credentials, message)
            
            if sent_message:
                gmail_id = sent_message.get('id')
                thread_id = sent_message.get('threadId')
                doc_count = len(file_paths)
                
                print(f"✅ Email sent to {recipient_email}")
                print(f"   📎 Documents attached: {doc_count}")
                print(f"   Gmail Message ID: {gmail_id}")
                print(f"   Gmail Thread ID: {thread_id}")
                
                result["success"] = True
                result["message"] = f"Email sent successfully with {doc_count} document(s)"
                result["gmail_data"] = {
                    "id": gmail_id,
                    "threadId": thread_id
                }
            else:
                result["message"] = "Failed to send email - no response from Gmail API"
                
            return result
            
        except (timeout, TimeoutError):
            result["message"] = "Connection timed out."
            return result
        except Exception as e:
            print("Gmail API error:", e)
            result["message"] = f"Email sending error: {e}"
            return result

    except Exception as e:
        print("Error sending Gmail:", e)
        result["message"] = f"Error preparing email: {e}"
        return result
# =============================================================================
# BULK EMAIL WRAPPER (adds Gmail tracking)
# =============================================================================

def send_application_email_with_gmail(recipient_email, company_name, user):
    """
    Wrapper that ensures consistent return format with Gmail tracking data
    """
    result = send_application_email(recipient_email, company_name, user)
    
    # Result is now always a dict with the correct structure
    if isinstance(result, dict):
        return result
    
    # Fallback for legacy tuple format (shouldn't happen with new code)
    if isinstance(result, tuple):
        success, message = result
        return {
            "success": success, 
            "message": message, 
            "gmail_data": {}
        }

    return {"success": False, "message": "Unknown error.", "gmail_data": {}}


# =============================================================================
# BULK EMAIL ROUTE — APPLY VIA EMAIL LIST
# =============================================================================
@app.route("/apply_bulk_email", methods=["POST"])
@login_required
@check_application_limit
def apply_bulk_email():
    try:
        ids = request.form.getlist("selected_emails")
        reapply_ids = request.form.getlist("reapply_emails")
        
        print(f"DEBUG: Received IDs: {ids}")
        print(f"DEBUG: Re-apply IDs: {reapply_ids}")

        if not ids and not reapply_ids:
            flash("Please select at least one company.", "warning")
            return redirect(url_for("learnerships"))

        # ✅ CHECK DOCUMENTS BEFORE STARTING
        docs = Document.query.filter_by(user_id=current_user.id, is_active=True).all()
        valid_docs = [d for d in docs if d.file_path and isinstance(d.file_path, str) and os.path.exists(d.file_path)]
        
        if not valid_docs:
            flash(
                "⚠️ You must upload at least one document (CV/Resume) before applying.",
                "warning"
            )
            return redirect(url_for("user_documents"))
        
        print(f"📎 User has {len(valid_docs)} valid document(s) to attach")

        # Premium limit check
        total_applications = len(ids) + len(reapply_ids)
        
        if not current_user.is_premium_active():
            remaining = current_user.get_remaining_applications()
            if remaining == 0:
                flash("Daily application limit reached. Upgrade to premium!", "warning")
                return redirect(url_for('upgrade_to_premium'))
            elif total_applications > remaining:
                flash(f"You can only apply to {remaining} more companies today.", "warning")
                return redirect(url_for('upgrade_to_premium'))

        # Get email entries
        email_entries = LearnershipEmail.query.filter(
            LearnershipEmail.id.in_(ids + reapply_ids),
            LearnershipEmail.is_active == True,
        ).all()
        
        print(f"DEBUG: Found {len(email_entries)} email entries")

        if not email_entries:
            flash("No valid email addresses selected.", "error")
            return redirect(url_for("learnerships"))

        successful = []
        failed = []
        timeout_list = []
        reapplied = []
        gmail_tracked = 0
        applications_sent = 0

        for entry in email_entries:
            print(f"\n{'='*50}")
            print(f"📧 Processing: {entry.company_name} - {entry.email_address}")
            
            # Check if user already applied to this company
            existing = Application.query.filter_by(
                user_id=current_user.id, 
                company_email=entry.email_address
            ).first()

            # ✅ HANDLE RE-APPLICATIONS - COMPLETE FIX WITH PROPER CASCADE ORDER
            if existing:
                if str(entry.id) not in reapply_ids:
                    print(f"   ⚠️ Already applied to {entry.company_name} (skipped)")
                    continue
                else:
                    print(f"   🔄 Re-applying to {entry.company_name}")
                    
                    # ✅ DELETE ALL RELATED RECORDS IN CORRECT CASCADE ORDER
                    try:
                        application_id = existing.id
                        print(f"   🔍 Deleting all records for application_id: {application_id}")
                        
                        # 1. Delete ConversationMessage records first (deepest level)
                        conversation_messages_deleted = 0
                        conversations = Conversation.query.filter_by(application_id=application_id).all()
                        for conversation in conversations:
                            messages = ConversationMessage.query.filter_by(conversation_id=conversation.id).all()
                            for message in messages:
                                db.session.delete(message)
                                conversation_messages_deleted += 1
                        print(f"   🗑️ Deleted {conversation_messages_deleted} conversation messages")
                        
                        # 2. Delete Conversation records
                        conversations_deleted = len(conversations)
                        for conversation in conversations:
                            db.session.delete(conversation)
                        print(f"   🗑️ Deleted {conversations_deleted} conversations")
                        
                        # 3. Delete CalendarEvent records
                        calendar_events = CalendarEvent.query.filter_by(application_id=application_id).all()
                        for event in calendar_events:
                            db.session.delete(event)
                        print(f"   🗑️ Deleted {len(calendar_events)} calendar events")
                        
                        # 4. Delete ApplicationMessage records
                        app_messages = ApplicationMessage.query.filter_by(application_id=application_id).all()
                        for msg in app_messages:
                            db.session.delete(msg)
                        print(f"   🗑️ Deleted {len(app_messages)} application messages")
                        
                        # 5. Delete any other related records that reference application_id
                        # Add any other models that have foreign keys to Application here if needed
                        
                        # 6. Finally delete the Application itself
                        db.session.delete(existing)
                        
                        # Commit all deletions
                        db.session.commit()
                        print(f"   ✅ Successfully deleted application {application_id} and all related data")
                        
                    except Exception as delete_error:
                        print(f"   ❌ Error deleting existing application: {delete_error}")
                        import traceback
                        traceback.print_exc()
                        db.session.rollback()
                        failed.append(entry.company_name)
                        continue
                    
            try:
                # Send email with documents
                result = send_application_email_with_gmail(
                    entry.email_address, entry.company_name, current_user
                )
                
                print(f"DEBUG: Email result: {result}")

                success = result.get("success", False)
                message = result.get("message", "")
                gmail_data = result.get("gmail_data", {})
                
                if gmail_data:
                    print(f"   📬 Gmail ID: {gmail_data.get('id')}")
                    print(f"   🧵 Thread ID: {gmail_data.get('threadId')}")

                # Create NEW Application record
                application = Application(
                    user_id=current_user.id,
                    company_name=entry.company_name,
                    company_email=entry.email_address,
                    learnership_name="Email Application",
                    status="submitted" if success else "pending",
                )

                if success:
                    application.email_status = "sent"
                    application.sent_at = datetime.utcnow()
                    application.gmail_message_id = gmail_data.get("id")
                    application.gmail_thread_id = gmail_data.get("threadId")
                    application.has_response = False
                    application.documents_attached = len(valid_docs)
                    
                    current_user.use_application()
                    applications_sent += 1
                    
                    print(f"   ✅ Creating new Application")
                else:
                    application.email_status = "failed"
                    print(f"   ❌ Email failed: {message}")

                db.session.add(application)
                db.session.commit()  # ✅ Commit immediately after adding new application

                if success:
                    successful.append(entry.company_name)
                    if str(entry.id) in reapply_ids:
                        reapplied.append(entry.company_name)
                    if gmail_data.get("id"):
                        gmail_tracked += 1
                else:
                    if "timeout" in message.lower():
                        timeout_list.append(entry.company_name)
                    else:
                        failed.append(entry.company_name)

                print(f"   💾 Saved to database")

            except Exception as e:
                print(f"❌ Error for {entry.company_name}: {e}")
                import traceback
                traceback.print_exc()
                db.session.rollback()
                failed.append(entry.company_name)

        # Summary
        print(f"\n{'='*50}")
        print(f"📊 BULK SEND SUMMARY:")
        print(f"   ✅ New applications: {len(successful) - len(reapplied)}")
        print(f"   🔄 Re-applications: {len(reapplied)}")
        print(f"   🎯 Gmail tracked: {gmail_tracked}")
        print(f"   📎 Documents per application: {len(valid_docs)}")
        print(f"   ❌ Failed: {len(failed)}")
        print(f"{'='*50}\n")

        # Flash messages
        if successful:
            new_count = len(successful) - len(reapplied)
            
            msg = f"✅ Successfully sent {len(successful)} application(s) with {len(valid_docs)} document(s)!"
            
            if new_count > 0:
                msg += f"\n   📝 New: {new_count}"
            if reapplied:
                msg += f"\n   🔄 Re-applied: {len(reapplied)}"
            
            if gmail_tracked:
                msg += f"\n🎯 {gmail_tracked} application(s) tracked for responses"
            
            flash(msg, "success")

        if timeout_list:
            flash(f"⏱️ Network timeout for: {', '.join(timeout_list)}", "warning")

        if failed:
            flash(f"❌ Failed: {', '.join(failed)}", "error")

        return redirect(url_for("my_applications"))

    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        flash("An error occurred.", "error")
        return redirect(url_for("learnerships"))


# ✅ NEW ROUTE: Check for existing applications and ask for confirmation
@app.route("/check_existing_applications", methods=["POST"])
@login_required
def check_existing_applications():
    """Check which companies user already applied to and ask for confirmation"""
    ids = request.json.get("selected_ids", [])
    
    if not ids:
        return jsonify({"existing": [], "new": ids})
    
    # Get all selected companies
    email_entries = LearnershipEmail.query.filter(
        LearnershipEmail.id.in_(ids)
    ).all()
    
    existing_companies = []
    new_companies = []
    
    for entry in email_entries:
        existing = Application.query.filter_by(
            user_id=current_user.id,
            company_email=entry.email_address
        ).first()
        
        if existing:
            existing_companies.append({
                "id": entry.id,
                "name": entry.company_name,
                "email": entry.email_address,
                "applied_at": existing.created_at.strftime("%Y-%m-%d %H:%M") if existing.created_at else "Unknown"
            })
        else:
            new_companies.append(entry.id)
    
    return jsonify({
        "existing": existing_companies,
        "new": new_companies,
        "total": len(email_entries)
    })


# --------------------------------------------------------------------
# USER PREMIUM FEATURES
# --------------------------------------------------------------------

# Add these imports at the top of your app.py
from decorators import admin_required, premium_required, check_application_limit, track_application_usage
from models import PremiumTransaction
from datetime import datetime, timedelta

# Add these routes to your existing app.py

# Premium Management Routes
@app.route('/admin/premium-management')
@login_required
@admin_required
def premium_management():
    """Premium management dashboard"""
    users = User.query.all()
    premium_users = User.query.filter_by(is_premium=True).all()
    transactions = PremiumTransaction.query.order_by(PremiumTransaction.created_at.desc()).limit(50).all()
    
    # Statistics
    total_premium = len(premium_users)
    expired_premium = sum(1 for user in premium_users if user.premium_expires and user.premium_expires <= datetime.now())
    active_premium = total_premium - expired_premium
    
    stats = {
        'total_premium': total_premium,
        'active_premium': active_premium,
        'expired_premium': expired_premium,
        'total_users': User.query.count()
    }
    
    return render_template('admin_premium.html', 
                         users=users, 
                         moment=datetime,
                         transactions=transactions, 
                         stats=stats)


@app.route('/admin/bulk-premium', methods=['POST'])
@login_required
@admin_required
def bulk_premium():
    """Handle bulk premium operations - AJAX version"""
    try:
        user_ids_str = request.form.get('user_ids', '')
        duration_days = int(request.form.get('duration_days', 30))
        notes = request.form.get('notes', '')
        
        # Parse user IDs
        user_ids = []
        for uid in user_ids_str.split(','):
            uid = uid.strip()
            if uid.isdigit():
                user_ids.append(int(uid))
        
        if not user_ids:
            return jsonify({
                'success': False,
                'message': 'No valid user IDs provided.'
            }), 400
        
        users = User.query.filter(User.id.in_(user_ids)).all()
        success_count = 0
        
        for user in users:
            user.is_premium = True
            user.premium_expires = datetime.utcnow() + timedelta(days=duration_days)
            user.premium_activated_by = current_user.id
            user.premium_activated_at = datetime.utcnow()
            
            transaction = PremiumTransaction(
                user_id=user.id,
                transaction_type='admin_bulk_grant',
                duration_days=duration_days,
                activated_by_admin=current_user.id,
                notes=f"Bulk grant: {notes}"
            )
            db.session.add(transaction)
            success_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Premium granted to {success_count} users for {duration_days} days!'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error in bulk premium grant: {str(e)}'
        }), 500

@app.route('/admin/premium-stats')
@login_required
@admin_required
def premium_stats():
    """Get updated premium statistics"""
    try:
        users = User.query.all()
        total_users = len(users)
        premium_users = [u for u in users if u.is_premium]
        total_premium = len(premium_users)
        
        now = datetime.utcnow()
        active_premium = sum(1 for u in premium_users if not u.premium_expires or u.premium_expires > now)
        expired_premium = total_premium - active_premium
        
        return jsonify({
            'success': True,
            'stats': {
                'total_users': total_users,
                'total_premium': total_premium,
                'active_premium': active_premium,
                'expired_premium': expired_premium
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/upgrade-to-premium')
@login_required
def upgrade_to_premium():
    """Premium upgrade page"""
    remaining = current_user.get_remaining_applications()
    premium_status = current_user.get_premium_status()
    
    return render_template('upgrade_premium.html', 
                         remaining_applications=remaining,
                         premium_status=premium_status)

@app.route('/api/user-stats')
@login_required
def user_stats():
    """API endpoint for user application statistics"""
    return jsonify({
        'is_premium': current_user.is_premium,
        'is_premium_active': current_user.is_premium_active(),
        'remaining_applications': current_user.get_remaining_applications(),
        'daily_used': current_user.daily_applications_used,
        'premium_expires': current_user.premium_expires.isoformat() if current_user.premium_expires else None,
        'premium_status': current_user.get_premium_status()
    })

@app.route('/api/check-application-limit')
@login_required
def check_application_limit_api():
    """API endpoint to check if user can apply"""
    can_apply = current_user.can_apply_today()
    remaining = current_user.get_remaining_applications()
    
    return jsonify({
        'can_apply': can_apply,
        'remaining': remaining,
        'is_premium': current_user.is_premium_active(),
        'message': 'You can apply' if can_apply else 'Daily limit reached'
    })

# Premium feature example routes
@app.route('/premium/analytics')
@login_required
@premium_required
def premium_analytics():
    """Premium analytics dashboard"""
    # Your premium analytics logic
    return render_template('premium_analytics.html')

@app.route('/premium/advanced-search')
@login_required
@premium_required
def premium_search():
    """Premium advanced search"""
    # Your premium search logic
    return render_template('premium_search.html')
# --------------------------------------------------------------------
# USER ANALYTICS DASHBOARD (REAL DATA)
# --------------------------------------------------------------------
from sqlalchemy import func
from datetime import datetime, timedelta
import os

def get_week_format(date_column):
    """Database-agnostic week formatting"""
    database_url = os.environ.get("DATABASE_URL", "")
    
    if database_url.startswith(("postgresql://", "postgres://")):
        # PostgreSQL version - returns YYYY-WW format
        return func.to_char(date_column, 'YYYY-WW').label("week")
    else:
        # SQLite version
        return func.strftime("%Y-%W", date_column).label("week")

@app.route("/user/applications/analytics", endpoint="application_analytics")
@login_required
def analytics_dashboard_user_live():
    """Render analytics page with user's real application stats"""
    user_id = current_user.id

    # --- STATUS SUMMARY ---------------------------------------------
    status_counts = dict(
        db.session.query(Application.email_status, func.count(Application.id))
        .filter(Application.user_id == user_id)
        .group_by(Application.email_status)
        .all()
    )

    all_statuses = ["sent", "delivered", "read", "responded", "pending", "failed"]
    status_summary = []
    for s in all_statuses:
        status_summary.append({
            "label": s.capitalize(),
            "value": status_counts.get(s, 0),
            "color": {
                "sent": "#3b82f6",
                "delivered": "#10b981",
                "read": "#8b5cf6",
                "responded": "#22c55e",
                "pending": "#f97316",
                "failed": "#ef4444"
            }.get(s, "#94a3b8")
        })

    # ✅ CURRENT WEEK RESPONSES (Monday to Sunday) -----------
    now = datetime.utcnow()
    days_since_monday = now.weekday()
    monday = now - timedelta(days=days_since_monday)
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    
    current_week_responses = []
    
    for i in range(7):  # Monday (0) to Sunday (6)
        day_start = monday + timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        
        # Count responses received on this day
        daily_responses = (
            db.session.query(func.count(Application.id))
            .filter(
                Application.user_id == user_id,
                Application.response_received_at.isnot(None),
                Application.response_received_at >= day_start,
                Application.response_received_at < day_end
            )
            .scalar() or 0
        )
        current_week_responses.append(daily_responses)

    # --- WEEKLY RESPONSE TREND (FIXED) -------------------------------------
    ten_weeks_ago = datetime.utcnow() - timedelta(weeks=10)
    
    try:
        weekly_responses = (
            db.session.query(
                get_week_format(Application.response_received_at),  # 🔧 FIXED: Database-agnostic
                func.count(Application.id)
            )
            .filter(
                Application.user_id == user_id,
                Application.response_received_at.isnot(None),
                Application.response_received_at >= ten_weeks_ago
            )
            .group_by(get_week_format(Application.response_received_at))  # 🔧 FIXED: Database-agnostic
            .order_by(get_week_format(Application.response_received_at))  # 🔧 FIXED: Database-agnostic
            .all()
        )
        response_trend = [r[1] for r in weekly_responses]
    except Exception as e:
        print(f"❌ Weekly trend error: {e}")
        response_trend = []  # Fallback to empty trend

    # --- RECENT APPLICATIONS ---------------------------------------
    recent_apps = (
        Application.query.filter_by(user_id=user_id)
        .order_by(Application.sent_at.desc().nullslast())
        .limit(5)
        .all()
    )

    recent_list = []
    for app_obj in recent_apps:
        recent_list.append({
            "company": app_obj.company_name or "Unknown",
            "date": app_obj.sent_at.strftime("%d %b %Y %H:%M") if app_obj.sent_at else "Pending",
            "status": app_obj.email_status or "pending"
        })

    # ✅ Debug output
    print(f"📊 Current Week Responses (Mon-Sun): {current_week_responses}")
    print(f"📅 Week starting: {monday.strftime('%Y-%m-%d')}")
    print(f"📈 Status Summary: {[s['label'] + ': ' + str(s['value']) for s in status_summary]}")
    print(f"📈 Response Trend: {response_trend}")

    # --- RENDER TEMPLATE -------------------------------------------
    return render_template(
        "analytics_dashboard.html",
        status_summary=status_summary,
        response_trend=response_trend,
        current_week_responses=current_week_responses,
        recent_list=recent_list,
        current_year=datetime.now().year
    )

# ✅ ADDED: API endpoint for real-time updates
@app.route('/api/current-week-responses')
@login_required
def get_current_week_responses():
    """API endpoint for real-time current week responses data"""
    try:
        user_id = current_user.id
        
        # Get Monday of current week
        now = datetime.utcnow()
        days_since_monday = now.weekday()
        monday = now - timedelta(days=days_since_monday)
        monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        
        current_week_responses = []
        
        for i in range(7):
            day_start = monday + timedelta(days=i)
            day_end = day_start + timedelta(days=1)
            
            daily_responses = (
                db.session.query(func.count(Application.id))
                .filter(
                    Application.user_id == user_id,
                    Application.response_received_at.isnot(None),
                    Application.response_received_at >= day_start,
                    Application.response_received_at < day_end
                )
                .scalar() or 0
            )
            current_week_responses.append(daily_responses)
        
        return jsonify({
            'success': True,
            'responses': current_week_responses,
            'week_start': monday.strftime('%Y-%m-%d'),
            'total_responses': sum(current_week_responses)
        })
        
    except Exception as e:
        print(f"❌ API error: {e}")
        return jsonify({ 
            'success': False, 
            'error': str(e),
            'responses': [0, 0, 0, 0, 0, 0, 0]
        })
# =============================================================================
# ADMIN DASHBOARD
# =============================================================================

@app.route("/admin/dashboard")
@login_required
@admin_required
def admin_dashboard():
    """Admin dashboard with system overview and management tools."""
    try:
        print("=== ADMIN DASHBOARD ===")

        # Fetch all system data
        users = User.query.all()
        applications = Application.query.all()
        learnerships = LearnershipEmail.query.filter_by(is_active=True).all()

        print(f"Users: {len(users)}")
        print(f"Learnership emails: {len(learnerships)}")
        print(f"Applications: {len(applications)}")

        # Stats summary
        stats = {
            "total_users": len(users),
            "active_users": sum(1 for u in users if u.is_active),
            "total_learnerships": len(learnerships),
            "total_applications": len(applications),
        }

        # Recent items
        recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
        recent_learnerships = (
            LearnershipEmail.query.filter_by(is_active=True)
            .order_by(LearnershipEmail.created_at.desc())
            .limit(5)
            .all()
        )
        recent_applications = (
            Application.query.order_by(Application.submitted_at.desc()).limit(5).all()
        )
        premium_users = User.query.filter_by(is_premium=True).all()

        premium_stats = {
            'total_premium': len(premium_users),
            'active_premium': sum(1 for user in premium_users 
                                if not user.premium_expires or user.premium_expires > datetime.now())
        }

        return render_template(
            "admin_dashboard.html",
            users=users,
            learnerships=learnerships,
            applications=applications,
            stats=stats,
            recent_users=recent_users,
            recent_learnerships=recent_learnerships,
            recent_applications=recent_applications,
            current_user=current_user,
            premium_stats=premium_stats,
            premium_count=premium_stats['active_premium']
        )

    except Exception as e:
        print("Error loading admin dashboard:", e)
        import traceback
        traceback.print_exc()

        # fallback
        return render_template(
            "admin_dashboard.html",
            users=[],
            learnerships=[],
            applications=[],
            stats={
                "total_users": 0,
                "active_users": 0,
                "total_learnerships": 0,
                "total_applications": 0,
            },
            recent_users=[],
            recent_learnerships=[],
            recent_applications=[],
            current_user=current_user,
            premium_stats=premium_stats,
            premium_count=premium_stats['active_premium']
        )


# =============================================================================
# ADMIN USER MANAGEMENT
# =============================================================================
@app.route('/admin/toggle-premium/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_premium(user_id):
    """Toggle premium status via AJAX"""
    try:
        data = request.get_json()
        user = User.query.get_or_404(user_id)
        action = data.get('action')
        duration_days = data.get('duration_days', 30)
        
        # DEBUG: Log current state
        print(f"DEBUG: Before toggle - User {user_id}: is_premium={user.is_premium}, expires={user.premium_expires}")
        
        if action == 'grant':
            user.is_premium = True
            user.premium_expires = datetime.utcnow() + timedelta(days=duration_days)
            user.premium_activated_by = current_user.id
            user.premium_activated_at = datetime.utcnow()
            message = f'Premium granted to {user.username or user.email}'
        elif action == 'revoke':
            user.is_premium = False
            user.premium_expires = datetime.utcnow() - timedelta(days=1)  # Set to past date
            message = f'Premium revoked from {user.username or user.email}'
        else:
            return jsonify({'success': False, 'message': 'Invalid action'}), 400
        
        # DEBUG: Log new state before commit
        print(f"DEBUG: After change - User {user_id}: is_premium={user.is_premium}, expires={user.premium_expires}")
        
        # Log transaction
        transaction = PremiumTransaction(
            user_id=user_id,
            transaction_type=f'admin_{action}',
            duration_days=duration_days if action == 'grant' else 0,
            activated_by_admin=current_user.id,
            notes=data.get('notes', f'{action.title()} via toggle button')
        )
        db.session.add(transaction)
        
        # Commit changes
        db.session.commit()
        
        # DEBUG: Verify changes after commit
        user_check = User.query.get(user_id)
        print(f"DEBUG: After commit - User {user_id}: is_premium={user_check.is_premium}, expires={user_check.premium_expires}")
        
        return jsonify({
            'success': True,
            'message': message,
            'is_premium_active': user.is_premium and (not user.premium_expires or user.premium_expires > datetime.utcnow())
        })
        
    except Exception as e:
        print(f"DEBUG: Error in toggle_premium: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
    
@app.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_user_status(user_id):
    """Toggle user active/inactive status."""
    user = User.query.get_or_404(user_id)

    # Prevent deactivating other admins
    if user.role == "admin" and user.id != current_user.id:
        flash("You cannot modify another admin's status.", "error")
        return redirect(url_for("admin_dashboard"))

    user.is_active = not user.is_active

    try:
        db.session.commit()
        status = "activated" if user.is_active else "deactivated"
        flash(f"User {user.username or user.email} has been {status}.", "success")
    except Exception as e:
        print("Toggle error:", e)
        db.session.rollback()
        flash("Error updating user status.", "error")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    """Delete a user and all their associated data."""
    user = User.query.get_or_404(user_id)

    if user.role == "admin":
        flash("Cannot delete admin users.", "error")
        return redirect(url_for("admin_dashboard"))

    try:
        # Delete documents physically
        documents = Document.query.filter_by(user_id=user_id).all()
        for doc in documents:
            if doc.file_path and os.path.exists(doc.file_path):
                try:
                    os.remove(doc.file_path)
                except Exception as e:
                    print("Error deleting file:", doc.file_path, e)

        # Delete DB records
        Application.query.filter_by(user_id=user_id).delete()
        Document.query.filter_by(user_id=user_id).delete()

        db.session.delete(user)
        db.session.commit()

        flash(f"User {user.username or user.email} deleted successfully.", "success")

    except Exception as e:
        print("Delete user error:", e)
        db.session.rollback()
        flash("Error deleting user.", "error")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/users/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_user():
    """Add a new user to the system."""
    if request.method == "POST":

        email = request.form.get("email")
        username = request.form.get("username")
        password = request.form.get("password")
        confirm = request.form.get("confirm_password")
        name = request.form.get("full_name")
        phone = request.form.get("phone")
        role = request.form.get("role")
        is_active = "is_active" in request.form

        # Validation
        if User.query.filter_by(email=email).first():
            flash("Email already exists.", "error")
            return render_template("add_user.html")

        if username and User.query.filter_by(username=username).first():
            flash("Username already exists.", "error")
            return render_template("add_user.html")

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("add_user.html")

        new_user = User(
            email=email,
            username=username,
            full_name=name,
            phone=phone,
            role=role,
            is_active=is_active,
            auth_method="local",
            created_at=datetime.utcnow(),
        )

        new_user.set_password(password)

        try:
            db.session.add(new_user)
            db.session.commit()
            flash("User created successfully!", "success")
            return redirect(url_for("admin_dashboard"))

        except Exception as e:
            print("Add user error:", e)
            db.session.rollback()
            flash("Error creating user.", "error")

    return render_template("add_user.html")


@app.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_user(user_id):
    """Edit an existing user's details."""
    user = User.query.get_or_404(user_id)

    if request.method == "POST":

        user.email_address = request.form.get("email")
        user.username = request.form.get("username")
        user.full_name = request.form.get("full_name")
        user.phone = request.form.get("phone")
        user.role = request.form.get("role")
        user.is_active = "is_active" in request.form

        # Optional password update
        new_password = request.form.get("new_password")
        if new_password:
            user.set_password(new_password)

        try:
            db.session.commit()
            flash("User updated successfully!", "success")
            return redirect(url_for("admin_dashboard"))

        except Exception as e:
            print("Edit user error:", e)
            db.session.rollback()
            flash("Error updating user.", "error")

    return render_template("edit_user.html", user=user)


@app.route("/admin/users/<int:user_id>/view")
@login_required
@admin_required
def view_user(user_id):
    """View detailed user information."""
    user = User.query.get_or_404(user_id)

    applications = Application.query.filter_by(user_id=user_id).all()
    documents = Document.query.filter_by(user_id=user_id).all()

    # Check if documents exist physically
    for doc in documents:
        if doc.file_path:
            if not os.path.isabs(doc.file_path):
                full_path = os.path.join(app.config["UPLOAD_FOLDER"], doc.file_path)
            else:
                full_path = doc.file_path

            doc.file_exists = os.path.exists(full_path)
        else:
            doc.file_exists = False

    return render_template(
        "view_user.html",
        user=user,
        applications=applications,
        documents=documents
    )


@app.route("/admin/documents/<int:document_id>/download")
@login_required
@admin_required
def download_document(document_id):
    """Download a user's uploaded document."""
    print(f"=== DOWNLOAD DEBUG - Document ID: {document_id} ===")
    
    document = Document.query.get_or_404(document_id)
    print(f"Document found: {document.filename}")
    print(f"File path from DB: {document.file_path}")

    if not document.file_path:
        flash("Document file path is missing.", "error")
        return redirect(request.referrer or url_for("admin_dashboard"))

    # Try to find file locally first
    upload_folder = app.config.get("UPLOAD_FOLDER", "uploads")
    
    # Handle path conversion for local development
    if os.path.isabs(document.file_path):
        if 'uploads/' in document.file_path:
            relative_part = document.file_path.split('uploads/', 1)[1]
            full_path = os.path.join(upload_folder, relative_part)
        else:
            filename = os.path.basename(document.file_path)
            full_path = os.path.join(upload_folder, 'documents', filename)
    else:
        full_path = os.path.join(upload_folder, document.file_path)

    print(f"Checking local path: {full_path}")
    
    # If file exists locally, serve it
    if os.path.exists(full_path):
        print("File found locally, serving...")
        return serve_local_file(full_path, document)
    
    # If running in development and file doesn't exist locally, 
    # redirect directly to production (simpler and more reliable)
    if app.debug or app.config.get('ENV') == 'development':
        print("File not found locally, redirecting to production...")
        PRODUCTION_URL = "https://codecraftco.onrender.com"
        production_download_url = f"{PRODUCTION_URL}/admin/documents/{document_id}/download"
        print(f"Redirecting to: {production_download_url}")
        return redirect(production_download_url)
    else:
        flash("Document file not found.", "error")
        return redirect(request.referrer or url_for("admin_dashboard"))

def serve_local_file(file_path, document):
    """Serve file from local storage"""
    mime = "application/octet-stream"
    ext = ""
    if document.original_filename:
        _, ext = os.path.splitext(document.original_filename)
        ext = ext.lower()
        mime_map = {
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
        }
        mime = mime_map.get(ext, mime)

    download_name = document.original_filename or f"document-{document.id}{ext}"
    
    return send_file(
        file_path,
        mimetype=mime,
        as_attachment=True,
        download_name=download_name,
    )

# =============================================================================
# ADMIN LEARNERSHIP EMAIL STATUS TOGGLE
# =============================================================================

@app.route("/admin/toggle-learnership-status/<int:learnership_id>", methods=["POST"])
@login_required
@admin_required
def toggle_learnership_status(learnership_id):
    """Toggle active/inactive status of a learnership email entry."""
    try:
        email = LearnershipEmail.query.get_or_404(learnership_id)
        email.is_active = not email.is_active
        db.session.commit()

        status = "activated" if email.is_active else "deactivated"
        flash(f"Learnership email for {email.company_name} has been {status}.", "success")

    except Exception as e:
        print("Toggle learnership status error:", e)
        flash("Error toggling learnership email.", "error")

    return redirect(url_for("admin_dashboard"))


# =============================================================================
# ADMIN UPDATE LEARNERSHIP EMAIL (AJAX)
# =============================================================================

@app.route("/admin/update-learnership-email/<int:email_id>", methods=["POST"])
@login_required
@admin_required
def update_learnership_email(email_id):
    """Update a learnership email via AJAX."""
    try:
        email = LearnershipEmail.query.get_or_404(email_id)
        data = request.get_json()

        # Validate email
        import re
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        new_email = data.get("email", "").strip()

        if not re.match(pattern, new_email):
            return jsonify(success=False, message="Invalid email format")

        # Update fields
        email.company_name = data.get("company_name", "").strip()
        email.email_address = new_email

        db.session.commit()
        return jsonify(success=True, message="Learnership email updated successfully")

    except Exception as e:
        print("Update learnership email error:", e)
        db.session.rollback()
        return jsonify(success=False, message=str(e))


# =============================================================================
# ADMIN DELETE LEARNERSHIP ENTRY
# =============================================================================

@app.route("/admin/learnerships/<int:learnership_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_learnership(learnership_id):
    """Delete a learnership and update related applications."""
    learnership = Learnership.query.get_or_404(learnership_id)

    try:
        # Update applications that reference this learnership
        apps = Application.query.filter_by(learnership_id=learnership_id).all()

        for app_item in apps:
            app_item.learnership_name = learnership.title
            app_item.company_name = learnership.company
            app_item.learnership_id = None

        db.session.delete(learnership)
        db.session.commit()

        flash(f'Learnership "{learnership.title}" deleted.', "success")

    except Exception as e:
        print("Delete learnership error:", e)
        db.session.rollback()
        flash("Error deleting learnership.", "error")

    return redirect(url_for("admin_dashboard"))


# =============================================================================
# ADMIN ADD LEARNERSHIP
# =============================================================================

@app.route("/admin/learnerships/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_learnership():
    """Admin adds a new learnership entry."""
    if request.method == "POST":

        title = request.form.get("title")
        company = request.form.get("company")
        category = request.form.get("category")
        location = request.form.get("location")
        duration = request.form.get("duration")
        stipend = request.form.get("stipend")
        description = request.form.get("description")
        requirements = request.form.get("requirements")
        is_active = "is_active" in request.form

        # Parse date
        closing_date_raw = request.form.get("closing_date")
        try:
            closing_date = (
                datetime.strptime(closing_date_raw, "%Y-%m-%d")
                if closing_date_raw
                else None
            )
        except ValueError:
            flash("Invalid closing date format. Use YYYY-MM-DD.", "error")
            return render_template("add_learnership.html")

        new_learnership = Learnership(
            title=title,
            company=company,
            category=category,
            location=location,
            duration=duration,
            stipend=stipend,
            closing_date=closing_date,
            description=description,
            requirements=requirements,
            created_at=datetime.utcnow(),
            is_active=is_active,
        )

        try:
            db.session.add(new_learnership)
            db.session.commit()
            flash("Learnership added successfully!", "success")
            return redirect(url_for("admin_dashboard"))

        except Exception as e:
            print("Add learnership error:", e)
            db.session.rollback()
            flash("Error adding learnership.", "error")

    return render_template("add_learnership.html")


# =============================================================================
# ADMIN VIEW LEARNERSHIP DETAILS
# =============================================================================

@app.route("/admin/learnerships/<int:learnership_id>/view")
@login_required
@admin_required
def view_learnership(learnership_id):
    """View detailed learnership info."""
    learnership = Learnership.query.get_or_404(learnership_id)
    apps = Application.query.filter_by(learnership_id=learnership_id).all()

    return render_template(
        "view_learnership.html",
        learnership=learnership,
        applications=apps
    )


# =============================================================================
# ADMIN EDIT LEARNERSHIP
# =============================================================================

@app.route("/admin/learnerships/<int:learnership_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_learnership(learnership_id):
    """Edit an existing learnership entry."""
    learnership = Learnership.query.get_or_404(learnership_id)

    if request.method == "POST":
        learnership.title = request.form.get("title")
        learnership.company = request.form.get("company")
        learnership.category = request.form.get("category")
        learnership.location = request.form.get("location")
        learnership.duration = request.form.get("duration")
        learnership.stipend = request.form.get("stipend")
        learnership.description = request.form.get("description")
        learnership.requirements = request.form.get("requirements")
        learnership.is_active = "is_active" in request.form

        # Parse date
        closing_raw = request.form.get("closing_date")
        try:
            learnership.closing_date = (
                datetime.strptime(closing_raw, "%Y-%m-%d") if closing_raw else None
            )
        except ValueError:
            flash("Invalid closing date format.", "error")
            return render_template("edit_learnership.html", learnership=learnership)

        try:
            db.session.commit()
            flash("Learnership updated successfully!", "success")
            return redirect(url_for("admin_dashboard"))

        except Exception as e:
            print("Edit learnership error:", e)
            db.session.rollback()
            flash("Error updating learnership.", "error")

    return render_template("edit_learnership.html", learnership=learnership)


# =============================================================================
# ADMIN APPLICATION MANAGEMENT
# =============================================================================

@app.route("/admin/applications/<int:application_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_application(application_id):
    """Admin deletes a specific application record."""
    application = Application.query.get_or_404(application_id)

    try:
        db.session.delete(application)
        db.session.commit()
        flash("Application deleted successfully.", "success")

    except Exception as e:
        print("Delete application error:", e)
        db.session.rollback()
        flash("Error deleting application.", "error")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/applications/<int:application_id>/view")
@login_required
@admin_required
def view_application(application_id):
    """Admin views full details of a specific application."""
    application = Application.query.get_or_404(application_id)

    # Use Document model instead - get all documents for this application's user
    application_documents = Document.query.filter_by(user_id=application.user_id).all()

    # Alternative: If you want to be more specific, you can filter by document types or recent uploads
    # application_documents = Document.query.filter_by(
    #     user_id=application.user_id,
    #     is_active=True
    # ).order_by(Document.uploaded_at.desc()).all()

    return render_template(
        "view_application.html",
        application=application,
        application_documents=application_documents
    )


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def allowed_file(filename):
    """Check if uploaded file extension is allowed."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def url_for_map():
    """Debug helper: prints all registered Flask routes."""
    from flask import current_app
    return {rule.endpoint: str(rule) for rule in current_app.url_map.iter_rules()}



# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 Not Found errors."""
    return render_template("errors/404.html"), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors."""
    db.session.rollback()
    return render_template("errors/500.html"), 500


@app.errorhandler(Exception)
def handle_exception(e):
    """Catch-all for any uncaught exceptions."""
    app.logger.error(f"Unhandled Exception: {str(e)}", exc_info=True)
    return render_template("errors/500.html"), 500


# =============================================================================
# CONTEXT PROCESSORS
# =============================================================================

@app.context_processor
def inject_user():
    """Inject the current user into all templates."""
    return {"current_user": current_user}


@app.context_processor
def utility_processor():
    """Inject commonly used utility functions into templates."""

    def format_datetime(dt):
        return dt.strftime("%Y-%m-%d %H:%M") if dt else "N/A"

    def format_date(dt):
        return dt.strftime("%Y-%m-%d") if dt else "N/A"

    def format_file_size(size):
        if size is None:
            return "Unknown"
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    return dict(
        format_datetime=format_datetime,
        format_date=format_date,
        format_file_size=format_file_size
    )


# =============================================================================
# TEMPLATE FILTERS
# =============================================================================

@app.template_filter("datetime")
def datetime_filter(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "N/A"


@app.template_filter("date")
def date_filter(dt):
    return dt.strftime("%Y-%m-%d") if dt else "N/A"


@app.template_filter("filesize")
def filesize_filter(size):
    if size is None:
        return "Unknown"
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


# =============================================================================
# BEFORE REQUEST — TRACK LAST ACTIVITY
# =============================================================================

@app.before_request
def before_request():
    """Update the user's last activity timestamp on every request."""
    if current_user.is_authenticated:
        current_user.last_activity = datetime.utcnow()
        try:
            db.session.commit()
        except Exception as e:
            print("Error updating last activity:", e)
            db.session.rollback()


# =============================================================================
# DATABASE INITIALIZATION FUNCTIONS
# =============================================================================

from db_data_update_prod.learnership_emails import learnership_email_data

def init_learnership_emails():
    """Initialize the database with unique learnership email entries."""
    with app.app_context():
        # Get existing emails (case-insensitive)
        existing_emails = {
            e.email.lower() for e in LearnershipEmail.query.all()
        }
        
        added = 0
        skipped = 0
        
        for entry in learnership_email_data:
            email_lower = entry["email"].lower()
            
            if email_lower in existing_emails:
                skipped += 1
                continue  # Skip duplicates
            
            # Add new entry
            email_entry = LearnershipEmail(
                company_name=entry["company_name"],
                email=entry["email"],
                is_active=True
            )
            db.session.add(email_entry)
            existing_emails.add(email_lower)  # Track it
            added += 1
        
        try:
            db.session.commit()
            if added > 0:
                print(f"✅ Added {added} new learnership emails. Skipped {skipped} duplicates.")
            else:
                print(f"No new emails to add. {skipped} already exist.")
        except Exception as e:
            print("Error adding learnership emails:", e)
            db.session.rollback()

def safe_db_init():
    """Safely initialize database tables and default admin."""
    try:
        with app.app_context():
            db.create_all()

            # Default admin creation
            admin = User.query.filter_by(username="admin").first()
            if not admin:
                admin = User(
                    email="admin@codecraftco.com",
                    username="admin",
                    full_name="System Administrator",
                    role="admin",
                    auth_method="credentials",
                    is_active=True,
                )
                admin.set_password("admin123")
                db.session.add(admin)
                db.session.commit()
                print("Default admin created.")


            # Initialize learnership emails
            init_learnership_emails()

    except Exception as e:
        print("Database initialization error:", e)


# =============================================================================
# PRIVACY POLICY & TERMS OF SERVICE
# =============================================================================

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html')


@app.route('/terms-of-service')
def terms_of_service():
    return render_template('terms_of_service.html')


@app.route('/help-center')
def help_center():
    return render_template('help_center.html')


@app.route('/contact-us')
def contact_us():
    return render_template('contact_us.html')


@app.route('/submit-contact', methods=['POST'])
def submit_contact():
    # Handle form submission
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    subject = request.form.get('subject')
    message = request.form.get('message')

    # Process the contact form (save to database, send email, etc.)
    print(f"📧 Contact Form: {first_name} {last_name} - {email} - {subject}")

    return jsonify({'status': 'success'}), 200

# =============================================================================
# CUSTOM TIME FILTERS (RESTORED)
# =============================================================================

@app.template_filter('days_ago')
def days_ago_filter(date):
    """Return how many days ago a date occurred."""
    if not date:
        return "Never"
    
    days = (datetime.utcnow() - date).days
    
    if days == 0:
        return "Today"
    if days == 1:
        return "1 day ago"
    
    return f"{days} days ago"


@app.template_filter('time_ago')
def time_ago_filter(date):
    """Human readable time difference."""
    if not date:
        return "Never"
    
    diff = datetime.utcnow() - date

    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    if diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    if diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    
    return "Just now"

# =============================================================================
# APPLICATION STARTUP
# =============================================================================

# Initialize database when app starts (local dev or Render)
if __name__ == "__main__" or os.environ.get("RENDER"):
    safe_db_init()


# =============================================================================
# MAIN APPLICATION RUNNER
# =============================================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"

    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug
    )