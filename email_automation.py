"""
Enhanced Email Automation for Corporate Workflow
"""
import base64
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from models import User, Application, GoogleToken

def get_gmail_service(user):
    """Get authenticated Gmail service for user"""
    try:
        token = GoogleToken.query.filter_by(user_id=user.id).first()
        if not token:
            return None
            
        # This would typically use your existing OAuth flow
        # For now, returning None - you'll integrate with your existing Gmail setup
        return None
        
    except Exception as e:
        print(f"Error getting Gmail service: {e}")
        return None

def send_interview_notification_email(application, interview_datetime, interview_type, location, notes):
    """Send interview scheduling notification to applicant"""
    try:
        # Get applicant
        applicant = User.query.get(application.user_id)
        if not applicant:
            return False
            
        # Get corporate user for sending
        corporate_user = User.query.get(application.corporate_user_id)
        if not corporate_user:
            return False
            
        # Create email content
        subject = f"Interview Scheduled - {corporate_user.company_name} Learnership"
        
        interview_date_str = interview_datetime.strftime('%A, %B %d, %Y at %I:%M %p')
        
        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9fafb;">
            <div style="background: linear-gradient(135deg, #3b82f6, #1e40af); padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 30px;">
                <h1 style="color: white; margin: 0; font-size: 28px;">🎉 Interview Scheduled!</h1>
                <p style="color: #e0e7ff; margin: 10px 0 0 0; font-size: 16px;">Your application is moving forward</p>
            </div>
            
            <div style="background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                <p style="color: #374151; font-size: 16px; line-height: 1.6;">Dear {applicant.full_name},</p>
                
                <p style="color: #374151; font-size: 16px; line-height: 1.6;">
                    Great news! <strong>{corporate_user.company_name}</strong> would like to interview you for the learnership position you applied for.
                </p>
                
                <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 25px 0;">
                    <h3 style="color: #1f2937; margin: 0 0 15px 0;">📅 Interview Details</h3>
                    <ul style="color: #4b5563; line-height: 1.8; margin: 0; padding-left: 20px;">
                        <li><strong>Date & Time:</strong> {interview_date_str}</li>
                        <li><strong>Type:</strong> {interview_type.title()}</li>
                        <li><strong>Location/Link:</strong> {location if location else 'Details will be provided'}</li>
                    </ul>
                    {f'<p style="color: #4b5563; margin: 15px 0 0 0;"><strong>Additional Notes:</strong><br>{notes}</p>' if notes else ''}
                </div>
                
                <div style="background: #ecfdf5; border-left: 4px solid #10b981; padding: 15px; margin: 25px 0;">
                    <p style="color: #065f46; margin: 0; font-weight: 500;">
                        💡 <strong>Tip:</strong> Please confirm your attendance by replying to this email. 
                        If you need to reschedule, contact us at least 24 hours in advance.
                    </p>
                </div>
                
                <p style="color: #374151; font-size: 16px; line-height: 1.6;">
                    We're excited to learn more about you and discuss this opportunity in detail.
                </p>
                
                <p style="color: #374151; font-size: 16px; line-height: 1.6;">
                    Best regards,<br>
                    <strong>{corporate_user.company_name}</strong><br>
                    <span style="color: #6b7280;">{corporate_user.contact_person}</span>
                </p>
            </div>
            
            <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                <p style="color: #9ca3af; font-size: 14px; margin: 0;">
                    This email was sent via <strong>CodeCraftCo</strong> - South Africa's premier learnership platform
                </p>
            </div>
        </div>
        """
        
        # Send via your existing Gmail integration
        gmail_message_id = send_email_via_gmail(
            corporate_user,
            applicant.email,
            subject,
            html_body
        )
        
        return gmail_message_id
        
    except Exception as e:
        print(f"Error sending interview notification: {e}")
        return False

def send_corporate_message_email(application, subject, message, corporate_user):
    """Send general message from corporate to applicant"""
    try:
        applicant = User.query.get(application.user_id)
        if not applicant:
            return False
            
        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9fafb;">
            <div style="background: linear-gradient(135deg, #6366f1, #4f46e5); padding: 25px; border-radius: 10px; text-align: center; margin-bottom: 30px;">
                <h1 style="color: white; margin: 0; font-size: 24px;">📧 Message from {corporate_user.company_name}</h1>
            </div>
            
            <div style="background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                <p style="color: #374151; font-size: 16px; line-height: 1.6;">Dear {applicant.full_name},</p>
                
                <div style="background: #f8fafc; padding: 20px; border-radius: 8px; margin: 25px 0; border-left: 4px solid #6366f1;">
                    <p style="color: #374151; font-size: 16px; line-height: 1.6; margin: 0; white-space: pre-wrap;">{message}</p>
                </div>
                
                <p style="color: #374151; font-size: 16px; line-height: 1.6;">
                    Best regards,<br>
                    <strong>{corporate_user.company_name}</strong><br>
                    <span style="color: #6b7280;">{corporate_user.contact_person}</span>
                </p>
            </div>
            
            <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                <p style="color: #9ca3af; font-size: 14px; margin: 0;">
                    Reply directly to this email or visit <strong>CodeCraftCo</strong> for more learnership opportunities
                </p>
            </div>
        </div>
        """
        
        gmail_message_id = send_email_via_gmail(
            corporate_user,
            applicant.email,
            subject,
            html_body
        )
        
        return gmail_message_id
        
    except Exception as e:
        print(f"Error sending corporate message: {e}")
        return False

def send_acceptance_email(application, corporate_user):
    """Send acceptance notification"""
    try:
        applicant = User.query.get(application.user_id)
        if not applicant:
            return False
            
        subject = f"🎉 Congratulations! Application Accepted - {corporate_user.company_name}"
        
        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f0fdf4;">
            <div style="background: linear-gradient(135deg, #10b981, #059669); padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 30px;">
                <h1 style="color: white; margin: 0; font-size: 32px;">🎉 Congratulations!</h1>
                <p style="color: #d1fae5; margin: 10px 0 0 0; font-size: 18px;">Your application has been accepted!</p>
            </div>
            
            <div style="background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                <p style="color: #374151; font-size: 16px; line-height: 1.6;">Dear {applicant.full_name},</p>
                
                <p style="color: #374151; font-size: 16px; line-height: 1.6;">
                    We are thrilled to inform you that your application for the learnership position at 
                    <strong>{corporate_user.company_name}</strong> has been <strong>accepted</strong>!
                </p>
                
                <div style="background: #ecfdf5; border: 2px solid #10b981; border-radius: 10px; padding: 25px; margin: 25px 0; text-align: center;">
                    <h3 style="color: #059669; margin: 0 0 10px 0; font-size: 20px;">🌟 Welcome to the Team!</h3>
                    <p style="color: #065f46; margin: 0; font-size: 16px;">You're now part of our learnership program</p>
                </div>
                
                <p style="color: #374151; font-size: 16px; line-height: 1.6;">
                    Our HR team will contact you shortly with next steps, including:
                </p>
                
                <ul style="color: #4b5563; line-height: 1.8; margin: 20px 0;">
                    <li>Program start date and orientation details</li>
                    <li>Required documentation</li>
                    <li>Program schedule and expectations</li>
                    <li>Contact information for your supervisor</li>
                </ul>
                
                <p style="color: #374151; font-size: 16px; line-height: 1.6;">
                    Once again, congratulations on this achievement! We look forward to supporting your professional growth.
                </p>
                
                <p style="color: #374151; font-size: 16px; line-height: 1.6;">
                    Warm regards,<br>
                    <strong>{corporate_user.company_name}</strong><br>
                    <span style="color: #6b7280;">{corporate_user.contact_person}</span>
                </p>
            </div>
        </div>
        """
        
        gmail_message_id = send_email_via_gmail(
            corporate_user,
            applicant.email,
            subject,
            html_body
        )
        
        return gmail_message_id
        
    except Exception as e:
        print(f"Error sending acceptance email: {e}")
        return False

def send_rejection_email(application, corporate_user):
    """Send rejection notification"""
    try:
        applicant = User.query.get(application.user_id)
        if not applicant:
            return False
            
        subject = f"Application Update - {corporate_user.company_name}"
        
        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #fafafa;">
            <div style="background: linear-gradient(135deg, #64748b, #475569); padding: 25px; border-radius: 10px; text-align: center; margin-bottom: 30px;">
                <h1 style="color: white; margin: 0; font-size: 24px;">Application Update</h1>
                <p style="color: #e2e8f0; margin: 10px 0 0 0; font-size: 16px;">Thank you for your interest</p>
            </div>
            
            <div style="background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                <p style="color: #374151; font-size: 16px; line-height: 1.6;">Dear {applicant.full_name},</p>
                
                <p style="color: #374151; font-size: 16px; line-height: 1.6;">
                    Thank you for your interest in the learnership position at <strong>{corporate_user.company_name}</strong> 
                    and for taking the time to apply.
                </p>
                
                <p style="color: #374151; font-size: 16px; line-height: 1.6;">
                    After careful consideration, we have decided to move forward with other candidates whose 
                    experience more closely matches our current requirements.
                </p>
                
                <div style="background: #f1f5f9; border-left: 4px solid #64748b; padding: 20px; margin: 25px 0;">
                    <p style="color: #475569; margin: 0; font-size: 16px; line-height: 1.6;">
                        <strong>This decision does not reflect your potential or abilities.</strong> 
                        We encourage you to continue pursuing opportunities and to apply for future positions 
                        that align with your skills and career goals.
                    </p>
                </div>
                
                <p style="color: #374151; font-size: 16px; line-height: 1.6;">
                    We wish you the best in your career journey and thank you again for considering 
                    <strong>{corporate_user.company_name}</strong>.
                </p>
                
                <p style="color: #374151; font-size: 16px; line-height: 1.6;">
                    Kind regards,<br>
                    <strong>{corporate_user.company_name}</strong><br>
                    <span style="color: #6b7280;">{corporate_user.contact_person}</span>
                </p>
            </div>
            
            <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                <p style="color: #9ca3af; font-size: 14px; margin: 0;">
                    Keep exploring opportunities on <strong>CodeCraftCo</strong> - Your next opportunity awaits!
                </p>
            </div>
        </div>
        """
        
        gmail_message_id = send_email_via_gmail(
            corporate_user,
            applicant.email,
            subject,
            html_body
        )
        
        return gmail_message_id
        
    except Exception as e:
        print(f"Error sending rejection email: {e}")
        return False

def send_email_via_gmail(sender_user, recipient_email, subject, html_body):
    """Send email via Gmail API - integrate with your existing system"""
    try:
        # This will integrate with your existing Gmail API setup
        # For now, returning a placeholder
        print(f"Sending email to {recipient_email}: {subject}")
        return f"msg_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
    except Exception as e:
        print(f"Error sending email via Gmail: {e}")
        return None