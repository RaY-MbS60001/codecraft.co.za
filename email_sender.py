# email_sender.py
import smtplib
import os
import time
import random
import logging
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from flask import current_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

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
                logging.error(f"Attachment file not found: {attachment['path']}")
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

def send_application_email(sender_email, sender_password, to_email, subject, body, attachments=None):
    """Send email via SMTP with error handling and retries"""
    if not is_valid_email(to_email):
        return (to_email, False, "Invalid email format")
        
    # Create message
    msg = create_application_email(sender_email, to_email, subject, body, attachments)
    
    # Try to send with retries
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.send_message(msg)
            logging.info(f"Email successfully sent to {to_email}")
            return (to_email, True, "Sent successfully")
        except Exception as e:
            if attempt < max_retries - 1:
                # Add random delay before retry
                time.sleep(random.uniform(1, 3))
                continue
            logging.error(f"Failed to send email to {to_email}: {e}")
            return (to_email, False, str(e))

def bulk_send_applications(user, learnerships, documents, email_config):
    """
    Send multiple application emails in parallel
    
    Parameters:
    user (User): User model instance
    learnerships (list): List of learnership dictionaries
    documents (list): List of Document model instances
    email_config (dict): Email configuration with sender email and password
    
    Returns:
    dict: Summary of sending results
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
        # Skip if no email address provided
        if 'apply_email' not in learnership or not learnership['apply_email']:
            continue
            
        # Generate subject and body
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
        
        # Add to tasks
        tasks.append({
            'learnership_id': learnership['id'],
            'to_email': learnership['apply_email'],
            'subject': subject,
            'body': body
        })
    
    # Send emails in parallel
    results = {
        'total': len(tasks),
        'successful': 0,
        'failed': 0,
        'details': []
    }
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_task = {}
        
        for task in tasks:
            future = executor.submit(
                send_application_email, 
                email_config['sender_email'],
                email_config['sender_password'],
                task['to_email'],
                task['subject'],
                task['body'],
                attachments
            )
            future_to_task[future] = task
        
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            try:
                to_email, success, message = future.result()
                result = {
                    'learnership_id': task['learnership_id'],
                    'to_email': to_email,
                    'success': success,
                    'message': message,
                    'timestamp': datetime.utcnow()
                }
                
                if success:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                    
                results['details'].append(result)
                
            except Exception as e:
                logging.error(f"Error processing task for {task['to_email']}: {str(e)}")
                results['failed'] += 1
                results['details'].append({
                    'learnership_id': task['learnership_id'],
                    'to_email': task['to_email'],
                    'success': False,
                    'message': f"Error: {str(e)}",
                    'timestamp': datetime.utcnow()
                })
    
    return results

# Add to email_sender.py

def send_bulk_applications(user, email_entries, documents=None):
    """
    Send applications to multiple learnership email addresses
    
    Parameters:
    user (User): User model instance
    email_entries (list): List of LearnshipEmail model instances
    documents (list, optional): List of Document model instances
    
    Returns:
    dict: Summary of sending results
    """
    # Get email configuration from app config
    try:
        sender_email = current_app.config.get('EMAIL_USERNAME')
        sender_password = current_app.config.get('EMAIL_PASSWORD')
        
        if not sender_email or not sender_password:
            logging.error("Email configuration missing in app config")
            return {
                'total': len(email_entries),
                'successful': 0,
                'failed': len(email_entries),
                'details': [{'to_email': e.email, 'success': False, 'message': 'Email configuration missing'} for e in email_entries]
            }
    except Exception as e:
        logging.error(f"Failed to get email configuration: {e}")
        return {'total': len(email_entries), 'successful': 0, 'failed': len(email_entries), 'error': str(e)}
    
    # Prepare attachments if documents are provided
    attachments = []
    if documents:
        for doc in documents:
            if doc.file_path and os.path.exists(doc.file_path):
                attachments.append({
                    'path': doc.file_path,
                    'filename': doc.original_filename or doc.filename
                })
    
    # Prepare application details for each email
    tasks = []
    for entry in email_entries:
        # Generate subject and body
        subject = f"Learnership Application - {user.full_name or user.email}"
        body = f"""
Dear {entry.company_name} Recruitment Team,

I am writing to express my interest in any learnership opportunities available at {entry.company_name}.

About me:
{user.full_name or 'Name not provided'} 
{f"Phone: {user.phone}" if user.phone else 'Phone not provided'}
Email: {user.email}
{f"Address: {user.address}" if user.address else ''}

I am eager to develop my skills and gain practical experience in a professional environment. I believe that a learnership at your company would be an excellent opportunity for me to grow professionally.

{f"Additional information: {user.bio}" if hasattr(user, 'bio') and user.bio else ''}

Please find my CV and supporting documents attached for your consideration.

Thank you for your time and consideration. I look forward to the possibility of contributing to your team.

Kind regards,
{user.full_name or user.email}
"""
        
        # Add to tasks
        tasks.append({
            'company_name': entry.company_name,
            'to_email': entry.email,
            'subject': subject,
            'body': body
        })
    
    # Send emails in parallel
    results = {
        'total': len(tasks),
        'successful': 0,
        'failed': 0,
        'details': []
    }
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_task = {}
        
        for task in tasks:
            future = executor.submit(
                send_application_email, 
                sender_email,
                sender_password,
                task['to_email'],
                task['subject'],
                task['body'],
                attachments
            )
            future_to_task[future] = task
        
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            try:
                to_email, success, message = future.result()
                result = {
                    'company_name': task['company_name'],
                    'to_email': to_email,
                    'success': success,
                    'message': message,
                    'timestamp': datetime.utcnow()
                }
                
                if success:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                    
                results['details'].append(result)
                
            except Exception as e:
                logging.error(f"Error processing task for {task['to_email']}: {str(e)}")
                results['failed'] += 1
                results['details'].append({
                    'company_name': task['company_name'],
                    'to_email': task['to_email'],
                    'success': False,
                    'message': f"Error: {str(e)}",
                    'timestamp': datetime.utcnow()
                })
    
    return results