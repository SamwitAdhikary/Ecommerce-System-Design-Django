from decimal import Decimal
from django.db import models, transaction
from django.db.models import F
from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractUser, BaseUserManager

class UserManager(BaseUserManager):
    """
    Custom user manager where email is the unique identifier
    for authentication instead of usernames.
    """
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
            
        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    """
    Custom User model extending AbstractUser.
    Email is used as the unique username field.
    """
    username = None
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    google_id = models.CharField(max_length=255, blank=True, null=True)
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    otp_code = models.CharField(max_length=6, blank=True, null=True)
    otp_expires_at = models.DateTimeField(blank=True, null=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        ordering = ['-date_joined']

    def __str__(self):
        return self.email


class Address(models.Model):
    """
    Customer shipping address model supporting multiple records per user
    with database-enforced single-default and deduplication constraints.
    """
    user = models.ForeignKey(User, related_name='addresses', on_delete=models.CASCADE)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    address_line = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Addresses"
        ordering = ['-is_default', '-id']
        indexes = [
            models.Index(fields=['user', 'is_default']),
        ]
        constraints = [
            # Partial unique constraint: Exactly ONE address can have is_default=True per user
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(is_default=True),
                name='unique_default_address_per_user'
            ),
            # Prevents duplicate identical address entries for the same user
            models.UniqueConstraint(
                fields=['user', 'first_name', 'last_name', 'address_line', 'city', 'state', 'pincode'],
                name='unique_address_per_user'
            ),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.city}, {self.pincode}"


class WalletTransaction(models.Model):
    """
    Append-only double-entry financial ledger recording all credit additions
    and debit deductions for customer store credit, supporting expiration
    schedules and FIFO bucket tracking.
    """
    TRANSACTION_TYPE_CHOICES = (
        ('CREDIT', 'Credit (Added to Wallet)'),
        ('DEBIT', 'Debit (Deducted from Wallet)'),
    )
    user = models.ForeignKey(User, related_name='wallet_transactions', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    description = models.CharField(max_length=255)
    order_id = models.CharField(max_length=100, blank=True, null=True, help_text="Associated Order ID if applicable")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Date and time when this credit expires. None means perpetual (never expires)."
    )
    remaining_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Remaining unused balance of this credit grant."
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'transaction_type']),
            models.Index(
                fields=['user', 'transaction_type', 'remaining_amount', 'expires_at'],
                name='idx_wallet_txn_fifo'
            ),
        ]

    def __str__(self):
        return f"{self.transaction_type} of ${self.amount} for {self.user.email}"

    def clean(self):
        if self.amount is not None and self.amount <= Decimal('0.00'):
            raise ValidationError({'amount': 'Transaction amount must be strictly greater than zero.'})

        if self.transaction_type == 'DEBIT' and self.user_id:
            # Fast UX validation check (for admin forms and early user feedback)
            current_balance = User.objects.filter(pk=self.user_id).values_list('wallet_balance', flat=True).first() or Decimal('0.00')
            if current_balance < self.amount:
                raise ValidationError({'amount': f'Insufficient wallet balance. Available: ${current_balance}, Requested: ${self.amount}'})

    def save(self, *args, **kwargs):
        is_new = not self.pk

        if is_new:
            # Initialize credit remaining bucket if not explicitly provided
            if self.transaction_type == 'CREDIT' and (self.remaining_amount is None or self.remaining_amount == Decimal('0.00')):
                self.remaining_amount = self.amount
            elif self.transaction_type == 'DEBIT':
                self.remaining_amount = Decimal('0.00')

            self.full_clean()

            with transaction.atomic():
                super().save(*args, **kwargs)

                # Atomic conditional SQL delta updates (eliminates race conditions and overdrafts)
                if self.transaction_type == 'CREDIT':
                    User.objects.filter(pk=self.user_id).update(wallet_balance=F('wallet_balance') + self.amount)
                elif self.transaction_type == 'DEBIT':
                    # Single atomic SQL statement enforcing balance sufficiency directly in the WHERE clause
                    updated = User.objects.filter(
                        pk=self.user_id,
                        wallet_balance__gte=self.amount
                    ).update(wallet_balance=F('wallet_balance') - self.amount)

                    if updated == 0:
                        raise ValidationError({
                            'amount': f'Insufficient wallet balance for debit of ${self.amount}.'
                        })

                # Sync the in-memory user instance
                if hasattr(self, 'user') and self.user:
                    self.user.refresh_from_db(fields=['wallet_balance'])
        else:
            # Ledger records are append-only and immutable (only remaining_amount can be updated via service)
            super().save(*args, **kwargs)
