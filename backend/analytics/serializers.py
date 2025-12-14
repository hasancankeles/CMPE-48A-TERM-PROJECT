from rest_framework import serializers

from .models import DailyStats


class DailyStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyStats
        fields = [
            "date",
            "computed_at",
            "duration_ms",
            "total_users",
            "total_posts",
            "total_recipes",
            "total_comments",
            "total_likes",
            "total_food_entries",
            "total_food_proposals",
            "total_meal_plans",
            "total_daily_logs",
            "total_food_log_entries",
            "notes",
        ]
