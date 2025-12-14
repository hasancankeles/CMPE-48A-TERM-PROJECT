"""
Badge Calculator Cloud Function

Triggered by Pub/Sub when:
- A user creates a new recipe (post with recipe)
- A user receives a like on their post

Calculates badges based on:
- Number of recipes posted
- Total likes received on posts with recipes

After calculation, calls back to the backend to update the user's badges.
"""

import base64
import json
import os
import requests


# Badge rules - same as backend but centralized here
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


def calculate_badges(event, context):
    """
    Pub/Sub triggered function to calculate user badges.
    
    Expects payload: {
        "user_id": <int>,
        "event_type": "recipe_created" | "post_liked" | "post_created",
        "stats": {
            "recipe_count": <int>,
            "total_likes": <int>,
            "post_count": <int>
        }
    }
    """
    try:
        # Decode Pub/Sub message
        data = json.loads(base64.b64decode(event["data"]).decode())
        user_id = data["user_id"]
        event_type = data.get("event_type", "unknown")
        stats = data.get("stats", {})
        
        print(f"Calculating badges for user {user_id} (event: {event_type})")
        print(f"Stats: {stats}")
        
    except Exception as e:
        print(f"Invalid Pub/Sub payload: {e}")
        return

    # Get stats from payload
    recipe_count = stats.get("recipe_count", 0)
    total_likes = stats.get("total_likes", 0)
    post_count = stats.get("post_count", 0)

    # Calculate earned badges
    badges = []
    
    # Recipe badges
    for badge in BADGE_RULES["recipes"]:
        if recipe_count >= badge["threshold"]:
            badges.append({
                "type": "recipes",
                "name": badge["name"],
                "description": badge["description"],
                "icon": badge["icon"],
                "threshold": badge["threshold"],
                "earned_at": None  # Could track when badge was first earned
            })
    
    # Like badges
    for badge in BADGE_RULES["likes"]:
        if total_likes >= badge["threshold"]:
            badges.append({
                "type": "likes",
                "name": badge["name"],
                "description": badge["description"],
                "icon": badge["icon"],
                "threshold": badge["threshold"],
                "earned_at": None
            })
    
    # Post badges
    for badge in BADGE_RULES["posts"]:
        if post_count >= badge["threshold"]:
            badges.append({
                "type": "posts",
                "name": badge["name"],
                "description": badge["description"],
                "icon": badge["icon"],
                "threshold": badge["threshold"],
                "earned_at": None
            })
    
    print(f"User {user_id} earned {len(badges)} badges")
    
    # Notify backend with calculated badges
    backend_url = os.environ.get("BACKEND_CALLBACK_URL", "")
    _notify_backend(backend_url, user_id, badges, stats)


def _notify_backend(backend_url: str, user_id: int, badges: list, stats: dict) -> None:
    """
    Call the backend to update the user's badges.
    """
    if not backend_url:
        print("BACKEND_CALLBACK_URL not set; skipping callback")
        print(f"Would have updated user {user_id} with badges: {badges}")
        return
    
    try:
        callback_endpoint = f"{backend_url}/api/users/badges-callback/"
        response = requests.post(
            callback_endpoint,
            json={
                "user_id": user_id,
                "badges": badges,
                "stats": stats
            },
            timeout=10,
            headers={"Content-Type": "application/json"}
        )
        if response.ok:
            print(f"Backend notified successfully: {response.status_code}")
        else:
            print(f"Backend notification failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Failed to notify backend: {e}")


# For local testing
if __name__ == "__main__":
    # Simulate a Pub/Sub message
    test_event = {
        "data": base64.b64encode(json.dumps({
            "user_id": 1,
            "event_type": "recipe_created",
            "stats": {
                "recipe_count": 12,
                "total_likes": 45,
                "post_count": 15
            }
        }).encode()).decode()
    }
    calculate_badges(test_event, None)
