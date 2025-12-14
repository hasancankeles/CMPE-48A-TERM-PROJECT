import time
from dataclasses import dataclass
from datetime import date

from django.db import transaction
from django.utils import timezone

from accounts.models import User
from foods.models import FoodEntry, FoodProposal
from forum.models import Comment, Like, Post, Recipe
from meal_planner.models import DailyNutritionLog, FoodLogEntry, MealPlan

from .models import DailyStats


@dataclass
class StatsComputationResult:
    stats: DailyStats
    created: bool
    duration_ms: int


def compute_daily_stats(target_date: date | None = None) -> StatsComputationResult:
    """
    Calculate and persist daily platform statistics.

    Returns:
        StatsComputationResult with the stored DailyStats instance.
    """
    started = time.perf_counter()
    as_of_date = target_date or timezone.now().date()

    # Lightweight aggregation queries; no prefetch needed
    payload = {
        "total_users": User.objects.count(),
        "total_posts": Post.objects.count(),
        "total_recipes": Recipe.objects.count(),
        "total_comments": Comment.objects.count(),
        "total_likes": Like.objects.count(),
        "total_food_entries": FoodEntry.objects.count(),
        "total_food_proposals": FoodProposal.objects.count(),
        "total_meal_plans": MealPlan.objects.count(),
        "total_daily_logs": DailyNutritionLog.objects.count(),
        "total_food_log_entries": FoodLogEntry.objects.count(),
    }

    duration_ms = int((time.perf_counter() - started) * 1000)

    with transaction.atomic():
        stats, created = DailyStats.objects.update_or_create(
            date=as_of_date,
            defaults={**payload, "duration_ms": duration_ms},
        )

    return StatsComputationResult(stats=stats, created=created, duration_ms=duration_ms)
