from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import synonym
import uuid

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=True)
    password_hash = db.Column(db.String(200), nullable=True)
    full_name = db.Column(db.String(100))
    role = db.Column(db.String(20), default='user')
    auth_method = db.Column(db.String(20))
    profile_picture = db.Column(db.String(500), nullable=True)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    # Session tracking fields - ADD THESE
    session_token = db.Column(db.String(255), unique=True, nullable=True)
    session_expires = db.Column(db.DateTime, nullable=True)
    session_ip = db.Column(db.String(45), nullable=True)  # For IP tracking
    session_user_agent = db.Column(db.String(500), nullable=True)  # For browser tracking

    applications = db.relationship('Application', back_populates='user', lazy=True)
    documents = db.relationship('Document', backref='owner', lazy=True)
    email_applications = db.relationship('EmailApplication', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if self.password_hash:
            return check_password_hash(self.password_hash, password)
        return False

    # ADD THESE SESSION METHODS
    def generate_session_token(self, ip_address=None, user_agent=None):
        """Generate a new session token for the user"""
        self.session_token = str(uuid.uuid4())
        self.session_expires = datetime.utcnow() + timedelta(hours=2)
        self.session_ip = ip_address
        self.session_user_agent = user_agent
        db.session.commit()
        return self.session_token

    def is_session_valid(self, session_token=None, ip_address=None):
        """Check if the current session is valid"""
        if not self.session_token or not self.session_expires:
            return False
        
        if session_token and session_token != self.session_token:
            return False
        
        if datetime.utcnow() > self.session_expires:
            self.clear_session()
            return False
        
        # Optional: Check IP address for additional security
        if ip_address and self.session_ip and ip_address != self.session_ip:
            return False
            
        return True

    def clear_session(self):
        """Clear the user's session"""
        self.session_token = None
        self.session_expires = None
        self.session_ip = None
        self.session_user_agent = None
        db.session.commit()

    def extend_session(self):
        """Extend the current session"""
        if self.session_token:
            self.session_expires = datetime.utcnow() + timedelta(hours=2)
            db.session.commit()

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'username': self.username,
            'profile_picture': self.profile_picture,
            'full_name': self.full_name,
            'role': self.role,
            'auth_method': self.auth_method,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
            'last_login': self.last_login.strftime('%Y-%m-%d %H:%M') if self.last_login else 'Never',
            'is_active': self.is_active
        }

# Keep all your other models unchanged...

class Learnership(db.Model):
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    company = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    requirements = db.Column(db.Text)
    location = db.Column(db.String(100))
    duration = db.Column(db.String(50))
    stipend = db.Column(db.String(50))
    closing_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    applications = db.relationship('Application', backref='learnership', lazy=True)

class LearnshipEmail(db.Model):
    __tablename__ = 'learnership_email'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    email_applications = db.relationship('EmailApplication', backref='learnership_email', lazy=True)

    def __repr__(self):
        return f'<LearnshipEmail {self.company_name}: {self.email}>'

class Application(db.Model):
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    learnership_id = db.Column(db.Integer, db.ForeignKey('learnership.id'), nullable=True)
    company_name = db.Column(db.String(255), nullable=True)
    _learnership_name = db.Column("learnership_name", db.String(255), nullable=True)  # Note the underscore in the variable name
    status = db.Column(db.String(50), default='pending')
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_at = synonym('submitted_at')
    user = db.relationship('User', back_populates='applications')
    
    @property
    def learnership_name(self):
        """Return the stored learnership name or calculate it if not available"""
        if self._learnership_name:
            return self._learnership_name
        return self.learnership.title if self.learnership else self.company_name
    
    @learnership_name.setter
    def learnership_name(self, value):
        """Set the stored learnership name"""
        self._learnership_name = value

class EmailApplication(db.Model):
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    learnership_email_id = db.Column(db.Integer, db.ForeignKey('learnership_email.id'), nullable=False)
    status = db.Column(db.String(50), default='sent')
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<EmailApplication {self.id}>'

class Document(db.Model):
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    document_type = db.Column(db.String(50), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    original_filename = db.Column(db.String(200))
    file_path = db.Column(db.String(500))
    file_size = db.Column(db.Integer)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

class ApplicationDocument(db.Model):
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    learnership_name = db.Column(db.String(100))

    document = db.relationship('Document', backref='application_links')
    application = db.relationship('Application', backref='documents')

class GoogleToken(db.Model):
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True)
    token_json = db.Column(db.Text)
    refreshed_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('google_token', uselist=False))
