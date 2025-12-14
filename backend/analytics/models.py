from django.db import models


class DailyStats(models.Model):
    """
    Aggregated platform statistics captured once per day.
    """

    date = models.DateField(unique=True)
    computed_at = models.DateTimeField(auto_now=True)
    duration_ms = models.IntegerField(default=0)

    total_users = models.PositiveIntegerField(default=0)
    total_posts = models.PositiveIntegerField(default=0)
    total_recipes = models.PositiveIntegerField(default=0)
    total_comments = models.PositiveIntegerField(default=0)
    total_likes = models.PositiveIntegerField(default=0)

    total_food_entries = models.PositiveIntegerField(default=0)
    total_food_proposals = models.PositiveIntegerField(default=0)

    total_meal_plans = models.PositiveIntegerField(default=0)
    total_daily_logs = models.PositiveIntegerField(default=0)
    total_food_log_entries = models.PositiveIntegerField(default=0)

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"DailyStats {self.date}"
