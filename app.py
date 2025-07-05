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


# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# =============================================================================
# APPLICATION CONFIGURATION
# =============================================================================

class ProductionConfig(Config):
    """Production configuration for deployment on Render"""
    # Handle Render's PostgreSQL URL
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_DATABASE_URI = DATABASE_URL or Config.SQLALCHEMY_DATABASE_URI
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True
    }


def get_database_url():
    """
    Get the appropriate database URL for the environment
    Returns PostgreSQL URL for production, SQLite for development
    """
    # Handle Render PostgreSQL URL
    render_db_url = os.environ.get('DATABASE_URL', '')
    if render_db_url and render_db_url.startswith('postgres://'):
        render_db_url = render_db_url.replace('postgres://', 'postgresql://', 1)
    
    # Fallback to SQLite with absolute path for development
    if not render_db_url:
        base_dir = Path(__file__).resolve().parent
        instance_path = base_dir / 'instance'
        instance_path.mkdir(exist_ok=True, parents=True)
        sqlite_path = instance_path / 'app.db'
        return f'sqlite:///{sqlite_path}'
    
    return render_db_url


# =============================================================================
# FLASK APP INITIALIZATION
# =============================================================================

app = Flask(__name__)

app.config.from_object(Config)
    
    # Apply security middleware
add_security_headers(app)
    
# Determine base directory and setup paths
BASE_DIR = Path(__file__).resolve().parent
instance_path = BASE_DIR / 'instance'
instance_path.mkdir(exist_ok=True, parents=True)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = get_database_url()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Security configuration
app.config['SECRET_KEY'] = os.environ.get(
    'SECRET_KEY', 
    'e1f8c81a1e6f0c6e3b23a7d94d72f1f519d6e8f7b6a9d68a23c5c6f27e8ab3f54'
)
app.config['SESSION_COOKIE_SECURE'] = True
app.config['REMEMBER_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_NAME'] = 'codecraftco_session'

# Load additional configuration
app.config.from_object(Config)

# File upload configuration
UPLOAD_FOLDER = BASE_DIR / 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'}

app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directories exist
UPLOAD_FOLDER.mkdir(exist_ok=True)
(UPLOAD_FOLDER / 'documents').mkdir(exist_ok=True)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# OAuth configuration
oauth = None
google = None

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

@app.route('/')
def index():
    """Home page - redirect to appropriate dashboard"""
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard' if current_user.role == 'admin' else 'user_dashboard'))
    return redirect(url_for('login'))


@app.route('/login')
def login():
    """User login page"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
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
            user.last_login = datetime.utcnow()
            db.session.commit()
            login_user(user, remember=True)
            flash('Welcome back, Admin!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('admin_login.html', form=form)


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
        
        demo_user.last_login = datetime.utcnow()
        db.session.commit()
        login_user(demo_user, remember=True)
        flash('Logged in as Demo User (Google OAuth not configured)', 'warning')
        return redirect(url_for('user_dashboard'))
    
    # Redirect to Google OAuth
    return google.authorize_redirect(
        url_for('google_callback', _external=True),
        prompt='consent',
        access_type='offline'
    )


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
                profile_picture=profile_picture,
                role='user',
                auth_method='google',
                is_active=True
            )
            db.session.add(user)
        else:
            # Update existing user's profile picture if it's different or empty
            if profile_picture and (not user.profile_picture or user.profile_picture != profile_picture):
                user.profile_picture = profile_picture
        
        # Update user's last login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Log in the user
        login_user(user, remember=True)
        
        # Logging for debugging
        app.logger.info(f"User logged in: {user.email}")
        app.logger.info(f"Profile Picture: {user.profile_picture}")
        
        flash(f'Welcome, {user.full_name or user.email}!', 'success')
        return redirect(url_for('user_dashboard'))
        
    except Exception as e:
        print(f"OAuth callback error: {e}")
        flash('Authentication failed. Please try again.', 'error')
        return redirect(url_for('login'))


@app.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out.', 'info')
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
    applications_created = 0
    applications_failed = 0
    
    for email_entry in email_entries:
        # Check if application already exists
        existing_app = EmailApplication.query.filter_by(
            user_id=current_user.id,
            learnership_email_id=email_entry.id
        ).first()
        
        if existing_app:
            flash(f'You have already applied to {email_entry.company_name}', 'info')
            continue
        
        # Send application email
        email_sent = send_application_email(
            email_entry.email,
            email_entry.company_name,
            current_user
        )
        
        # Create application records if email was sent successfully
        if email_sent:
            # Create EmailApplication record
            app = EmailApplication(
                user_id=current_user.id,
                learnership_email_id=email_entry.id,
                status='sent'
            )
            db.session.add(app)
            
            # Create standard Application record
            std_app = Application(
                user_id=current_user.id,
                company_name=email_entry.company_name,
                learnership_name="Email Application",
                status='sent'
            )
            db.session.add(std_app)
            
            applications_created += 1
        else:
            applications_failed += 1
    
    db.session.commit()
    
    # Provide feedback to user
    if applications_created > 0:
        flash(f"Successfully sent applications to {applications_created} companies!", 'success')
    
    if applications_failed > 0:
        flash(f"Failed to send applications to {applications_failed} companies.", 'warning')
    
    return redirect(url_for('my_applications'))


# =============================================================================
# EMAIL SENDING FUNCTIONS
# =============================================================================

def send_application_email(recipient_email, company_name, user):
    """Send an application email to a company using Gmail API with OAuth"""
    from mailer import build_credentials, create_message_with_attachments, send_gmail_message
    from models import GoogleToken
    
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
            return False
            
        # Build credentials for Gmail API
        credentials = build_credentials(token_row.token_json)
        
        # Get user's documents for attachments
        documents = Document.query.filter_by(user_id=user.id, is_active=True).all()
        file_paths = []
        for doc in documents:
            file_paths.append({
                'path': doc.file_path,
                'filename': doc.original_filename
            })
        
        # Create and send email message
        message = create_message_with_attachments(
            user.email,
            recipient_email,
            subject,
            body,
            file_paths
        )
        
        result = send_gmail_message(credentials, message)
        print(f"Email sent with result: {result}")
        return True
        
    except Exception as e:
        print(f"Error sending email to {recipient_email}: {str(e)}")
        return False


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
    # Fetch all system data
    users = User.query.all()
    learnerships = Learnership.query.all()
    applications = Application.query.all()
    
    # Calculate statistics for dashboard
    stats = {
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'total_learnerships': Learnership.query.count(),
        'total_applications': Application.query.count()
    }
    
    # Get recent activity data
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_learnerships = Learnership.query.order_by(Learnership.created_at.desc()).limit(5).all()
    recent_applications = Application.query.order_by(Application.submitted_at.desc()).limit(5).all()
    
    return render_template('admin_dashboard.html', 
                          users=users,
                          learnerships=learnerships, 
                          applications=applications,
                          stats=stats,
                          recent_users=recent_users,
                          recent_learnerships=recent_learnerships,
                          recent_applications=recent_applications,
                          current_user=current_user)


# =============================================================================
# ADMIN USER MANAGEMENT ROUTES
# =============================================================================

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


@app.route('/admin/users/<int:user_id>/view')
@login_required
@admin_required
def view_user(user_id):
    """View detailed user information"""
    user = User.query.get_or_404(user_id)
    
    # Get user's applications and documents
    applications = Application.query.filter_by(user_id=user_id).all()
    documents = Document.query.filter_by(user_id=user_id).all()
    
    return render_template('view_user.html', 
                          user=user,
                          applications=applications,
                          documents=documents)


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


# =============================================================================
# ADMIN LEARNERSHIP MANAGEMENT ROUTES
# =============================================================================

@app.route('/admin/learnerships/<int:learnership_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_learnership_status(learnership_id):
    """Toggle learnership active/inactive status"""
    learnership = Learnership.query.get_or_404(learnership_id)
    
    # Toggle status
    learnership.is_active = not learnership.is_active
    
    try:
        db.session.commit()
        status = 'activated' if learnership.is_active else 'deactivated'
        flash(f'Learnership "{learnership.title}" has been {status}', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error updating learnership status', 'error')
    
    return redirect(url_for('admin_dashboard'))


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


@app.route('/admin/documents/<int:document_id>/download')
@login_required
@admin_required
def download_document(document_id):
    """Download document file"""
    document = Document.query.get_or_404(document_id)
    
    # Check if file exists
    if not document.file_path or not os.path.exists(document.file_path):
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
        document.file_path, 
        mimetype=mime_type,
        as_attachment=True,
        download_name=document.original_filename or f'document-{document.id}{os.path.splitext(document.file_path)[1]}'
    )


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

            {"company_name": "Tric Talent Recruitment", "email": "anatte@trictalent.co.za"},
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