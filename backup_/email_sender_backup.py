# email_sender.py
# Updated to use Gmail API for tracking

import base64
import os
import time
import random
import logging
import re
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from flask import current_app
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def is_valid_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def create_application_email(sender_email, to_email, subject, body, attachments=None):
    """Create a MIME message with attachments"""
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    # Add attachments
    if attachments:
        for attachment in attachments:
            if not os.path.exists(attachment['path']):
                logger.error(f"Attachment file not found: {attachment['path']}")
                continue
                
            with open(attachment['path'], "rb") as file:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(file.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{attachment["filename"]}"'
                )
                msg.attach(part)
                
    return msg


def get_gmail_service(user_id):
    """Get authenticated Gmail service for a user"""
    try:
        from models import GoogleToken
        
        google_token = GoogleToken.query.filter_by(user_id=user_id).first()
        if not google_token:
            logger.error(f"No Google token found for user {user_id}")
            return None
        
        token_data = json.loads(google_token.token_json)
        
        # Get client credentials from config or token
        client_id = token_data.get('client_id') or current_app.config.get('GOOGLE_CLIENT_ID')
        client_secret = token_data.get('client_secret') or current_app.config.get('GOOGLE_CLIENT_SECRET')
        
        credentials = Credentials(
            token=token_data.get('access_token') or token_data.get('token'),
            refresh_token=token_data.get('refresh_token'),
            token_uri=token_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
            client_id=client_id,
            client_secret=client_secret,
            scopes=token_data.get('scopes', [
                'https://www.googleapis.com/auth/gmail.send',
                'https://www.googleapis.com/auth/gmail.readonly',
                'https://www.googleapis.com/auth/gmail.modify'
            ])
        )
        
        # Refresh if expired
        if credentials.expired and credentials.refresh_token:
            from google.auth.transport.requests import Request
            credentials.refresh(Request())
            
            # Update stored token
            token_data['access_token'] = credentials.token
            token_data['token'] = credentials.token
            google_token.token_json = json.dumps(token_data)
            
            from models import db
            db.session.commit()
            logger.info(f"Refreshed token for user {user_id}")
        
        service = build('gmail', 'v1', credentials=credentials)
        return service
        
    except Exception as e:
        logger.error(f"Error creating Gmail service for user {user_id}: {e}")
        return None


def send_email_via_gmail_api(user_id, to_email, subject, body, attachments=None):
    """
    Send email via Gmail API and return tracking IDs
    
    Returns:
        dict: {
            'success': bool,
            'to_email': str,
            'message': str,
            'gmail_message_id': str or None,
            'gmail_thread_id': str or None
        }
    """
    result = {
        'success': False,
        'to_email': to_email,
        'message': '',
        'gmail_message_id': None,
        'gmail_thread_id': None
    }
    
    if not is_valid_email(to_email):
        result['message'] = "Invalid email format"
        return result
    
    try:
        # Get Gmail service
        service = get_gmail_service(user_id)
        if not service:
            result['message'] = "Could not connect to Gmail. Please re-authenticate."
            return result
        
        # Get sender email
        from models import User
        user = User.query.get(user_id)
        if not user:
            result['message'] = "User not found"
            return result
        
        sender_email = user.email
        
        # Create MIME message
        msg = create_application_email(sender_email, to_email, subject, body, attachments)
        
        # Encode for Gmail API
        raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
        
        # Send via Gmail API
        sent_message = service.users().messages().send(
            userId='me',
            body={'raw': raw_message}
        ).execute()
        
        # Extract tracking IDs
        gmail_message_id = sent_message.get('id')
        gmail_thread_id = sent_message.get('threadId')
        
        logger.info(f"✅ Email sent to {to_email}")
        logger.info(f"   Gmail Message ID: {gmail_message_id}")
        logger.info(f"   Gmail Thread ID: {gmail_thread_id}")
        
        result['success'] = True
        result['message'] = "Sent successfully"
        result['gmail_message_id'] = gmail_message_id
        result['gmail_thread_id'] = gmail_thread_id
        
        return result
        
    except HttpError as e:
        error_msg = f"Gmail API error: {e.reason if hasattr(e, 'reason') else str(e)}"
        logger.error(f"❌ {error_msg}")
        result['message'] = error_msg
        return result
        
    except Exception as e:
        error_msg = f"Error sending email: {str(e)}"
        logger.error(f"❌ {error_msg}")
        result['message'] = error_msg
        return result


def send_application_email(sender_email, sender_password, to_email, subject, body, attachments=None):
    """
    Legacy SMTP function - kept for backward compatibility
    Use send_email_via_gmail_api() instead for tracking
    
    Returns:
        tuple: (to_email, success, message)
    """
    if not is_valid_email(to_email):
        return (to_email, False, "Invalid email format")
    
    # Try Gmail API first if we have a current user
    try:
        from flask_login import current_user
        if current_user and current_user.is_authenticated:
            result = send_email_via_gmail_api(
                user_id=current_user.id,
                to_email=to_email,
                subject=subject,
                body=body,
                attachments=attachments
            )
            if result['success']:
                # Return with gmail_id attached for caller to use
                return (to_email, True, "Sent successfully", result['gmail_message_id'], result['gmail_thread_id'])
            else:
                logger.warning(f"Gmail API failed, falling back to SMTP: {result['message']}")
    except Exception as e:
        logger.warning(f"Could not use Gmail API, falling back to SMTP: {e}")
    
    # Fallback to SMTP (no tracking)
    import smtplib
    msg = create_application_email(sender_email, to_email, subject, body, attachments)
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.send_message(msg)
            logger.info(f"Email successfully sent to {to_email} via SMTP")
            return (to_email, True, "Sent successfully (SMTP - no tracking)")
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(random.uniform(1, 3))
                continue
            logger.error(f"Failed to send email to {to_email}: {e}")
            return (to_email, False, str(e))


def send_single_application_with_tracking(user, to_email, company_name, subject=None, body=None, attachments=None):
    """
    Send a single application email and create Application record with tracking
    
    Parameters:
        user: User model instance
        to_email: Recipient email address
        company_name: Company name for the application
        subject: Email subject (optional, will generate default)
        body: Email body (optional, will generate default)
        attachments: List of attachment dicts with 'path' and 'filename'
    
    Returns:
        dict: Result with application_id and tracking info
    """
    from models import Application, db
    
    # Generate default subject if not provided
    if not subject:
        subject = f"Learnership Application - {user.full_name or user.email}"
    
    # Generate default body if not provided
    if not body:
        body = f"""
Dear {company_name} Recruitment Team,

I am writing to express my interest in any learnership opportunities available at {company_name}.

About me:
{user.full_name or 'Name not provided'}
{f"Phone: {user.phone}" if user.phone else ''}
Email: {user.email}
{f"Address: {user.address}" if user.address else ''}

I am eager to develop my skills and gain practical experience in a professional environment. I believe that a learnership at your company would be an excellent opportunity for me to grow professionally.

Please find my CV and supporting documents attached for your consideration.

Thank you for your time and consideration. I look forward to the possibility of contributing to your team.

Kind regards,
{user.full_name or user.email}
"""
    
    # Send email via Gmail API
    result = send_email_via_gmail_api(
        user_id=user.id,
        to_email=to_email,
        subject=subject,
        body=body,
        attachments=attachments
    )
    
    # Create Application record
    application = None
    if result['success']:
        try:
            application = Application(
                user_id=user.id,
                company_name=company_name,
                learnership_name=f"Application to {company_name}",
                status='submitted',
                email_status='sent',
                sent_at=datetime.utcnow(),
                gmail_message_id=result['gmail_message_id'],
                gmail_thread_id=result['gmail_thread_id']
            )
            db.session.add(application)
            db.session.commit()
            
            logger.info(f"✅ Created Application #{application.id} with Gmail tracking")
            
            result['application_id'] = application.id
            
        except Exception as e:
            logger.error(f"❌ Error creating application record: {e}")
            db.session.rollback()
            result['db_error'] = str(e)
    
    return result


def send_bulk_applications_with_tracking(user, email_entries, documents=None):
    """
    Send applications to multiple companies with Gmail tracking
    
    Parameters:
        user: User model instance
        email_entries: List of objects with 'email' and 'company_name' attributes
        documents: List of Document model instances (optional)
    
    Returns:
        dict: Summary of results with tracking info
    """
    from models import Application, db
    
    results = {
        'total': len(email_entries),
        'successful': 0,
        'failed': 0,
        'details': [],
        'applications_created': []
    }
    
    # Prepare attachments from documents
    attachments = []
    if documents:
        for doc in documents:
            file_path = doc.file_path
            if file_path and os.path.exists(file_path):
                attachments.append({
                    'path': file_path,
                    'filename': doc.original_filename or doc.filename
                })
                logger.info(f"📎 Attached: {doc.original_filename or doc.filename}")
    
    logger.info(f"📧 Starting bulk send to {len(email_entries)} recipients")
    logger.info(f"📎 Attachments: {len(attachments)}")
    
    for entry in email_entries:
        # Get email and company name from entry
        to_email = entry.email if hasattr(entry, 'email') else entry.get('email')
        company_name = entry.company_name if hasattr(entry, 'company_name') else entry.get('company_name', 'Unknown Company')
        
        if not to_email:
            logger.warning(f"⚠️ Skipping entry with no email: {entry}")
            results['failed'] += 1
            results['details'].append({
                'company_name': company_name,
                'to_email': None,
                'success': False,
                'message': 'No email address provided',
                'timestamp': datetime.utcnow()
            })
            continue
        
        logger.info(f"📤 Sending to {company_name} ({to_email})...")
        
        # Send email
        send_result = send_single_application_with_tracking(
            user=user,
            to_email=to_email,
            company_name=company_name,
            attachments=attachments
        )
        
        # Record result
        detail = {
            'company_name': company_name,
            'to_email': to_email,
            'success': send_result['success'],
            'message': send_result['message'],
            'gmail_message_id': send_result.get('gmail_message_id'),
            'gmail_thread_id': send_result.get('gmail_thread_id'),
            'application_id': send_result.get('application_id'),
            'timestamp': datetime.utcnow()
        }
        
        results['details'].append(detail)
        
        if send_result['success']:
            results['successful'] += 1
            if send_result.get('application_id'):
                results['applications_created'].append(send_result['application_id'])
            logger.info(f"✅ Success: {company_name}")
        else:
            results['failed'] += 1
            logger.error(f"❌ Failed: {company_name} - {send_result['message']}")
        
        # Small delay to avoid rate limiting
        time.sleep(0.5)
    
    logger.info(f"📊 Bulk send complete: {results['successful']}/{results['total']} successful")
    
    return results


def bulk_send_applications(user, learnerships, documents, email_config):
    """
    Legacy function - kept for backward compatibility
    Use send_bulk_applications_with_tracking() instead
    """
    # Prepare attachments
    attachments = []
    for doc in documents:
        attachments.append({
            'path': doc.file_path,
            'filename': doc.original_filename
        })
    
    # Prepare application details for each learnership
    tasks = []
    for learnership in learnerships:
        if 'apply_email' not in learnership or not learnership['apply_email']:
            continue
            
        subject = f"Application for {learnership['title']} – {user.full_name or user.email}"
        body = f"""
Dear Hiring Team at {learnership['company']},

I hope this message finds you well.

I am writing to express my sincere interest in the {learnership['title']} opportunity within your organization. I am eager to develop my skills, gain practical experience, and grow professionally in a dynamic and supportive environment like yours.

{user.email_body if hasattr(user, 'email_body') and user.email_body else ''}

Please find my documents attached, which provide more detail about my background and aspirations. I am enthusiastic about the opportunity to contribute to your team while continuing to learn and improve.

Thank you for considering my application. I look forward to the opportunity to engage further.

Kind regards,
{user.full_name or user.email}
{f"📞 {user.phone}" if user.phone else ''}
📧 {user.email}
"""
        
        tasks.append({
            'learnership_id': learnership['id'],
            'to_email': learnership['apply_email'],
            'company_name': learnership['company'],
            'subject': subject,
            'body': body
        })
    
    # Send emails
    results = {
        'total': len(tasks),
        'successful': 0,
        'failed': 0,
        'details': []
    }
    
    from models import Application, db
    
    for task in tasks:
        send_result = send_email_via_gmail_api(
            user_id=user.id,
            to_email=task['to_email'],
            subject=task['subject'],
            body=task['body'],
            attachments=attachments
        )
        
        result = {
            'learnership_id': task['learnership_id'],
            'to_email': task['to_email'],
            'success': send_result['success'],
            'message': send_result['message'],
            'gmail_message_id': send_result.get('gmail_message_id'),
            'timestamp': datetime.utcnow()
        }
        
        if send_result['success']:
            results['successful'] += 1
            
            # Create application record with tracking
            try:
                application = Application(
                    user_id=user.id,
                    learnership_id=task['learnership_id'],
                    company_name=task['company_name'],
                    status='submitted',
                    email_status='sent',
                    sent_at=datetime.utcnow(),
                    gmail_message_id=send_result['gmail_message_id'],
                    gmail_thread_id=send_result['gmail_thread_id']
                )
                db.session.add(application)
                db.session.commit()
                result['application_id'] = application.id
            except Exception as e:
                logger.error(f"Error saving application: {e}")
                db.session.rollback()
        else:
            results['failed'] += 1
            
        results['details'].append(result)
        time.sleep(0.3)
    
    return results


def send_bulk_applications(user, email_entries, documents=None):
    """
    Updated version that uses Gmail API with tracking
    Backward compatible wrapper around send_bulk_applications_with_tracking
    """
    return send_bulk_applications_with_tracking(user, email_entries, documents)