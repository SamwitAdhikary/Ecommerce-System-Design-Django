from decimal import Decimal
from typing import List, Optional
from django.db import transaction, models
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import User, WalletTransaction


@transaction.atomic
def process_wallet_debit(
    user: User, 
    amount: Decimal, 
    description: str, 
    order_id: Optional[str] = None
) -> WalletTransaction:
    """
    Deducts store credit from active user credit balances using a FIFO
    (First-In, First-Out / Soonest-Expiring-First) allocation strategy.
    
    Credits expiring earliest are consumed first, preserving non-expiring
    credits. Then generates an immutable DEBIT WalletTransaction.
    """
    if amount is None or amount <= Decimal('0.00'):
        raise ValidationError({'amount': 'Debit amount must be strictly greater than zero.'})

    # Pessimistically lock user row to prevent race conditions during multi-bucket deduction
    locked_user = User.objects.select_for_update().get(pk=user.pk)
    
    # Query active, unexpired credit transactions ordered by soonest expiring first
    now = timezone.now()
    active_credits = locked_user.wallet_transactions.select_for_update().filter(
        transaction_type='CREDIT',
        remaining_amount__gt=Decimal('0.00')
    ).filter(
        models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now)
    ).order_by(
        models.F('expires_at').asc(nulls_last=True),
        'created_at'
    )
    
    total_available = sum((txn.remaining_amount for txn in active_credits), Decimal('0.00'))
    if total_available < amount:
        raise ValidationError({
            'amount': f'Insufficient active wallet balance. Available unexpired: ${total_available}, Requested: ${amount}'
        })
    
    # Consume from active credit buckets in FIFO order
    remaining_to_deduct = amount
    for txn in active_credits:
        if remaining_to_deduct <= Decimal('0.00'):
            break
        if txn.remaining_amount >= remaining_to_deduct:
            txn.remaining_amount -= remaining_to_deduct
            txn.save(update_fields=['remaining_amount'])
            remaining_to_deduct = Decimal('0.00')
        else:
            remaining_to_deduct -= txn.remaining_amount
            txn.remaining_amount = Decimal('0.00')
            txn.save(update_fields=['remaining_amount'])
            
    # Create the immutable DEBIT transaction log (which atomically decrements locked_user.wallet_balance)
    debit_txn = WalletTransaction.objects.create(
        user=locked_user,
        amount=amount,
        transaction_type='DEBIT',
        description=description,
        order_id=order_id,
        remaining_amount=Decimal('0.00')
    )
    
    return debit_txn


@transaction.atomic
def expire_user_credits(user: User) -> List[WalletTransaction]:
    """
    Finds all expired CREDIT transactions for a user that still hold remaining_amount > 0,
    zeroes out their remaining amount, and records corresponding DEBIT audit transactions.
    """
    now = timezone.now()
    locked_user = User.objects.select_for_update().get(pk=user.pk)
    
    expired_credits = locked_user.wallet_transactions.select_for_update().filter(
        transaction_type='CREDIT',
        remaining_amount__gt=Decimal('0.00'),
        expires_at__lte=now
    ).order_by('expires_at')
    
    created_debits = []
    for credit_txn in expired_credits:
        amount_to_expire = credit_txn.remaining_amount
        credit_txn.remaining_amount = Decimal('0.00')
        credit_txn.save(update_fields=['remaining_amount'])
        
        # Create corresponding DEBIT audit entry (atomically decrements user.wallet_balance)
        debit_txn = WalletTransaction.objects.create(
            user=locked_user,
            amount=amount_to_expire,
            transaction_type='DEBIT',
            description=f"Store credit expired (from Transaction #{credit_txn.id})",
            order_id=credit_txn.order_id,
            remaining_amount=Decimal('0.00')
        )
        created_debits.append(debit_txn)
        
    return created_debits


def expire_all_pending_credits() -> int:
    """
    Batch expiration runner for periodic background cron / Celery jobs.
    Scans for any expired credits across all users and executes expiration logic.
    Returns total count of expired transaction batches processed.
    """
    now = timezone.now()
    user_ids_with_expired = WalletTransaction.objects.filter(
        transaction_type='CREDIT',
        remaining_amount__gt=Decimal('0.00'),
        expires_at__lte=now
    ).values_list('user_id', flat=True).distinct()
    
    processed_count = 0
    for user_id in user_ids_with_expired:
        try:
            user = User.objects.get(pk=user_id)
            debits = expire_user_credits(user)
            processed_count += len(debits)
        except Exception:
            # Continue processing remaining users even if one encounters an issue
            continue
            
    return processed_count
