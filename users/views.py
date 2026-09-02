import secrets
from datetime import timedelta
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

from .models import User
from .serializers import UserSerializer
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


from django.conf import settings


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
