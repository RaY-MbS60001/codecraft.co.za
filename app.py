from pathlib import Path
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from authlib.integrations.flask_client import OAuth
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from flask_wtf import FlaskForm
from wtforms import TextAreaField, SubmitField, SelectMultipleField, widgets
from wtforms.validators import Optional
import json, os, time
import logging
logging.basicConfig(level=logging.INFO)
from tasks import launch_bulk_send
from models import db, User, Learnership, Application, Document, ApplicationDocument, GoogleToken, LearnshipEmail, EmailApplication
# Add these imports at the top of your app.py file
from datetime import datetime
from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from config import Config
from forms import AdminLoginForm, EditProfileForm, ChangePasswordForm, ApplicationForm, DocumentUploadForm, LearnershipSearchForm
from decorators import admin_required
from dotenv import load_dotenv
load_dotenv()

# Configuration
class ProductionConfig(Config):
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


app = Flask(__name__)


# Determine base directory
BASE_DIR = Path(__file__).resolve().parent


# Ensure instance directory exists
instance_path = BASE_DIR / 'instance'
instance_path.mkdir(exist_ok=True, parents=True)

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{instance_path}/app.db')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL

# Database URL configuration with PostgreSQL support
if os.environ.get('RENDER'):
    # Render provides DATABASE_URL for PostgreSQL
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
else:
    # Fallback to SQLite for local development
    DATABASE_URL = f'sqlite:///{instance_path}/app.db'

import os
from pathlib import Path

# Determine base directory
BASE_DIR = Path(__file__).resolve().parent

# Ensure instance directory exists
instance_path = BASE_DIR / 'instance'
instance_path.mkdir(exist_ok=True, parents=True)

# Database URL configuration
def get_database_url():
    # Render PostgreSQL URL handling
    render_db_url = os.environ.get('DATABASE_URL', '')
    if render_db_url and render_db_url.startswith('postgres://'):
        render_db_url = render_db_url.replace('postgres://', 'postgresql://', 1)
    
    # Fallback to SQLite with absolute path
    sqlite_path = instance_path / 'app.db'
    return render_db_url or f'sqlite:///{sqlite_path}'

# Update app configuration
app.config['SQLALCHEMY_DATABASE_URI'] = get_database_url()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'e1f8c81a1e6f0c6e3b23a7d94d72f1f519d6e8f7b6a9d68a23c5c6f27e8ab3f54')

# Update app configuration
app.config['SQLALCHEMY_DATABASE_URI'] = get_database_url()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


# Common configuration
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Update app configuration
app.config['SESSION_COOKIE_SECURE'] = True
app.config['REMEMBER_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config.from_object(Config)

app.config['SESSION_COOKIE_NAME'] = 'codecraftco_session'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'documents'), exist_ok=True)

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

oauth = None
google = None

# Ensure uploads directory exists
uploads_dir = BASE_DIR / 'uploads'
uploads_dir.mkdir(exist_ok=True)
(uploads_dir / 'documents').mkdir(exist_ok=True)

app.config['UPLOAD_FOLDER'] = str(uploads_dir)

# Define the custom MultiCheckboxField
class MultiCheckBoxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()

# In app.py, modify the OAuth setup
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

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard' if current_user.role == 'admin' else 'user_dashboard'))
    return redirect(url_for('login'))

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
                          
@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
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
    if not google:
        # Create demo user for testing
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
    
    # Fixed: Use the correct redirect URI that matches Google Console
    return google.authorize_redirect(
        url_for('google_callback', _external=True),
        prompt='consent',  # Force consent screen to get refresh token
        access_type='offline'  # Request offline access (needed for refresh token)
    )

@app.route('/google/callback')
def google_callback():
    if not google:
        flash('Google OAuth not configured', 'error')
        return redirect(url_for('login'))
    
    try:
        # Get token from Google
        token = google.authorize_access_token()
        
        # Get user info
        user_info = token.get('userinfo')
        if not user_info:
            resp = google.get('https://www.googleapis.com/oauth2/v1/userinfo', token=token)
            user_info = resp.json()
        
        # Check if user exists
        user = User.query.filter_by(email=user_info['email']).first()
        
        if not user:
            # Create new user
            user = User(
                email=user_info['email'],
                full_name=user_info.get('name'),
                profile_picture=user_info.get('picture'),
                role='user',
                auth_method='google',
                is_active=True
            )
            db.session.add(user)
        
        # Update user info and last login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Store or update Google token - UPDATED CODE HERE
        token_row = GoogleToken.query.filter_by(user_id=user.id).first()
        if not token_row:
            token_row = GoogleToken(user_id=user.id)
        
        # Add client credentials to the token for Gmail API
        enhanced_token = {
            'token': token.get('access_token'),
            'refresh_token': token.get('refresh_token'),
            'token_uri': 'https://oauth2.googleapis.com/token',
            'client_id': app.config['GOOGLE_CLIENT_ID'],
            'client_secret': app.config['GOOGLE_CLIENT_SECRET'],
            'scopes': ['https://www.googleapis.com/auth/gmail.send']
        }
        
        # Log the token for debugging
        print(f"Enhanced token being stored: {json.dumps({**enhanced_token, 'client_secret': '***'})}")

        token_row.token_json = json.dumps(enhanced_token)
        token_row.token_json = json.dumps(enhanced_token)
        token_row.refreshed_at = datetime.utcnow()
        db.session.add(token_row)
        db.session.commit()
        
        # Log in the user
        login_user(user, remember=True)
        flash(f'Welcome, {user.full_name or user.email}!', 'success')
        return redirect(url_for('user_dashboard'))
        
    except Exception as e:
        print(f"OAuth callback error: {e}")
        flash('Authentication failed. Please try again.', 'error')
        return redirect(url_for('login'))


@app.route('/user/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    
    if form.validate_on_submit():
        current_user.full_name = form.full_name.data
        current_user.phone = form.phone.data
        current_user.address = form.address.data
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('user_dashboard'))
    
    # Pre-populate form
    form.full_name.data = current_user.full_name
    form.phone.data = current_user.phone
    form.address.data = current_user.address
    
    return render_template('edit_profile.html', form=form)



@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/user/dashboard')
@login_required
def user_dashboard():
    # Get user's recent applications
    recent_applications = Application.query.filter_by(user_id=current_user.id)\
        .order_by(Application.created_at.desc()).limit(5).all()
    
    # Get user's documents count
    documents_count = Document.query.filter_by(user_id=current_user.id, is_active=True).count()
    
    return render_template('user_dashboard.html', 
                         user=current_user,
                         recent_applications=recent_applications,
                         documents_count=documents_count)


def load_learnerships_from_json():
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
    # Initialize search form
    form = LearnershipSearchForm()
    
    # Start with all active learnerships from the database
    query = Learnership.query.filter_by(is_active=True)
    
    # Apply filters if form is submitted
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
    
    # Execute the query
    learnerships = query.order_by(Learnership.closing_date).all()
    
    # Prepare categories for the category dropdown
    categories = db.session.query(Learnership.category.distinct()).all()
    categories = [category[0] for category in categories]
    
    # Populate category choices
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
    
    # Fetch learnership emails for bulk application
    learnership_emails = LearnshipEmail.query.filter_by(is_active=True).all()
    
    return render_template('learnerships.html', 
                           form=form,
                           categories=categorized_learnerships,
                           learnerships=learnerships,
                           learnership_emails=learnership_emails)


# Fixed: Added app parameter to load_learnerships_from_json call
@app.route('/user/apply', methods=['GET', 'POST'])
@login_required
def apply_learnership():
    # Get selected IDs from request
    selected_ids = request.args.getlist('selected')
    
    if not selected_ids:
        flash('Please select at least one learnership to apply for.', 'warning')
        return redirect(url_for('learnerships'))
    
    # Convert string IDs to integers
    selected_ids = [int(id) for id in selected_ids if id.isdigit()]
    
    if not selected_ids:
        flash('Invalid selection.', 'warning')
        return redirect(url_for('learnerships'))
    
    # Get all learnerships from JSON
    all_learnerships = load_learnerships_from_json()
    
    # Make sure each learnership has an apply_email field
    for learnership in all_learnerships:
        if 'apply_email' not in learnership or not learnership['apply_email']:
            learnership['apply_email'] = 'applications@' + learnership['company'].lower().replace(' ', '') + '.co.za'
    
    # Filter to only selected learnerships
    selected_learnerships = [l for l in all_learnerships if l['id'] in selected_ids]
    
    if not selected_learnerships:
        flash('No valid learnerships selected.', 'warning')
        return redirect(url_for('learnerships'))
    
    # Get user's documents
    user_documents = Document.query.filter_by(user_id=current_user.id, is_active=True).all()
    
    # Create form for application
    form = ApplicationForm()  # You need to define this form class
    
    if form.validate_on_submit():
        # Create applications in the database first
        created_apps = []
        for lr in selected_learnerships:
            try:
                # Create application in database
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
        
        # Only proceed with email if we have applications
        if created_apps:
            try:
                # Get selected document IDs
                attachment_ids = []
                if hasattr(form, 'attachments'):
                    attachment_ids = [int(id) for id in form.attachments.data]
                
                # Save email body to user temporarily
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
    # Get all user's applications
    applications = Application.query.filter_by(user_id=current_user.id)\
        .order_by(Application.created_at.desc()).all()
    
    # Group by status
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


@app.route('/user/documents', methods=['GET', 'POST'])
@login_required
def document_center():
    form = DocumentUploadForm()
    
    if form.validate_on_submit():
        file = form.document.data
        if file:
            # Secure the filename
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_filename = f"{current_user.id}_{timestamp}_{filename}"
            
            # Save file
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'documents', unique_filename)
            file.save(file_path)
            
            # Save document record
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
    document = Document.query.filter_by(id=doc_id, user_id=current_user.id).first_or_404()
    
    # Mark as inactive instead of deleting
    document.is_active = False
    db.session.commit()
    
    flash('Document removed successfully!', 'success')
    return redirect(url_for('document_center'))


# Add this function to initialize sample learnerships

# Initialize database
def init_db():
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Optional: Create default admin if not exists
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

def safe_db_init():
    try:
        with app.app_context():
            # Create tables
            db.create_all()
            
            # Create default admin if not exists
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
            
            # Initialize other data
            init_learnership_emails()
    except Exception as e:
        print(f"Database initialization error: {e}")

# Call during app startup
if __name__ == '__main__' or os.environ.get('RENDER'):
    safe_db_init()



def bulk_send_job(app, user_id, learnerships, attachment_ids):
    """Background job to send application emails"""
    # Use app context within the thread
    with app.app_context():
        try:
            # Import necessary models
            from models import User, Document, Application, ApplicationDocument, GoogleToken, db
            from mailer import build_credentials, create_message_with_attachments, send_gmail_message
            
            print(f"Starting bulk send job for user {user_id} with {len(learnerships)} learnerships")
            
            # Get user
            user = User.query.get(user_id)
            if not user:
                print(f"User {user_id} not found")
                return
            
            # Get Google token
            token_row = GoogleToken.query.filter_by(user_id=user.id).first()
            if not token_row:
                print(f"No Google token for user {user_id}")
                return
                
            # Build credentials
            credentials = build_credentials(token_row.token_json)
            
            # Get documents
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
            
            # Process each learnership
            for lr in learnerships:
                try:
                    print(f"Processing application for learnership: {lr.get('title')}")
                    
                    # Create application record directly with verified field names
                    new_application = Application(
                        user_id=user.id,
                        status='processing'
                    )
                    
                    # Set optional fields if they exist in the learnership data
                    if 'id' in lr:
                        new_application.learnership_id = lr.get('id')
                    
                    if 'title' in lr:
                        new_application.learnership_name = lr.get('title')
                        
                    if 'company' in lr:
                        new_application.company_name = lr.get('company')
                    
                    # Add to session
                    print(f"Adding new application to database")
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
                    
                    # Save document associations
                    db.session.commit()
                    print(f"Added {len(docs)} document associations")
                    
                    # Verify learnership has email
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
                        # Create and send message
                        message = create_message_with_attachments(
                            user.email,
                            apply_email,
                            subject,
                            body,
                            file_paths
                        )
                        
                        result = send_gmail_message(credentials, message)
                        print(f"Email sent with result: {result}")
                        
                        # Update application status
                        new_application.status = 'submitted'
                        db.session.commit()
                        print(f"Application status updated to 'submitted'")
                        
                    except Exception as e:
                        # Handle sending error
                        print(f"Failed to send email: {str(e)}")
                        new_application.status = 'error'
                        db.session.commit()
                        print(f"Application status updated to 'error'")
                    
                except Exception as e:
                    print(f"Error processing application: {str(e)}")
                    import traceback
                    print(traceback.format_exc())
                    db.session.rollback()
                    
                # Simulate delay between emails
                time.sleep(1)
                
        except Exception as e:
            print(f"Bulk send job error: {str(e)}")
            import traceback
            print(traceback.format_exc())

def send_application_email(recipient_email, company_name, user):
    """Send an application email to a company using the Gmail API with OAuth"""
    from mailer import build_credentials, create_message_with_attachments, send_gmail_message
    from models import GoogleToken
    
    subject = f"Learnership Application from {user.full_name or user.email}"
    
    body = f"""
Hello {company_name},

I would like to apply for any available learnership opportunities at your company.

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
            
        # Build credentials
        credentials = build_credentials(token_row.token_json)
        
        # Get user's documents
        documents = Document.query.filter_by(user_id=user.id, is_active=True).all()
        file_paths = []
        for doc in documents:
            file_paths.append({
                'path': doc.file_path,
                'filename': doc.original_filename
            })
        
        # Create and send message
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
    

# Route for the email list view
@app.route('/learnerships/emails')
@login_required
def learnership_emails():
    """Display list of learnership email addresses for bulk applications"""
    # Get all active learnership emails
    learnership_emails = LearnshipEmail.query.filter_by(is_active=True).order_by(LearnshipEmail.company_name).all()
    return render_template('learnerships.html', learnership_emails=learnership_emails)

# Route for bulk email applications
@app.route('/apply_bulk_email', methods=['POST'])
@login_required
def apply_bulk_email():
    """Process bulk application to selected email addresses"""
    selected_email_ids = request.form.getlist('selected_emails')
    
    if not selected_email_ids:
        flash('Please select at least one company to apply to.', 'warning')
        return redirect(url_for('learnership_emails'))
    
    # Get the email entries
    email_entries = LearnshipEmail.query.filter(
        LearnshipEmail.id.in_(selected_email_ids),
        LearnshipEmail.is_active == True
    ).all()
    
    if not email_entries:
        flash('No valid email addresses found.', 'error')
        return redirect(url_for('learnership_emails'))
    
    # Get user's documents (CV, etc.)
    user_documents = Document.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()
    
    # Process each email
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
        
        # Send email
        email_sent = send_application_email(
            email_entry.email,
            email_entry.company_name,
            current_user
        )
        
        # Create application records
        if email_sent:
            # Create EmailApplication record
            app = EmailApplication(
                user_id=current_user.id,
                learnership_email_id=email_entry.id,
                status='sent'
            )
            db.session.add(app)
            
            # Also create standard Application record
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
    
    # Flash appropriate messages
    if applications_created > 0:
        flash(f"Successfully sent applications to {applications_created} companies!", 'success')
    
    if applications_failed > 0:
        flash(f"Failed to send applications to {applications_failed} companies.", 'warning')
    
    return redirect(url_for('my_applications'))

# Function to initialize learnership emails
def init_learnership_emails():
    """Initialize the database with learnership email addresses"""
    with app.app_context():
        # Check if emails already exist
        if LearnshipEmail.query.first() is not None:
            print("Learnership emails already exist in database. Skipping initialization.")
            return
        
        # List of email addresses with company names
        email_data = [
            {"company_name": "Tych", "email": "Precious@tych.co.za"},
            {"company_name": "Progression", "email": "farhana@progression.co.za"},
            {"company_name": "QASA", "email": "recruitment@qasa.co.za"},
            {"company_name": "TLO", "email": "Recruitment@tlo.co.za"},
            {"company_name": "Dibanisa Learning", "email": "Slindile@dibanisaleaening.co.za"},
            {"company_name": "Tric Talent", "email": "Anatte@trictalent.co.za"},
            {"company_name": "Novia One", "email": "Tai@noviaone.com"},
            {"company_name": "Edge Executive", "email": "kgotso@edgexec.co.za"},
            {"company_name": "Related Ed", "email": "kagiso@related-ed.com"},
            {"company_name": "Skills Panda", "email": "refiloe@skillspanda.co.za"},
            {"company_name": "RMA Education", "email": "Skills@rma.edu.co.za"},
            {"company_name": "Signa", "email": "nkhensani@signa.co.za"},
            {"company_name": "CSG Skills", "email": "Sdube@csgskills.co.za"},
            {"company_name": "SITA", "email": "Lerato.recruitment@sita.co.za"},
            {"company_name": "TJH Business", "email": "melviln@tjhbusiness.co.za"},
            {"company_name": "Thandsh C", "email": "Moodleyt@thandshc.co.za"},
            {"company_name": "Kunaku", "email": "leaners@kunaku.co.za"},
            {"company_name": "KLM Empowered", "email": "leanership@klmempowerd.com"}
        ]
        
        # Add email addresses to the database
        for data in email_data:
            email = LearnshipEmail(company_name=data["company_name"], email=data["email"])
            db.session.add(email)
        
        db.session.commit()
        print(f"Added {len(email_data)} learnership emails to the database")

# Add this helper function to check if a route exists
def url_for_map():
    return {rule.endpoint: rule for rule in current_app.url_map.iter_rules()}

# Admin dashboard with additional data
# Admin dashboard route
@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    # Fetch data for dashboard
    users = User.query.all()
    learnerships = Learnership.query.all()
    applications = Application.query.all()
    
    # Stats for dashboard
    stats = {
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'total_learnerships': Learnership.query.count(),
        'total_applications': Application.query.count()
    }
    
    # Recent data
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


# Toggle user status route
@app.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user_status(user_id):
    user = User.query.get_or_404(user_id)
    
    # Don't allow toggling admin users (safety check)
    if user.role == 'admin' and user.id != current_user.id:
        flash('Cannot modify admin user status', 'error')
        return redirect(url_for('admin_dashboard'))
    
    # Toggle status
    user.is_active = not user.is_active
    
    try:
        db.session.commit()
        status = 'activated' if user.is_active else 'deactivated'
        flash(f'User {user.username or user.email} has been {status}', 'success')
    except:
        db.session.rollback()
        flash('Error updating user status', 'error')
    
    return redirect(url_for('admin_dashboard'))

# Delete user route
@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # Safety check - don't delete admin users
    if user.role == 'admin':
        flash('Cannot delete admin users', 'error')
        return redirect(url_for('admin_dashboard'))
    
    # Delete associated records first (to avoid foreign key constraints)
    try:
        # Get all documents owned by this user
        documents = Document.query.filter_by(user_id=user_id).all()
        
        # Delete the actual files
        for doc in documents:
            if doc.file_path and os.path.exists(doc.file_path):
                try:
                    os.remove(doc.file_path)
                except:
                    # Log this error but continue
                    pass
        
        # Delete all applications by this user
        Application.query.filter_by(user_id=user_id).delete()
        
        # Delete all documents
        Document.query.filter_by(user_id=user_id).delete()
        
        # Finally delete the user
        db.session.delete(user)
        db.session.commit()
        
        flash(f'User {user.username or user.email} has been deleted', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'error')
    
    return redirect(url_for('admin_dashboard'))

# Toggle learnership status route
@app.route('/admin/learnerships/<int:learnership_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_learnership_status(learnership_id):
    learnership = Learnership.query.get_or_404(learnership_id)
    
    # Toggle status
    learnership.is_active = not learnership.is_active
    
    try:
        db.session.commit()
        status = 'activated' if learnership.is_active else 'deactivated'
        flash(f'Learnership "{learnership.title}" has been {status}', 'success')
    except:
        db.session.rollback()
        flash('Error updating learnership status', 'error')
    
    return redirect(url_for('admin_dashboard'))

# Delete learnership route
@app.route('/admin/learnerships/<int:learnership_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_learnership(learnership_id):
    learnership = Learnership.query.get_or_404(learnership_id)
    
    try:
        # First update any applications that reference this learnership
        applications = Application.query.filter_by(learnership_id=learnership_id).all()
        for app in applications:
            # Store the learnership name before deleting the relationship
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

# Update application status route
@app.route('/admin/applications/<int:application_id>/status/<status>', methods=['POST'])
@login_required
@admin_required
def update_application_status(application_id, status):
    if status not in ['pending', 'approved', 'rejected']:
        flash('Invalid status', 'error')
        return redirect(url_for('admin_dashboard'))
    
    application = Application.query.get_or_404(application_id)
    application.status = status
    application.updated_at = datetime.utcnow()
    
    try:
        db.session.commit()
        flash(f'Application status updated to {status}', 'success')
    except:
        db.session.rollback()
        flash('Error updating application status', 'error')
    
    return redirect(url_for('admin_dashboard'))

# Delete application route
@app.route('/admin/applications/<int:application_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_application(application_id):
    application = Application.query.get_or_404(application_id)
    
    try:
        # Delete the application
        db.session.delete(application)
        db.session.commit()
        
        flash(f'Application has been deleted', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting application: {str(e)}', 'error')
    
    return redirect(url_for('admin_dashboard'))

# Add User route
@app.route('/admin/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
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
        
        # Validate data
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
        
        # Set password
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
    
    # GET request - show the form
    return render_template('add_user.html')


# Add Learnership route
@app.route('/admin/learnerships/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_learnership():
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
        
        # Convert closing date string to datetime
        try:
            closing_date = datetime.strptime(closing_date_str, '%Y-%m-%d')
        except:
            closing_date = None
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
    
    # GET request - show the form
    return render_template('add_learnership.html')


# View User Details
@app.route('/admin/users/<int:user_id>/view')
@login_required
@admin_required
def view_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # Get user applications
    applications = Application.query.filter_by(user_id=user_id).all()
    
    # Get user documents
    documents = Document.query.filter_by(user_id=user_id).all()
    
    return render_template('view_user.html', 
                          user=user,
                          applications=applications,
                          documents=documents)

# Edit User
@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        # Update user data from form
        user.email = request.form.get('email')
        user.username = request.form.get('username')
        user.full_name = request.form.get('full_name')
        user.phone = request.form.get('phone')
        user.role = request.form.get('role')
        user.is_active = 'is_active' in request.form
        
        # Only update password if provided
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

# View Learnership Details
@app.route('/admin/learnerships/<int:learnership_id>/view')
@login_required
@admin_required
def view_learnership(learnership_id):
    learnership = Learnership.query.get_or_404(learnership_id)
    
    # Get applications for this learnership
    applications = Application.query.filter_by(learnership_id=learnership_id).all()
    
    return render_template('view_learnership.html',
                          learnership=learnership,
                          applications=applications)

# Edit Learnership
@app.route('/admin/learnerships/<int:learnership_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_learnership(learnership_id):
    learnership = Learnership.query.get_or_404(learnership_id)
    
    if request.method == 'POST':
        # Update learnership data from form
        learnership.title = request.form.get('title')
        learnership.company = request.form.get('company')
        learnership.category = request.form.get('category')
        learnership.location = request.form.get('location')
        learnership.duration = request.form.get('duration')
        learnership.stipend = request.form.get('stipend')
        
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


# View Application Details
@app.route('/admin/applications/<int:application_id>/view')
@login_required
@admin_required
def view_application(application_id):
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
    document = Document.query.get_or_404(document_id)
    
    # Check if file exists
    if not document.file_path or not os.path.exists(document.file_path):
        flash('Document file not found', 'error')
        return redirect(request.referrer or url_for('admin_dashboard'))
    
    # Determine the mime type (or use a default)
    mime_type = 'application/octet-stream'
    if document.original_filename:
        _, ext = os.path.splitext(document.original_filename)
        if ext.lower() == '.pdf':
            mime_type = 'application/pdf'
        elif ext.lower() in ['.doc', '.docx']:
            mime_type = 'application/msword'
        elif ext.lower() in ['.jpg', '.jpeg']:
            mime_type = 'image/jpeg'
        elif ext.lower() == '.png':
            mime_type = 'image/png'
    
    # Return the file
    return send_file(document.file_path, 
                    mimetype=mime_type,
                    as_attachment=True,
                    download_name=document.original_filename or f'document-{document.id}{os.path.splitext(document.file_path)[1]}')


# View User Details
@app.route('/admin/users/<int:user_id>/view')
@login_required
@admin_required
def admin_view_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # Get user applications
    applications = Application.query.filter_by(user_id=user_id).all()
    
    # Get user documents
    documents = Document.query.filter_by(user_id=user_id).all()
    
    return render_template('view_user.html', 
                          user=user,
                          applications=applications,
                          documents=documents)


# Edit User
@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        # Update user data from form
        user.email = request.form.get('email')
        user.username = request.form.get('username')
        user.full_name = request.form.get('full_name')
        user.phone = request.form.get('phone')
        user.role = request.form.get('role')
        user.is_active = 'is_active' in request.form
        
        # Only update password if provided
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
    

# View Learnership Details
@app.route('/admin/learnerships/<int:learnership_id>/view')
@login_required
@admin_required
def admin_view_learnership(learnership_id):
    learnership = Learnership.query.get_or_404(learnership_id)
    
    # Get applications for this learnership
    applications = Application.query.filter_by(learnership_id=learnership_id).all()
    
    return render_template('view_learnership.html',
                          learnership=learnership,
                          applications=applications)



# Edit Learnership
@app.route('/admin/learnerships/<int:learnership_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_learnership(learnership_id):
    learnership = Learnership.query.get_or_404(learnership_id)
    
    if request.method == 'POST':
        # Update learnership data from form
        learnership.title = request.form.get('title')
        learnership.company = request.form.get('company')
        learnership.category = request.form.get('category')
        learnership.location = request.form.get('location')
        learnership.duration = request.form.get('duration')
        learnership.stipend = request.form.get('stipend')
        
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


# View Application Details
@app.route('/admin/applications/<int:application_id>/view')
@login_required
@admin_required
def admin_view_application(application_id):
    application = Application.query.get_or_404(application_id)
    
    # Get documents associated with this application
    application_documents = ApplicationDocument.query.filter_by(application_id=application_id).all()
    
    return render_template('view_application.html',
                          application=application,
                          application_documents=application_documents)

@app.errorhandler(Exception)
def handle_exception(e):
    # Log the error
    app.logger.error(f'Unhandled Exception: {str(e)}', exc_info=True)
    return 'An internal error occurred', 500

# Initialize database when app starts
init_db()

# Initialize learnership emails
init_learnership_emails()

if __name__ == '__main__':
    app.run(debug=True)