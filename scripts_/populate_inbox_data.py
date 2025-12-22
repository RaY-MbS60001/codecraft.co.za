# scripts_/populate_inbox_data.py

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import User, Application, Conversation, ConversationMessage
from datetime import datetime, timedelta
import random

with app.app_context():
    print("\n" + "=" * 90)
    print("📧 POPULATING INBOX WITH CONVERSATIONS")
    print("=" * 90 + "\n")
    
    # Get corporate user
    tech_corp_user = User.query.filter_by(email='hr@techcorp.co.za').first()
    if not tech_corp_user:
        print("❌ Corporate user not found!")
        exit()
    
    print(f"👤 Corporate User: {tech_corp_user.full_name}\n")
    
    # Get applications with sent emails
    applications = Application.query.filter_by(
        corporate_user_id=tech_corp_user.id,
        email_status='sent'
    ).limit(5).all()
    
    if not applications:
        print("❌ No applications found!")
        exit()
    
    print(f"✅ Found {len(applications)} applications\n")
    
    # Delete existing conversations and messages for this user
    print("🗑️  Cleaning up old conversations...")
    old_conversations = Conversation.query.filter_by(
        corporate_user_id=tech_corp_user.id
    ).all()
    for conv in old_conversations:
        db.session.delete(conv)
    db.session.commit()
    print(f"   ✅ Deleted {len(old_conversations)} old conversations\n")
    
    # Create conversations and messages for each application
    conv_count = 0
    msg_count = 0
    
    for app in applications:
        try:
            applicant = User.query.get(app.user_id)
            if not applicant:
                continue
            
            # Create conversation
            conv = Conversation(
                application_id=app.id,
                gmail_thread_id=f"thread_{app.id}_{tech_corp_user.id}@mail.google.com",
                subject=f"Re: Your Application for {app.learnership_name}",
                corporate_user_id=tech_corp_user.id,
                applicant_user_id=applicant.id,
                is_active=True,
                last_message_at=datetime.utcnow(),
                corporate_unread_count=random.randint(0, 3)
            )
            db.session.add(conv)
            db.session.flush()
            
            print(f"✅ Created conversation for {applicant.full_name}")
            conv_count += 1
            
            # Create initial message from corporate
            msg1 = ConversationMessage(
                conversation_id=conv.id,
                gmail_message_id=f"msg_{conv.id}_1@mail.google.com",
                sender_id=tech_corp_user.id,
                sender_type='corporate',
                subject=f"Re: Your Application for {app.learnership_name}",
                body=f"Hi {applicant.full_name},\n\nThank you for applying for the {app.learnership_name} position. We have reviewed your application and would like to move forward with the next stage.\n\nBest regards,\n{tech_corp_user.full_name}\nTech Corp Solutions",
                html_body=f"<p>Hi {applicant.full_name},</p><p>Thank you for applying for the {app.learnership_name} position. We have reviewed your application and would like to move forward with the next stage.</p><p>Best regards,<br>{tech_corp_user.full_name}<br>Tech Corp Solutions</p>",
                gmail_timestamp=datetime.utcnow() - timedelta(days=random.randint(1, 10)),
                has_attachments=False,
                is_read_by_corporate=True,
                is_read_by_applicant=False
            )
            db.session.add(msg1)
            db.session.flush()
            msg_count += 1
            
            # Create response from applicant
            msg2 = ConversationMessage(
                conversation_id=conv.id,
                gmail_message_id=f"msg_{conv.id}_2@mail.google.com",
                sender_id=applicant.id,
                sender_type='applicant',
                subject=f"Re: Your Application for {app.learnership_name}",
                body=f"Hi {tech_corp_user.full_name},\n\nThank you for the opportunity! I'm very interested in this position and would love to discuss it further.\n\nBest regards,\n{applicant.full_name}",
                html_body=f"<p>Hi {tech_corp_user.full_name},</p><p>Thank you for the opportunity! I'm very interested in this position and would love to discuss it further.</p><p>Best regards,<br>{applicant.full_name}</p>",
                gmail_timestamp=datetime.utcnow() - timedelta(days=random.randint(1, 5)),
                has_attachments=False,
                is_read_by_corporate=False,
                is_read_by_applicant=True
            )
            db.session.add(msg2)
            db.session.flush()
            msg_count += 1
            
            # Create another message from corporate
            msg3 = ConversationMessage(
                conversation_id=conv.id,
                gmail_message_id=f"msg_{conv.id}_3@mail.google.com",
                sender_id=tech_corp_user.id,
                sender_type='corporate',
                subject=f"Re: Your Application for {app.learnership_name}",
                body=f"Perfect! Let's schedule an interview for next week. Are you available on Monday, Wednesday, or Friday afternoon?\n\nRegards,\n{tech_corp_user.full_name}",
                html_body=f"<p>Perfect! Let's schedule an interview for next week. Are you available on Monday, Wednesday, or Friday afternoon?</p><p>Regards,<br>{tech_corp_user.full_name}</p>",
                gmail_timestamp=datetime.utcnow() - timedelta(days=random.randint(1, 3)),
                has_attachments=False,
                is_read_by_corporate=True,
                is_read_by_applicant=False
            )
            db.session.add(msg3)
            db.session.flush()
            msg_count += 1
            
            # Update conversation last message time
            conv.last_message_at = datetime.utcnow()
            
        except Exception as e:
            print(f"   ❌ Error creating conversation: {e}")
    
    db.session.commit()
    
    print(f"\n✅ Created {conv_count} conversations")
    print(f"✅ Created {msg_count} messages\n")
    
    print("=" * 90)
    print("\n🚀 INBOX DATA POPULATED!\n")
    print("You should now see:")
    print("   ✅ Conversations from applicants")
    print("   ✅ Unread message counts")
    print("   ✅ Message threads with replies")
    print()