# mailer.py
import base64
import os
import json
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from flask import current_app
from socket import timeout


def build_credentials(token_json):
    """Build Google credentials from token JSON"""
    try:
        # Parse JSON if it's a string
        if isinstance(token_json, str):
            token_dict = json.loads(token_json)
        else:
            token_dict = token_json
            
        # Log what we received for debugging
        current_app.logger.debug(f"Token data before processing: {token_dict}")
        
        # Make sure all required fields are present
        if 'client_id' not in token_dict or not token_dict['client_id']:
            token_dict['client_id'] = current_app.config.get('GOOGLE_CLIENT_ID')
            
        if 'client_secret' not in token_dict or not token_dict['client_secret']:
            token_dict['client_secret'] = current_app.config.get('GOOGLE_CLIENT_SECRET')
            
        if 'token_uri' not in token_dict or not token_dict['token_uri']:
            token_dict['token_uri'] = 'https://oauth2.googleapis.com/token'
        
        # Handle different token formats (Authlib vs. standard)
        if 'token' in token_dict and 'access_token' not in token_dict:
            token_dict['access_token'] = token_dict['token']
            
        if 'access_token' in token_dict and 'token' not in token_dict:
            token_dict['token'] = token_dict['access_token']
            
        # Final check for required fields
        required_fields = ['token', 'refresh_token', 'token_uri', 'client_id', 'client_secret']
        missing_fields = [field for field in required_fields if field not in token_dict or not token_dict[field]]
        
        if missing_fields:
            current_app.logger.error(f"Missing required credential fields: {missing_fields}")
            if 'refresh_token' in missing_fields:
                current_app.logger.error("Missing refresh_token - user may need to re-authenticate with prompt=consent")
        
        # GET SCOPES FROM CONFIG INSTEAD OF HARDCODING
        oauth_scopes = current_app.config.get('GOOGLE_OAUTH_SCOPES', [
            'https://www.googleapis.com/auth/gmail.send',
            'https://www.googleapis.com/auth/gmail.readonly', 
            'https://www.googleapis.com/auth/gmail.modify'
        ])
                
        # Create credentials object
        credentials = Credentials(
            token=token_dict.get('token') or token_dict.get('access_token'),
            refresh_token=token_dict.get('refresh_token'),
            token_uri=token_dict.get('token_uri'),
            client_id=token_dict.get('client_id'),
            client_secret=token_dict.get('client_secret'),
            scopes=oauth_scopes
        )
        
        return credentials
            
    except Exception as e:
        current_app.logger.error(f"Error building credentials: {str(e)}")
        raise


def create_message_with_attachments(sender, to, subject, body, file_paths=None):
    """Create a message with attachments"""
    message = MIMEMultipart()
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    
    # Add body
    message.attach(MIMEText(body))
    
    # Add attachments
    if file_paths:
        for file_path in file_paths:
            path = file_path.get('path') if isinstance(file_path, dict) else file_path
            filename = file_path.get('filename') if isinstance(file_path, dict) else os.path.basename(path)
            
            if not os.path.exists(path):
                current_app.logger.warning(f"File not found: {path}")
                continue
                
            with open(path, 'rb') as file:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(file.read())
                
            # Encode and add header
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f"attachment; filename={filename}")
            message.attach(part)
    
    # Encode message
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': raw}


def refresh_credentials_if_needed(credentials):
    """Refresh credentials if they're expired"""
    try:
        if credentials.expired and credentials.refresh_token:
            from google.auth.transport.requests import Request
            credentials.refresh(Request())
            current_app.logger.info("Credentials refreshed successfully")
            return True
        return False
    except Exception as e:
        current_app.logger.error(f"Error refreshing credentials: {str(e)}")
        return False


def send_gmail_message(credentials, message, max_retries=3, retry_delay=2):
    """
    Send message using Gmail API with retry logic
    
    Returns:
        dict: The sent message with 'id' and 'threadId' for tracking
    """
    current_app.logger.info("DEBUG: Starting send_gmail_message function")
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Check if we're using a mock credential (for development)
            if hasattr(credentials, 'valid') and not isinstance(credentials.valid, bool):
                current_app.logger.info("Using mock credentials - email would be sent in production")
                return {'id': 'mock-message-id', 'threadId': 'mock-thread-id'}
            
            # Refresh credentials if needed
            current_app.logger.info("DEBUG: About to refresh credentials if needed")
            refresh_credentials_if_needed(credentials)
            
            # Build Gmail service
            current_app.logger.info("DEBUG: About to build Gmail service")
            service = build('gmail', 'v1', credentials=credentials)
            current_app.logger.info("DEBUG: Gmail service built successfully")
            
            # Send the message
            current_app.logger.info("DEBUG: About to send message")
            sent_message = service.users().messages().send(userId='me', body=message).execute()
            
            # Log the tracking IDs
            gmail_id = sent_message.get('id')
            thread_id = sent_message.get('threadId')
            current_app.logger.info(f"✅ Email sent successfully!")
            current_app.logger.info(f"   Message ID: {gmail_id}")
            current_app.logger.info(f"   Thread ID: {thread_id}")
            
            return sent_message
            
        except HttpError as e:
            current_app.logger.error(f"Gmail API HttpError: {e}")
            
            if hasattr(e, 'resp'):
                status = e.resp.status
                
                if status == 429:  # Rate limited
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = retry_delay * (2 ** (retry_count - 1))
                        current_app.logger.info(f"Rate limited, waiting {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise Exception("Rate limit exceeded after all retries")
                        
                elif status == 401:
                    raise Exception("Gmail API unauthorized. Please re-authenticate.")
                    
                elif status == 403:
                    raise Exception("Gmail API access forbidden. Check your OAuth scopes.")
                    
            raise
            
        except (timeout, TimeoutError) as e:
            retry_count += 1
            current_app.logger.warning(f"Email send timed out (attempt {retry_count}/{max_retries}): {str(e)}")
            
            if retry_count < max_retries:
                current_app.logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30)
            else:
                current_app.logger.error("Maximum retry attempts reached, giving up.")
                raise
                
        except Exception as e:
            current_app.logger.error(f"Exception in send_gmail_message: {str(e)}")
            
            # Check for network errors
            if any(err_type in str(e).lower() for err_type in ['timeout', 'timed out', 'connection', 'network']):
                retry_count += 1
                if retry_count < max_retries:
                    current_app.logger.info(f"Network error, retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 30)
                    continue
                    
            raise
    
    raise Exception("Maximum retry attempts exceeded")


def send_email_with_tracking(user_id, to_email, subject, body, attachments=None):
    """
    High-level function to send email and return tracking info
    
    Parameters:
        user_id: ID of the user sending the email
        to_email: Recipient email address
        subject: Email subject
        body: Email body text
        attachments: List of file path dicts with 'path' and 'filename'
    
    Returns:
        dict: {
            'success': bool,
            'message': str,
            'gmail_message_id': str or None,
            'gmail_thread_id': str or None
        }
    """
    from models import GoogleToken, User
    
    result = {
        'success': False,
        'message': '',
        'gmail_message_id': None,
        'gmail_thread_id': None
    }
    
    try:
        # Get user's token
        google_token = GoogleToken.query.filter_by(user_id=user_id).first()
        if not google_token:
            result['message'] = "No Google authentication found. Please connect your Google account."
            return result
        
        # Get sender email
        user = User.query.get(user_id)
        if not user:
            result['message'] = "User not found"
            return result
        
        sender_email = user.email
        
        # Build credentials
        credentials = build_credentials(google_token.token_json)
        
        # Create message
        message = create_message_with_attachments(
            sender=sender_email,
            to=to_email,
            subject=subject,
            body=body,
            file_paths=attachments
        )
        
        # Send message
        sent_message = send_gmail_message(credentials, message)
        
        if sent_message:
            result['success'] = True
            result['message'] = "Email sent successfully"
            result['gmail_message_id'] = sent_message.get('id')
            result['gmail_thread_id'] = sent_message.get('threadId')
        else:
            result['message'] = "Failed to send email"
            
    except Exception as e:
        current_app.logger.error(f"Error in send_email_with_tracking: {e}")
        result['message'] = str(e)
    
    return result