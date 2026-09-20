from django.core.management.base import BaseCommand
from django.utils import timezone
from orders.tasks import send_abandoned_cart_recovery_emails


class Command(BaseCommand):
    help = "Scans for abandoned customer shopping carts and dispatches recovery emails."

    def add_arguments(self, parser):
        parser.add_argument(
            '--threshold-hours',
            type=int,
            default=2,
            dest='threshold_hours',
            help='Inactivity threshold in hours before a cart is marked abandoned (default: 2).'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help='Simulate scan without dispatching emails or modifying database records.'
        )

    def handle(self, *args, **options):
        threshold_hours = options['threshold_hours']
        dry_run = options['dry_run']
        now = timezone.now()

        self.stdout.write(
            self.style.NOTICE(
                f"Starting abandoned cart recovery scan (Threshold: {threshold_hours}h, Dry Run: {dry_run}) at {now.isoformat()}..."
            )
        )

        result = send_abandoned_cart_recovery_emails(
            hours_threshold=threshold_hours,
            dry_run=dry_run
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY-RUN] Found {result['eligible_count']} eligible abandoned carts. No emails dispatched."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Recovery scan completed: {result['dispatched_count']} of {result['eligible_count']} recovery emails dispatched successfully."
                )
            )
