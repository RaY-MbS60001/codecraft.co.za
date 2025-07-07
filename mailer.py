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
        if 'token' in token_dict and not 'access_token' in token_dict:
            token_dict['access_token'] = token_dict['token']
            
        if 'access_token' in token_dict and not 'token' in token_dict:
            token_dict['token'] = token_dict['access_token']
            
        # Final check for required fields
        required_fields = ['token', 'refresh_token', 'token_uri', 'client_id', 'client_secret']
        missing_fields = [field for field in required_fields if field not in token_dict or not token_dict[field]]
        
        if missing_fields:
            current_app.logger.error(f"Missing required credential fields: {missing_fields}")
            if 'refresh_token' in missing_fields:
                current_app.logger.error("Missing refresh_token - user may need to re-authenticate with prompt=consent")
                
        # Create credentials object
        credentials = Credentials(
            token=token_dict.get('token') or token_dict.get('access_token'),
            refresh_token=token_dict.get('refresh_token'),
            token_uri=token_dict.get('token_uri'),
            client_id=token_dict.get('client_id'),
            client_secret=token_dict.get('client_secret'),
            scopes=['https://www.googleapis.com/auth/gmail.send']
        )
        
        return credentials
            
    except Exception as e:
        current_app.logger.error(f"Error building credentials: {str(e)}")
        raise  # Re-raise the exception instead of returning a mock

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
            if not os.path.exists(file_path['path']):
                current_app.logger.warning(f"File not found: {file_path['path']}")
                continue
                
            with open(file_path['path'], 'rb') as file:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(file.read())
                
            # Encode and add header
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f"attachment; filename={file_path['filename']}")
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
    """Send message using Gmail API with retry logic for timeouts"""
    current_app.logger.info("DEBUG: Starting send_gmail_message function")
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Check if we're using a mock credential (for development)
            if hasattr(credentials, 'valid') and not isinstance(credentials.valid, bool):
                current_app.logger.info("Using mock credentials - email would be sent in production")
                return {'id': 'mock-message-id'}
            
            # Refresh credentials if needed
            current_app.logger.info("DEBUG: About to refresh credentials if needed")
            refresh_credentials_if_needed(credentials)
            
            # Build Gmail service - ONLY pass credentials, no http parameter
            current_app.logger.info("DEBUG: About to build Gmail service with credentials only")
            service = build('gmail', 'v1', credentials=credentials)
            current_app.logger.info("DEBUG: Gmail service built successfully")
            
            # Send the message
            current_app.logger.info("DEBUG: About to send message")
            sent_message = service.users().messages().send(userId='me', body=message).execute()
            current_app.logger.info(f"Email sent successfully: {sent_message.get('id')}")
            return sent_message
            
        except Exception as e:
            current_app.logger.error(f"DEBUG: Exception in send_gmail_message: {str(e)}")
            current_app.logger.error(f"DEBUG: Exception type: {type(e)}")
            
            # Check if it's the http/credentials error
            if "Arguments http and credentials are mutually exclusive" in str(e):
                current_app.logger.error("DEBUG: This is the http/credentials error - investigating...")
                # Let's see the full stack trace
                import traceback
                current_app.logger.error(f"DEBUG: Full traceback: {traceback.format_exc()}")
            
            # Handle specific exceptions
            if isinstance(e, (timeout, TimeoutError)):
                retry_count += 1
                current_app.logger.warning(f"Email send timed out (attempt {retry_count}/{max_retries}): {str(e)}")
                
                if retry_count < max_retries:
                    current_app.logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 30)
                else:
                    current_app.logger.error("Maximum retry attempts reached, giving up.")
                    raise
                    
            elif isinstance(e, HttpError):
                # Handle HTTP errors
                error_details = e.error_details if hasattr(e, 'error_details') else str(e)
                current_app.logger.error(f'Gmail API HttpError: {error_details}')
                
                if hasattr(e, 'resp') and e.resp.status == 429:
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = retry_delay * (2 ** (retry_count - 1))
                        current_app.logger.info(f"Rate limited, waiting {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise Exception("Rate limit exceeded after all retries")
                elif hasattr(e, 'resp') and e.resp.status == 401:
                    raise Exception("Gmail API unauthorized. Please re-authenticate.")
                elif hasattr(e, 'resp') and e.resp.status == 403:
                    raise Exception("Gmail API access forbidden. Check your OAuth scopes.")
                else:
                    raise
                    
            else:
                # Other exceptions
                if any(err_type in str(e).lower() for err_type in ['timeout', 'timed out', 'connection', 'network']):
                    retry_count += 1
                    if retry_count < max_retries:
                        current_app.logger.info(f"Network error, retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, 30)
                        continue
                    else:
                        current_app.logger.error("Maximum retry attempts reached, giving up.")
                        raise
                else:
                    raise
    
    raise Exception("Maximum retry attempts exceeded")