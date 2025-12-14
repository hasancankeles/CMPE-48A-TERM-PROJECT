from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from analytics.services import compute_daily_stats


class Command(BaseCommand):
    help = "Compute and store daily platform statistics."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            help="Target date for stats (YYYY-MM-DD). Defaults to today.",
        )

    def handle(self, *args, **options):
        date_arg = options.get("date")
        target_date = None

        if date_arg:
            try:
                target_date = datetime.strptime(date_arg, "%Y-%m-%d").date()
            except ValueError as exc:
                raise CommandError("date must be in YYYY-MM-DD format") from exc

        result = compute_daily_stats(target_date)
        stats = result.stats
        verb = "Created" if result.created else "Updated"
        self.stdout.write(
            f"{verb} stats for {stats.date} in {result.duration_ms} ms "
            f"(users={stats.total_users}, posts={stats.total_posts}, recipes={stats.total_recipes})"
        )
