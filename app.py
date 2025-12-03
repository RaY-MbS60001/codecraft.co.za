"""
Flask Application for Learnership Management System
A comprehensive platform for managing learnership applications with OAuth authentication,
document management, and bulk email functionality.
"""

# Standard library imports
import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta

# Flask and related imports
from flask import (
    Flask, render_template, redirect, url_for, flash, request, 
    jsonify, session, send_file
)
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from flask_wtf import FlaskForm
from werkzeug.utils import secure_filename
from wtforms import TextAreaField, SubmitField, SelectMultipleField, widgets
from wtforms.validators import Optional

# Third-party imports
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv

from dotenv import load_dotenv
import os

load_dotenv()  # <-- load .env variables into os.environ

DATABASE_URL = os.getenv('DATABASE_URL')
print(f"DEBUG: DATABASE_URL is '{DATABASE_URL}'")  # <-- Add this line to confirm loading


# Local imports
from tasks import launch_bulk_send
from models import (
    db, User, Learnership, Application, Document, ApplicationDocument, 
    GoogleToken, LearnshipEmail, EmailApplication
)
from config import Config
from forms import (
    AdminLoginForm, EditProfileForm, ChangePasswordForm, ApplicationForm, 
    DocumentUploadForm, LearnershipSearchForm
)
from decorators import admin_required
from security_middleware import add_security_headers


# =============================================================================
# FLASK APP INITIALIZATION (MUST COME FIRST!)
# =============================================================================

app = Flask(__name__)

# Determine base directory and setup paths
BASE_DIR = Path(__file__).resolve().parent
instance_path = BASE_DIR / 'instance'
instance_path.mkdir(exist_ok=True, parents=True)

# =============================================================================
# APPLICATION CONFIGURATION
# =============================================================================

import os
from datetime import timedelta
from urllib.parse import quote_plus

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    # In development, you might want less strict security
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent
instance_path = BASE_DIR / 'instance'
instance_path.mkdir(exist_ok=True, parents=True)

import socket

import os
import socket
from pathlib import Path

# Define instance_path globally or pass it as an argument
instance_path = Path(__file__).parent / 'instance'

def get_database_url_and_options():
    # Force SQLite in development environment
    if os.environ.get('FLASK_ENV') == 'development':
        print("✓ Development mode: Using SQLite database")
        db_url = f"sqlite:///{instance_path / 'codecraft.db'}"
        return db_url, {}
    
    # Production logic (your existing PostgreSQL code)
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        raise ValueError("DATABASE_URL must be set in production environment")
    
    # Handle PostgreSQL URLs for production
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    # PostgreSQL engine options
    engine_options = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'connect_args': {
            'sslmode': 'require',
            'connect_timeout': 10,
        }
    }
    
    return database_url, engine_options

# =============================================================================
# GMAIL TRACKING STATUS ROUTES
# =============================================================================



# =============================================================================
# LOAD CONFIGURATION
# =============================================================================

# Load configuration based on environment
if os.environ.get('FLASK_ENV') == 'production':
    app.config.from_object(ProductionConfig)
else:
    app.config.from_object(DevelopmentConfig)

# Database configuration (ONLY SET ONCE)
# Set SQLAlchemy URL and engine options correctly
db_url, engine_options = get_database_url_and_options()
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options
#db = SQLAlchemy(app)

# File upload configuration
UPLOAD_FOLDER = BASE_DIR / 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'}

app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directories exist
UPLOAD_FOLDER.mkdir(exist_ok=True)
(UPLOAD_FOLDER / 'documents').mkdir(exist_ok=True)

# =============================================================================
# INITIALIZE EXTENSIONS
# =============================================================================

# Apply security middleware
add_security_headers(app)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# OAuth configuration
oauth = None
google = None

# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

with app.app_context():
    try:
        db.create_all()
        db.session.commit()
        print("✓ Database initialized successfully with Render PostgreSQL")
    except Exception as e:
        print("✗ Database initialization error:", e)
        print("⚠️ Check your DATABASE_URL in the .env file or connection settings.")
        raise SystemExit(e)

# =============================================================================
# CUSTOM FORM FIELDS
# =============================================================================

class MultiCheckBoxField(SelectMultipleField):
    """Custom field for multiple checkbox selections"""
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


# =============================================================================
# OAUTH SETUP
# =============================================================================

def setup_oauth():
    """Setup Google OAuth configuration"""
    global oauth, google
    
    try:
        if app.config.get('GOOGLE_CLIENT_ID') and app.config.get('GOOGLE_CLIENT_SECRET'):
            oauth = OAuth(app)
            google = oauth.register(
                name='google',
                client_id=app.config['GOOGLE_CLIENT_ID'],
                client_secret=app.config['GOOGLE_CLIENT_SECRET'],
                server_metadata_url=app.config['GOOGLE_DISCOVERY_URL'],
                client_kwargs={
                    'scope': 'openid email profile https://www.googleapis.com/auth/gmail.send',
                    'access_type': 'offline',
                    'prompt': 'consent'
                }
            )
            print("Google OAuth configured successfully")
        else:
            print("Warning: Google OAuth credentials not found")
    except Exception as e:
        print(f"Error setting up Google OAuth: {e}")

# Initialize OAuth
setup_oauth()


# =============================================================================
# USER LOADER
# =============================================================================

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    return db.session.get(User, int(user_id))


# =============================================================================
# AUTHENTICATION ROUTES
# =============================================================================
from flask import session, request, redirect, url_for, flash, g
from flask_login import current_user, logout_user

from flask import session, request, redirect, url_for, flash, g
from flask_login import current_user, logout_user

@app.before_request
def validate_session():
    """Validate user session on each request"""
    
    # Skip validation for static files and auth routes
    excluded_endpoints = [
        'static', 'index', 'feed', 'home', 'login', 'register', 'forgot_password', 
        'reset_password', 'google_login', 'google_callback',
        'privacy', 'terms', 'contact',
        'admin_login'  # ADD THIS LINE - This is what's missing!
    ]
    
    if request.endpoint in excluded_endpoints:
        return
    
    # Skip validation for AJAX requests to avoid redirect loops
    if request.is_json:
        return
    
    if current_user.is_authenticated:
        # Get client info
        client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
        user_agent = request.headers.get('User-Agent', '')
        
        # Check if session data exists
        session_token = session.get('session_token')
        user_id = session.get('user_id')
        
        # Validate session data matches current user
        if not session_token or not user_id or user_id != current_user.id:
            app.logger.warning(f"Session mismatch for user {current_user.id}")
            session.clear()
            logout_user()
            flash('Session expired. Please log in again.', 'warning')
            return redirect(url_for('login'))
        
        # Validate session token with database
        if not current_user.is_session_valid(session_token, client_ip):
            app.logger.warning(f"Invalid session for user {current_user.id}")
            session.clear()
            logout_user()
            flash('Session expired. Please log in again.', 'warning')
            return redirect(url_for('login'))
        
        # Check if user is still active
        if not current_user.is_active:
            app.logger.warning(f"Inactive user {current_user.id} attempted access")
            session.clear()
            logout_user()
            flash('Your account has been deactivated.', 'error')
            return redirect(url_for('login'))
        
        # Extend session if it's about to expire (within 30 minutes)
        if current_user.session_expires:
            time_left = current_user.session_expires - datetime.utcnow()
            if time_left.total_seconds() < 1800:  # 30 minutes
                current_user.extend_session()
        
        # Store user info in g for easy access
        g.current_user = current_user
        
    elif request.endpoint and not request.endpoint.startswith('auth'):
        # User is not authenticated but trying to access protected route
        flash('Please log in to access this page.', 'info')
        return redirect(url_for('login'))
    
@app.route('/')
def index():
    """Home page - shows beautiful landing page for everyone"""
    return render_template('home.html', current_year=datetime.now().year)

@app.route('/feed')
@login_required
def feed():
    """Display the main feed with learnership posts"""
    return render_template('feed.html')


@app.route('/login', methods=['GET', 'POST'])
def login():  
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('Please enter both email and password.', 'error')
            return render_template('login.html')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been deactivated.', 'error')
                return render_template('login.html')
            
            # Get client information
            client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
            user_agent = request.headers.get('User-Agent', '')
             #ccccccccccccccccccccccccccccccccccccccc
            user.clear_session()
            
            # Clear Flask session completely
            session.clear()
            
            # Generate new session token
            session_token = user.generate_session_token(client_ip, user_agent)
            
            # Login the user
            login_user(user, remember=False)
            
            # Set session data
            session['user_id'] = user.id
            session['user_email'] = user.email
            session['user_role'] = user.role
            session['session_token'] = session_token
            session['login_time'] = datetime.utcnow().isoformat()
            session.permanent = True
            
            # Update last login
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            app.logger.info(f"User {user.id} ({user.email}) logged in from {client_ip}")
            
            flash(f'Welcome back, {user.full_name or user.email}!', 'success')
            
            # Redirect based on role
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('feed'))  # Instead of user_dashboard
        else:
            flash('Invalid email or password.', 'error')
    
    return render_template('login.html')


@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    """Admin login with username and password"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = AdminLoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data, role='admin').first()
        
        if user and user.check_password(form.password.data):
            # Get client information
            client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
            user_agent = request.headers.get('User-Agent', '')
            
            # Clear any existing session for this user
            user.clear_session()
            
            # Clear Flask session completely
            session.clear()
            
            # Generate new session token
            session_token = user.generate_session_token(client_ip, user_agent)
            
            # Login the user
            login_user(user, remember=False)
            
            # Set session data - THIS IS WHAT WAS MISSING!
            session['user_id'] = user.id
            session['user_email'] = user.email
            session['user_role'] = user.role
            session['session_token'] = session_token
            session['login_time'] = datetime.utcnow().isoformat()
            session.permanent = True
            
            # Update last login
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            app.logger.info(f"Admin {user.id} ({user.email}) logged in from {client_ip}")
            
            flash('Welcome back, Admin!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('admin_login.html', form=form)


@app.cli.command()
def cleanup_sessions():
    """Clean up expired sessions"""
    expired_users = User.query.filter(
        User.session_expires < datetime.utcnow()
    ).all()
    
    count = 0
    for user in expired_users:
        user.clear_session()
        count += 1
    
    print(f"Cleaned up {count} expired sessions")

@app.route('/login/google')
def google_login():
    """Initiate Google OAuth login"""
    if not google:
        # Fallback for development - create demo user
        demo_user = User.query.filter_by(email='demo@codecraftco.com').first()
        if not demo_user:
            demo_user = User(
                email='demo@codecraftco.com',
                full_name='Demo User',
                role='user',
                auth_method='google',
                is_active=True
            )
            db.session.add(demo_user)
            db.session.commit()
        
        # Clear existing session
        demo_user.clear_session()
        session.clear()
        
        # Generate session token
        client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
        user_agent = request.headers.get('User-Agent', '')
        session_token = demo_user.generate_session_token(client_ip, user_agent)
        
        # Login user
        login_user(demo_user, remember=False)
        
        # Set session data
        session['user_id'] = demo_user.id
        session['user_email'] = demo_user.email
        session['user_role'] = demo_user.role
        session['session_token'] = session_token
        session.permanent = True
        
        demo_user.last_login = datetime.utcnow()
        db.session.commit()
        
        flash('Logged in as Demo User (Google OAuth not configured)', 'warning')
        return redirect(url_for('user_dashboard'))
    
    # Redirect to Google OAuth
    return google.authorize_redirect(
        url_for('google_callback', _external=True),
        prompt='consent',
        access_type='offline'
    )


@app.route('/logout')
def logout():
    if current_user.is_authenticated:
        app.logger.info(f"User {current_user.id} ({current_user.email}) logged out")
        
        # Clear database session
        current_user.clear_session()
        
        # Clear Flask session
        session.clear()
        
        # Logout user
        logout_user()
        
        flash('You have been logged out successfully.', 'success')
    
    return redirect(url_for('index'))


@app.route('/admin/sessions')
@login_required
def admin_sessions():
    """Admin view for active sessions"""
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('user_dashboard'))
    
    active_sessions = User.query.filter(
        User.session_token.isnot(None),
        User.session_expires > datetime.utcnow()
    ).all()
    
    return render_template('admin/sessions.html', sessions=active_sessions)

@app.route('/debug/profile')
@login_required
def debug_profile():
    return f"""
    <h2>Debug Info</h2>
    <p>Profile Picture: {current_user.profile_picture}</p>
    <p>Full Name: {current_user.full_name}</p>
    <p>Email: {current_user.email}</p>
    {f'<img src="{current_user.profile_picture}" width="100">' if current_user.profile_picture else '<p>No image</p>'}
    """
@app.route('/fix-profile-image')
@login_required
def fix_profile_image():
    """Fix the profile image URL by removing trailing commas"""
    if current_user.profile_picture:
        # Clean the URL
        cleaned_url = current_user.profile_picture.strip().rstrip(',').strip()
        
        if cleaned_url != current_user.profile_picture:
            print(f"Original: {current_user.profile_picture}")
            print(f"Cleaned: {cleaned_url}")
            
            current_user.profile_picture = cleaned_url
            db.session.commit()
            
            flash('Profile image URL fixed!', 'success')
        else:
            flash('Profile image URL is already clean.', 'info')
    else:
        flash('No profile image found.', 'warning')
    
    return redirect(url_for('user_dashboard'))


@app.route('/google/callback')
def google_callback():
    try:
        # Get token from Google
        token = google.authorize_access_token()
        
        # Get user info
        userinfo = token.get('userinfo')
        if not userinfo:
            resp = google.get('https://www.googleapis.com/oauth2/v1/userinfo', token=token)
            userinfo = resp.json()
        
        # Debug prints
        print("Full Userinfo:", userinfo)
        print("Full Token:", token)
        print("Profile Picture URL:", userinfo.get('picture'))
        
        # Ensure profile picture URL is valid and complete
        profile_picture = userinfo.get('picture')
        if profile_picture and not profile_picture.startswith(('http://', 'https://')):
            profile_picture = None
        
        # Check if user exists or create new one
        user = User.query.filter_by(email=userinfo['email']).first()
        
        if not user:
            user = User(
                email=userinfo['email'],
                full_name=userinfo.get('name'),
                role='user',
                auth_method='google',
                is_active=True
            )
            db.session.add(user)
            db.session.flush()

        # Download and store the profile picture locally for all users
        if profile_picture:
            saved_path = download_and_save_profile_picture(profile_picture, user.id)
            if saved_path:
                user.profile_picture = saved_path

        # Store or update Google token
        from models import GoogleToken
        google_token = GoogleToken.query.filter_by(user_id=user.id).first()
        
        # Prepare token data with ACTUAL scopes from token
        token_data = {
            'access_token': token.get('access_token'),
            'refresh_token': token.get('refresh_token'),
            'token_uri': 'https://oauth2.googleapis.com/token',
            'client_id': app.config.get('GOOGLE_CLIENT_ID'),
            'client_secret': app.config.get('GOOGLE_CLIENT_SECRET'),
            'scopes': token.get('scope', '').split(),
            'expires_at': token.get('expires_at'),
            'token_type': token.get('token_type', 'Bearer'),
            'expires_in': token.get('expires_in')
        }
        
        # Debug: Print the scopes we actually got
        print(f"Token scopes: {token_data['scopes']}")
        
        if google_token:
            # Update existing token
            google_token.token_json = json.dumps(token_data)
            google_token.refreshed_at = datetime.utcnow()
        else:
            # Create new token record
            google_token = GoogleToken(
                user_id=user.id,
                token_json=json.dumps(token_data),
                refreshed_at=datetime.utcnow()
            )
            db.session.add(google_token)
        
        # Update user's last login
        user.last_login = datetime.utcnow()
        
        # Commit all changes
        db.session.commit()
        
        # ============= ADD THIS SECTION - CRITICAL FIX =============
        # Get client information
        client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
        user_agent = request.headers.get('User-Agent', '')
        
        # Clear any existing session for this user
        user.clear_session()
        
        # Clear Flask session completely
        session.clear()
        
        # Generate new session token
        session_token = user.generate_session_token(client_ip, user_agent)
        
        # Login the user
        login_user(user, remember=False)
        
        # Set session data - THIS IS WHAT WAS MISSING!
        session['user_id'] = user.id
        session['user_email'] = user.email
        session['user_role'] = user.role
        session['session_token'] = session_token
        session['login_time'] = datetime.utcnow().isoformat()
        session.permanent = True
        
        # Commit session changes
        db.session.commit()
        # ============= END OF CRITICAL FIX =============
        
        # Logging for debugging
        app.logger.info(f"User logged in: {user.email}")
        app.logger.info(f"Profile Picture: {user.profile_picture}")
        app.logger.info(f"Google token stored for user: {user.id}")
        print(f"Token stored successfully for user {user.id}")
        
        flash(f'Welcome, {user.full_name or user.email}!', 'success')
        return redirect(url_for('feed', login='success'))

        
    except Exception as e:
        print(f"OAuth callback error: {e}")
        import traceback
        traceback.print_exc()
        flash('Authentication failed. Please try again.', 'error')
        return redirect(url_for('login'))

@app.after_request
def add_csp_headers(response):
    response.headers['Content-Security-Policy'] = (
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
# USER DASHBOARD AND PROFILE ROUTES
# =============================================================================
@app.route('/user/dashboard')
@login_required
def user_dashboard():
    """User dashboard with overview of applications and documents"""
    try:
        # Get user's recent applications with enhanced data
        recent_applications = Application.query.filter_by(user_id=current_user.id)\
            .order_by(Application.created_at.desc()).limit(5).all()
        
        # Get user's documents count
        documents_count = Document.query.filter_by(user_id=current_user.id, is_active=True).count()
        
        # Calculate application statistics
        total_applications = Application.query.filter_by(user_id=current_user.id).count()
        pending_applications = Application.query.filter_by(user_id=current_user.id, status='pending').count()
        
        # Count responses 
        responses_count = Application.query.filter(
            Application.user_id == current_user.id,
            Application.email_status == 'responded'
        ).count() if hasattr(Application, 'email_status') else 0
        
        # Basic stats object
        application_stats = {
            'total': total_applications,
            'pending': pending_applications, 
            'responses': responses_count,
            'response_rate': 0
        }
        
        # Calculate DYNAMIC profile completion
        profile_completion = calculate_profile_completion(current_user)
        
        # Enhanced recent applications with actual company info
        enhanced_applications = []
        for app in recent_applications:
            # Try to get learnership details first, then fallback to app attributes
            if hasattr(app, 'learnership') and app.learnership:
                # Using learnership relationship
                company_name = app.learnership.company
                position_title = app.learnership.title
                company_logo = getattr(app.learnership, 'company_logo', None)
                location = app.learnership.location
            else:
                # Fallback to application attributes
                company_name = getattr(app, 'company_name', None)
                position_title = getattr(app, 'position_title', None) or getattr(app, 'learnership_title', None)
                company_logo = getattr(app, 'company_logo', None)
                location = getattr(app, 'location', None)
            
            # Create enhanced application data (clean fallbacks)
            app_data = {
                'id': app.id,
                'company_name': company_name or 'Company Name Not Available',
                'position_title': position_title or company_name or 'Application',  # Use company name as fallback
                'company_logo': company_logo,
                'location': location if location else None,  # Only pass location if it exists
                'status': getattr(app, 'status', 'pending'),
                'email_status': getattr(app, 'email_status', None),
                'created_at': app.created_at,
                'learnership': getattr(app, 'learnership', None)
            }
            enhanced_applications.append(app_data)
        
        return render_template('user_dashboard.html', 
                             user=current_user,
                             current_user=current_user,
                             recent_applications=enhanced_applications,
                             application_stats=application_stats,
                             profile_completion=profile_completion,  # Dynamic completion
                             documents_count=documents_count)
    
    except Exception as e:
        app.logger.error(f"Dashboard error: {str(e)}")
        # Fallback data if there's an error
        fallback_stats = {
            'total': 0,
            'pending': 0,
            'responses': 0,
            'response_rate': 0
        }
        
        return render_template('user_dashboard.html',
                             user=current_user,
                             current_user=current_user,
                             recent_applications=[],
                             application_stats=fallback_stats,
                             profile_completion=calculate_profile_completion(current_user),  # Dynamic even in fallback
                             documents_count=0)
    


def calculate_profile_completion(user):
    """Calculate user profile completion percentage - SIMPLIFIED"""
    completion_score = 0
    total_fields = 6  # Reduced to essential fields only
    
    # Essential fields only
    if user.full_name:
        completion_score += 1
    if user.email:
        completion_score += 1
    if user.profile_picture:
        completion_score += 1
    if hasattr(user, 'phone') and user.phone:
        completion_score += 1
    if hasattr(user, 'address') and user.address:
        completion_score += 1
    
    # Documents (any document upload counts)
    try:
        has_documents = Document.query.filter_by(
            user_id=user.id, 
            is_active=True
        ).count() > 0
        
        if has_documents:
            completion_score += 1
    except:
        pass  # If document check fails, don't break
    
    percentage = round((completion_score / total_fields) * 100)
    
    # Debug print (remove after testing)
    print(f"Profile completion for {user.full_name}: {completion_score}/{total_fields} = {percentage}%")
    
    return percentage


@app.route('/api/dashboard-stats')
@login_required
def api_dashboard_stats():
    """API endpoint for real-time dashboard stats"""
    try:
        # Get current stats
        total_applications = Application.query.filter_by(user_id=current_user.id).count()
        pending_applications = Application.query.filter_by(user_id=current_user.id, status='pending').count()
        
        # Recent applications (last 7 days)
        from datetime import datetime, timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_count = Application.query.filter(
            Application.user_id == current_user.id,
            Application.created_at >= week_ago
        ).count()
        
        # Responses
        responses_count = Application.query.filter(
            Application.user_id == current_user.id,
            Application.email_status == 'responded'
        ).count()
        
        # Response rate
        sent_emails = Application.query.filter(
            Application.user_id == current_user.id,
            Application.email_status.in_(['sent', 'delivered', 'read', 'responded'])
        ).count()
        
        response_rate = (responses_count / sent_emails * 100) if sent_emails > 0 else 0
        
        # Profile completion
        profile_completion = calculate_profile_completion(current_user)
        
        stats = {
            'total': total_applications,
            'pending': pending_applications,
            'recent_count': recent_count,
            'responses': responses_count,
            'response_rate': response_rate,
            'profile_completion': profile_completion
        }
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        app.logger.error(f"API Dashboard stats error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/recent-applications')
@login_required
def api_recent_applications():
    """API endpoint for real-time recent applications"""
    try:
        recent_applications = Application.query.filter_by(
            user_id=current_user.id
        ).order_by(Application.created_at.desc()).limit(3).all()
        
        applications_data = []
        for app in recent_applications:
            learnership = getattr(app, 'learnership', None)
            
            app_data = {
                'id': app.id,
                'learnership_title': learnership.title if learnership else getattr(app, 'position', 'Application'),
                'company_name': learnership.company if learnership else getattr(app, 'company_name', 'Company not specified'),
                'company_logo': learnership.company_logo if learnership else getattr(app, 'company_logo', None),
                'location': learnership.location if learnership else getattr(app, 'location', None),
                'status': getattr(app, 'status', 'pending'),
                'email_status': getattr(app, 'email_status', None),
                'created_at': app.created_at.isoformat() if app.created_at else None,
                'gmail_thread_id': getattr(app, 'gmail_thread_id', None),
                'gmail_tracked': getattr(app, 'gmail_message_id', None) is not None,
                'has_response': getattr(app, 'email_status', None) == 'responded'
            }
            applications_data.append(app_data)
        
        return jsonify({
            'success': True,
            'applications': applications_data
        })
        
    except Exception as e:
        app.logger.error(f"API Recent applications error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/application-status/<int:app_id>')
@login_required
def api_application_status(app_id):
    """API endpoint for checking individual application status"""
    try:
        application = Application.query.filter_by(
            id=app_id, 
            user_id=current_user.id
        ).first()
        
        if not application:
            return jsonify({
                'success': False,
                'error': 'Application not found'
            }), 404
        
        return jsonify({
            'success': True,
            'status': getattr(application, 'status', 'pending'),
            'email_status': getattr(application, 'email_status', None),
            'has_response': getattr(application, 'email_status', None) == 'responded',
            'gmail_thread_id': getattr(application, 'gmail_thread_id', None),
            'last_updated': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        app.logger.error(f"API Application status error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    


import os
import requests
from werkzeug.utils import secure_filename

def download_and_save_profile_picture(picture_url, user_id):
    if not picture_url:
        return None

    try:
        response = requests.get(picture_url)
        if response.status_code == 200:
            filename = secure_filename(f"profile_{user_id}.jpg")
            folder = os.path.join(app.root_path, 'static/uploads')
            os.makedirs(folder, exist_ok=True)
            filepath = os.path.join(folder, filename)

            with open(filepath, 'wb') as f:
                f.write(response.content)

            return f"/static/uploads/{filename}"
    except Exception as e:
        print("Profile picture download failed:", e)

    return None


@app.route('/user/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit user profile information"""
    form = EditProfileForm()
    
    if form.validate_on_submit():
        current_user.full_name = form.full_name.data
        current_user.phone = form.phone.data
        current_user.address = form.address.data
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('user_dashboard'))
    
    # Pre-populate form with current data
    form.full_name.data = current_user.full_name
    form.phone.data = current_user.phone
    form.address.data = current_user.address
    
    return render_template('edit_profile.html', form=form)

@app.route('/user/documents/view/<int:document_id>')
@login_required
def view_document(document_id):
    try:
        # Get the document and verify ownership
        document = Document.query.filter_by(id=document_id, user_id=current_user.id).first()
        if not document:
            flash('Document not found.', 'error')
            return redirect(url_for('document_center'))
        
        # Get file path
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'documents', document.filename)
        
        # Check if file exists
        if not os.path.exists(file_path):
            flash('Document file not found.', 'error')
            return redirect(url_for('document_center'))
        
        # Get file extension
        file_extension = document.filename.lower().split('.')[-1]
        
        # For images, serve directly
        if file_extension in ['jpg', 'jpeg', 'png', 'gif']:
            return send_file(file_path, as_attachment=False)
        
        # For PDFs, serve with PDF viewer
        elif file_extension == 'pdf':
            return send_file(file_path, as_attachment=False, mimetype='application/pdf')
        
        # For other files, download them
        else:
            return send_file(file_path, as_attachment=True)
            
    except Exception as e:
        current_app.logger.error(f'Error viewing document: {str(e)}')
        flash('Error viewing document.', 'error')
        return redirect(url_for('document_center'))

@app.route('/user/documents/preview/<int:document_id>')
@login_required
def preview_document(document_id):
    try:
        # Get the document and verify ownership
        document = Document.query.filter_by(id=document_id, user_id=current_user.id).first()
        if not document:
            return jsonify({'error': 'Document not found'}), 404
        
        # Get file path
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'documents', document.filename)
        
        # Check if file exists
        if not os.path.exists(file_path):
            return jsonify({'error': 'Document file not found'}), 404
        
        # Get file extension
        file_extension = document.filename.lower().split('.')[-1]
        
        # Return document info for preview
        return jsonify({
            'id': document.id,
            'filename': document.filename,
            'original_name': document.original_name,
            'file_type': file_extension,
            'upload_date': document.upload_date.strftime('%Y-%m-%d %H:%M:%S'),
            'view_url': url_for('view_document', document_id=document.id),
            'download_url': url_for('download_document', document_id=document.id)
        })
        
    except Exception as e:
        current_app.logger.error(f'Error previewing document: {str(e)}')
        return jsonify({'error': 'Error previewing document'}), 500
    
# =============================================================================
# LEARNERSHIP MANAGEMENT ROUTES
# =============================================================================

def load_learnerships_from_json():
    """Load learnership data from JSON file"""
    json_path = os.path.join(app.static_folder, 'data', 'learnerships.json')
    try:
        with open(json_path, 'r') as file:
            data = json.load(file)
            for item in data:
                if 'closing_date' in item and isinstance(item['closing_date'], str):
                    try:
                        item['closing_date'] = datetime.strptime(item['closing_date'], '%Y-%m-%d')
                    except ValueError:
                        item['closing_date'] = datetime.now().replace(year=datetime.now().year + 1)
            return data
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading learnerships data: {e}")
        return []


@app.route('/user/learnerships', methods=['GET', 'POST'])
@login_required
def learnerships():
    """Display and search available learnerships"""
    # Initialize search form
    form = LearnershipSearchForm()
    
    # Start with all active learnerships from database
    query = Learnership.query.filter_by(is_active=True)
    
    # Apply search filters
    if form.validate_on_submit():
        # Filter by search term
        if form.search.data:
            search_term = form.search.data.lower()
            query = query.filter(
                (Learnership.title.ilike(f'%{search_term}%')) |
                (Learnership.company.ilike(f'%{search_term}%')) |
                (Learnership.description.ilike(f'%{search_term}%'))
            )
        
        # Filter by category
        if form.category.data and form.category.data != 'all':
            query = query.filter(Learnership.category == form.category.data)
    
    # Execute query
    learnerships = query.order_by(Learnership.closing_date).all()
    
    # Prepare category choices for dropdown
    categories = db.session.query(Learnership.category.distinct()).all()
    categories = [category[0] for category in categories]
    
    form.category.choices = [('all', 'All Categories')] + [
        (category, category.replace('_', ' ').title()) 
        for category in categories
    ]
    
    # Group learnerships by category
    categorized_learnerships = {}
    for learnership in learnerships:
        category = learnership.category or 'Other'
        if category not in categorized_learnerships:
            categorized_learnerships[category] = []
        categorized_learnerships[category].append(learnership)
    
    # Get learnership emails for bulk application
    learnership_emails = LearnshipEmail.query.filter_by(is_active=True).all()
    
    return render_template('learnerships.html', 
                           form=form,
                           categories=categorized_learnerships,
                           learnerships=learnerships,
                           learnership_emails=learnership_emails)




@app.route('/cv-generator')
@login_required
def cv_generator():
    return render_template('index.html')

@app.route('/cv-template/<template>')
@login_required
def cv_template(template):
    """Serve CV template previews"""
    template_map = {
        'classic': 'classic.html',
        'modern': 'modern.html',
        'creative': 'creative.html',
        'minimal': 'minimal.html',
        'sidebar': 'sidebar.html'
    }
    
    template_file = template_map.get(template, 'classic.html')
    
    try:
        return render_template(template_file)
    except Exception as e:
        print(f"Error loading template {template_file}: {e}")
        # Return a fallback template or error message
        return f"<html><body><h1>Template Error</h1><p>Could not load {template_file}</p><p>Error: {str(e)}</p></body></html>"




@app.route('/user/apply', methods=['GET', 'POST'])
@login_required
def apply_learnership():
    """Apply for selected learnerships"""
    # Get selected learnership IDs
    selected_ids = request.args.getlist('selected')
    
    if not selected_ids:
        flash('Please select at least one learnership to apply for.', 'warning')
        return redirect(url_for('learnerships'))
    
    # Convert to integers and validate
    selected_ids = [int(id) for id in selected_ids if id.isdigit()]
    
    if not selected_ids:
        flash('Invalid selection.', 'warning')
        return redirect(url_for('learnerships'))
    
    # Get learnerships from JSON data
    all_learnerships = load_learnerships_from_json()
    
    # Ensure each learnership has an apply_email field
    for learnership in all_learnerships:
        if 'apply_email' not in learnership or not learnership['apply_email']:
            learnership['apply_email'] = 'applications@' + learnership['company'].lower().replace(' ', '') + '.co.za'
    
    # Filter to selected learnerships
    selected_learnerships = [l for l in all_learnerships if l['id'] in selected_ids]
    
    if not selected_learnerships:
        flash('No valid learnerships selected.', 'warning')
        return redirect(url_for('learnerships'))
    
    # Get user's documents
    user_documents = Document.query.filter_by(user_id=current_user.id, is_active=True).all()
    
    # Create application form
    form = ApplicationForm()
    
    if form.validate_on_submit():
        # Create application records in database
        created_apps = []
        for lr in selected_learnerships:
            try:
                app = Application(
                    user_id=current_user.id,
                    learnership_id=lr.get('id'),
                    learnership_name=lr.get('title', 'Unknown'),
                    company_name=lr.get('company', 'Unknown'),
                    status='pending'
                )
                db.session.add(app)
                db.session.commit()
                created_apps.append(app)
                print(f"Created application record: {app.id}")
            except Exception as e:
                print(f"Error creating application: {e}")
                db.session.rollback()
        
        # Process email sending if applications were created
        if created_apps:
            try:
                # Get selected document IDs for attachments
                attachment_ids = []
                if hasattr(form, 'attachments'):
                    attachment_ids = [int(id) for id in form.attachments.data]
                
                # Temporarily save email body to user
                current_user.email_body = form.email_body.data
                
                # Launch background job to send emails
                launch_bulk_send(current_user, selected_learnerships, attachment_ids)
                
                flash(f'Created {len(created_apps)} applications. Email sending in progress...', 'success')
            except Exception as e:
                flash(f'Applications created but email sending failed: {str(e)}', 'warning')
        else:
            flash('Failed to create applications.', 'error')
            
        return redirect(url_for('my_applications'))
    
    return render_template('apply_learnership.html',
                          form=form,
                          selected_learnerships=selected_learnerships,
                          user_documents=user_documents)


# =============================================================================
# GMAIL STATUS TRACKING ROUTES
# =============================================================================

@app.route('/user/applications')
@login_required
def my_applications():
    """Display user's applications grouped by status with Gmail tracking"""
    # Get all user's applications with Gmail tracking info
    applications = Application.query.filter_by(user_id=current_user.id)\
        .order_by(Application.updated_at.desc()).all()
    
    # Group applications by status
    grouped_applications = {
        'pending': [],
        'submitted': [],
        'reviewed': [],
        'accepted': [],
        'rejected': []
    }
    
    # Group by email status for Gmail tracking
    email_status_groups = {
        'draft': [],
        'sent': [],
        'delivered': [],
        'read': [],
        'responded': [],
        'failed': []
    }
    
    # Statistics counters
    stats = {
        'total': len(applications),
        'sent_emails': 0,
        'responses_received': 0,
        'pending_responses': 0,
        'gmail_tracked': 0,
        'failed_emails': 0,
        'recent_activity': 0
    }
    
    for app in applications:
        # Your existing grouping
        if app.status in grouped_applications:
            grouped_applications[app.status].append(app)
        
        # Group by email status
        email_status = getattr(app, 'email_status', 'draft')
        if email_status in email_status_groups:
            email_status_groups[email_status].append(app)
        
        # Calculate statistics
        if hasattr(app, 'sent_at') and app.sent_at:
            stats['sent_emails'] += 1
        
        if hasattr(app, 'has_response') and app.has_response:
            stats['responses_received'] += 1
        
        if hasattr(app, 'gmail_message_id') and app.gmail_message_id:
            stats['gmail_tracked'] += 1
            
        if hasattr(app, 'email_status') and app.email_status == 'failed':
            stats['failed_emails'] += 1
            
        # Applications sent but no response yet
        if (hasattr(app, 'email_status') and app.email_status == 'sent' and 
            hasattr(app, 'has_response') and not app.has_response):
            stats['pending_responses'] += 1
        
        # Recent activity (last 7 days)
        if app.is_recent(7):
            stats['recent_activity'] += 1
    
    # Get applications that need status updates (sent in last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    needs_update = Application.query.filter_by(user_id=current_user.id)\
        .filter(Application.gmail_message_id.isnot(None))\
        .filter(Application.sent_at >= thirty_days_ago)\
        .filter(Application.email_status.in_(['sent', 'delivered']))\
        .count()
    
    return render_template('my_applications.html', 
                         applications=applications,
                         grouped_applications=grouped_applications,
                         email_status_groups=email_status_groups,
                         stats=stats,
                         needs_update=needs_update)

@app.route('/update_application_statuses', methods=['POST'])
@login_required
def update_application_statuses():
    """Update Gmail statuses for current user's applications"""
    try:
        from gmail_status_checker import GmailStatusChecker
        
        checker = GmailStatusChecker(current_user.id)
        updated_count = checker.update_application_statuses()
        
        return jsonify({
            'success': True, 
            'updated_count': updated_count,
            'message': f'Updated {updated_count} application statuses'
        })
        
    except Exception as e:
        print(f"Error updating statuses: {e}")
        return jsonify({
            'success': False, 
            'error': str(e)
        }), 500

@app.route('/api/application_status/<int:app_id>')
@login_required
def get_application_status(app_id):
    """Get real-time status for a specific application"""
    application = Application.query.filter_by(
        id=app_id, 
        user_id=current_user.id
    ).first_or_404()
    
    live_status = None
    if application.gmail_message_id:
        try:
            from gmail_status_checker import GmailStatusChecker
            checker = GmailStatusChecker(current_user.id)
            live_status = checker.check_message_status(application.gmail_message_id)
        except Exception as e:
            print(f"Error checking live status: {e}")
    
    return jsonify({
        'id': application.id,
        'status': application.status,
        'email_status': application.email_status,
        'sent_at': application.sent_at.isoformat() if application.sent_at else None,
        'has_response': application.has_response,
        'response_count': application.response_thread_count,
        'response_received_at': application.response_received_at.isoformat() if application.response_received_at else None,
        'gmail_message_id': application.gmail_message_id,
        'gmail_thread_id': application.gmail_thread_id,
        'gmail_url': application.get_gmail_url(),
        'days_since_sent': application.days_since_sent(),
        'live_status': live_status
    })

@app.route('/auto-update-gmail-status')
@login_required
def auto_update_gmail_status():
    """Auto-update Gmail statuses for applications sent in last 7 days"""
    try:
        from gmail_status_checker import GmailStatusChecker
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        # Only check recent applications to avoid rate limits
        recent_applications = Application.query.filter_by(user_id=current_user.id)\
            .filter(Application.gmail_message_id.isnot(None))\
            .filter(Application.sent_at >= seven_days_ago)\
            .all()
        
        if not recent_applications:
            return jsonify({
                'success': True,
                'message': 'No recent applications to update',
                'updated_count': 0
            })
        
        checker = GmailStatusChecker(current_user.id)
        updated_count = 0
        
        for app in recent_applications:
            try:
                status_info = checker.check_message_status(app.gmail_message_id)
                if status_info:
                    app.update_from_gmail_status(status_info)
                    updated_count += 1
                    
                time.sleep(0.2)  # Slower rate to avoid limits
            except Exception as e:
                print(f"Error updating app {app.id}: {e}")
                continue
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'updated_count': updated_count,
            'total_checked': len(recent_applications),
            'message': f'Updated {updated_count} of {len(recent_applications)} recent applications'
        })
        
    except Exception as e:
        print(f"Error in auto-update: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/bulk-check-responses')
@login_required
def bulk_check_responses():
    """Check for responses on all sent applications"""
    try:
        from gmail_status_checker import GmailStatusChecker
        
        checker = GmailStatusChecker(current_user.id)
        responses_found = checker.check_recent_responses(days=30)
        
        return jsonify({
            'success': True,
            'responses_found': responses_found,
            'message': f'Found {responses_found} new responses!'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/gmail-status-dashboard')
@login_required
def gmail_status_dashboard():
    """Detailed Gmail status dashboard"""
    applications_with_gmail = Application.query.filter_by(user_id=current_user.id)\
        .filter(Application.gmail_message_id.isnot(None))\
        .order_by(Application.sent_at.desc()).all()
    
    # Group by email status
    status_groups = {
        'sent': [],
        'delivered': [],
        'read': [],
        'responded': [],
        'failed': []
    }
    
    response_stats = {
        'total_tracked': len(applications_with_gmail),
        'awaiting_response': 0,
        'got_responses': 0,
        'avg_response_time': None
    }
    
    response_times = []
    
    for app in applications_with_gmail:
        email_status = getattr(app, 'email_status', 'sent')
        if email_status in status_groups:
            status_groups[email_status].append(app)
        
        if app.has_response and app.sent_at and app.response_received_at:
            response_times.append((app.response_received_at - app.sent_at).days)
            response_stats['got_responses'] += 1
        elif app.email_status == 'sent' and not app.has_response:
            response_stats['awaiting_response'] += 1
    
    if response_times:
        response_stats['avg_response_time'] = sum(response_times) / len(response_times)
    
    return render_template('gmail_status_dashboard.html',
                         applications=applications_with_gmail,
                         status_groups=status_groups,
                         response_stats=response_stats)


# =============================================================================
# DOCUMENT MANAGEMENT ROUTES
# =============================================================================

@app.route('/user/documents', methods=['GET', 'POST'])
@login_required
def document_center():
    """Document upload and management center"""
    form = DocumentUploadForm()
    
    if form.validate_on_submit():
        file = form.document.data
        if file:
            # Secure filename and create unique name
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_filename = f"{current_user.id}_{timestamp}_{filename}"
            
            # Save file to uploads directory
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'documents', unique_filename)
            file.save(file_path)
            
            # Create document record in database
            document = Document(
                user_id=current_user.id,
                document_type=form.document_type.data,
                filename=unique_filename,
                original_filename=filename,
                file_path=file_path,
                file_size=os.path.getsize(file_path)
            )
            db.session.add(document)
            db.session.commit()
            
            flash('Document uploaded successfully!', 'success')
            return redirect(url_for('document_center'))
    
    # Get user's documents
    documents = Document.query.filter_by(user_id=current_user.id, is_active=True)\
        .order_by(Document.uploaded_at.desc()).all()
    
    # Group documents by type
    grouped_documents = {}
    for doc in documents:
        doc_type = doc.document_type.replace('_', ' ').title()
        if doc_type not in grouped_documents:
            grouped_documents[doc_type] = []
        grouped_documents[doc_type].append(doc)
    
    return render_template('document_center.html',
                         form=form,
                         documents=documents,
                         grouped_documents=grouped_documents)


@app.route('/user/document/delete/<int:doc_id>', methods=['POST'])
@login_required
def delete_document(doc_id):
    """Soft delete user document"""
    document = Document.query.filter_by(id=doc_id, user_id=current_user.id).first_or_404()
    
    # Mark as inactive instead of deleting
    document.is_active = False
    db.session.commit()
    
    flash('Document removed successfully!', 'success')
    return redirect(url_for('document_center'))


# =============================================================================
# BULK EMAIL APPLICATION ROUTES
# =============================================================================
from datetime import datetime

@app.template_filter('days_ago')
def days_ago_filter(date):
    """Calculate days ago from a given date"""
    if not date:
        return "Never"
    
    days = (datetime.utcnow() - date).days
    
    if days == 0:
        return "Today"
    elif days == 1:
        return "1 day ago"
    else:
        return f"{days} days ago"

# Also add this for time differences
@app.template_filter('time_ago')
def time_ago_filter(date):
    """Human readable time ago"""
    if not date:
        return "Never"
    
    diff = datetime.utcnow() - date
    
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    elif diff.seconds > 3600: 
        hours = diff.seconds // 3600 
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "Just now"
    

def send_application_email_with_gmail(recipient_email, company_name, user):
    """Enhanced email sending function that returns Gmail tracking data"""
    result = send_application_email(recipient_email, company_name, user)
    
    # If result is the old format (tuple), convert to new format
    if isinstance(result, tuple):
        success, message = result
        return {
            'success': success,
            'message': message,
            'gmail_data': {}
        }
    
    # If it's already a dict, return as is
    if isinstance(result, dict):
        return result
    
    # Fallback
    return {
        'success': False,
        'message': 'Unknown email sending result format',
        'gmail_data': {}
    }

@app.route('/apply_bulk_email', methods=['POST'])
@login_required
def apply_bulk_email():
    """Process bulk application to selected email addresses with Gmail tracking"""
    selected_email_ids = request.form.getlist('selected_emails')
    
    if not selected_email_ids:
        flash('Please select at least one company to apply to.', 'warning')
        return redirect(url_for('learnership_emails'))
    
    # Get the selected email entries
    email_entries = LearnshipEmail.query.filter(
        LearnshipEmail.id.in_(selected_email_ids),
        LearnshipEmail.is_active == True
    ).all()
    
    if not email_entries:
        flash('No valid email addresses found.', 'error')
        return redirect(url_for('learnership_emails'))
    
    # Process each selected email
    successful_companies = []
    failed_companies = []
    timeout_companies = []
    already_applied = []
    gmail_tracked_count = 0
    
    for email_entry in email_entries:
        # Check if application already exists
        existing_app = EmailApplication.query.filter_by(
            user_id=current_user.id,
            learnership_email_id=email_entry.id
        ).first()
        
        if existing_app:
            already_applied.append(email_entry.company_name)
            continue
        
        try:
            # Send application email with Gmail tracking
            email_result = send_application_email_with_gmail(
                email_entry.email,
                email_entry.company_name,
                current_user
            )
            
            success = email_result.get('success', False)
            message = email_result.get('message', '')
            gmail_data = email_result.get('gmail_data', {})
            
            # Create application records
            if success:
                # Create EmailApplication record
                app_record = EmailApplication(
                    user_id=current_user.id,
                    learnership_email_id=email_entry.id,
                    status='sent'
                )
                db.session.add(app_record)
                
                # Create enhanced Application record with Gmail tracking
                std_app = Application(
                    user_id=current_user.id,
                    company_name=email_entry.company_name,
                    learnership_name="Email Application",
                    status='sent'
                )
                
                # Add Gmail tracking fields if they exist
                if hasattr(std_app, 'email_status'):
                    std_app.email_status = 'sent'
                if hasattr(std_app, 'sent_at'):
                    std_app.sent_at = datetime.utcnow()
                if hasattr(std_app, 'gmail_message_id'):
                    std_app.gmail_message_id = gmail_data.get('id')
                if hasattr(std_app, 'gmail_thread_id'):
                    std_app.gmail_thread_id = gmail_data.get('threadId')
                if hasattr(std_app, 'has_response'):
                    std_app.has_response = False
                if hasattr(std_app, 'response_thread_count'):
                    std_app.response_thread_count = 0
                
                db.session.add(std_app)
                successful_companies.append(email_entry.company_name)
                
                # Count successful Gmail tracking
                if gmail_data.get('id'):
                    gmail_tracked_count += 1
                    
            else:
                # Create records but mark as failed
                app_record = EmailApplication(
                    user_id=current_user.id,
                    learnership_email_id=email_entry.id,
                    status='failed'
                )
                db.session.add(app_record)
                
                std_app = Application(
                    user_id=current_user.id,
                    company_name=email_entry.company_name,
                    learnership_name="Email Application",
                    status='pending'
                )
                
                if hasattr(std_app, 'email_status'):
                    std_app.email_status = 'failed'
                
                db.session.add(std_app)
                
                if "timed out" in message.lower() or "timeout" in message.lower():
                    timeout_companies.append(email_entry.company_name)
                else:
                    failed_companies.append(email_entry.company_name)
                
            # Commit after each application to prevent losing all if one fails
            db.session.commit()
                
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error processing application to {email_entry.company_name}: {str(e)}")
            
            if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                timeout_companies.append(email_entry.company_name)
            else:
                failed_companies.append(email_entry.company_name)
    
    # Enhanced feedback with Gmail tracking info
    if successful_companies:
        if len(successful_companies) <= 5:
            base_message = f"Successfully sent applications to: {', '.join(successful_companies)}"
        else:
            base_message = f"Successfully sent applications to {len(successful_companies)} companies!"
        
        # Add Gmail tracking info
        if gmail_tracked_count > 0:
            base_message += f" ({gmail_tracked_count} tracked via Gmail for status updates)"
        
        flash(base_message, 'success')
    
    if timeout_companies:
        if len(timeout_companies) <= 3:
            flash(f"Network timeout when sending to: {', '.join(timeout_companies)}. Please try these again later.", 'warning')
        else:
            flash(f"Network timeout when sending to {len(timeout_companies)} companies. Please check your internet connection and try again later.", 'warning')
    
    if failed_companies:
        if len(failed_companies) <= 3:
            flash(f"Failed to send applications to: {', '.join(failed_companies)}", 'error')
        else:
            flash(f"Failed to send applications to {len(failed_companies)} companies due to errors.", 'error')
    
    if already_applied:
        if len(already_applied) <= 3:
            flash(f"You've already applied to: {', '.join(already_applied)}", 'info')
        else:
            flash(f"You've already applied to {len(already_applied)} of the selected companies.", 'info')
    
    # Enhanced retry instructions
    if timeout_companies:
        flash("Applications that failed due to network timeouts can be retried from your Applications page.", 'info')
    
    # Gmail status update info
    if gmail_tracked_count > 0:
        flash(f"🔔 {gmail_tracked_count} applications are now being tracked for responses via Gmail!", 'info')
    
    return redirect(url_for('my_applications'))

# =============================================================================
# EMAIL SENDING FUNCTIONS
# =============================================================================
def send_application_email(recipient_email, company_name, user):
    """Send an application email to a company using Gmail API with OAuth"""
    from mailer import build_credentials, create_message_with_attachments, send_gmail_message
    from models import GoogleToken
    from socket import timeout
    
    # Prepare email content
    subject = f"Learnership Application from {user.full_name or user.email}"
    
    body = f"""
Dear {company_name}'s hiring team,

I would like to apply for any available learnership opportunities in your organization.

Applicant Details:
Name: {user.full_name or 'Not provided'}
Email: {user.email}
Phone: {user.phone or 'Not provided'}

Please find my CV and supporting documents attached for your consideration.

Thank you for your time and consideration. I look forward to the possibility of contributing to your team.

Kind regards,
{user.full_name or user.email}
    """
    
    try:
        # Get user's OAuth token
        token_row = GoogleToken.query.filter_by(user_id=user.id).first()
        if not token_row:
            print(f"No Google token found for user {user.id}")
            return False, "Google authorization required"
        
        print(f"Found token for user {user.id}, token length: {len(token_row.token_json)}")
        
        # Build credentials for Gmail API
        credentials = build_credentials(token_row.token_json)
        
        # Get user's documents for attachments
        documents = Document.query.filter_by(user_id=user.id, is_active=True).all()
        file_paths = []
        for doc in documents:
            if os.path.exists(doc.file_path):
                file_paths.append({
                    'path': doc.file_path,
                    'filename': doc.original_filename
                })
        
        print(f"Found {len(file_paths)} attachments for user {user.id}")
        
        # Create email message
        message = create_message_with_attachments(
            user.email,
            recipient_email,
            subject,
            body,
            file_paths
        )
        
        # Send with timeout handling and retries
        try:
            result = send_gmail_message(credentials, message, max_retries=3, retry_delay=2)
            print(f"Email sent with result: {result}")
            return True, "Email sent successfully"
        except (timeout, TimeoutError) as e:
            print(f"Email sending timed out after retries: {str(e)}")
            app.logger.error(f"Email timeout error to {recipient_email}: {str(e)}")
            return False, "Connection timed out. Please try again later."
        except Exception as e:
            print(f"Error in Gmail API: {str(e)}")
            app.logger.error(f"Gmail API error: {str(e)}")
            if "quota" in str(e).lower():
                return False, "Email quota exceeded. Please try again tomorrow."
            return False, f"Email sending error: {str(e)}"
        
    except Exception as e:
        print(f"Error sending email to {recipient_email}: {str(e)}")
        app.logger.error(f"Error sending email: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, f"Error preparing email: {str(e)}"


def bulk_send_job(app, user_id, learnerships, attachment_ids):
    """Background job to send application emails"""
    with app.app_context():
        try:
            # Import necessary modules within app context
            from models import User, Document, Application, ApplicationDocument, GoogleToken, db
            from mailer import build_credentials, create_message_with_attachments, send_gmail_message
            
            print(f"Starting bulk send job for user {user_id} with {len(learnerships)} learnerships")
            
            # Get user and verify existence
            user = User.query.get(user_id)
            if not user:
                print(f"User {user_id} not found")
                return
            
            # Get Google token for Gmail API
            token_row = GoogleToken.query.filter_by(user_id=user.id).first()
            if not token_row:
                print(f"No Google token for user {user_id}")
                return
                
            # Build Gmail API credentials
            credentials = build_credentials(token_row.token_json)
            
            # Get documents for attachments
            docs = Document.query.filter(
                Document.id.in_(attachment_ids),
                Document.user_id == user.id,
                Document.is_active == True
            ).all()
            
            if not docs:
                print(f"No valid documents found for user {user_id}")
            
            # Prepare file paths for attachments
            file_paths = [
                {'path': doc.file_path, 'filename': doc.original_filename}
                for doc in docs
            ]
            
            # Process each learnership application
            for lr in learnerships:
                try:
                    print(f"Processing application for learnership: {lr.get('title')}")
                    
                    # Create application record
                    new_application = Application(
                        user_id=user.id,
                        status='processing'
                    )
                    
                    # Set optional fields if available
                    if 'id' in lr:
                        new_application.learnership_id = lr.get('id')
                    if 'title' in lr:
                        new_application.learnership_name = lr.get('title')
                    if 'company' in lr:
                        new_application.company_name = lr.get('company')
                    
                    # Save application to database
                    db.session.add(new_application)
                    db.session.commit()
                    print(f"Application created with ID: {new_application.id}")
                    
                    # Add document associations
                    for doc in docs:
                        attachment = ApplicationDocument(
                            application_id=new_application.id,
                            document_id=doc.id
                        )
                        db.session.add(attachment)
                    
                    db.session.commit()
                    print(f"Added {len(docs)} document associations")
                    
                    # Verify learnership has email address
                    apply_email = lr.get('apply_email')
                    if not apply_email:
                        print(f"Missing apply_email for learnership {lr.get('id')}")
                        new_application.status = 'error'
                        db.session.commit()
                        continue
                    
                    # Prepare email content
                    subject = f"Application for {lr.get('title')} – {user.full_name or user.email}"
                    body = f"""Dear Hiring Team at {lr.get('company')},

I am writing to express my interest in the {lr.get('title')} position at {lr.get('company')}.

{getattr(user, 'email_body', '')}

Please find my documents attached. I look forward to discussing how my skills and experience align with this opportunity.

Kind regards,
{user.full_name or user.email}
{f"Phone: {user.phone}" if hasattr(user, 'phone') and user.phone else ''}
Email: {user.email}
"""
                    
                    try:
                        # Create and send email message
                        message = create_message_with_attachments(
                            user.email,
                            apply_email,
                            subject,
                            body,
                            file_paths
                        )
                        
                        result = send_gmail_message(credentials, message)
                        print(f"Email sent with result: {result}")
                        
                        # Update application status to submitted
                        new_application.status = 'submitted'
                        db.session.commit()
                        print(f"Application status updated to 'submitted'")
                        
                    except Exception as e:
                        # Handle email sending errors
                        print(f"Failed to send email: {str(e)}")
                        new_application.status = 'error'
                        db.session.commit()
                        print(f"Application status updated to 'error'")
                    
                except Exception as e:
                    print(f"Error processing application: {str(e)}")
                    import traceback
                    print(traceback.format_exc())
                    db.session.rollback()
                    
                # Add delay between emails to avoid rate limiting
                time.sleep(1)
                
        except Exception as e:
            print(f"Bulk send job error: {str(e)}")
            import traceback
            print(traceback.format_exc())


# =============================================================================
# ADMIN DASHBOARD AND MANAGEMENT ROUTES
# =============================================================================

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    """Admin dashboard with system overview and management tools"""
    try:
        print("=== ADMIN DASHBOARD ROUTE ===")
        
        # Fetch all system data
        users = User.query.all()
        applications = Application.query.all()
        
        # Use the existing LearnshipEmail data as learnerships
        learnerships = LearnshipEmail.query.filter_by(is_active=True).all()
        
        # Debug output
        print(f"DEBUG: Found {len(users)} users")
        print(f"DEBUG: Found {len(learnerships)} learnerships from LearnshipEmail")
        print(f"DEBUG: Found {len(applications)} applications")
        
        # Show learnerships
        if learnerships:
            print("Learnerships from LearnshipEmail:")
            for i, l in enumerate(learnerships, 1):
                print(f"  {i}. {l.company_name} - {l.email}")
        else:
            print("⚠️  No learnerships found!")
        
        # Calculate statistics
        stats = {
            'total_users': len(users),
            'active_users': sum(1 for u in users if u.is_active),
            'total_learnerships': len(learnerships),
            'total_applications': len(applications)
        }
        
        # Get recent activity data
        recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
        recent_learnerships = LearnshipEmail.query.filter_by(is_active=True).order_by(LearnshipEmail.created_at.desc()).limit(5).all()
        recent_applications = Application.query.order_by(Application.submitted_at.desc()).limit(5).all()
        
        # Debug: Print what we're passing
        print(f"DEBUG: Passing {len(recent_learnerships)} recent learnerships:")
        for l in recent_learnerships:
            print(f"  - {l.company_name}: {l.email}")
        
        return render_template('admin_dashboard.html', 
                              users=users,
                              learnerships=learnerships,  # LearnshipEmail data
                              applications=applications,
                              stats=stats,
                              recent_users=recent_users,
                              recent_learnerships=recent_learnerships,
                              recent_applications=recent_applications,
                              current_user=current_user)
    
    except Exception as e:
        print(f"ERROR in admin_dashboard: {e}")
        import traceback
        traceback.print_exc()
        
        return render_template('admin_dashboard.html', 
                              users=[],
                              learnerships=[], 
                              applications=[],
                              stats={'total_users': 0, 'active_users': 0, 'total_learnerships': 0, 'total_applications': 0},
                              recent_users=[],
                              recent_learnerships=[],
                              recent_applications=[],
                              current_user=current_user)

# =============================================================================
# ADMIN USER MANAGEMENT ROUTES
# =============================================================================

# Add this near the top of your mailer.py
from httplib2 import Http
from googleapiclient.http import set_user_agent

def create_http_with_timeout(timeout=60):
    """Create an Http instance with increased timeout"""
    http = Http(timeout=timeout)
    return http

def send_gmail_message(credentials, message, max_retries=3, retry_delay=2):
    """Send a message via Gmail with longer timeout"""
    from googleapiclient.discovery import build
    
    # Use custom HTTP with longer timeout
    http = create_http_with_timeout(timeout=60)
    service = build('gmail', 'v1', credentials=credentials, http=http)
    
    # Rest of your function with retry logic...


# Add routes for privacy and terms
@app.route('/privacy')
def privacy_policy():
    return render_template('privacy_policy.html')
    
@app.route('/terms')
def terms_of_service():
    return render_template('terms_of_service.html')
    
@app.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user_status(user_id):
    """Toggle user active/inactive status"""
    user = User.query.get_or_404(user_id)
    
    # Security check - don't allow toggling other admin users
    if user.role == 'admin' and user.id != current_user.id:
        flash('Cannot modify admin user status', 'error')
        return redirect(url_for('admin_dashboard'))
    
    # Toggle user status
    user.is_active = not user.is_active
    
    try:
        db.session.commit()
        status = 'activated' if user.is_active else 'deactivated'
        flash(f'User {user.username or user.email} has been {status}', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error updating user status', 'error')
    
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Delete user and all associated data"""
    user = User.query.get_or_404(user_id)
    
    # Security check - don't delete admin users
    if user.role == 'admin':
        flash('Cannot delete admin users', 'error')
        return redirect(url_for('admin_dashboard'))
    
    try:
        # Delete user's physical document files
        documents = Document.query.filter_by(user_id=user_id).all()
        for doc in documents:
            if doc.file_path and os.path.exists(doc.file_path):
                try:
                    os.remove(doc.file_path)
                except Exception as e:
                    print(f"Error deleting file {doc.file_path}: {e}")
        
        # Delete database records (foreign key constraints handled by cascade)
        Application.query.filter_by(user_id=user_id).delete()
        Document.query.filter_by(user_id=user_id).delete()
        
        # Delete the user
        db.session.delete(user)
        db.session.commit()
        
        flash(f'User {user.username or user.email} has been deleted', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'error')
    
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    """Add new user to the system"""
    if request.method == 'POST':
        # Extract form data
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        role = request.form.get('role')
        is_active = 'is_active' in request.form
        
        # Validate form data
        if User.query.filter_by(email=email).first():
            flash('Email address already exists', 'error')
            return render_template('add_user.html')
        
        if username and User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return render_template('add_user.html')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('add_user.html')
        
        # Create new user
        new_user = User(
            email=email,
            username=username,
            full_name=full_name,
            phone=phone,
            role=role,
            is_active=is_active,
            auth_method='local',
            created_at=datetime.utcnow()
        )
        
        # Set encrypted password
        new_user.set_password(password)
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('User created successfully', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating user: {str(e)}', 'error')
            return render_template('add_user.html')
    
    return render_template('add_user.html')



@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    """Edit user information"""
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        # Update user data from form
        user.email = request.form.get('email')
        user.username = request.form.get('username')
        user.full_name = request.form.get('full_name')
        user.phone = request.form.get('phone')
        user.role = request.form.get('role')
        user.is_active = 'is_active' in request.form
        
        # Update password if provided
        new_password = request.form.get('new_password')
        if new_password:
            user.set_password(new_password)
        
        try:
            db.session.commit()
            flash('User updated successfully', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating user: {str(e)}', 'error')
    
    return render_template('edit_user.html', user=user)

@app.route('/admin/users/<int:user_id>/view')
@login_required
@admin_required
def view_user(user_id):
    """View detailed user information"""
    user = User.query.get_or_404(user_id)
    
    # Get user's applications and documents
    applications = Application.query.filter_by(user_id=user_id).all()
    documents = Document.query.filter_by(user_id=user_id).all()
    
    # Check file existence for each document
    for document in documents:
        if document.file_path:
            # Construct full file path
            if not os.path.isabs(document.file_path):
                full_file_path = os.path.join(app.config['UPLOAD_FOLDER'], document.file_path)
            else:
                full_file_path = document.file_path
            document.file_exists = os.path.exists(full_file_path)
        else:
            document.file_exists = False
    
    return render_template('view_user.html', 
                          user=user,
                          applications=applications,
                          documents=documents)

@app.route('/admin/documents/<int:document_id>/download')
@login_required
@admin_required
def download_document(document_id):
    """Download document file"""
    document = Document.query.get_or_404(document_id)
    
    # Construct full file path
    if document.file_path:
        # If file_path is relative, join with upload folder
        if not os.path.isabs(document.file_path):
            full_file_path = os.path.join(app.config['UPLOAD_FOLDER'], document.file_path)
        else:
            full_file_path = document.file_path
    else:
        full_file_path = None
    
    # Check if file exists
    if not full_file_path or not os.path.exists(full_file_path):
        flash('Document file not found', 'error')
        return redirect(request.referrer or url_for('admin_dashboard'))
    
    # Determine MIME type based on file extension
    mime_type = 'application/octet-stream'
    if document.original_filename:
        _, ext = os.path.splitext(document.original_filename)
        mime_types = {
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png'
        }
        mime_type = mime_types.get(ext.lower(), mime_type)
    
    # Return file for download
    return send_file(
        full_file_path, 
        mimetype=mime_type,
        as_attachment=True,
        download_name=document.original_filename or f'document-{document.id}{os.path.splitext(full_file_path)[1]}'
    )
        
# =============================================================================
# ADMIN LEARNERSHIP MANAGEMENT ROUTES
# =============================================================================
@app.route('/admin/toggle-learnership-status/<int:learnership_id>', methods=['POST'])
@login_required
@admin_required
def toggle_learnership_status(learnership_id):
    """Toggle the active status of a learnership email"""
    try:
        email = LearnshipEmail.query.get_or_404(learnership_id)
        email.is_active = not email.is_active
        db.session.commit()
        
        status = "activated" if email.is_active else "deactivated"
        flash(f'Learnership email for {email.company_name} has been {status}', 'success')
    except Exception as e:
        flash(f'Error toggling learnership email: {str(e)}', 'error')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/update-learnership-email/<int:email_id>', methods=['POST'])
@login_required
@admin_required
def update_learnership_email(email_id):
    """Update a learnership email via AJAX"""
    try:
        email = LearnshipEmail.query.get_or_404(email_id)
        data = request.get_json()
        
        # Validate email format
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        new_email = data.get('email', '').strip()
        
        if not re.match(email_pattern, new_email):
            return jsonify({'success': False, 'message': 'Invalid email format'})
        
        # Update the fields
        email.company_name = data.get('company_name', '').strip()
        email.email = new_email
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Learnership email updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})
    

@app.route('/admin/learnerships/<int:learnership_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_learnership(learnership_id):
    """Delete learnership and update related applications"""
    learnership = Learnership.query.get_or_404(learnership_id)
    
    try:
        # Update applications that reference this learnership
        applications = Application.query.filter_by(learnership_id=learnership_id).all()
        for app in applications:
            # Store learnership details before deleting the relationship
            app.learnership_name = learnership.title
            app.company_name = learnership.company
            app.learnership_id = None
        
        # Delete the learnership
        db.session.delete(learnership)
        db.session.commit()
        
        flash(f'Learnership "{learnership.title}" has been deleted', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting learnership: {str(e)}', 'error')
    
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/learnerships/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_learnership():
    """Add new learnership to the system"""
    if request.method == 'POST':
        # Extract form data
        title = request.form.get('title')
        company = request.form.get('company')
        category = request.form.get('category')
        location = request.form.get('location')
        duration = request.form.get('duration')
        stipend = request.form.get('stipend')
        closing_date_str = request.form.get('closing_date')
        description = request.form.get('description')
        requirements = request.form.get('requirements')
        is_active = 'is_active' in request.form
        
        # Parse closing date
        try:
            closing_date = datetime.strptime(closing_date_str, '%Y-%m-%d') if closing_date_str else None
        except ValueError:
            flash('Invalid closing date format. Please use YYYY-MM-DD.', 'error')
            return render_template('add_learnership.html')
        
        # Create new learnership
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
            is_active=is_active
        )
        
        try:
            db.session.add(new_learnership)
            db.session.commit()
            flash('Learnership created successfully', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating learnership: {str(e)}', 'error')
            return render_template('add_learnership.html')
    
    return render_template('add_learnership.html')


@app.route('/admin/learnerships/<int:learnership_id>/view')
@login_required
@admin_required
def view_learnership(learnership_id):
    """View detailed learnership information"""
    learnership = Learnership.query.get_or_404(learnership_id)
    
    # Get applications for this learnership
    applications = Application.query.filter_by(learnership_id=learnership_id).all()
    
    return render_template('view_learnership.html',
                          learnership=learnership,
                          applications=applications)


@app.route('/admin/learnerships/<int:learnership_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_learnership(learnership_id):
    """Edit learnership information"""
    learnership = Learnership.query.get_or_404(learnership_id)
    
    if request.method == 'POST':
        # Update learnership data from form
        learnership.title = request.form.get('title')
        learnership.company = request.form.get('company')
        learnership.category = request.form.get('category')
        learnership.location = request.form.get('location')
        learnership.duration = request.form.get('duration')
        learnership.stipend = request.form.get('stipend')
        
        # Parse closing date
        closing_date_str = request.form.get('closing_date')
        try:
            learnership.closing_date = datetime.strptime(closing_date_str, '%Y-%m-%d') if closing_date_str else None
        except ValueError:
            flash('Invalid date format for closing date', 'error')
            return render_template('edit_learnership.html', learnership=learnership)
            
        learnership.description = request.form.get('description')
        learnership.requirements = request.form.get('requirements')
        learnership.is_active = 'is_active' in request.form
        
        try:
            db.session.commit()
            flash('Learnership updated successfully', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating learnership: {str(e)}', 'error')
    
    return render_template('edit_learnership.html', learnership=learnership)


# =============================================================================
# ADMIN APPLICATION MANAGEMENT ROUTES
# =============================================================================


@app.route('/admin/applications/<int:application_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_application(application_id):
    """Delete application record"""
    application = Application.query.get_or_404(application_id)
    
    try:
        db.session.delete(application)
        db.session.commit()
        flash('Application has been deleted', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting application: {str(e)}', 'error')
    
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/applications/<int:application_id>/view')
@login_required
@admin_required
def view_application(application_id):
    """View detailed application information"""
    application = Application.query.get_or_404(application_id)
    
    # Get documents associated with this application
    application_documents = ApplicationDocument.query.filter_by(application_id=application_id).all()
    
    return render_template('view_application.html',
                          application=application,
                          application_documents=application_documents)



# =============================================================================
# DATABASE INITIALIZATION FUNCTIONS
# =============================================================================

def init_db():
    """Initialize database with tables and default admin user"""
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Create default admin user if it doesn't exist
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                email='admin@codecraftco.com',
                username='admin',
                full_name='System Administrator',
                role='admin',
                auth_method='credentials',
                is_active=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully!")


from learnership_emails import learnership_email_data

def init_learnership_emails():
    """Initialize the database with learnership email addresses"""
    with app.app_context():
        if LearnshipEmail.query.first() is not None:
            print("Learnership emails already exist in database. Skipping initialization.")
            return
        
        # Deduplicate by email (case-insensitive)
        seen_emails = set()
        unique_email_data = []
        for data in learnership_email_data:
            email_lower = data["email"].lower()
            if email_lower not in seen_emails:
                seen_emails.add(email_lower)
                unique_email_data.append(data)

        # Add unique email addresses to the database
        for data in unique_email_data:
            email = LearnshipEmail(
                company_name=data["company_name"],
                email=data["email"],
                is_active=True
            )
            db.session.add(email)
        
        try:
            db.session.commit()
            print(f"Added {len(unique_email_data)} learnership emails to the database")
        except Exception as e:
            db.session.rollback()
            print(f"Error adding learnership emails: {e}")


def safe_db_init():
    """Safely initialize database with error handling"""
    try:
        with app.app_context():
            # Create all database tables
            db.create_all()
            
            # Create default admin user
            admin = User.query.filter_by(username='admin').first()
            if not admin:
                admin = User(
                    email='admin@codecraftco.com',
                    username='admin',
                    full_name='System Administrator',
                    role='admin',
                    auth_method='credentials',
                    is_active=True
                )
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                print("Admin user created successfully!")
            
            # Initialize learnership emails
            init_learnership_emails()  # Add this line
            
    except Exception as e:
        print(f"Database initialization error: {e}")


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def allowed_file(filename):
    """Check if uploaded file has allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def url_for_map():
    """Helper function to get URL mapping for debugging"""
    from flask import current_app
    return {rule.endpoint: rule for rule in current_app.url_map.iter_rules()}


# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    db.session.rollback()
    return render_template('errors/500.html'), 500



@app.errorhandler(Exception)
def handle_exception(e):
    """Handle all unhandled exceptions"""
    # Log the error for debugging
    app.logger.error(f'Unhandled Exception: {str(e)}', exc_info=True)
    
    # Return generic error message to user
    return render_template('errors/500.html'), 500


# =============================================================================
# CONTEXT PROCESSORS
# =============================================================================

@app.context_processor
def inject_user():
    """Inject current user into all templates"""
    return dict(current_user=current_user)


@app.context_processor
def utility_processor():
    """Inject utility functions into templates"""
    def format_datetime(dt):
        """Format datetime for display"""
        if dt:
            return dt.strftime('%Y-%m-%d %H:%M')
        return 'N/A'
    
    def format_date(dt):
        """Format date for display"""
        if dt:
            return dt.strftime('%Y-%m-%d')
        return 'N/A'
    
    def format_file_size(size):
        """Format file size in human readable format"""
        if size is None:
            return 'Unknown'
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
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

@app.template_filter('datetime')
def datetime_filter(dt):
    """Template filter for datetime formatting"""
    if dt:
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    return 'N/A'


@app.template_filter('date')
def date_filter(dt):
    """Template filter for date formatting"""
    if dt:
        return dt.strftime('%Y-%m-%d')
    return 'N/A'


@app.template_filter('filesize')
def filesize_filter(size):
    """Template filter for file size formatting"""
    if size is None:
        return 'Unknown'
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


# =============================================================================
# BEFORE REQUEST HANDLERS
# =============================================================================

@app.before_request
def before_request():
    """Execute before each request"""
    # Update user's last activity if authenticated
    if current_user.is_authenticated:
        current_user.last_activity = datetime.utcnow()
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error updating last activity: {e}")


# =============================================================================
# APPLICATION STARTUP
# =============================================================================

# Initialize database when application starts
if __name__ == '__main__' or os.environ.get('RENDER'):
    safe_db_init()


# =============================================================================
# MAIN APPLICATION RUNNER
# =============================================================================

if __name__ == '__main__':
    # Run the application
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    ) 