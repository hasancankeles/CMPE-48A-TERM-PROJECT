"""
Email notification utilities.

Handles publishing login notification events to Pub/Sub
for async email sending via Cloud Function.
"""

import json
from datetime import datetime
from django.conf import settings as django_settings


# Lazy-loaded Pub/Sub publisher (shared instance)
_pubsub_publisher = None


def _get_pubsub_publisher():
    """
    Lazily initialize the Pub/Sub publisher client.
    Returns None if GCP is not configured.
    """
    global _pubsub_publisher
    if _pubsub_publisher is None:
        project_id = getattr(django_settings, "GCP_PROJECT_ID", "")
        if project_id:
            try:
                from google.cloud import pubsub_v1
                _pubsub_publisher = pubsub_v1.PublisherClient()
            except Exception as e:
                print(f"Failed to initialize Pub/Sub client: {e}")
                return None
    return _pubsub_publisher


def publish_login_notification(user, request=None) -> bool:
    """
    Publish a login notification event to Pub/Sub.
    The Cloud Function will send an email to the user.
    
    Args:
        user: User instance who logged in
        request: Optional Django request object (for IP and user agent)
    
    Returns:
        bool: True if published successfully, False otherwise
    """
    project_id = getattr(django_settings, "GCP_PROJECT_ID", "")
    topic_name = getattr(django_settings, "PUBSUB_LOGIN_EMAIL_TOPIC", "login-email-notifications")
    
    if not project_id:
        print("GCP_PROJECT_ID not configured, skipping login email Pub/Sub publish")
        return False
    
    publisher = _get_pubsub_publisher()
    if not publisher:
        return False
    
    # Extract request info if available
    ip_address = "Unknown"
    user_agent = "Unknown"
    
    if request:
        # Get IP address
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR', 'Unknown')
        
        # Get user agent
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
    
    try:
        topic_path = publisher.topic_path(project_id, topic_name)
        message_data = json.dumps({
            "user_id": user.id,
            "email": user.email,
            "username": user.username,
            "login_time": datetime.utcnow().isoformat() + "Z",
            "ip_address": ip_address,
            "user_agent": user_agent
        }).encode("utf-8")
        
        future = publisher.publish(topic_path, message_data)
        future.result(timeout=5)  # Wait up to 5 seconds for publish
        print(f"Published login notification for user {user.username}")
        return True
    except Exception as e:
        print(f"Failed to publish login notification to Pub/Sub: {e}")
        return False
