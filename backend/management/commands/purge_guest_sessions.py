"""Delete guest sessions past their expiry.

Guest measurements cascade with the session (FK on_delete=CASCADE), so this
is the data-retention cleanup for anonymous usage. Run periodically (cron /
scheduled task):

    python manage.py purge_guest_sessions [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from backend.models import GuestSession


class Command(BaseCommand):
    help = "Delete expired guest sessions (and their measurements, via cascade)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be deleted without deleting anything.",
        )

    def handle(self, *args, **options):
        expired = GuestSession.objects.filter(expires_at__lt=timezone.now())

        if options["dry_run"]:
            self.stdout.write(
                f"Would delete {expired.count()} expired guest session(s)."
            )
            return

        # delete() already reports per-model counts — no separate COUNT
        # query, and no count/delete race window in the reported numbers.
        total_deleted, per_model = expired.delete()
        sessions = per_model.get("backend.GuestSession", 0)
        measurements = per_model.get("backend.Measurement", 0)
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {sessions} expired guest session(s) "
                f"and {measurements} associated measurement(s)."
            )
        )
