import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from django.db import transaction

from .models import Cart
from .emails import send_abandoned_cart_email

logger = logging.getLogger(__name__)


@shared_task(name='orders.tasks.send_abandoned_cart_recovery_emails')
def send_abandoned_cart_recovery_emails(hours_threshold: int = 2, dry_run: bool = False) -> dict:
    """
    Scans for shopping carts that have remained inactive for longer than hours_threshold,
    have active items, have not yet received an abandonment notification, and belong
    to registered active customer accounts. Dispatches personalized recovery emails.
    """
    cutoff_time = timezone.now() - timedelta(hours=hours_threshold)

    # Query eligible abandoned carts
    eligible_carts = Cart.objects.filter(
        items__isnull=False,
        abandoned_email_sent=False,
        updated_at__lte=cutoff_time,
        user__isnull=False,
        user__is_active=True,
    ).distinct()

    cart_ids = list(eligible_carts.values_list('id', flat=True))
    total_eligible = len(cart_ids)
    dispatched_count = 0

    if dry_run:
        return {
            'status': 'dry_run_complete',
            'eligible_count': total_eligible,
            'dispatched_count': 0,
            'cart_ids': cart_ids,
        }

    for cart_id in cart_ids:
        try:
            with transaction.atomic():
                cart = Cart.objects.select_for_update().get(id=cart_id)
                # Double-check invariant under row lock
                if cart.abandoned_email_sent or not cart.items.exists():
                    continue

                # Claim task by marking flag under lock to prevent concurrent workers from claiming it
                Cart.objects.filter(id=cart.id).update(abandoned_email_sent=True)

            # Database lock is released; perform slow network I/O outside transaction.atomic()
            sent = send_abandoned_cart_email(cart)
            if sent:
                dispatched_count += 1
            else:
                # Revert flag if sending failed so it can be retried in future runs
                Cart.objects.filter(id=cart.id).update(abandoned_email_sent=False)
        except Cart.DoesNotExist:
            continue
        except Exception:
            # In production, log diagnostic traceback and revert flag on error to allow future retry
            logger.exception("Unexpected error processing abandoned cart recovery for cart %s", cart_id)
            Cart.objects.filter(id=cart_id).update(abandoned_email_sent=False)
            continue

    return {
        'status': 'success',
        'eligible_count': total_eligible,
        'dispatched_count': dispatched_count,
        'cart_ids': cart_ids,
    }


@shared_task(name='orders.tasks.dispatch_single_cart_recovery_email')
def dispatch_single_cart_recovery_email(cart_id: int) -> bool:
    """
    Asynchronous task to format and dispatch a recovery email for a specific cart instance.
    """
    try:
        with transaction.atomic():
            cart = Cart.objects.select_for_update().get(id=cart_id)
            if not cart.user or not cart.user.email or not cart.items.exists() or cart.abandoned_email_sent:
                return False
            Cart.objects.filter(id=cart.id).update(abandoned_email_sent=True)

        # Database lock is released; perform network I/O outside transaction
        sent = send_abandoned_cart_email(cart)
        if not sent:
            Cart.objects.filter(id=cart.id).update(abandoned_email_sent=False)
            return False
        return True
    except Cart.DoesNotExist:
        return False
    except Exception:
        logger.exception("Unexpected error in single cart recovery task for cart %s", cart_id)
        Cart.objects.filter(id=cart_id).update(abandoned_email_sent=False)
        return False
