import secrets
from datetime import timedelta
from django.conf import settings
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str

from rest_framework import status, permissions, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from .models import User, Address, WalletTransaction
from .serializers import UserSerializer, AddressSerializer, WalletTransactionSerializer, WalletDebitRequestSerializer
from .services import process_wallet_debit
from .emails import send_otp_email, send_password_reset_email


class ThrottledTokenObtainPairView(TokenObtainPairView):
    """
    Login endpoint that issues JWT access and refresh tokens.
    Defended with ScopedRateThrottle to prevent brute-force dictionary attacks.
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'  # Maps to '5/minute' in settings.py


class LogoutView(APIView):
    """
    Revokes the provided refresh token by writing its JTI into the database blacklist.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {"error": "Refresh token is required in the request body."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {"message": "Token successfully blacklisted. User logged out."},
                status=status.HTTP_200_OK
            )
        except TokenError as e:
            return Response(
                {"error": f"Invalid or expired token: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


class SecurityProbeView(APIView):
    """
    A protected test endpoint used to verify JWT authorization
    and rate-limiting defenses.
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'sensitive'  # Maps to '10/minute' in settings.py

    def get(self, request):
        return Response({
            "status": "authenticated",
            "user_email": request.user.email,
            "message": "You have successfully accessed a secured, rate-limited endpoint."
        })


class UserViewSet(viewsets.ModelViewSet):
    """
    User account management viewset.
    Enforces registration with OTP generation, secure profile updates, and locked endpoints.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    http_method_names = ['get', 'post', 'put', 'patch']

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_throttles(self):
        if self.action == 'create':
            self.throttle_scope = 'register'  # Maps to '5/hour' in settings.py
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def create(self, request, *args, **kwargs):
        """
        Customer registration:
        1. Validates and saves User with is_active=False.
        2. Generates a cryptographically secure 6-digit OTP (000000 - 999999).
        3. Sets a 10-minute expiration window.
        4. Dispatches HTML email via background daemon thread.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        user = serializer.instance
        
        # Generate cryptographically secure 6-digit OTP spanning all 1,000,000 permutations
        otp = f"{secrets.randbelow(1000000):06d}"
        user.otp_code = otp
        user.otp_expires_at = timezone.now() + timedelta(minutes=10)
        user.save(update_fields=['otp_code', 'otp_expires_at'])
        
        # Non-blocking async email dispatch
        send_otp_email(user.email, otp)
        
        headers = self.get_success_headers(serializer.data)
        return Response(
            {
                "message": "Registration successful. Please verify your email with the 6-digit code sent to your inbox.",
                "email": user.email
            },
            status=status.HTTP_201_CREATED,
            headers=headers
        )

    @action(detail=False, methods=['get', 'put', 'patch'])
    def me(self, request):
        """Returns or updates the authenticated customer's own profile."""
        serializer = self.get_serializer(request.user)
        if request.method in ['PUT', 'PATCH']:
            serializer = self.get_serializer(request.user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
        return Response(serializer.data)

    def list(self, request, *args, **kwargs):
        """Blocked — customers cannot list all accounts."""
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def retrieve(self, request, *args, **kwargs):
        """Blocked — customers cannot retrieve other accounts by ID."""
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


class VerifyOTPView(APIView):
    """
    Verifies 6-digit OTP, activates user, clears OTP credentials,
    and returns JWT tokens for immediate authenticated session.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'otp_verify'  # Dedicated rate limit: 5/minute in settings.py

    def post(self, request):
        email = request.data.get('email')
        otp_input = request.data.get('otp')
        
        if not email or not otp_input:
            return Response(
                {'error': 'Both email and otp fields are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)
            
        if not user.otp_code or not user.otp_expires_at:
            return Response({'error': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)
            
        if user.otp_code != str(otp_input).strip() or user.otp_expires_at < timezone.now():
            return Response({'error': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)
            
        # Activate account and wipe OTP credentials to prevent replay
        user.is_active = True
        user.otp_code = None
        user.otp_expires_at = None
        user.save(update_fields=['is_active', 'otp_code', 'otp_expires_at'])
        
        # Generate JWT tokens for instant login
        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'Email verified successfully! Your account is now active.',
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        }, status=status.HTTP_200_OK)


class ResendOTPView(APIView):
    """
    Re-generates and dispatches a fresh 6-digit OTP code.
    Masks non-existent emails to prevent user enumeration.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'register'  # Maps to '5/hour' in settings.py

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            user = User.objects.get(email=email)
            if user.is_active:
                return Response(
                    {'error': 'This email is already verified and active.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            otp = f"{secrets.randbelow(1000000):06d}"
            user.otp_code = otp
            user.otp_expires_at = timezone.now() + timedelta(minutes=10)
            user.save(update_fields=['otp_code', 'otp_expires_at'])
            
            send_otp_email(user.email, otp)
            return Response(
                {'message': 'A fresh 6-digit verification code has been dispatched to your email.'},
                status=status.HTTP_200_OK
            )
            
        except User.DoesNotExist:
            # Prevent email enumeration by returning generic success message
            return Response(
                {'message': 'If the email exists and is unverified, a fresh verification code has been dispatched.'},
                status=status.HTTP_200_OK
            )


class PasswordResetView(APIView):
    """
    Initiates cryptographic password reset.
    Masks account existence to prevent email enumeration.
    Builds reset URL from trusted server configuration (FRONTEND_URL) to prevent reset poisoning.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'  # Dedicated rate limit: 5/minute in settings.py

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            user = User.objects.get(email=email)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            
            # Secure: Always build reset links from trusted server settings, never from client Origin headers
            frontend_url = getattr(settings, 'FRONTEND_URL', 'https://yourstore.com').rstrip('/')
            reset_url = f"{frontend_url}/reset-password?uid={uid}&token={token}"
            
            send_password_reset_email(user.email, reset_url)
        except User.DoesNotExist:
            # Return HTTP 200 even if user does not exist to prevent email enumeration
            pass
            
        return Response(
            {'message': 'If an account with this email exists, a password reset link has been sent to your inbox.'},
            status=status.HTTP_200_OK
        )


class PasswordResetConfirmView(APIView):
    """
    Validates cryptographic token and updates user password with standard validators.
    Automatically invalidates the token upon successful password update.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'  # Dedicated rate limit: 5/minute in settings.py

    def post(self, request):
        uidb64 = request.data.get('uid')
        token = request.data.get('token')
        new_password = request.data.get('password')
        
        if not uidb64 or not token or not new_password:
            return Response(
                {'error': 'Missing required fields: uid, token, and password are all required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
            
        if user is not None and default_token_generator.check_token(user, token):
            try:
                validate_password(new_password, user=user)
            except DjangoValidationError as e:
                return Response({'error': e.messages}, status=status.HTTP_400_BAD_REQUEST)
                
            user.set_password(new_password)
            user.save(update_fields=['password'])
            return Response(
                {'message': 'Password has been reset successfully. You may now log in with your new credentials.'},
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {'error': 'Invalid or expired password reset link.'},
                status=status.HTTP_400_BAD_REQUEST
            )


class AddressViewSet(viewsets.ModelViewSet):
    """
    Customer shipping address management viewset.
    Enforces user isolation, atomic default toggling, duplicate prevention,
    nested savepoint error handling, and delete auto-promotion.
    """
    queryset = Address.objects.all()
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Restricts addresses strictly to the authenticated customer (IDOR defense)."""
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        """
        Creates a new shipping address:
        1. Checks for existing identical addresses to update phone/email and avoid duplicates.
        2. Enforces single is_default selection logic across all user addresses atomically.
        3. Uses nested savepoints to gracefully recover from concurrent constraint races.
        """
        data = serializer.validated_data
        user = self.request.user

        with transaction.atomic():
            # Check for existing identical physical address
            existing_address = Address.objects.filter(
                user=user,
                first_name=data.get('first_name'),
                last_name=data.get('last_name'),
                address_line=data.get('address_line'),
                city=data.get('city'),
                state=data.get('state'),
                pincode=data.get('pincode')
            ).first()

            if existing_address:
                # Update contact details on the existing record if newly provided
                update_fields = []
                if data.get('phone') and existing_address.phone != data.get('phone'):
                    existing_address.phone = data.get('phone')
                    update_fields.append('phone')
                if data.get('email') and existing_address.email != data.get('email'):
                    existing_address.email = data.get('email')
                    update_fields.append('email')

                if data.get('is_default'):
                    Address.objects.filter(user=user).update(is_default=False)
                    existing_address.is_default = True
                    update_fields.append('is_default')

                if update_fields:
                    existing_address.save(update_fields=update_fields)

                serializer.instance = existing_address
                return

            # If it is the user's first address, automatically make it the default
            is_first_address = not Address.objects.filter(user=user).exists()
            is_default = data.get('is_default', False) or is_first_address

            if is_default:
                Address.objects.filter(user=user).update(is_default=False)

            # Use a nested savepoint to isolate race condition collisions
            try:
                with transaction.atomic():
                    serializer.save(user=user, is_default=is_default)
            except IntegrityError:
                # Determine which constraint fired by checking if a physical duplicate exists
                duplicate_address = Address.objects.filter(
                    user=user,
                    first_name=data.get('first_name'),
                    last_name=data.get('last_name'),
                    address_line=data.get('address_line'),
                    city=data.get('city'),
                    state=data.get('state'),
                    pincode=data.get('pincode')
                ).first()

                if duplicate_address:
                    # Case A: Identical duplicate race (unique_address_per_user fired)
                    # Reuse the winning duplicate row, promoting to default if requested
                    if data.get('is_default'):
                        with transaction.atomic():
                            Address.objects.filter(user=user).update(is_default=False)
                            duplicate_address.is_default = True
                            duplicate_address.save(update_fields=['is_default'])
                    serializer.instance = duplicate_address
                else:
                    # Case B: Default-slot race (unique_default_address_per_user fired)
                    # This is a genuinely distinct address that lost the is_default race.
                    # Save it as non-default so zero customer data is lost.
                    with transaction.atomic():
                        serializer.save(user=user, is_default=False)

    def perform_update(self, serializer):
        """
        Updates an existing address, ensuring is_default atomicity and preventing
        a user from leaving their account with zero default addresses.
        """
        user = self.request.user
        data = serializer.validated_data
        instance = serializer.instance

        with transaction.atomic():
            # Prevent explicitly un-setting is_default on an active default address
            if instance.is_default and 'is_default' in data and not data['is_default']:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({
                    "is_default": "A default shipping address cannot be unset directly. Please mark another address as default instead."
                })

            if data.get('is_default'):
                Address.objects.filter(user=user).exclude(pk=instance.pk).update(is_default=False)

            serializer.save()

    def perform_destroy(self, instance):
        """
        Deletes an address. If the deleted address was the primary default,
        automatically promotes the next remaining address to maintain the default invariant.
        """
        user = self.request.user
        was_default = instance.is_default

        with transaction.atomic():
            instance.delete()
            if was_default:
                remaining_address = Address.objects.filter(user=user).first()
                if remaining_address:
                    remaining_address.is_default = True
                    remaining_address.save(update_fields=['is_default'])

    @action(detail=True, methods=['post'], url_path='set-default')
    def set_default(self, request, pk=None):
        """
        Atomic endpoint to set the selected address as the primary default address.
        """
        address = self.get_object()
        with transaction.atomic():
            Address.objects.filter(user=request.user).update(is_default=False)
            address.is_default = True
            address.save(update_fields=['is_default'])

        serializer = self.get_serializer(address)
        return Response(serializer.data, status=status.HTTP_200_OK)


class WalletTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only financial ledger history for the authenticated customer.
    Enforces user isolation, chronological ordering, and prevents mutations.
    Provides concurrency-hardened store credit checkout debit endpoint.
    """
    queryset = WalletTransaction.objects.all()
    serializer_class = WalletTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Restricts transaction history strictly to the authenticated customer."""
        return self.queryset.filter(user=self.request.user).order_by('-created_at')

    @action(detail=False, methods=['post'], url_path='debit')
    def debit(self, request):
        """
        Protected, concurrency-safe store credit deduction endpoint for checkout.
        Applies pessimistic row locking via process_wallet_debit() to prevent double-spending.
        """
        serializer = WalletDebitRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        amount = serializer.validated_data['amount']
        description = serializer.validated_data.get('description', 'Store credit checkout deduction')
        order_id = serializer.validated_data.get('order_id')
        
        try:
            debit_txn = process_wallet_debit(
                user=request.user,
                amount=amount,
                description=description,
                order_id=order_id
            )
            return Response(
                WalletTransactionSerializer(debit_txn).data,
                status=status.HTTP_201_CREATED
            )
        except DjangoValidationError as e:
            return Response(
                e.message_dict if hasattr(e, 'message_dict') else {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )



