from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta, date
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import synonym
import uuid

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'user'
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
    
    # Session tracking fields
    session_token = db.Column(db.String(255), unique=True, nullable=True)
    session_expires = db.Column(db.DateTime, nullable=True)
    session_ip = db.Column(db.String(45), nullable=True)
    session_user_agent = db.Column(db.String(500), nullable=True)

    # Premium Account Fields
    is_premium = db.Column(db.Boolean, default=False, nullable=False)
    premium_expires = db.Column(db.DateTime, nullable=True)
    daily_applications_used = db.Column(db.Integer, default=0, nullable=False)
    last_application_date = db.Column(db.Date, default=date.today)
    premium_activated_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    premium_activated_at = db.Column(db.DateTime, nullable=True)

    # Relationships - CLEANED (removed EmailApplication and LearnershipApplication)
    applications = db.relationship('Application', back_populates='user', lazy=True)
    documents = db.relationship('Document', backref='owner', lazy=True)

    # Daily limits constants
    FREE_DAILY_LIMIT = 24
    PREMIUM_DAILY_LIMIT = None  # Unlimited

    @property
    def is_admin(self):
        return self.role == 'admin'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if self.password_hash:
            return check_password_hash(self.password_hash, password)
        return False

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

    # Premium Account Methods
    def can_apply_today(self):
        """Check if user can make more applications today"""
        today = date.today()
        
        # Reset counter if it's a new day
        if self.last_application_date != today:
            self.daily_applications_used = 0
            self.last_application_date = today
            db.session.commit()
        
        # Premium users have unlimited applications
        if self.is_premium and (not self.premium_expires or self.premium_expires > datetime.now()):
            return True
        
        # Free users are limited to 24 per day
        return self.daily_applications_used < self.FREE_DAILY_LIMIT
    
    def get_remaining_applications(self):
        """Get remaining applications for today"""
        if self.is_premium and (not self.premium_expires or self.premium_expires > datetime.now()):
            return "Unlimited"
        
        today = date.today()
        if self.last_application_date != today:
            return self.FREE_DAILY_LIMIT
        
        return max(0, self.FREE_DAILY_LIMIT - self.daily_applications_used)
    
    def use_application(self):
        """Record an application usage"""
        today = date.today()
        
        if self.last_application_date != today:
            self.daily_applications_used = 0
            self.last_application_date = today
        
        self.daily_applications_used += 1
        db.session.commit()

    def is_premium_active(self):
        """Check if premium is currently active"""
        return self.is_premium and (not self.premium_expires or self.premium_expires > datetime.now())

    def get_premium_status(self):
        """Get premium status with details"""
        if not self.is_premium:
            return {'status': 'free', 'message': 'Free Account'}
        
        if self.premium_expires and self.premium_expires <= datetime.now():
            return {'status': 'expired', 'message': 'Premium Expired'}
        
        if self.premium_expires:
            days_left = (self.premium_expires - datetime.now()).days
            return {'status': 'active', 'message': f'Premium Active ({days_left} days left)'}
        
        return {'status': 'active', 'message': 'Premium Active (Lifetime)'}

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
            'is_active': self.is_active,
            'is_premium': self.is_premium,
            'premium_status': self.get_premium_status(),
            'remaining_applications': self.get_remaining_applications()
        }

class PremiumTransaction(db.Model):
    __tablename__ = 'premium_transactions'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    transaction_type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=True)
    duration_days = db.Column(db.Integer, nullable=False)
    activated_by_admin = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)
    
    user = db.relationship('User', foreign_keys=[user_id], backref='premium_transactions')
    admin = db.relationship('User', foreign_keys=[activated_by_admin])

    def __repr__(self):
        return f'<PremiumTransaction {self.id}: {self.transaction_type} for User {self.user_id}>'

# LEARNERSHIP EMAIL MODEL - For company emails with domain checking
class LearnershipEmail(db.Model):
    __tablename__ = 'learnership_email'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(255), nullable=False)
    email_address = db.Column(db.String(255), nullable=False)
    
    # Domain checker results
    is_reachable = db.Column(db.Boolean, default=None)  # True=reachable, False=unreachable, None=not checked
    response_time = db.Column(db.Float, default=None)   # Response time in seconds
    last_checked = db.Column(db.DateTime, default=None) # When was it last checked
    check_count = db.Column(db.Integer, default=0)      # How many times checked
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<LearnershipEmail {self.company_name}: {self.email_address}>'
    
    @property
    def email(self):
        """Backward compatibility property"""
        return self.email_address
    
    @email.setter
    def email(self, value):
        """Backward compatibility setter"""
        self.email_address = value
    
    @property
    def status(self):
        """Convert is_reachable boolean to status string for display"""
        if self.is_reachable is None:
            return 'unknown'
        elif self.is_reachable:
            return 'reachable'
        else:
            return 'unreachable'
    
    @status.setter
    def status(self, value):
        """Convert status string back to is_reachable boolean"""
        if value == 'reachable':
            self.is_reachable = True
        elif value == 'unreachable':
            self.is_reachable = False
        else: 
            self.is_reachable = None

    def mark_as_checked(self, is_reachable, response_time=None):
        """Update the domain check results"""
        self.is_reachable = is_reachable
        self.response_time = response_time
        self.last_checked = datetime.utcnow()
        self.check_count += 1

    @classmethod
    def get_reachable_opportunities(cls):
        """Get only reachable opportunities for display"""
        return cls.query.filter_by(
            is_reachable=True, 
            is_active=True
        ).order_by(cls.company_name.asc()).all()

    @classmethod
    def get_unchecked_emails(cls):
        """Get emails that haven't been domain checked yet"""
        return cls.query.filter_by(
            is_reachable=None, 
            is_active=True
        ).limit(50).all()

# MAIN APPLICATION MODEL - This handles EVERYTHING!
class Application(db.Model):
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Company info (stored directly - no foreign keys needed)
    company_name = db.Column(db.String(255), nullable=False)
    company_email = db.Column(db.String(255), nullable=True)  # Store email directly
    _learnership_name = db.Column("learnership_name", db.String(255), nullable=True)
    
    status = db.Column(db.String(50), default='pending')
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Gmail tracking fields - ALL IN ONE TABLE!
    sent_at = db.Column(db.DateTime, nullable=True)
    gmail_message_id = db.Column(db.String(255), nullable=True)
    gmail_thread_id = db.Column(db.String(255), nullable=True)
    email_status = db.Column(db.String(50), default='draft')
    delivered_at = db.Column(db.DateTime, nullable=True)
    read_at = db.Column(db.DateTime, nullable=True)
    response_received_at = db.Column(db.DateTime, nullable=True)
    has_response = db.Column(db.Boolean, default=False)
    response_thread_count = db.Column(db.Integer, default=0)

    created_at = synonym('submitted_at')
    user = db.relationship('User', back_populates='applications')
    
    @property
    def learnership_name(self): 
        """Return the stored learnership name or company name"""
        return self._learnership_name or self.company_name
    
    @learnership_name.setter
    def learnership_name(self, value):
        """Set the stored learnership name"""
        self._learnership_name = value

    def get_email_status_display(self):
        """Return user-friendly email status display"""
        status_map = {
            'draft': {'text': 'Draft', 'class': 'status-draft', 'icon': '📝'},
            'sent': {'text': 'Sent', 'class': 'status-sent', 'icon': '📤'},
            'delivered': {'text': 'Delivered', 'class': 'status-delivered', 'icon': '✅'},
            'read': {'text': 'Read', 'class': 'status-read', 'icon': '👁️'},
            'responded': {'text': 'Response Received', 'class': 'status-responded', 'icon': '💬'},
            'failed': {'text': 'Failed', 'class': 'status-failed', 'icon': '❌'}
        }
        return status_map.get(self.email_status, status_map['draft'])
    
    def get_overall_status(self):
        """Get combined status (application status + email status)"""
        if self.has_response:
            return 'responded'
        elif self.email_status in ['sent', 'delivered', 'read']:
            return self.email_status
        else:
            return self.status
    
    def update_from_gmail_status(self, status_info):
        """Update application based on Gmail API response"""
        if not status_info:
            return
            
        if status_info.get('timestamp') and not self.sent_at:
            self.sent_at = status_info['timestamp']
            self.email_status = 'sent'
        
        thread_info = status_info.get('thread_info', {})
        if thread_info.get('has_responses'):
            self.email_status = 'responded'
            self.has_response = True
            self.response_thread_count = max(0, thread_info.get('message_count', 1) - 1)
            
            if thread_info.get('latest_response_time'):
                self.response_received_at = thread_info['latest_response_time']
        
        self.updated_at = datetime.utcnow()
    
    def get_gmail_url(self):
        """Get direct Gmail URL for this application"""
        if self.gmail_thread_id:
            return f"https://mail.google.com/mail/u/0/#inbox/{self.gmail_thread_id}"
        return None
    
    def days_since_sent(self):
        """Get number of days since email was sent"""
        if self.sent_at:
            return (datetime.utcnow() - self.sent_at).days
        return None
    
    def is_recent(self, days=7):
        """Check if application was sent recently"""  
        if self.sent_at:
            return (datetime.utcnow() - self.sent_at).days <= days
        return False

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

class GoogleToken(db.Model):
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True)
    token_json = db.Column(db.Text)
    refreshed_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('google_token', uselist=False))