from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import synonym

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

    applications = db.relationship('Application', back_populates='user', lazy=True)
    documents = db.relationship('Document', backref='owner', lazy=True)
    email_applications = db.relationship('EmailApplication', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if self.password_hash:
            return check_password_hash(self.password_hash, password)
        return False

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
