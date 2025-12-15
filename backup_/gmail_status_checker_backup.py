# gmail_status_checker.py
import json
import time
import logging
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GmailStatusChecker:
    def __init__(self, user_id):
        self.user_id = user_id
        self.service = None
        logger.info(f"🔧 Initializing GmailStatusChecker for user {user_id}")
        
    def get_gmail_service(self):
        """Get authenticated Gmail service"""
        try:
            logger.info(f"📧 Creating Gmail service for user {self.user_id}")
            
            from models import GoogleToken
            
            google_token = GoogleToken.query.filter_by(user_id=self.user_id).first()
            if not google_token:
                logger.error(f"❌ No Google token found for user {self.user_id}")
                print(f"❌ No Google token found for user {self.user_id}")
                return None
            
            logger.info(f"✅ Found Google token for user {self.user_id}")
            
            token_data = json.loads(google_token.token_json)
            logger.info(f"🔑 Token scopes: {token_data.get('scopes', [])}")
            
            # Get client credentials
            from flask import current_app
            client_id = token_data.get('client_id') or current_app.config.get('GOOGLE_CLIENT_ID')
            client_secret = token_data.get('client_secret') or current_app.config.get('GOOGLE_CLIENT_SECRET')
            
            credentials = Credentials(
                token=token_data.get('access_token') or token_data.get('token'),
                refresh_token=token_data.get('refresh_token'),
                token_uri=token_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
                client_id=client_id,
                client_secret=client_secret,
                scopes=token_data.get('scopes', [])
            )
            
            # Refresh if expired
            if credentials.expired and credentials.refresh_token:
                from google.auth.transport.requests import Request
                credentials.refresh(Request())
                logger.info("🔄 Token refreshed")
                
                # Update stored token
                token_data['access_token'] = credentials.token
                token_data['token'] = credentials.token
                google_token.token_json = json.dumps(token_data)
                
                from models import db
                db.session.commit()
            
            logger.info("🔧 Building Gmail service...")
            self.service = build('gmail', 'v1', credentials=credentials)
            logger.info("✅ Gmail service created successfully")
            return self.service
            
        except Exception as e:
            logger.error(f"❌ Error creating Gmail service: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def check_message_status(self, gmail_message_id, gmail_thread_id=None):
        """Check comprehensive status of a Gmail message"""
        logger.info(f"🔍 Checking message status for ID: {gmail_message_id}")
        
        if not self.service:
            self.service = self.get_gmail_service()
            
        if not self.service:
            logger.error("❌ Could not create Gmail service")
            return None
            
        try:
            # Get message details
            message = self.service.users().messages().get(
                userId='me', 
                id=gmail_message_id,
                format='full'
            ).execute()
            
            logger.info(f"✅ Successfully fetched message {gmail_message_id}")
            
            # Check labels
            labels = message.get('labelIds', [])
            logger.info(f"🏷️ Message labels: {labels}")
            
            is_sent = 'SENT' in labels
            is_draft = 'DRAFT' in labels
            
            if is_draft:
                return {'status': 'draft', 'timestamp': None, 'delivered': False, 'read': False}
            
            if not is_sent:
                return {'status': 'pending', 'timestamp': None, 'delivered': False, 'read': False}
            
            # Get timestamp
            internal_date = int(message.get('internalDate', 0))
            sent_time = datetime.fromtimestamp(internal_date / 1000) if internal_date else None
            
            # Check thread activity
            thread_id = gmail_thread_id or message.get('threadId')
            delivery_status = self.check_delivery_and_read_status(gmail_message_id, thread_id)
            thread_info = self.check_thread_activity(thread_id)
            
            # Determine final status
            final_status = 'sent'
            if delivery_status.get('delivered'):
                final_status = 'delivered'
            if delivery_status.get('read'):
                final_status = 'read'
            if thread_info.get('has_responses'):
                final_status = 'responded'
            
            return {
                'status': final_status,
                'timestamp': sent_time,
                'delivered': delivery_status.get('delivered', True),
                'read': delivery_status.get('read', False),
                'read_time': delivery_status.get('read_time'),
                'thread_info': thread_info
            }
            
        except HttpError as error:
            if error.resp.status == 404:
                logger.error(f"❌ Message {gmail_message_id} not found")
                return {'status': 'failed', 'error': 'Message not found'}
            logger.error(f"❌ Gmail API error: {error}")
            return None
        except Exception as e:
            logger.error(f"❌ Error checking message status: {e}")
            return None
    
    def check_delivery_and_read_status(self, message_id, thread_id):
        """Check delivery and read status"""
        try:
            if not thread_id:
                return {'delivered': True, 'read': False}
            
            thread = self.service.users().threads().get(
                userId='me',
                id=thread_id,
                format='full'
            ).execute()
            
            messages = thread.get('messages', [])
            
            # Find original message
            original_message = None
            for msg in messages:
                if msg['id'] == message_id:
                    original_message = msg
                    break
            
            if not original_message:
                return {'delivered': True, 'read': False}
            
            delivered = True
            has_replies = len(messages) > 1
            
            internal_date = int(original_message.get('internalDate', 0))
            sent_time = datetime.fromtimestamp(internal_date / 1000) if internal_date else None
            
            read_status = False
            read_time = None
            
            if sent_time:
                time_since_sent = datetime.utcnow() - sent_time
                
                if time_since_sent > timedelta(hours=1):
                    delivered = True
                
                if has_replies or time_since_sent > timedelta(hours=4):
                    read_status = True
                    read_time = sent_time + timedelta(hours=2)
            
            return {
                'delivered': delivered,
                'read': read_status,
                'read_time': read_time,
                'has_replies': has_replies
            }
            
        except Exception as e:
            logger.error(f"❌ Error checking delivery status: {e}")
            return {'delivered': True, 'read': False}
    
    def check_thread_activity(self, thread_id):
        """Check for responses in the thread"""
        try:
            thread = self.service.users().threads().get(
                userId='me',
                id=thread_id,
                format='metadata'
            ).execute()
            
            messages = thread.get('messages', [])
            message_count = len(messages)
            has_responses = message_count > 1
            
            latest_response_time = None
            response_count = 0
            
            if has_responses:
                response_count = message_count - 1
                latest_message = messages[-1]
                internal_date = int(latest_message.get('internalDate', 0))
                latest_response_time = datetime.fromtimestamp(internal_date / 1000) if internal_date else None
            
            return {
                'has_responses': has_responses,
                'message_count': message_count,
                'response_count': response_count,
                'latest_response_time': latest_response_time
            }
            
        except Exception as e:
            logger.error(f"❌ Error checking thread activity: {e}")
            return {'has_responses': False, 'message_count': 1, 'response_count': 0, 'latest_response_time': None}
    
    def update_application_statuses(self):
        """Update statuses for all applications with Gmail IDs"""
        logger.info(f"🔄 Starting status update for user {self.user_id}")
        print(f"🔄 Starting status update for user {self.user_id}")
        
        from models import Application
        from app import db
        
        # Get applications WITH gmail_message_id
        applications = Application.query.filter_by(
            user_id=self.user_id
        ).filter(
            Application.gmail_message_id.isnot(None)
        ).all()
        
        # Also log applications WITHOUT gmail_message_id for debugging
        apps_without_id = Application.query.filter_by(
            user_id=self.user_id
        ).filter(
            Application.gmail_message_id.is_(None)
        ).all()
        
        logger.info(f"📋 Found {len(applications)} applications WITH Gmail ID to check")
        logger.info(f"⚠️ Found {len(apps_without_id)} applications WITHOUT Gmail ID (cannot track)")
        print(f"📋 Found {len(applications)} applications WITH Gmail ID to check")
        print(f"⚠️ Found {len(apps_without_id)} applications WITHOUT Gmail ID (cannot track)")
        
        if apps_without_id:
            print("\n📝 Applications without Gmail ID:")
            for app in apps_without_id[:5]:  # Show first 5
                print(f"   - #{app.id}: {app.company_name} (status: {app.email_status})")
            if len(apps_without_id) > 5:
                print(f"   ... and {len(apps_without_id) - 5} more")
            print("\n💡 Tip: Run 'python scripts_/fix_missing_gmail_ids.py' to fix these\n")
        
        updated_count = 0
        
        for app in applications:
            try:
                logger.info(f"🔍 Checking application {app.id}, Gmail ID: {app.gmail_message_id[:20]}...")
                
                status_info = self.check_message_status(app.gmail_message_id, app.gmail_thread_id)
                
                if status_info and 'error' not in status_info:
                    old_status = app.email_status
                    
                    if status_info['timestamp'] and not app.sent_at:
                        app.sent_at = status_info['timestamp']
                    
                    if status_info.get('read') and not app.read_at:
                        app.read_at = status_info.get('read_time') or datetime.utcnow()
                    
                    new_status = status_info['status']
                    if new_status != old_status:
                        app.email_status = new_status
                        logger.info(f"🔄 Status changed: {old_status} → {new_status}")
                    
                    thread_info = status_info.get('thread_info', {})
                    if thread_info.get('has_responses'):
                        app.email_status = 'responded'
                        app.has_response = True
                        app.response_thread_count = thread_info.get('response_count', 0)
                        
                        if thread_info.get('latest_response_time') and not app.response_received_at:
                            app.response_received_at = thread_info['latest_response_time']
                    
                    app.updated_at = datetime.utcnow()
                    updated_count += 1
                    
                    logger.info(f"✅ Updated application {app.id}")
                
                elif status_info and status_info.get('error'):
                    logger.error(f"❌ Error for application {app.id}: {status_info['error']}")
                    if status_info.get('status') == 'failed':
                        app.email_status = 'failed'
                        updated_count += 1
                
                time.sleep(0.2)
                
            except Exception as e:
                logger.error(f"❌ Error updating application {app.id}: {e}")
                continue
        
        try:
            db.session.commit()
            logger.info(f"✅ Updated {updated_count} applications")
            print(f"✅ Updated {updated_count} applications")
        except Exception as e:
            logger.error(f"❌ Error committing changes: {e}")
            db.session.rollback()
        
        return updated_count
    
    def check_recent_responses(self, days=7):
        """Check for responses in recent applications"""
        logger.info(f"🔍 Checking recent responses (last {days} days)")
        
        from models import Application
        from app import db
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        recent_apps = Application.query.filter_by(user_id=self.user_id)\
            .filter(Application.sent_at >= cutoff_date)\
            .filter(Application.gmail_thread_id.isnot(None))\
            .filter(Application.has_response == False).all()
        
        logger.info(f"📋 Found {len(recent_apps)} recent apps to check for responses")
        
        responses_found = 0
        
        for app in recent_apps:
            try:
                if app.gmail_thread_id:
                    thread_info = self.check_thread_activity(app.gmail_thread_id)
                    if thread_info.get('has_responses'):
                        app.email_status = 'responded'
                        app.has_response = True
                        app.response_thread_count = thread_info.get('response_count', 0)
                        app.response_received_at = thread_info.get('latest_response_time')
                        app.updated_at = datetime.utcnow()
                        responses_found += 1
                        logger.info(f"✅ Found response for application {app.id}")
                
                time.sleep(0.2)
            except Exception as e:
                logger.error(f"❌ Error checking app {app.id}: {e}")
                continue
        
        try:
            db.session.commit()
            logger.info(f"✅ Found {responses_found} new responses")
        except Exception as e:
            logger.error(f"❌ Error committing: {e}")
            db.session.rollback()
        
        return responses_found
    
    def force_status_refresh(self, application_id):
        """Force refresh status for a specific application"""
        logger.info(f"🚀 Force refreshing application {application_id}")
        
        from models import Application
        from app import db
        
        try:
            app = Application.query.filter_by(id=application_id, user_id=self.user_id).first()
            
            if not app:
                return {'error': 'Application not found'}
            
            if not app.gmail_message_id:
                return {'error': 'No Gmail message ID - cannot track this application'}
            
            status_info = self.check_message_status(app.gmail_message_id, app.gmail_thread_id)
            
            if status_info and 'error' not in status_info:
                old_status = app.email_status
                
                if status_info['timestamp'] and not app.sent_at:
                    app.sent_at = status_info['timestamp']
                
                if status_info.get('read') and not app.read_at:
                    app.read_at = status_info.get('read_time') or datetime.utcnow()
                
                app.email_status = status_info['status']
                
                thread_info = status_info.get('thread_info', {})
                if thread_info.get('has_responses'):
                    app.email_status = 'responded'
                    app.has_response = True
                    app.response_thread_count = thread_info.get('response_count', 0)
                    if thread_info.get('latest_response_time'):
                        app.response_received_at = thread_info['latest_response_time']
                
                app.updated_at = datetime.utcnow()
                db.session.commit()
                
                return {
                    'success': True,
                    'old_status': old_status,
                    'new_status': app.email_status,
                    'read': bool(app.read_at),
                    'has_response': app.has_response
                }
            else:
                error = status_info.get('error', 'Unknown error') if status_info else 'Failed to get status'
                return {'error': error}
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Error: {e}")
            return {'error': str(e)}