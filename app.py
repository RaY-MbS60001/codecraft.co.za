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

def get_database_url():
    database_url = os.environ.get('DATABASE_URL')

    if not database_url:
        print("⚠️ DATABASE_URL not set. Falling back to SQLite for local development.")
        return f"sqlite:///{instance_path / 'codecraft.db'}"

    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    try:
        host = database_url.split('@')[1].split('/')[0]
        socket.gethostbyname(host)
    except (IndexError, socket.gaierror):
        print("⚠️ Could not resolve hostname. Using external Render DB hostname.")
        database_url = database_url.replace(
            'dpg-d1lknv6r433s73drf130-a',
            'dpg-d1lknv6r433s73drf130-a.oregon-postgres.render.com'
        )

    return database_url


# =============================================================================
# LOAD CONFIGURATION
# =============================================================================

# Load configuration based on environment
if os.environ.get('FLASK_ENV') == 'production':
    app.config.from_object(ProductionConfig)
else:
    app.config.from_object(DevelopmentConfig)

# Database configuration (ONLY SET ONCE)
app.config['SQLALCHEMY_DATABASE_URI'] = get_database_url()
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
    'connect_args': {
        'sslmode': 'require',
        'connect_timeout': 10,
    }
}
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
        'static', 'login', 'register', 'forgot_password', 
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
    """Home page - redirect to appropriate dashboard"""
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard' if current_user.role == 'admin' else 'user_dashboard'))
    return redirect(url_for('login'))


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
            
            # Clear any existing session for this user
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
                return redirect(url_for('user_dashboard'))
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
    
    return redirect(url_for('login'))


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
        return redirect(url_for('user_dashboard', login='success'))

        
    except Exception as e:
        print(f"OAuth callback error: {e}")
        import traceback
        traceback.print_exc()
        flash('Authentication failed. Please try again.', 'error')
        return redirect(url_for('login'))



# =============================================================================
# USER DASHBOARD AND PROFILE ROUTES
# =============================================================================

@app.route('/user/dashboard')
@login_required
def user_dashboard():
    """User dashboard with overview of applications and documents"""
    # Get user's recent applications
    recent_applications = Application.query.filter_by(user_id=current_user.id)\
        .order_by(Application.created_at.desc()).limit(5).all()
    
    # Get user's documents count
    documents_count = Document.query.filter_by(user_id=current_user.id, is_active=True).count()
    
    return render_template('user_dashboard.html', 
                         user=current_user,
                         recent_applications=recent_applications,
                         documents_count=documents_count)

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


@app.route('/user/applications')
@login_required
def my_applications():
    """Display user's applications grouped by status"""
    # Get all user's applications
    applications = Application.query.filter_by(user_id=current_user.id)\
        .order_by(Application.created_at.desc()).all()
    
    # Group applications by status
    grouped_applications = {
        'pending': [],
        'submitted': [],
        'reviewed': [],
        'accepted': [],
        'rejected': []
    }
    
    for app in applications:
        if app.status in grouped_applications:
            grouped_applications[app.status].append(app)
    
    return render_template('my_applications.html', 
                         applications=applications,
                         grouped_applications=grouped_applications)


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

@app.route('/learnerships/emails')
@login_required
def learnership_emails():
    """Display list of learnership email addresses for bulk applications"""
    learnership_emails = LearnshipEmail.query.filter_by(is_active=True)\
        .order_by(LearnshipEmail.company_name).all()
    return render_template('learnerships.html', learnership_emails=learnership_emails)


@app.route('/apply_bulk_email', methods=['POST'])
@login_required
def apply_bulk_email():
    """Process bulk application to selected email addresses"""
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
            # Send application email with timeout handling
            success, message = send_application_email(
                email_entry.email,
                email_entry.company_name,
                current_user
            )
            
            # Create application records
            if success:
                # Create EmailApplication record
                app = EmailApplication(
                    user_id=current_user.id,
                    learnership_email_id=email_entry.id,
                    status='sent'
                )
                db.session.add(app)
                
                # Create standard Application record for dashboard tracking
                std_app = Application(
                    user_id=current_user.id,
                    company_name=email_entry.company_name,
                    learnership_name="Email Application",
                    status='sent'
                )
                db.session.add(std_app)
                
                successful_companies.append(email_entry.company_name)
                
            else:
                # Create records but mark as failed
                app = EmailApplication(
                    user_id=current_user.id,
                    learnership_email_id=email_entry.id,
                    status='failed'
                )
                db.session.add(app)
                
                std_app = Application(
                    user_id=current_user.id,
                    company_name=email_entry.company_name,
                    learnership_name="Email Application",
                    status='pending'  # Could be retried later
                )
                db.session.add(std_app)
                
                if "timed out" in message.lower() or "timeout" in message.lower():
                    timeout_companies.append(email_entry.company_name)
                else:
                    failed_companies.append(email_entry.company_name)
                
            # Commit after each application to prevent losing all if one fails
            db.session.commit()
                
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error processing application to {email_entry.company_name}: {str(e)}")
            
            if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                timeout_companies.append(email_entry.company_name)
            else:
                failed_companies.append(email_entry.company_name)
    
    # Provide detailed feedback to user
    if successful_companies:
        if len(successful_companies) <= 5:
            flash(f"Successfully sent applications to: {', '.join(successful_companies)}", 'success')
        else:
            flash(f"Successfully sent applications to {len(successful_companies)} companies!", 'success')
    
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
    
    # Add retry instructions if there were timeouts
    if timeout_companies:
        flash("Applications that failed due to network timeouts can be retried from your Applications page.", 'info')
    
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

@app.route('/admin/applications/<int:application_id>/status/<status>', methods=['POST'])
@login_required
@admin_required
def update_application_status(application_id, status):
    """Update application status"""
    if status not in ['pending', 'approved', 'rejected']:
        flash('Invalid status', 'error')
        return redirect(url_for('admin_dashboard'))
    
    application = Application.query.get_or_404(application_id)
    application.status = status
    application.updated_at = datetime.utcnow()
    
    try:
        db.session.commit()
        flash(f'Application status updated to {status}', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error updating application status', 'error')
    
    return redirect(url_for('admin_dashboard'))


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


def init_learnership_emails():
    """Initialize the database with learnership email addresses"""
    with app.app_context():
        # Check if emails already exist to avoid duplicates
        if LearnshipEmail.query.first() is not None:
            print("Learnership emails already exist in database. Skipping initialization.")
            return
        
        # Comprehensive list of learnership email addresses
        email_data = [
            {"company_name": "TEST MAIL", "email": "sfisomabaso12242001@gmail.com"},
            {"company_name": "Diversity Empowerment", "email": "Info@diversityempowerment.co.za"},
            {"company_name": "Sparrow Portal", "email": "Enquiries@sparrowportal.co.za"},
            {"company_name": "Impactful", "email": "Sihle.Nyanga@impactful.co.za"},
            {"company_name": "CSG Skills", "email": "mseleke@csgskills.co.za"},
            {"company_name": "AFREC", "email": "Consultant@afrec.co.za"},
            {"company_name": "Vision Academy", "email": "recruit@visionacademy.co.za"},
            {"company_name": "The Skills Hub", "email": "info@theskillshub.co.za"},
            {"company_name": "Rivoningo Consultancy", "email": "careers@rivoningoconsultancy.co.za"},
            {"company_name": "OKS", "email": "Recruitment@oks.co.za"},
            {"company_name": "I-Fundi", "email": "Farina.bowen@i-fundi.com"},
            {"company_name": "MSC", "email": "za031-cvapplications@msc.com"},
            {"company_name": "Liberty College", "email": "Funda@liberty-college.co.za"},
            {"company_name": "Sisekelo", "email": "ayandam@sisekelo.co.za"},
            {"company_name": "AAAT", "email": "apply@aaat.co.za"},
            {"company_name": "Learn SETA", "email": "hr@learnseta.online"},
            {"company_name": "Amphisa", "email": "tigane@amphisa.co.za"},
            {"company_name": "AfriSam", "email": "cm.gpnorthaggregate@za.afrisam.com"},
            {"company_name": "iLearn", "email": "tinyikom@ilearn.co.za"},
            {"company_name": "TechTISA", "email": "prabashini@techtisa.co.za"},
            {"company_name": "Fitho", "email": "cv@fitho.co.za"},
            {"company_name": "Training Force", "email": "Application@trainingforce.co.za"},
            {"company_name": "Tidy Swip", "email": "Learnerships@tidyswip.co.za"},
            {"company_name": "Nthuse Foundation", "email": "brandons@nthusefoundation.co.za"},
            {"company_name": "Ample Recruitment", "email": "cv@amplerecruitment.co.za"},
            {"company_name": "I-People", "email": "cv@i-people.co.za"},
            {"company_name": "FACT SA", "email": "recruitment3@factsa.co.za"},
            {"company_name": "IKWorx", "email": "recruitment@ikworx.co.za"},
            {"company_name": "APD JHB", "email": "recruitment@apdjhb.co.za"},
            {"company_name": "Skill Tech SA", "email": "query@skilltechsa.co.za"},
            {"company_name": "Camblish", "email": "qualitycontrol@camblish.co.za"},
            {"company_name": "BPC HR Solutions", "email": "Queen@bpchrsolutions.co.za"},
            {"company_name": "CTU Training", "email": "walter.mngomezulu@ctutraining.co.za"},
            {"company_name": "U-Belong", "email": "work@u-belong.co.za"},
            {"company_name": "eStudy SA", "email": "recruitment@estudysa.co.za"},
            {"company_name": "Zigna Training Online", "email": "ayo@zignatrainingonline.co.za"},
            {"company_name": "CDPA", "email": "amelia@cdpa.co.za"},
            {"company_name": "AFREC", "email": "Cv@afrec.co.za"},
            {"company_name": "AFREC", "email": "recruit@afrec.co.za"},
            {"company_name": "AFREC", "email": "recruitment@afrec.co.za"},
            {"company_name": "AFREC", "email": "Cvs@afrec.co.za"},
            {"company_name": "Bidvest Catering", "email": "Training2@bidvestcatering.co.za"},
            {"company_name": "CDA Solutions", "email": "faith.khethani@cdasolutions.co.za"},
            {"company_name": "Tiger Brands", "email": "Culinary.Recruitment@tigerbrands.com"},
            {"company_name": "Telebest", "email": "learners@telebest.co.za"},
            {"company_name": "Access4All SA", "email": "ginab@access4all-sa.co.za"},
            {"company_name": "GLU", "email": "cv@glu.co.za"},
            {"company_name": "GLU", "email": "ilze@glu.co.za"},
            {"company_name": "CSS Solutions", "email": "csshr@csssolutions.co.za"},
            {"company_name": "Advanced Assessments", "email": "genevieve@advancedassessments.co.za"},
            {"company_name": "AAAT", "email": "Jonas@aaat.co.za"},
            {"company_name": "Prime Serv", "email": "Infoct@primeserv.co.za"},
            {"company_name": "TE Academy", "email": "recruitmentofficer@teacademy.co.za"},
            {"company_name": "Retshepeng", "email": "training@retshepeng.co.za"},
            {"company_name": "KDS Training", "email": "Recruitment@kdstraining.co.za"},
            {"company_name": "Cowhirla Academy", "email": "learn@cowhirlacademy.co.za"},
            {"company_name": "Roah Consulting", "email": "recruitment@roahconsulting.co.za"},
            {"company_name": "Kboneng Consulting", "email": "admin@kbonengconsulting.co.za"},
            {"company_name": "NZ Consultants", "email": "victory@nzconsultancts.co.za"},
            {"company_name": "AAAT", "email": "Leratomoraba@aaat.co.za"},
            {"company_name": "Stratism", "email": "learnership@stratism.co.za"},
            {"company_name": "MPower Smart", "email": "recruitment@mpowersmart.co.za"},
            {"company_name": "Afrika Tikkun", "email": "LucyC@afrikatikkun.org"},
            {"company_name": "WeThinkCode", "email": "Info@wethinkcode.co.za"},
            {"company_name": "B School", "email": "justice.seupe@bschool.edu.za"},
            {"company_name": "TE Academy", "email": "sdf1@teacademy.co.za"},
            {"company_name": "African Bank", "email": "NMakazi@afrikanbank.co.za"},
            {"company_name": "Blind SA", "email": "trainingcentre.admin@blindsa.org.za"},
            {"company_name": "Pro-Learn", "email": "data.admin@pro-learn.co.za"},
            {"company_name": "Skills Junction", "email": "learnerships@skillsjunction.co.za"},
            {"company_name": "Friends 4 Life", "email": "achievement@friends4life.co.za"},
            {"company_name": "Dial A Dude", "email": "hr@dialadude.co.za"},
            {"company_name": "IBM SkillsBuild", "email": "ibmskillsbuild.emea@skilluponline.com"},
            {"company_name": "Snergy", "email": "info@snergy.co.za"},
            {"company_name": "SA Entrepreneurship Empowerment", "email": "samukelo@saentrepreneurshipempowerment.org.za"},
            {"company_name": "Signa", "email": "yes@signa.co.za"},
            {"company_name": "Edu-Wize", "email": "info@edu-wize.co.za"},
            {"company_name": "Edu-Wize", "email": "elsie@edu-wize.co.za"},
            {"company_name": "4YS", "email": "recruit@4ys.co.za"},
            {"company_name": "LeapCo", "email": "olwethu@leapco.co.za"},
            {"company_name": "LeapCo", "email": "Offer@leapco.co.za"},
            {"company_name": "Learnex", "email": "cv@learnex.co.za"},
            {"company_name": "Innovation Advance", "email": "hello@innovationadvance.co.za"},
            {"company_name": "Dynamic DNA", "email": "Talent@dynamicdna.co.za"},
            {"company_name": "NCPD", "email": "nombulelo@ncpd.org.za"},
            {"company_name": "Siyaya Skills", "email": "lebohang.matlala@siyayaskills.co.za"},
            {"company_name": "Transcend", "email": "learnerships@transcend.co.za"},
            {"company_name": "iLearn", "email": "Vusumuzig@ilearn.co.za"},
            {"company_name": "Barnne", "email": "cv@barnne.com"},
            {"company_name": "SASSETA", "email": "recruitment@sasseta.org"},
            {"company_name": "WPX Solutions", "email": "hr@wpxsolutions.com"},
            {"company_name": "Amphisa", "email": "Kruger@amphisa.co.za"},
            {"company_name": "TIHSA", "email": "faneleg@tihsa.co.za"},
            {"company_name": "Afrika Tikkun", "email": "pokellom@afrikatikkun.org"},
            {"company_name": "Swift Skills Academy", "email": "recruitment@swiftskillsacademy.co.za"},
            {"company_name": "Skills Panda", "email": "refiloe@skillspanda.co.za"},
            {"company_name": "ICAN SA", "email": "Nalini.cuppusamy@ican-sa.co.za"},
            {"company_name": "GCC-SD", "email": "placements@gcc-sd.com"},
            {"company_name": "EH Hassim", "email": "trainingcenter@ehhassim.co.za"},
            {"company_name": "Anova Health", "email": "Recruitment-parktown@anovahealth.co.za"},
            {"company_name": "iLearn", "email": "tshepisom@ilearn.co.za"},
            {"company_name": "Moonstone Info", "email": "faisexam@moonstoneinfo.co.za"},
            {"company_name": "Phosaane", "email": "recruitment@phosaane.co.za"},
            {"company_name": "Lethatsi PTY LTD", "email": "Luzuko@lethatsiptyltd.co.za"},
            {"company_name": "CBM Training", "email": "info@cbm-training.co.za"},
            {"company_name": "Bradshaw Leroux", "email": "Recruit@bradshawleroux.co.za"},
            {"company_name": "HRC Training", "email": "Info@Hrctraining.co.za"},
            {"company_name": "Bee Empowerment Services", "email": "Support@beeempowermentservices.co.za"},
            {"company_name": "Shimrag", "email": "lesegos@shimrag.co.za"},
            {"company_name": "TransUnion", "email": "Kgomotso.Modiba@transunion.com"},
            {"company_name": "Gijima", "email": "lebo.makgale@gijima.com"},
            {"company_name": "Eshy Brand", "email": "tumelo@eshybrand.co.za"},
            {"company_name": "Kunaku", "email": "learners@kunaku.co.za"},
            {"company_name": "Affinity Services", "email": "recruitment@affinityservices.co.za"},
            {"company_name": "CBM Training", "email": "Gugulethu@cbm-traning.co.za"},
            {"company_name": "TransUnion", "email": "GCCALearners@transunion.com"},
            {"company_name": "Quest College", "email": "Maria@questcollege.org.za"},
            {"company_name": "MI Centre", "email": "info@micentre.org.za"},
            {"company_name": "CBM Training", "email": "palesa@cbm-training.co.za"},
            {"company_name": "Consulting By Bongi", "email": "Info@consultingbybongi.com"},
            {"company_name": "Training Portal", "email": "learn@trainingportal.co.za"},
            {"company_name": "GCC-SD", "email": "info@gcc-sd.com"},
            {"company_name": "Retshepeng", "email": "Sales@retshepeng.co.za"},
            {"company_name": "Retshepeng", "email": "it@retshepeng.co.za"},
            {"company_name": "Tych", "email": "Precious@tych.co.za"},
            {"company_name": "Progression", "email": "farhana@progression.co.za"},
            {"company_name": "QASA", "email": "recruitment@qasa.co.za"},
            {"company_name": "TLO", "email": "Recruitment@tlo.co.za"},
            {"company_name": "Dibanisa Learning", "email": "Slindile@dibanisaleaening.co.za"},
            {"company_name": "Tric Talent", "email": "Anatte@trictalent.co.za"},
            {"company_name": "Novia One", "email": "Tai@noviaone.com"},
            {"company_name": "Edge Exec", "email": "kgotso@edgexec.co.za"},
            {"company_name": "Related Ed", "email": "kagiso@related-ed.com"},
            {"company_name": "RMA Education", "email": "Skills@rma.edu.co.za"},
            {"company_name": "Signa", "email": "nkhensani@signa.co.za"},
            {"company_name": "Learnex", "email": "joyce@learnex.co.za"},
            {"company_name": "XBO", "email": "cornelia@xbo.co.za"},
            {"company_name": "Nicasia Holdings", "email": "Primrose.mathe@nicasiaholdings.co.za"},
            {"company_name": "STS Africa", "email": "Recruitment@sts-africa.co.za"},
            {"company_name": "BSI Steel", "email": "Sifiso.ntamane@bsisteel.com"},
            {"company_name": "Progression", "email": "Recruitment@progression.co.za"},
            {"company_name": "Modern Centric", "email": "applications@moderncentric.co.za"},
            {"company_name": "Dynamic DNA", "email": "Smacaulay@dynamicdna.co.za"},
            {"company_name": "Dekra", "email": "reception@dekra.com"},
            {"company_name": "Quest College", "email": "patience@questcollege.org.za"},
            {"company_name": "Modern Centric", "email": "karenm@moderncentric.co.za"},
            {"company_name": "Octopi Renewed", "email": "IvyS@octopi-renewed.co.za"},
            {"company_name": "Eagle ESS", "email": "training2@eagle-ess.co.za"},
            {"company_name": "IBUSA", "email": "Mpumi.m@ibusa.co.za"},
            {"company_name": "RMV Solutions", "email": "Learnership@rmvsolutions.co.za"},
            {"company_name": "Talent Development", "email": "info@talentdevelooment.co.za"},
            {"company_name": "Transcend", "email": "unathi.mbiyoza@transcend.co.za"},
            {"company_name": "SEESA", "email": "helga@seesa.co.za"},
            {"company_name": "Skills Empire", "email": "admin@skillsempire.co.za"},
            {"company_name": "Foster Melliar", "email": "kutlwano.mothibe@fostermelliar.co.za"},
            {"company_name": "Alef Bet Learning", "email": "teddym@alefbetlearning.com"},
            {"company_name": "Pendula", "email": "rika@pendula.co.za"},
            {"company_name": "Siza Abantu", "email": "admin@sizaabantu.co.za"},
            {"company_name": "CBM Training", "email": "lorenzo@cbm-training.co.za"},
            {"company_name": "CBM Training", "email": "Winile@cbm-training.co.za"},
            {"company_name": "SERR", "email": "Maria@serr.co.za"},
            {"company_name": "CSG Skills", "email": "Sdube@csgskills.co.za"},
            {"company_name": "Modern Centric", "email": "kagisom@moderncentric.co.za"},
            {"company_name": "SITA", "email": "recruitment@sita.co.za"},
            {"company_name": "Mudi Training", "email": "kelvi.c@muditraining.co.za"},
            {"company_name": "Net Campus", "email": "Ntombi.Zondo@netcampus.com"},
            {"company_name": "Net Campus", "email": "Mary.carelse@netcampus.com"},
            {"company_name": "EduPower SA", "email": "divan@edupowersa.co.za"},
            {"company_name": "TLO", "email": "info@tlo.co.za"},
            {"company_name": "Liquor Barn", "email": "admin4@liquorbarn.co.za"},
            {"company_name": "King Rec", "email": "Zena@KingRec.co.za"},
            {"company_name": "Fennell", "email": "Hal@Fennell.co.za"},
            {"company_name": "SP Forge", "email": "Info@SpForge.co.za"},
            {"company_name": "Direct Axis", "email": "Careers@Directaxis.co.za"},
            {"company_name": "Benteler", "email": "Yasmin.theron@benteler.com"},
            {"company_name": "MASA", "email": "Pe@masa.co.za"},
            {"company_name": "MASA", "email": "Feziwe@masa.co.za"},
            {"company_name": "Adcorp Blu", "email": "Kasina.sithole@adcorpblu.com"},
            {"company_name": "Formex", "email": "enquiries@formex.co.za"},
            {"company_name": "Formex", "email": "byoyophali@formex.co.za"},
            {"company_name": "Q-Plas", "email": "Zandile@q-plas.co.za"},
            {"company_name": "Lumo Tech", "email": "contact@lumotech.co.za"},
            {"company_name": "Bel Essex", "email": "belcorp@belessex.co.za"},
            {"company_name": "Workforce", "email": "portelizabeth@workforce.co.za"},
            {"company_name": "Quest", "email": "lucilleh@quest.co.za"},
            {"company_name": "Top Personnel", "email": "reception@toppersonnel.co.za"},
            {"company_name": "MPC", "email": "rosanne@mpc.co.za"},
            {"company_name": "Online Personnel", "email": "claire@onlinepersonnel.co.za"},
            {"company_name": "Kelly", "email": "nicola.monsma@kelly.co.za"},
            {"company_name": "JR Recruitment", "email": "sandi@jrrecruitment.co.za"},
            {"company_name": "Ikamva Recruitment", "email": "nomsa@ikamvarecruitment.co.za"},
            {"company_name": "Abantu Staffing Solutions", "email": "tracy@abantustaffingsolutions.co.za"},
            {"company_name": "Alpha Labour", "email": "wayne@alphalabour.co.za"},
            {"company_name": "Thomas", "email": "jackiec@thomas.co.za"},
            {"company_name": "Capacity", "email": "nakitap@capacity.co.za"},
            {"company_name": "Colven", "email": "natalie@colven.co.za"},
            {"company_name": "Head Hunt", "email": "admin@headhunt.co.za"},
            {"company_name": "Icon", "email": "focus@icon.co.za"},
            {"company_name": "QS Africa", "email": "ADMIN@QSAFRICA.CO.ZA"},
            {"company_name": "CR Solutions", "email": "chantal@crsolutions.co.za"},
            {"company_name": "Bell Mark", "email": "zukiswa.nogqala@bell-mark.co.za"},
            {"company_name": "Pop Up", "email": "nokuthula.ndamase@popup.co.za"},
            {"company_name": "Seonnyatseng", "email": "Tsholofelo@seonyatseng.co.za"},
            {"company_name": "TN Electrical", "email": "info@tnelectrical.co.za"},
            {"company_name": "AAAA", "email": "adminb@aaaa.co.za"},
            {"company_name": "Ubuhle HR", "email": "reception@ubuhlehr.co.za"},
            {"company_name": "SITA", "email": "vettinginternship@sita.co.za"},
            {"company_name": "Careers IT", "email": "leanerships@careersit.co.za"},
            {"company_name": "TJH Business", "email": "melvin@tjhbusiness.co.za"},
            {"company_name": "Learner Sphere CD", "email": "recruitment@learnerspherecd.co.za"},
            {"company_name": "Odin Fin", "email": "alex@odinfin.co.za"},
            {"company_name": "Platinum Life", "email": "Manaka.Ramukuvhati@platinumlife.co.za"},
            {"company_name": "Seonnyatseng", "email": "info@seonyatseng.co.za"},
            {"company_name": "TLO", "email": "Application@tlo.co.za"},
            {"company_name": "Metanoia Group", "email": "Loren@metanoiagroup.co.za"},
            {"company_name": "Edu-Wize", "email": "r1@edu-wize.co.za"},
            {"company_name": "Advanced Assessments", "email": "recruitment@advancedassessments.co.za"},
            {"company_name": "Enpower", "email": "Angelique.haskins@enpower.co.za"},
            {"company_name": "ICAN SA", "email": "Jhbsourcing@ican-sa.co.za"},
            {"company_name": "Talent Development", "email": "Projects@talentdevelopment.co.za"},
            {"company_name": "Providing Skills", "email": "training1@providingskills.co.za"},
            {"company_name": "Providing Skills", "email": "thando@providingskills.co.za"},
            {"company_name": "Camblish", "email": "Info@camblish.co.za"},
            {"company_name": "Brightrock", "email": "Youniversity@brightrock.co.za"},
            {"company_name": "Heart Solutions", "email": "admin@heartsolutions.co.za"},
            {"company_name": "Star Schools", "email": "rnyoka@starschools.co.za"},
            {"company_name": "Modern Centric", "email": "malvinn@moderncentric.co.za"},
            {"company_name": "Skills Bureau", "email": "operations2@skillsbureau.co.za"},
            {"company_name": "Xtensive ICT", "email": "sphiwe@xtensiveict.co.za"},
            {"company_name": "Engen Oil", "email": "Learnerships@engenoil.com"},
            {"company_name": "GLU", "email": "ouma@glu.co.za"},
            {"company_name": "ICAN SA", "email": "Pretty.Dlamini@ican-sa.co.za"},
            {"company_name": "Vistech", "email": "skills@vistech.co.za"},
            {"company_name": "Gold Rush", "email": "mpho.moletsane@goldrurush.co.za"},
            {"company_name": "HCI Skills", "email": "recruitment@hciskills.co.za"},
            {"company_name": "PMI SA", "email": "boitumelo.makhubela@pmi-sa.co.za"},
            {"company_name": "Skills Bureau", "email": "talent@skillsbureau.co.za"},
            {"company_name": "Vital Online", "email": "training@vitalonline.co.za"},
            {"company_name": "Compare A Quote", "email": "Admin@compareaquote.co.za"},
            {"company_name": "Besec", "email": "cv@besec.co.za"},
            {"company_name": "eStudy SA", "email": "trainme@estudysa.co.za"},
            {"company_name": "Net Campus", "email": "info@netcampus.com"}
        ]
        
        # Add email addresses to the database
        for data in email_data:
            email = LearnshipEmail(
                company_name=data["company_name"], 
                email=data["email"],
                is_active=True
            )
            db.session.add(email)
        
        try:
            db.session.commit()
            print(f"Added {len(email_data)} learnership emails to the database")
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