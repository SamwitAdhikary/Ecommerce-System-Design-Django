from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError


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
    A protected test endpoint used in Chapter 2 to verify JWT authorization
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
