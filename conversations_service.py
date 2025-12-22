# conversations_service.py
from datetime import datetime
from email.utils import parsedate_to_datetime

from models import db, Application, Conversation, ConversationMessage

# --- Utility: very simple HTML strip (or reuse your own) ---
import re
TAG_RE = re.compile(r'<[^>]+>')

def strip_tags(html):
    if not html:
        return ''
    return TAG_RE.sub('', html)


# ========== OUTGOING (APPLICANT SENDS FROM APP) ==========

def sync_outgoing_application_message(application, email_result, subject, body_html, attachments=None):
    """
    Call this right after a Gmail send succeeds for an Application.
    - application: Application model instance
    - email_result: dict with email_result["gmail_data"] = {"id": ..., "threadId": ...}
    - subject: string used in the email
    - body_html: HTML body you sent
    - attachments: list or None
    """
    attachments = attachments or []

    gmail_data = email_result.get("gmail_data") or {}
    gmail_message_id = gmail_data.get("id")
    gmail_thread_id = gmail_data.get("threadId")

    if not gmail_message_id or not gmail_thread_id:
        return  # nothing to sync

    # Update application Gmail tracking
    application.gmail_message_id = gmail_message_id
    application.gmail_thread_id = gmail_thread_id
    application.sent_at = datetime.utcnow()
    application.email_status = 'sent'

    # Get or create conversation for this application/thread
    convo = Conversation.query.filter_by(gmail_thread_id=gmail_thread_id).first()
    if not convo:
        convo = Conversation(
            application_id=application.id,
            gmail_thread_id=gmail_thread_id,
            subject=subject or application.learnership_name,
            # We don't care about corporate side here; if column is non‑nullable,
            # you can set a default corporate_user_id or map from company_email.
            corporate_user_id=application.corporate_user_id,
            applicant_user_id=application.user_id,
            last_message_at=application.sent_at,
            corporate_unread_count=0,
            applicant_unread_count=0,
        )
        db.session.add(convo)
        db.session.flush()  # gets convo.id

    # Create outgoing message from applicant
    msg = ConversationMessage(
        conversation_id=convo.id,
        gmail_message_id=gmail_message_id,
        sender_id=application.user_id,
        sender_type='applicant',
        subject=subject,
        body=strip_tags(body_html),
        html_body=body_html,
        gmail_timestamp=application.sent_at,
        has_attachments=bool(attachments),
        is_read_by_applicant=True,
        is_read_by_applicant=True,
        is_read_by_corporate=False,
    )

    convo.last_message_at = application.sent_at

    db.session.add(msg)
    db.session.commit()


# ========== INCOMING (COMPANY REPLIES VIA GMAIL) ==========
# conversations_service.py
from datetime import datetime
from email.utils import parsedate_to_datetime
from models import db, Application, Conversation, ConversationMessage
import re

TAG_RE = re.compile(r'<[^>]+>')

def strip_tags(html):
    if not html:
        return ''
    return TAG_RE.sub('', html)

def extract_text_and_html_from_gmail_message(gmail_msg):
    payload = gmail_msg.get('payload', {})
    body_text = ''
    body_html = ''

    def _walk(part):
        nonlocal body_text, body_html
        mime_type = part.get('mimeType', '')
        body_data = part.get('body', {}).get('data')
        if body_data:
            import base64
            decoded = base64.urlsafe_b64decode(body_data.encode('utf-8')).decode('utf-8', errors='ignore')
            if mime_type == 'text/plain':
                body_text += decoded
            elif mime_type == 'text/html':
                body_html += decoded
        for p in part.get('parts', []) or []:
            _walk(p)

    if payload:
        if payload.get('parts'):
            for p in payload['parts']:
                _walk(p)
        else:
            _walk(payload)

    if not body_text and body_html:
        body_text = strip_tags(body_html)
    if not body_html and body_text:
        body_html = body_text.replace('\n', '<br>')

    return body_text, body_html


def process_incoming_gmail_message_for_user(gmail_msg):
    """
    Process a single Gmail message as a potential incoming reply.
    Only creates a ConversationMessage if its threadId matches an Application.gmail_thread_id.
    """
    thread_id = gmail_msg.get('threadId')
    msg_id = gmail_msg.get('id')
    if not thread_id or not msg_id:
        return

    # Does this thread belong to an application sent from this app?
    app = Application.query.filter_by(gmail_thread_id=thread_id).first()
    if not app:
        return  # ignore messages not tied to any app

    # Avoid duplicates
    if ConversationMessage.query.filter_by(gmail_message_id=msg_id).first():
        return

    # Find or create conversation
    convo = Conversation.query.filter_by(gmail_thread_id=thread_id).first()
    if not convo:
        convo = Conversation(
            application_id=app.id,
            gmail_thread_id=thread_id,
            subject=app.learnership_name,
            corporate_user_id=app.corporate_user_id,
            applicant_user_id=app.user_id,
            last_message_at=datetime.utcnow(),
            corporate_unread_count=0,
            applicant_unread_count=0,
        )
        db.session.add(convo)
        db.session.flush()

    # Parse headers
    headers = gmail_msg.get('payload', {}).get('headers', [])
    subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), convo.subject)
    date_header = next((h['value'] for h in headers if h['name'].lower() == 'date'), None)
    if date_header:
        gmail_ts = parsedate_to_datetime(date_header)
    else:
        gmail_ts = datetime.utcnow()

    body_text, body_html = extract_text_and_html_from_gmail_message(gmail_msg)

    # Treat this as a "corporate" (employer) message to the applicant
    msg = ConversationMessage(
        conversation_id=convo.id,
        gmail_message_id=msg_id,
        sender_id=app.user_id,   # we don't have a separate corporate user yet
        sender_type='corporate',
        subject=subject,
        body=body_text,
        html_body=body_html,
        gmail_timestamp=gmail_ts,
        has_attachments=bool(gmail_msg.get('payload', {}).get('parts')),
        is_read_by_applicant=False,
        is_read_by_corporate=True,
    )

    convo.last_message_at = gmail_ts
    convo.applicant_unread_count = (convo.applicant_unread_count or 0) + 1

    # Update application flags
    app.has_response = True
    app.email_status = 'responded'
    app.response_received_at = gmail_ts

    db.session.add(msg)
    db.session.commit()