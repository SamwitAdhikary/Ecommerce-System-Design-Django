from django.core.management.base import BaseCommand
from django.utils import timezone
from catalog.models import ActiveVisitor


class Command(BaseCommand):
    help = "Prunes inactive storefront visitor presence telemetry records older than specified minutes."

    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout',
            type=int,
            default=15,
            help="Inactivity timeout threshold in minutes (default: 15)."
        )

    def handle(self, *args, **options):
        timeout = options['timeout']
        self.stdout.write(f"Starting active visitor presence scan (TTL: {timeout} minutes) at {timezone.now().isoformat()}...")
        deleted_count = ActiveVisitor.prune_stale(timeout_minutes=timeout)
        self.stdout.write(
            self.style.SUCCESS(f"Successfully pruned {deleted_count} stale visitor session records.")
        )
