from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from users.models import User, WalletTransaction
from users.services import expire_user_credits, expire_all_pending_credits


class Command(BaseCommand):
    help = "Scans and debits expired store credits across all user wallets."

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            dest='user_id',
            help='Expire credits for a specific user ID only.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help='Simulate expiration run without modifying database records.',
        )

    def handle(self, *args, **options):
        now = timezone.now()
        user_id = options.get('user_id')
        dry_run = options.get('dry_run')

        self.stdout.write(self.style.NOTICE(f"Starting store credit expiration scan at {now.isoformat()}..."))

        if dry_run:
            query = WalletTransaction.objects.filter(
                transaction_type='CREDIT',
                remaining_amount__gt=Decimal('0.00'),
                expires_at__lte=now
            )
            if user_id:
                query = query.filter(user_id=user_id)

            count = query.count()
            total_amount = sum((txn.remaining_amount for txn in query), Decimal('0.00'))
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY-RUN] Found {count} expired credit grants totaling ${total_amount} across matching wallets."
                )
            )
            return

        if user_id:
            try:
                user = User.objects.get(pk=user_id)
                debits = expire_user_credits(user)
                total_expired = sum((d.amount for d in debits), Decimal('0.00'))
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully expired {len(debits)} credit grants totaling ${total_expired} for user {user.email}."
                    )
                )
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"User with ID {user_id} does not exist."))
        else:
            processed_count = expire_all_pending_credits()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Expiration scan completed successfully. Processed {processed_count} expired credit grants."
                )
            )
