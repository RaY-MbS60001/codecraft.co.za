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

    # Corporate-specific fields
    company_name = db.Column(db.String(200), nullable=True)
    company_email = db.Column(db.String(120), nullable=True) 
    contact_person = db.Column(db.String(100), nullable=True)
    company_phone = db.Column(db.String(20), nullable=True)
    company_website = db.Column(db.String(200), nullable=True)
    company_address = db.Column(db.Text, nullable=True)
    is_verified = db.Column(db.Boolean, default=False)  # Corporate verification

    # Daily limits constants
    FREE_DAILY_LIMIT = 24
    PREMIUM_DAILY_LIMIT = None  # Unlimited

    # FIXED RELATIONSHIPS - Specify foreign_keys to avoid conflicts
    applications = db.relationship(
        'Application', 
        foreign_keys='Application.user_id',
        back_populates='user', 
        lazy=True
    )
    documents = db.relationship('Document', backref='owner', lazy=True)

    @property
    def is_corporate(self):
        return self.role == 'corporate'
    
    @property
    def is_admin(self):
        return self.role == 'admin'

    def get_corporate_stats(self):
        """Get corporate-specific statistics"""
        if not self.is_corporate:
            return {'opportunities': 0, 'applications': 0, 'views': 0}
            
        # Count opportunities posted by this corporate user
        opportunities = LearnearshipOpportunity.query.filter_by(
            company_id=self.id, 
            is_active=True
        ).count()
        
        # Count applications received
        applications = Application.query.filter_by(
            company_email=self.company_email
        ).count() if self.company_email else 0
        
        return {
            'opportunities': opportunities,
            'applications': applications,
            'views': 0,  # You can implement view tracking later
        }

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


class Application(db.Model):
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Company info (stored directly - no foreign keys needed)
    company_name = db.Column(db.String(255), nullable=False)
    company_email = db.Column(db.String(255), nullable=True)
    _learnership_name = db.Column("learnership_name", db.String(255), nullable=True)
    
    status = db.Column(db.String(50), default='pending')
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Gmail tracking fields
    sent_at = db.Column(db.DateTime, nullable=True)
    gmail_message_id = db.Column(db.String(255), nullable=True)
    gmail_thread_id = db.Column(db.String(255), nullable=True)
    email_status = db.Column(db.String(50), default='draft')
    delivered_at = db.Column(db.DateTime, nullable=True)
    read_at = db.Column(db.DateTime, nullable=True)
    response_received_at = db.Column(db.DateTime, nullable=True)
    has_response = db.Column(db.Boolean, default=False)
    response_thread_count = db.Column(db.Integer, default=0)

    # NEW CORPORATE FIELDS - Added for enhanced tracking
    application_stage = db.Column(db.String(50), default='applied')
    interview_date = db.Column(db.DateTime)
    interview_time = db.Column(db.String(20))
    interview_type = db.Column(db.String(50))
    interview_location = db.Column(db.Text)
    interview_notes = db.Column(db.Text)
    corporate_notes = db.Column(db.Text)
    rejection_reason = db.Column(db.Text)
    hire_date = db.Column(db.DateTime)
    last_corporate_action = db.Column(db.DateTime)
    corporate_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    interview_reminder_sent = db.Column(db.Boolean, default=False)
    applicant_notified = db.Column(db.Boolean, default=False)

    # FIXED RELATIONSHIPS - Specify foreign_keys explicitly
    created_at = synonym('submitted_at')
    user = db.relationship(
        'User', 
        foreign_keys=[user_id], 
        back_populates='applications'
    )
    corporate_user = db.relationship(
        'User', 
        foreign_keys=[corporate_user_id],
        backref='managed_applications'
    )
    
    @property
    def learnership_name(self): 
        """Return the stored learnership name or company name"""
        return self._learnership_name or self.company_name
    
    @learnership_name.setter
    def learnership_name(self, value):
        """Set the stored learnership name"""
        self._learnership_name = value

    def get_stage_display(self):
        """Get user-friendly stage display"""
        stage_map = {
            'applied': {'text': 'Applied', 'class': 'stage-applied', 'icon': '📝'},
            'reviewed': {'text': 'Under Review', 'class': 'stage-reviewed', 'icon': '👀'},
            'interview_scheduled': {'text': 'Interview Scheduled', 'class': 'stage-interview', 'icon': '📅'},
            'interview_completed': {'text': 'Interview Completed', 'class': 'stage-completed', 'icon': '✅'},
            'accepted': {'text': 'Accepted', 'class': 'stage-accepted', 'icon': '🎉'},
            'rejected': {'text': 'Not Selected', 'class': 'stage-rejected', 'icon': '❌'},
            'hired': {'text': 'Hired', 'class': 'stage-hired', 'icon': '🏆'}
        }
        return stage_map.get(self.application_stage, stage_map['applied'])
    
    def update_stage(self, new_stage, corporate_user_id=None, notes=None):
        """Update application stage with tracking"""
        self.application_stage = new_stage
        self.last_corporate_action = datetime.utcnow()
        if corporate_user_id:
            self.corporate_user_id = corporate_user_id
        if notes:
            self.corporate_notes = notes
        db.session.commit()
    
    def schedule_interview(self, interview_data):
        """Schedule an interview for this application"""
        self.interview_date = interview_data['date']
        self.interview_time = interview_data['time']
        self.interview_type = interview_data['type']
        self.interview_location = interview_data.get('location')
        self.interview_notes = interview_data.get('notes')
        self.application_stage = 'interview_scheduled'
        self.last_corporate_action = datetime.utcnow()
        db.session.commit()
    
    def has_upcoming_interview(self):
        """Check if application has upcoming interview"""
        if self.interview_date:
            return self.interview_date > datetime.utcnow()
        return False
    
    def get_interview_status(self):
        """Get interview status"""
        if not self.interview_date:
            return None
        
        now = datetime.utcnow()
        if self.interview_date > now:
            return 'upcoming'
        elif self.interview_date <= now and self.application_stage == 'interview_scheduled':
            return 'ongoing'
        else:
            return 'completed'

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


# NEW MODEL: CalendarEvent
class CalendarEvent(db.Model):
    __tablename__ = 'calendar_event'
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    corporate_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    applicant_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    event_type = db.Column(db.String(50), default='interview')
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(200))
    meeting_link = db.Column(db.String(500))
    google_event_id = db.Column(db.String(200))
    status = db.Column(db.String(50), default='scheduled')  # scheduled, completed, cancelled
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reminder_sent = db.Column(db.Boolean, default=False)
    
    # FIXED RELATIONSHIPS - Specify foreign_keys explicitly
    application = db.relationship('Application', backref='calendar_events')
    corporate_user = db.relationship(
        'User', 
        foreign_keys=[corporate_user_id], 
        backref='created_events'
    )
    applicant = db.relationship(
        'User', 
        foreign_keys=[applicant_user_id], 
        backref='scheduled_events'
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'start': self.start_datetime.isoformat(),
            'end': self.end_datetime.isoformat(),
            'description': self.description,
            'location': self.location,
            'status': self.status
        }


# NEW MODEL: ApplicationMessage
class ApplicationMessage(db.Model):
    __tablename__ = 'application_message'
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sender_type = db.Column(db.String(20), nullable=False)  # 'corporate', 'applicant'
    
    subject = db.Column(db.String(200))
    message = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(50), default='general')  # general, interview_invite, rejection, acceptance
    
    gmail_message_id = db.Column(db.String(200))
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime)
    is_read = db.Column(db.Boolean, default=False)
    
    # FIXED RELATIONSHIPS
    application = db.relationship('Application', backref='messages')
    sender = db.relationship('User', backref='sent_messages')
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()
            db.session.commit()


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


class LearnershipEmail(db.Model):
    __tablename__ = 'learnership_email'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(255), nullable=False)
    email_address = db.Column(db.String(255), nullable=False)
    
    # Domain checker results
    is_reachable = db.Column(db.Boolean, default=None)
    response_time = db.Column(db.Float, default=None)
    last_checked = db.Column(db.DateTime, default=None)
    check_count = db.Column(db.Integer, default=0)
    
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


class LearnearshipOpportunity(db.Model):
    __tablename__ = 'learnership_opportunity'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Opportunity details
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    requirements = db.Column(db.Text)
    benefits = db.Column(db.Text)
    location = db.Column(db.String(100))
    duration = db.Column(db.String(50))
    stipend = db.Column(db.String(50))
    
    # Application settings
    application_email = db.Column(db.String(120), nullable=False)
    application_deadline = db.Column(db.DateTime)
    max_applicants = db.Column(db.Integer)
    
    # Post management
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    expire_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Recurring settings
    is_recurring = db.Column(db.Boolean, default=False)
    recurring_frequency = db.Column(db.String(20))
    next_post_date = db.Column(db.DateTime)
    
    # Stats
    views_count = db.Column(db.Integer, default=0)
    applications_count = db.Column(db.Integer, default=0)
    
    # Relationships
    company = db.relationship('User', backref='posted_opportunities')
    
    def is_expired(self):
        return self.expire_date and self.expire_date <= datetime.utcnow()
    
    def days_until_deadline(self):
        if self.application_deadline:
            delta = self.application_deadline - datetime.utcnow()
            return delta.days if delta.days > 0 else 0
        return None
    
    def can_apply(self):
        return (self.is_active and 
                not self.is_expired() and 
                (not self.application_deadline or self.application_deadline > datetime.utcnow()))
    
    def increment_view(self):
        self.views_count = (self.views_count or 0) + 1
        db.session.commit()


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


# Add these new models to your models.py

class Conversation(db.Model):
    __tablename__ = 'conversation'
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    gmail_thread_id = db.Column(db.String(255), nullable=False, unique=True)
    subject = db.Column(db.String(500), nullable=False)
    
    last_read_at = db.Column(db.DateTime)
    # Participants
    corporate_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    applicant_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Status tracking
    is_active = db.Column(db.Boolean, default=True)
    last_message_at = db.Column(db.DateTime, default=datetime.utcnow)
    corporate_unread_count = db.Column(db.Integer, default=0)
    applicant_unread_count = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    application = db.relationship('Application', backref='conversation')
    corporate_user = db.relationship('User', foreign_keys=[corporate_user_id])
    applicant = db.relationship('User', foreign_keys=[applicant_user_id])

class ConversationMessage(db.Model):
    __tablename__ = 'conversation_message'
    
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    gmail_message_id = db.Column(db.String(255), nullable=False, unique=True)
    
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sender_type = db.Column(db.String(20), nullable=False)  # 'corporate', 'applicant'
    
    subject = db.Column(db.String(500))
    body = db.Column(db.Text, nullable=False)
    html_body = db.Column(db.Text)
    
    # Gmail metadata
    gmail_timestamp = db.Column(db.DateTime, nullable=False)
    has_attachments = db.Column(db.Boolean, default=False)
    
    # Read status
    is_read_by_corporate = db.Column(db.Boolean, default=False)
    is_read_by_applicant = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    conversation = db.relationship('Conversation', backref='messages')
    sender = db.relationship('User')
    
    def mark_as_read(self, user_type):
        """Mark message as read by corporate or applicant"""
        if user_type == 'corporate':
            self.is_read_by_corporate = True
        elif user_type == 'applicant':
            self.is_read_by_applicant = True
        
        if not self.read_at:
            self.read_at = datetime.utcnow()
        
        db.session.commit()