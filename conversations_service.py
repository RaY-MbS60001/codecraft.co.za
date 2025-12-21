# Add to your gmail_service.py or create a new conversations_service.py

import base64
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import re

class ConversationService:
    def __init__(self, gmail_service):
        self.service = gmail_service
    
    def get_thread_messages(self, thread_id):
        """Get all messages in a Gmail thread"""
        try:
            thread = self.service.users().threads().get(
                userId='me', 
                id=thread_id,
                format='full'
            ).execute()
            
            messages = []
            for msg in thread.get('messages', []):
                message_data = self.parse_message(msg)
                messages.append(message_data)
            
            return messages
        except Exception as e:
            print(f"Error getting thread messages: {e}")
            return []
    
    def parse_message(self, message):
        """Parse Gmail message into structured data"""
        headers = {h['name']: h['value'] for h in message['payload'].get('headers', [])}
        
        # Get message body
        body = self.extract_message_body(message['payload'])
        
        return {
            'id': message['id'],
            'thread_id': message['threadId'],
            'subject': headers.get('Subject', ''),
            'from': headers.get('From', ''),
            'to': headers.get('To', ''),
            'date': headers.get('Date', ''),
            'timestamp': self.parse_gmail_date(headers.get('Date', '')),
            'body': body.get('text', ''),
            'html_body': body.get('html', ''),
            'snippet': message.get('snippet', ''),
            'has_attachments': self.has_attachments(message['payload'])
        }
    
    def extract_message_body(self, payload):
        """Extract text and HTML body from message payload"""
        body = {'text': '', 'html': ''}
        
        if payload.get('body', {}).get('data'):
            # Simple message
            data = payload['body']['data']
            text = base64.urlsafe_b64decode(data).decode('utf-8')
            body['text'] = text
        elif payload.get('parts'):
            # Multipart message
            for part in payload['parts']:
                mime_type = part.get('mimeType', '')
                if mime_type == 'text/plain' and part.get('body', {}).get('data'):
                    data = part['body']['data']
                    body['text'] = base64.urlsafe_b64decode(data).decode('utf-8')
                elif mime_type == 'text/html' and part.get('body', {}).get('data'):
                    data = part['body']['data']
                    body['html'] = base64.urlsafe_b64decode(data).decode('utf-8')
        
        return body
    
    def has_attachments(self, payload):
        """Check if message has attachments"""
        if payload.get('parts'):
            for part in payload['parts']:
                if part.get('filename') and part['filename'] != '':
                    return True
        return False
    
    def parse_gmail_date(self, date_str):
        """Parse Gmail date string to datetime"""
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except:
            return datetime.utcnow()
    
    def send_reply(self, thread_id, to_email, subject, body, from_email):
        """Send a reply to an existing thread"""
        try:
            message = MIMEText(body)
            message['to'] = to_email
            message['subject'] = f"Re: {subject}" if not subject.startswith('Re:') else subject
            message['from'] = from_email
            
            # Add thread reference headers
            message['In-Reply-To'] = thread_id
            message['References'] = thread_id
            
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            send_message = {
                'raw': raw_message,
                'threadId': thread_id
            }
            
            result = self.service.users().messages().send(
                userId='me',
                body=send_message
            ).execute()
            
            return result
            
        except Exception as e:
            print(f"Error sending reply: {e}")
            return None
    
    def sync_conversation_from_thread(self, thread_id, application_id):
        """Sync conversation data from Gmail thread"""
        try:
            messages = self.get_thread_messages(thread_id)
            
            if not messages:
                return None
            
            # Get or create conversation
            conversation = Conversation.query.filter_by(
                gmail_thread_id=thread_id
            ).first()
            
            if not conversation:
                application = Application.query.get(application_id)
                if not application:
                    return None
                
                conversation = Conversation(
                    application_id=application_id,
                    gmail_thread_id=thread_id,
                    subject=messages[0]['subject'],
                    corporate_user_id=application.corporate_user_id,
                    applicant_user_id=application.user_id
                )
                db.session.add(conversation)
                db.session.flush()
            
            # Sync messages
            for msg in messages:
                existing_msg = ConversationMessage.query.filter_by(
                    gmail_message_id=msg['id']
                ).first()
                
                if not existing_msg:
                    # Determine sender type
                    sender_type = self.determine_sender_type(msg['from'], conversation)
                    sender_id = self.get_sender_id(msg['from'], conversation)
                    
                    conv_message = ConversationMessage(
                        conversation_id=conversation.id,
                        gmail_message_id=msg['id'],
                        sender_id=sender_id,
                        sender_type=sender_type,
                        subject=msg['subject'],
                        body=msg['body'],
                        html_body=msg['html_body'],
                        gmail_timestamp=msg['timestamp'],
                        has_attachments=msg['has_attachments']
                    )
                    
                    db.session.add(conv_message)
            
            # Update conversation metadata
            conversation.last_message_at = max(msg['timestamp'] for msg in messages)
            conversation.updated_at = datetime.utcnow()
            
            db.session.commit()
            return conversation
            
        except Exception as e:
            db.session.rollback()
            print(f"Error syncing conversation: {e}")
            return None
    
    def determine_sender_type(self, from_email, conversation):
        """Determine if sender is corporate or applicant"""
        corporate_user = User.query.get(conversation.corporate_user_id)
        if corporate_user and corporate_user.company_email in from_email:
            return 'corporate'
        return 'applicant'
    
    def get_sender_id(self, from_email, conversation):
        """Get sender user ID"""
        corporate_user = User.query.get(conversation.corporate_user_id)
        if corporate_user and corporate_user.company_email in from_email:
            return conversation.corporate_user_id
        return conversation.applicant_user_id