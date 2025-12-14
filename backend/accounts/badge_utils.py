"""
Badge calculation utilities.

Handles publishing badge calculation requests to Pub/Sub
and managing user badge data.
"""

import json
from django.conf import settings as django_settings
from django.db.models import Count, Sum
from django.utils import timezone


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


def get_user_badge_stats(user):
    """
    Calculate badge-related statistics for a user.
    
    Returns:
        dict: {
            "recipe_count": int,
            "total_likes": int,
            "post_count": int
        }
    """
    from forum.models import Post, Recipe, Like
    
    # Count posts by this user
    post_count = Post.objects.filter(author=user).count()
    
    # Count recipes (posts that have a recipe attached)
    recipe_count = Recipe.objects.filter(post__author=user).count()
    
    # Count total likes received on user's posts
    total_likes = Like.objects.filter(post__author=user).count()
    
    return {
        "recipe_count": recipe_count,
        "total_likes": total_likes,
        "post_count": post_count,
    }


def publish_badge_calculation_request(user, event_type: str = "manual") -> bool:
    """
    Publish a message to Pub/Sub to request badge calculation for a user.
    
    Args:
        user: User instance
        event_type: Type of event that triggered the calculation
                   ("recipe_created", "post_liked", "post_created", "manual")
    
    Returns:
        bool: True if published successfully, False otherwise
    """
    project_id = getattr(django_settings, "GCP_PROJECT_ID", "")
    topic_name = getattr(django_settings, "PUBSUB_BADGE_CALC_TOPIC", "badge-calculation-requests")
    
    if not project_id:
        print("GCP_PROJECT_ID not configured, skipping badge calc Pub/Sub publish")
        return False
    
    publisher = _get_pubsub_publisher()
    if not publisher:
        return False
    
    try:
        # Get current stats for the user
        stats = get_user_badge_stats(user)
        
        topic_path = publisher.topic_path(project_id, topic_name)
        message_data = json.dumps({
            "user_id": user.id,
            "event_type": event_type,
            "stats": stats
        }).encode("utf-8")
        
        future = publisher.publish(topic_path, message_data)
        future.result(timeout=5)  # Wait up to 5 seconds for publish
        print(f"Published badge calculation request for user {user.id} (event: {event_type})")
        return True
    except Exception as e:
        print(f"Failed to publish badge calculation to Pub/Sub: {e}")
        return False


def calculate_badges_sync(user):
    """
    Calculate badges synchronously (fallback when Cloud Function is not available).
    
    This can be used:
    - For local development
    - As a fallback if Pub/Sub is not configured
    - For immediate badge display before async update
    """
    stats = get_user_badge_stats(user)
    
    # Badge rules
    BADGE_RULES = {
        "recipes": [
            {"threshold": 1, "name": "First Recipe", "description": "Posted your first recipe", "icon": "🍳"},
            {"threshold": 5, "name": "Home Cook", "description": "Posted 5 recipes", "icon": "👨‍🍳"},
            {"threshold": 10, "name": "Recipe Creator", "description": "Posted 10 recipes", "icon": "📖"},
            {"threshold": 25, "name": "Culinary Expert", "description": "Posted 25 recipes", "icon": "⭐"},
            {"threshold": 50, "name": "Master Chef", "description": "Posted 50 recipes", "icon": "👑"},
            {"threshold": 100, "name": "Recipe Legend", "description": "Posted 100 recipes", "icon": "🏆"},
        ],
        "likes": [
            {"threshold": 1, "name": "First Like", "description": "Received your first like", "icon": "❤️"},
            {"threshold": 10, "name": "Rising Star", "description": "Received 10 likes", "icon": "⬆️"},
            {"threshold": 50, "name": "Popular Chef", "description": "Received 50 likes", "icon": "🔥"},
            {"threshold": 100, "name": "Community Favorite", "description": "Received 100 likes", "icon": "💯"},
            {"threshold": 500, "name": "Influencer", "description": "Received 500 likes", "icon": "🌟"},
            {"threshold": 1000, "name": "NutriHub Celebrity", "description": "Received 1000 likes", "icon": "👸"},
        ],
        "posts": [
            {"threshold": 1, "name": "First Post", "description": "Created your first post", "icon": "✍️"},
            {"threshold": 10, "name": "Active Contributor", "description": "Created 10 posts", "icon": "📝"},
            {"threshold": 50, "name": "Prolific Writer", "description": "Created 50 posts", "icon": "📚"},
        ],
    }
    
    badges = []
    
    # Recipe badges
    for badge in BADGE_RULES["recipes"]:
        if stats["recipe_count"] >= badge["threshold"]:
            badges.append({
                "type": "recipes",
                "name": badge["name"],
                "description": badge["description"],
                "icon": badge["icon"],
                "threshold": badge["threshold"],
            })
    
    # Like badges
    for badge in BADGE_RULES["likes"]:
        if stats["total_likes"] >= badge["threshold"]:
            badges.append({
                "type": "likes",
                "name": badge["name"],
                "description": badge["description"],
                "icon": badge["icon"],
                "threshold": badge["threshold"],
            })
    
    # Post badges
    for badge in BADGE_RULES["posts"]:
        if stats["post_count"] >= badge["threshold"]:
            badges.append({
                "type": "posts",
                "name": badge["name"],
                "description": badge["description"],
                "icon": badge["icon"],
                "threshold": badge["threshold"],
            })
    
    return badges, stats


def update_user_badges(user, badges: list, stats: dict = None):
    """
    Update a user's badges in the database.
    
    Args:
        user: User instance
        badges: List of badge dicts
        stats: Optional stats dict to log
    """
    user.badges = badges
    user.badges_updated_at = timezone.now()
    user.save(update_fields=["badges", "badges_updated_at"])
    print(f"Updated badges for user {user.id}: {len(badges)} badges")
