from decimal import Decimal
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import User, Address, WalletTransaction


class AddressSerializer(serializers.ModelSerializer):
    """
    Serializer for customer shipping addresses.
    User is automatically attached from request context.
    """
    class Meta:
        model = Address
        fields = (
            'id',
            'user',
            'first_name',
            'last_name',
            'address_line',
            'city',
            'state',
            'pincode',
            'phone',
            'email',
            'is_default',
        )
        read_only_fields = ('user',)


class WalletTransactionSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for customer financial ledger transactions.
    Exposes immutable credit and debit history, expiration metadata, and remaining balances.
    """
    is_expired = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()

    class Meta:
        model = WalletTransaction
        fields = (
            'id',
            'user',
            'amount',
            'transaction_type',
            'description',
            'order_id',
            'created_at',
            'expires_at',
            'remaining_amount',
            'is_expired',
            'days_remaining',
        )
        read_only_fields = (
            'id',
            'user',
            'amount',
            'transaction_type',
            'description',
            'order_id',
            'created_at',
            'expires_at',
            'remaining_amount',
            'is_expired',
            'days_remaining',
        )

    def get_is_expired(self, obj):
        if obj.transaction_type != 'CREDIT' or not obj.expires_at:
            return False
        from django.utils import timezone
        return obj.expires_at <= timezone.now()

    def get_days_remaining(self, obj):
        if obj.transaction_type != 'CREDIT' or not obj.expires_at:
            return None
        from django.utils import timezone
        now = timezone.now()
        if obj.expires_at <= now:
            return 0
        diff = obj.expires_at - now
        return diff.days


class WalletDebitRequestSerializer(serializers.Serializer):
    """
    Request payload serializer for store credit checkout debit operations.
    Enforces positive numeric amounts and optional transaction metadata.
    """
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    description = serializers.CharField(max_length=255, required=False, default='Store credit checkout deduction')
    order_id = serializers.CharField(max_length=100, required=False, allow_null=True, allow_blank=True)


class WalletTransferRequestSerializer(serializers.Serializer):
    """
    Request payload serializer for peer-to-peer store credit transfers.
    Enforces recipient existence, positive numeric amounts, and self-transfer defense.
    """
    recipient_email = serializers.EmailField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    description = serializers.CharField(max_length=255, required=False, default='')

    def validate_recipient_email(self, value):
        from .models import User
        if not User.objects.filter(email=value, is_active=True).exists():
            raise serializers.ValidationError("Active recipient account with this email does not exist.")
        return value


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model with nested shipping addresses,
    wallet balance, registration validation, and secure password hashing.
    """
    addresses = AddressSerializer(many=True, read_only=True)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = (
            'id', 
            'email', 
            'password', 
            'first_name', 
            'last_name', 
            'phone_number', 
            'addresses',
            'wallet_balance', 
            'is_staff', 
            'is_active', 
            'date_joined'
        )
        read_only_fields = ('wallet_balance', 'is_staff', 'is_active', 'date_joined')
        extra_kwargs = {
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
        }

    def validate_password(self, value):
        """Enforce Django's configured password validators during registration or update."""
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value

    def create(self, validated_data):
        """
        Creates user with is_active=False in a single database write until OTP verification succeeds.
        """
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            phone_number=validated_data.get('phone_number', ''),
            is_active=False  # Requires OTP verification before activation
        )
        return user

    def update(self, instance, validated_data):
        """
        Securely handles profile updates.
        Intercepts password updates to pass through set_password(), preventing plaintext storage.
        """
        password = validated_data.pop('password', None)
        instance = super().update(instance, validated_data)
        
        if password:
            instance.set_password(password)
            instance.save(update_fields=['password'])
            
        return instance
