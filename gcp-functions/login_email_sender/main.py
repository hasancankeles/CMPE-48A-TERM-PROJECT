"""
Login Email Sender Cloud Function

Triggered by Pub/Sub when a user successfully logs in.
Sends a notification email to the user about the login activity.

This is a security feature - users are notified when their account is accessed.
"""

import base64
import json
import os
from datetime import datetime


def send_login_email(event, context):
    """
    Pub/Sub triggered function to send login notification emails.
    
    Expects payload: {
        "user_id": <int>,
        "email": "<user_email>",
        "username": "<username>",
        "login_time": "<ISO timestamp>",
        "ip_address": "<optional IP>",
        "user_agent": "<optional browser info>"
    }
    """
    try:
        # Decode Pub/Sub message
        data = json.loads(base64.b64decode(event["data"]).decode())
        
        user_id = data.get("user_id")
        email = data.get("email")
        username = data.get("username")
        login_time = data.get("login_time", datetime.utcnow().isoformat())
        ip_address = data.get("ip_address", "Unknown")
        user_agent = data.get("user_agent", "Unknown")
        
        print(f"Processing login notification for user {username} ({email})")
        
    except Exception as e:
        print(f"Invalid Pub/Sub payload: {e}")
        return

    if not email:
        print("No email address provided, skipping notification")
        return

    # Get email service configuration
    email_service = os.environ.get("EMAIL_SERVICE", "log")  # "sendgrid", "mailgun", or "log"
    
    # Prepare email content
    subject = f"New login to your NutriHub account"
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background-color: #4CAF50; padding: 20px; text-align: center;">
            <h1 style="color: white; margin: 0;">🥗 NutriHub</h1>
        </div>
        
        <div style="padding: 20px; background-color: #f9f9f9;">
            <h2 style="color: #333;">New Login Detected</h2>
            
            <p>Hello <strong>{username}</strong>,</p>
            
            <p>We detected a new login to your NutriHub account:</p>
            
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #ddd;"><strong>Time:</strong></td>
                    <td style="padding: 10px; border-bottom: 1px solid #ddd;">{login_time}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #ddd;"><strong>IP Address:</strong></td>
                    <td style="padding: 10px; border-bottom: 1px solid #ddd;">{ip_address}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #ddd;"><strong>Device:</strong></td>
                    <td style="padding: 10px; border-bottom: 1px solid #ddd;">{user_agent[:50]}...</td>
                </tr>
            </table>
            
            <p style="color: #666;">
                If this was you, no action is needed.<br>
                If you didn't log in, please <a href="https://nutrihub.fit/change-password">change your password</a> immediately.
            </p>
        </div>
        
        <div style="padding: 20px; text-align: center; color: #888; font-size: 12px;">
            <p>This is an automated security notification from NutriHub.</p>
            <p>© 2024 NutriHub - Your Nutrition Companion</p>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    New Login to Your NutriHub Account
    
    Hello {username},
    
    We detected a new login to your NutriHub account:
    
    Time: {login_time}
    IP Address: {ip_address}
    Device: {user_agent[:50]}...
    
    If this was you, no action is needed.
    If you didn't log in, please change your password immediately at https://nutrihub.fit/change-password
    
    This is an automated security notification from NutriHub.
    """
    
    # Send email based on configured service
    if email_service == "sendgrid":
        _send_via_sendgrid(email, subject, html_content, text_content)
    elif email_service == "mailgun":
        _send_via_mailgun(email, subject, html_content, text_content)
    else:
        # Default: just log (for testing)
        _log_email(email, subject, text_content)


def _send_via_sendgrid(to_email: str, subject: str, html_content: str, text_content: str):
    """Send email using SendGrid API."""
    import requests
    
    api_key = os.environ.get("SENDGRID_API_KEY")
    from_email = os.environ.get("FROM_EMAIL", "noreply@nutrihub.fit")
    
    if not api_key:
        print("SENDGRID_API_KEY not set, logging email instead")
        _log_email(to_email, subject, text_content)
        return
    
    try:
        response = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "personalizations": [{"to": [{"email": to_email}]}],
                "from": {"email": from_email, "name": "NutriHub"},
                "subject": subject,
                "content": [
                    {"type": "text/plain", "value": text_content},
                    {"type": "text/html", "value": html_content}
                ]
            },
            timeout=10
        )
        
        if response.status_code in [200, 202]:
            print(f"Email sent successfully to {to_email} via SendGrid")
        else:
            print(f"SendGrid error: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Failed to send email via SendGrid: {e}")


def _send_via_mailgun(to_email: str, subject: str, html_content: str, text_content: str):
    """Send email using Mailgun API."""
    import requests
    
    api_key = os.environ.get("MAILGUN_API_KEY")
    domain = os.environ.get("MAILGUN_DOMAIN")
    from_email = os.environ.get("FROM_EMAIL", "noreply@nutrihub.fit")
    
    if not api_key or not domain:
        print("MAILGUN_API_KEY or MAILGUN_DOMAIN not set, logging email instead")
        _log_email(to_email, subject, text_content)
        return
    
    try:
        response = requests.post(
            f"https://api.mailgun.net/v3/{domain}/messages",
            auth=("api", api_key),
            data={
                "from": f"NutriHub <{from_email}>",
                "to": [to_email],
                "subject": subject,
                "text": text_content,
                "html": html_content
            },
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"Email sent successfully to {to_email} via Mailgun")
        else:
            print(f"Mailgun error: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Failed to send email via Mailgun: {e}")


def _log_email(to_email: str, subject: str, content: str):
    """Log email content (for testing without email service)."""
    print("=" * 60)
    print("EMAIL NOTIFICATION (logged, not sent)")
    print("=" * 60)
    print(f"To: {to_email}")
    print(f"Subject: {subject}")
    print("-" * 60)
    print(content[:500])
    print("=" * 60)


# For local testing
if __name__ == "__main__":
    test_event = {
        "data": base64.b64encode(json.dumps({
            "user_id": 1,
            "email": "test@example.com",
            "username": "testuser",
            "login_time": "2024-12-14T12:30:00Z",
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        }).encode()).decode()
    }
    send_login_email(test_event, None)
