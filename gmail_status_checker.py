import json
import time
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class GmailStatusChecker:
    def __init__(self, user_id):
        self.user_id = user_id
        self.service = None
        
    def get_gmail_service(self):
        """Get authenticated Gmail service"""
        try:
            # Import here to avoid circular import
            from models import GoogleToken
            
            # Get user's Google token
            google_token = GoogleToken.query.filter_by(user_id=self.user_id).first()
            if not google_token:
                print(f"No Google token found for user {self.user_id}")
                return None
            
            # Parse token data
            token_data = json.loads(google_token.token_json)
            
            # Create credentials
            credentials = Credentials(
                token=token_data.get('access_token'),
                refresh_token=token_data.get('refresh_token'),
                token_uri=token_data.get('token_uri'),
                client_id=token_data.get('client_id'),
                client_secret=token_data.get('client_secret'),
                scopes=token_data.get('scopes', [])
            )
            
            # Build Gmail service
            self.service = build('gmail', 'v1', credentials=credentials)
            return self.service
            
        except Exception as e:
            print(f"Error creating Gmail service: {e}")
            return None
    
    def check_message_status(self, gmail_message_id):
        """Check status of a specific Gmail message"""
        if not self.service:
            self.service = self.get_gmail_service()
            
        if not self.service:
            return None
            
        try:
            # Get message details
            message = self.service.users().messages().get(
                userId='me', 
                id=gmail_message_id,
                format='metadata',
                metadataHeaders=['Message-ID', 'Subject', 'To', 'Date']
            ).execute()
            
            # Check if message exists in sent folder
            labels = message.get('labelIds', [])
            is_sent = 'SENT' in labels
            
            if not is_sent:
                return {'status': 'draft', 'timestamp': None}
            
            # Get message timestamp
            internal_date = int(message.get('internalDate', 0))
            sent_time = datetime.fromtimestamp(internal_date / 1000) if internal_date else None
            
            # Check for thread activity (responses)
            thread_id = message.get('threadId')
            thread_info = self.check_thread_activity(thread_id)
            
            return {
                'status': 'responded' if thread_info.get('has_responses') else 'sent',
                'timestamp': sent_time,
                'thread_info': thread_info
            }
            
        except HttpError as error:
            print(f"Gmail API error checking message {gmail_message_id}: {error}")
            return None
        except Exception as e:
            print(f"Error checking message status: {e}")
            return None
    
    def check_thread_activity(self, thread_id):
        """Check if there are responses in the thread"""
        try:
            thread = self.service.users().threads().get(
                userId='me',
                id=thread_id
            ).execute()
            
            messages = thread.get('messages', [])
            message_count = len(messages)
            
            # If more than 1 message, there are responses
            has_responses = message_count > 1
            
            # Get latest message timestamp if there are responses
            latest_response_time = None
            if has_responses and message_count > 1:
                latest_message = messages[-1]  # Last message in thread
                internal_date = int(latest_message.get('internalDate', 0))
                latest_response_time = datetime.fromtimestamp(internal_date / 1000) if internal_date else None
            
            return {
                'has_responses': has_responses,
                'message_count': message_count,
                'latest_response_time': latest_response_time
            }
            
        except HttpError as error:
            print(f"Gmail API error checking thread {thread_id}: {error}")
            return {'has_responses': False, 'message_count': 1, 'latest_response_time': None}
        except Exception as e:
            print(f"Error checking thread activity: {e}")
            return {'has_responses': False, 'message_count': 1, 'latest_response_time': None}
    
    def update_application_statuses(self):
        """Update statuses for all applications for this user"""
        # Import here to avoid circular import
        from models import Application
        from app import db
        
        applications = Application.query.filter_by(
            user_id=self.user_id
        ).filter(
            Application.gmail_message_id.isnot(None)
        ).all()
        
        updated_count = 0
        
        for app in applications:
            try:
                print(f"Checking status for application {app.id}, message ID: {app.gmail_message_id}")
                
                status_info = self.check_message_status(app.gmail_message_id)
                
                if status_info:
                    # Update basic status
                    if status_info['timestamp'] and not app.sent_at:
                        app.sent_at = status_info['timestamp']
                    
                    # Update email status
                    if status_info['status']:
                        app.email_status = status_info['status']
                    
                    # Update thread activity
                    thread_info = status_info.get('thread_info', {})
                    if thread_info.get('has_responses'):
                        app.email_status = 'responded'
                        app.has_response = True
                        app.response_thread_count = max(0, thread_info.get('message_count', 1) - 1)
                        
                        if thread_info.get('latest_response_time'):
                            app.response_received_at = thread_info['latest_response_time']
                    
                    app.updated_at = datetime.utcnow()
                    updated_count += 1
                    
                    print(f"✓ Updated application {app.id}: status={app.email_status}, responses={app.has_response}")
                
                # Add small delay to avoid rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Error updating application {app.id}: {e}")
                continue
        
        db.session.commit()
        print(f"✅ Updated {updated_count} applications")
        return updated_count
    
    def check_recent_responses(self, days=7):
        """Check for responses in applications from the last N days"""
        # Import here to avoid circular import
        from models import Application
        from app import db
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        recent_apps = Application.query.filter_by(user_id=self.user_id)\
            .filter(Application.sent_at >= cutoff_date)\
            .filter(Application.gmail_thread_id.isnot(None))\
            .filter(Application.has_response == False).all()
        
        responses_found = 0
        
        for app in recent_apps:
            try:
                if app.gmail_thread_id:
                    thread_info = self.check_thread_activity(app.gmail_thread_id)
                    if thread_info.get('has_responses'):
                        app.email_status = 'responded'
                        app.has_response = True
                        app.response_thread_count = thread_info.get('message_count', 1) - 1
                        app.response_received_at = thread_info.get('latest_response_time')
                        app.updated_at = datetime.utcnow()
                        responses_found += 1
                        print(f"✓ Found response for application {app.id}")
                
                time.sleep(0.1)
            except Exception as e:
                print(f"Error checking responses for app {app.id}: {e}")
                continue
        
        db.session.commit()
        return responses_found