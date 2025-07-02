# tasks.py
import threading
import traceback
import json
import time
from flask import current_app
from datetime import datetime

def launch_bulk_send(user, learnerships, attachment_ids):
    """Launch a background thread to send application emails"""
    # Store app reference to use in the thread
    app = current_app._get_current_object()
    thread = threading.Thread(
        target=bulk_send_job,
        args=(app, user.id, learnerships, attachment_ids)
    )
    thread.daemon = True
    thread.start()
    return thread

def bulk_send_job(app, user_id, learnerships, attachment_ids):
    """Background job to send application emails"""
    # Use app context within the thread
    with app.app_context():
        try:
            # Import db from models, not from extensions
            from models import User, Document, Application, ApplicationDocument, GoogleToken, db
            from mailer import build_credentials, create_message_with_attachments, send_gmail_message
            
            # Rest of your code remains the same
            # Get user
            user = User.query.get(user_id)
            if not user:
                print(f"User {user_id} not found")
                return
            
            # Get Google token
            token_row = GoogleToken.query.filter_by(user_id=user.id).first()
            if not token_row:
                print(f"No Google token for user {user_id}")
                return
                
            # Build credentials
            credentials = build_credentials(token_row.token_json)
            
            # Get documents
            docs = Document.query.filter(
                Document.id.in_(attachment_ids),
                Document.user_id == user.id,
                Document.is_active == True
            ).all()
            
            if not docs:
                print(f"No valid documents found for user {user_id}")
            
            # Prepare file paths for attachments
            file_paths = [
                {'path': doc.file_path, 'filename': doc.original_filename}
                for doc in docs
            ]
            
            # Process each learnership
            for lr in learnerships:
                try:
                    # Check which fields Application model supports
                    # Adjust these fields based on your Application model
                    app_data = {
                        'user_id': user.id,
                        'status': 'processing',
                        'submitted_at': datetime.utcnow()
                    }
                    
                    # Add optional fields if they exist in your model
                    if hasattr(Application, 'learnership_id'):
                        app_data['learnership_id'] = lr.get('id')
                        
                    if hasattr(Application, 'company_name'):
                        app_data['company_name'] = lr.get('company', 'Unknown')
                        
                    if hasattr(Application, 'learnership_name'):
                        app_data['learnership_name'] = lr.get('title', 'Unknown')
                    
                    # Create application record
                    app_row = Application(**app_data)
                    db.session.add(app_row)
                    db.session.flush()
                    
                    # Add document associations
                    for doc in docs:
                        attachment = ApplicationDocument(
                            application_id=app_row.id,
                            document_id=doc.id
                        )
                        db.session.add(attachment)
                    
                    # Verify learnership has email
                    apply_email = lr.get('apply_email')
                    if not apply_email:
                        app_row.status = 'error'
                        print(f"Missing apply_email for learnership {lr.get('id')}")
                        db.session.commit()
                        continue
                    
                    # Prepare email content
                    subject = f"Application for {lr.get('title')} – {user.full_name or user.email}"
                    body = f"""Dear Hiring Team at {lr.get('company')},

I am writing to express my interest in the {lr.get('title')} position at {lr.get('company')}.

{getattr(user, 'email_body', '')}

Please find my documents attached. I look forward to discussing how my skills and experience align with this opportunity.

Kind regards,
{user.full_name or user.email}
{f"Phone: {user.phone}" if hasattr(user, 'phone') and user.phone else ''}
Email: {user.email}
"""
                    
                    try:
                        # Create and send message
                        message = create_message_with_attachments(
                            user.email,
                            apply_email,
                            subject,
                            body,
                            file_paths
                        )
                        
                        send_gmail_message(credentials, message)
                        
                        # Update application status
                        app_row.status = 'submitted'
                        print(f"Email sent for learnership {lr.get('id')} by user {user.id}")
                        
                    except Exception as e:
                        # Handle sending error
                        app_row.status = 'error'
                        print(f"Failed to send email for learnership {lr.get('id')}: {str(e)}")
                        print(traceback.format_exc())
                    
                    # Save changes
                    db.session.commit()
                
                except Exception as e:
                    print(f"Error processing application for {lr.get('title')}: {e}")
                    try:
                        db.session.rollback()
                    except:
                        print("Could not rollback session")
                    
                # Simulate delay between emails
                time.sleep(1)
                
        except Exception as e:
            print(f"Bulk send job error: {str(e)}")
            print(traceback.format_exc())

# Add this missing function that app.py is trying to import
def launch_bulk_application(user_id, learnership_ids, data=None):
    """Launch a background thread to process multiple applications"""
    app = current_app._get_current_object()
    thread = threading.Thread(
        target=bulk_application_job,
        args=(app, user_id, learnership_ids, data)
    )
    thread.daemon = True
    thread.start()
    return thread

def bulk_application_job(app, user_id, learnership_ids, data=None):
    """Background job to process multiple applications"""
    with app.app_context():
        try:
            from models import User, Learnership, Application, db
            # Use db from models instead of from extensions
            
            # Rest of your code remains the same
            from models import User, Learnership, Application
            from extensions import db
            
            user = User.query.get(user_id)
            if not user:
                print(f"User {user_id} not found")
                return
            
            learnerships = Learnership.query.filter(Learnership.id.in_(learnership_ids)).all()
            
            for learnership in learnerships:
                try:
                    # Create application record
                    application = Application(
                        user_id=user_id,
                        status='pending'
                    )
                    
                    # Add learnership information if the fields exist
                    if hasattr(Application, 'learnership_id'):
                        application.learnership_id = learnership.id
                        
                    if hasattr(Application, 'learnership_name'):
                        application.learnership_name = learnership.title
                        
                    if hasattr(Application, 'company_name'):
                        application.company_name = learnership.company
                    
                    # Add any additional data if provided
                    if data:
                        if 'cover_letter' in data and hasattr(Application, 'cover_letter'):
                            application.cover_letter = data['cover_letter']
                    
                    db.session.add(application)
                    db.session.commit()
                    
                    print(f"Application created for {user.full_name} - {learnership.title}")
                    
                except Exception as e:
                    print(f"Error creating application: {e}")
                    db.session.rollback()
                    
        except Exception as e:
            print(f"Bulk application job error: {e}")
            print(traceback.format_exc())